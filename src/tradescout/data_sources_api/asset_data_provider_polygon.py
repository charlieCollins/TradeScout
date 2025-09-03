"""
Polygon.io Adapter - Implementation of AssetDataProvider using Polygon.io API

Uses Polygon.io API for high-quality market data with intelligent caching 
to optimize API usage and improve performance.
Specializes in extended hours data via snapshot endpoint.
"""

import logging
import requests
from datetime import datetime, timedelta, time
from decimal import Decimal
from typing import Any, Dict, List, Optional

from ..caches.api_cache import APICache, CachePolicy, cached_api_call
from ..data_models.domain_models_core import (
    Asset,
    AssetType,
    ExtendedHoursData,
    Market,
    MarketQuote,
    MarketStatus,
    MarketType,
    PriceData,
)
from ..data_models.interfaces import AssetDataProvider
from ..data_models.market_wide_models import MarketMover
from ..config.screening_universe_config import get_default_screening_universe

logger = logging.getLogger(__name__)


class AssetDataProviderPolygon(AssetDataProvider):
    """
    Polygon.io adapter implementing our AssetDataProvider interface
    
    Features:
    - High-quality financial data from Polygon.io
    - Excellent extended hours data via snapshot endpoint
    - Intelligent caching with appropriate TTLs
    - Rate-friendly API calls with built-in delays
    - Comprehensive market data coverage
    - Real-time gap calculation for extended hours
    """

    def __init__(self, api_key: str, cache: Optional[APICache] = None, request_delay: float = 0.2):
        """
        Initialize Polygon.io adapter
        
        Args:
            api_key: Polygon.io API key
            cache: API cache instance (creates default if None)
            request_delay: Delay between requests in seconds
        """
        self.cache = cache or APICache()
        self.request_delay = request_delay
        self.provider_name = "polygon"
        self.api_key = api_key
        self.base_url = "https://api.polygon.io"
        
        # Create default market for US stocks
        self.default_market = Market(
            id="US_STOCKS",
            name="US Stock Market (via Polygon)",
            market_type=MarketType.STOCK,
            timezone="America/New_York",
            currency="USD",
            regular_open=time(9, 30),
            regular_close=time(16, 0),
            pre_market_start=time(4, 0),
            after_hours_end=time(20, 0)
        )

    @property
    def rate_limit_per_minute(self) -> int:
        """Return the rate limit for Polygon API (varies by subscription)"""
        return 300  # Conservative estimate - check your plan

    @property
    def supports_extended_hours(self) -> bool:
        """Polygon supports extended hours data via snapshot endpoint"""
        return True

    @property
    def supports_market_movers(self) -> bool:
        """Polygon supports market screening capabilities"""
        return True

    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Make a request to Polygon API with error handling
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            
        Returns:
            JSON response data or None if failed
        """
        try:
            url = f"{self.base_url}/{endpoint}"
            request_params = {"apikey": self.api_key}
            if params:
                request_params.update(params)
            
            response = requests.get(url, params=request_params, timeout=15)
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 403:
                logger.error(f"Polygon API access denied (403): {response.text}")
                return None
            else:
                logger.warning(f"Polygon API error {response.status_code}: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Error making Polygon API request to {endpoint}: {e}")
            return None

    def get_current_quote(self, asset: Asset) -> Optional[MarketQuote]:
        """
        Get current market quote for an asset using Polygon snapshot
        
        Args:
            asset: Asset to get quote for
            
        Returns:
            MarketQuote with current pricing data or None if unavailable
        """
        try:
            if asset.asset_type not in [AssetType.COMMON_STOCK, AssetType.PREFERRED_STOCK]:
                logger.warning(f"Polygon only supports stocks, got {asset.asset_type}")
                return None

            # Use snapshot endpoint for real-time data
            snapshot_data = self._get_market_snapshot(asset.symbol)
            if not snapshot_data:
                return None

            return self._convert_snapshot_to_quote(snapshot_data, asset)

        except Exception as e:
            logger.error(f"Error getting current quote for {asset.symbol}: {e}")
            return None

    def _get_market_snapshot(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get market snapshot data for a symbol
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Snapshot data or None if unavailable
        """
        endpoint = f"v2/snapshot/locale/us/markets/stocks/tickers/{symbol}"
        response = self._make_request(endpoint)
        
        if response and response.get("status") == "OK":
            return response.get("ticker")
        
        return None

    def _convert_snapshot_to_quote(self, snapshot_data: Dict[str, Any], asset: Asset) -> MarketQuote:
        """Convert Polygon snapshot data to our MarketQuote format"""
        try:
            # Get current price from snapshot
            # Priority: min.c (latest minute close) > day.c (current day close) > prevDay.c
            current_price = None
            volume = 0
            timestamp = datetime.now()
            
            # Try to get most recent price
            if "min" in snapshot_data and snapshot_data["min"]:
                min_data = snapshot_data["min"]
                current_price = Decimal(str(min_data.get("c", 0)))
                volume = int(min_data.get("v", 0))
                if "t" in min_data:
                    timestamp = datetime.fromtimestamp(min_data["t"] / 1000)
            elif "day" in snapshot_data and snapshot_data["day"]:
                day_data = snapshot_data["day"]
                current_price = Decimal(str(day_data.get("c", 0)))
                volume = int(day_data.get("v", 0))
            
            if not current_price or current_price <= 0:
                logger.warning(f"No valid price data in snapshot for {asset.symbol}")
                return None
            
            # Get OHLC data from day or min data
            day_data = snapshot_data.get("day", {})
            open_price = Decimal(str(day_data.get("o", current_price)))
            high_price = Decimal(str(day_data.get("h", current_price)))
            low_price = Decimal(str(day_data.get("l", current_price)))
            
            # Create PriceData
            price_data = PriceData(
                asset=asset,
                timestamp=timestamp,
                price=current_price,
                volume=volume,
                open_price=open_price,
                high_price=high_price,
                low_price=low_price,
            )

            return MarketQuote(
                asset=asset,
                price_data=price_data,
            )

        except Exception as e:
            logger.error(f"Error converting Polygon snapshot data: {e}")
            raise

    def get_extended_hours_data(
        self, asset: Asset, session: MarketStatus
    ) -> Optional[ExtendedHoursData]:
        """
        Get extended hours trading data with real-time gap calculation
        
        Uses Polygon snapshot endpoint for current extended hours price
        and previous close data for gap calculation.
        
        Args:
            asset: Asset to get extended hours data for
            session: Pre-market or after-hours session
            
        Returns:
            ExtendedHoursData with calculated gap metrics or None if unavailable
        """
        try:
            if asset.asset_type not in [AssetType.COMMON_STOCK, AssetType.PREFERRED_STOCK]:
                return None

            # Get market snapshot for real-time extended hours data
            snapshot_data = self._get_market_snapshot(asset.symbol)
            if not snapshot_data:
                return None

            # Extract current price (prefer minute data for most recent)
            current_price = None
            volume = 0
            timestamp = datetime.now()
            
            if "min" in snapshot_data and snapshot_data["min"]:
                min_data = snapshot_data["min"]
                current_price = Decimal(str(min_data.get("c", 0)))
                volume = int(min_data.get("v", 0))
                if "t" in min_data:
                    timestamp = datetime.fromtimestamp(min_data["t"] / 1000)
            elif "day" in snapshot_data and snapshot_data["day"]:
                day_data = snapshot_data["day"]
                current_price = Decimal(str(day_data.get("c", 0)))
                volume = int(day_data.get("v", 0))
            
            # Get previous close
            prev_close = None
            if "prevDay" in snapshot_data and snapshot_data["prevDay"]:
                prev_close = Decimal(str(snapshot_data["prevDay"].get("c", 0)))
            
            if not current_price or not prev_close or prev_close <= 0:
                logger.warning(f"Missing price data for {asset.symbol}: current={current_price}, prev={prev_close}")
                return None
            
            # Create PriceData for current extended hours price
            price_data = PriceData(
                asset=asset,
                timestamp=timestamp,
                price=current_price,
                volume=volume,
                open_price=current_price,  # For extended hours, use current as OHLC
                high_price=current_price,
                low_price=current_price,
            )
            
            # Create ExtendedHoursData - gap calculation happens in __post_init__
            extended_hours_data = ExtendedHoursData(
                asset=asset,
                session_type=session,
                price_data=price_data,
                regular_session_close=prev_close
            )
            
            return extended_hours_data
            
        except Exception as e:
            logger.error(f"Error getting extended hours data for {asset.symbol}: {e}")
            return None

    def get_historical_prices(
        self,
        asset: Asset,
        start_date: datetime,
        end_date: Optional[datetime] = None,
        interval: str = "1d",
    ) -> List[PriceData]:
        """
        Get historical price data for an asset using Polygon aggregates
        
        Args:
            asset: Asset to get historical data for
            start_date: Start date for historical data
            end_date: End date (defaults to today)
            interval: Data interval (1d, 1wk, 1mo)
            
        Returns:
            List of PriceData objects
        """
        try:
            if asset.asset_type not in [AssetType.COMMON_STOCK, AssetType.PREFERRED_STOCK]:
                return []

            end_date = end_date or datetime.now()
            
            # Convert interval to Polygon format
            multiplier, timespan = self._convert_interval(interval)
            
            # Use caching for historical data
            historical_data = cached_api_call(
                provider=self.provider_name,
                endpoint="historical_prices",
                params={
                    "symbol": asset.symbol,
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": end_date.strftime("%Y-%m-%d"),
                    "interval": interval,
                },
                api_function=lambda: self._fetch_aggregates(
                    asset.symbol, start_date, end_date, multiplier, timespan
                ),
                policy=CachePolicy.DAILY,
            )

            if not historical_data:
                return []

            return [self._convert_to_price_data(record, asset) for record in historical_data]

        except Exception as e:
            logger.error(f"Error getting historical prices for {asset.symbol}: {e}")
            return []

    def _convert_interval(self, interval: str) -> tuple[int, str]:
        """Convert standard interval to Polygon multiplier and timespan"""
        if interval == "1d":
            return 1, "day"
        elif interval == "1wk":
            return 1, "week"
        elif interval == "1mo":
            return 1, "month"
        else:
            return 1, "day"  # Default

    def _fetch_aggregates(
        self, symbol: str, start_date: datetime, end_date: datetime, 
        multiplier: int, timespan: str
    ) -> List[Dict[str, Any]]:
        """Fetch historical aggregates from Polygon"""
        try:
            endpoint = f"v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{start_date.strftime('%Y-%m-%d')}/{end_date.strftime('%Y-%m-%d')}"
            response = self._make_request(endpoint)
            
            if response and response.get("status") == "OK":
                return response.get("results", [])
            
            return []

        except Exception as e:
            logger.error(f"Error fetching aggregates from Polygon for {symbol}: {e}")
            return []

    def _convert_to_price_data(self, record: Dict[str, Any], asset: Asset) -> PriceData:
        """Convert Polygon aggregate record to PriceData"""
        try:
            close_price = Decimal(str(record.get("c", 0)))
            open_price = Decimal(str(record.get("o", close_price)))
            high_price = Decimal(str(record.get("h", close_price)))
            low_price = Decimal(str(record.get("l", close_price)))
            volume = int(record.get("v", 0))
            
            # Convert timestamp from milliseconds
            timestamp = datetime.fromtimestamp(record.get("t", 0) / 1000)

            return PriceData(
                asset=asset,
                timestamp=timestamp,
                price=close_price,
                volume=volume,
                open_price=open_price,
                high_price=high_price,
                low_price=low_price,
            )

        except Exception as e:
            logger.error(f"Error converting Polygon price record: {e}")
            return PriceData(
                asset=asset,
                timestamp=datetime.now(),
                price=Decimal("0"),
                volume=0,
            )

    def get_market_gainers(self, limit: int = 20, force_refresh: bool = False) -> List[MarketMover]:
        """
        Get top market gainers using Polygon snapshot screening
        
        Args:
            limit: Maximum number of gainers to return
            force_refresh: Force refresh (ignored for now)
            
        Returns:
            List of MarketMover objects
        """
        try:
            return self._screen_market_movers("gainers", limit)
        except Exception as e:
            logger.error(f"Error getting market gainers: {e}")
            return []

    def get_market_losers(self, limit: int = 20, force_refresh: bool = False) -> List[MarketMover]:
        """
        Get top market losers using Polygon snapshot screening
        
        Args:
            limit: Maximum number of losers to return
            force_refresh: Force refresh (ignored for now)
            
        Returns:
            List of MarketMover objects
        """
        try:
            return self._screen_market_movers("losers", limit)
        except Exception as e:
            logger.error(f"Error getting market losers: {e}")
            return []

    def _screen_market_movers(self, mover_type: str, limit: int) -> List[MarketMover]:
        """
        Screen for market movers using Polygon snapshot data
        
        TODO: Optimize using Polygon's dedicated market movers endpoint:
        https://polygon.io/docs/rest/stocks/snapshots/top-market-movers
        This would be much more efficient than individual snapshot calls.
        
        Args:
            mover_type: 'gainers' or 'losers'
            limit: Maximum number of movers to return
            
        Returns:
            List of MarketMover objects sorted by percentage change
        """
        try:
            screening_symbols = self._get_screening_universe()
            logger.info(f"Screening {len(screening_symbols)} symbols for {mover_type}")
            
            movers_data = []
            failed_symbols = 0
            
            for symbol in screening_symbols:
                try:
                    asset = Asset(
                        symbol=symbol,
                        name=symbol,
                        asset_type=AssetType.COMMON_STOCK,
                        market=self.default_market,
                        currency="USD"
                    )
                    
                    # Get extended hours data for gap calculation
                    extended_data = self.get_extended_hours_data(asset, MarketStatus.AFTER_HOURS)
                    if not extended_data:
                        failed_symbols += 1
                        continue
                    
                    current_price = extended_data.price_data.price
                    prev_close = extended_data.regular_session_close
                    volume = extended_data.price_data.volume
                    gap_pct = extended_data.gap_percent
                    
                    # Filter by minimum criteria - only exclude penny stocks
                    if current_price < 1.0:
                        continue
                        
                    movers_data.append({
                        'symbol': symbol,
                        'current_price': current_price,
                        'previous_close': prev_close,
                        'change_pct': gap_pct,
                        'price_change': extended_data.gap_amount,
                        'volume': volume,
                        'timestamp': extended_data.price_data.timestamp
                    })
                    
                except Exception as e:
                    logger.debug(f"Failed to process {symbol}: {e}")
                    failed_symbols += 1
                    continue
            
            logger.info(f"Successfully processed {len(movers_data)} symbols, {failed_symbols} failed")
            
            # Sort by change percentage
            reverse_sort = mover_type == "gainers"
            movers_data.sort(key=lambda x: x['change_pct'], reverse=reverse_sort)
            
            # Convert to MarketMover objects
            market_movers = []
            for data in movers_data[:limit]:
                try:
                    asset = Asset(
                        symbol=data['symbol'],
                        name=data['symbol'],
                        asset_type=AssetType.COMMON_STOCK,
                        market=self.default_market,
                        currency=self.default_market.currency
                    )
                    
                    market_mover = MarketMover(
                        asset=asset,
                        current_price=data['current_price'],
                        price_change=data['price_change'],
                        price_change_percent=data['change_pct'],
                        volume=data['volume']
                    )
                    
                    market_movers.append(market_mover)
                    
                except Exception as e:
                    logger.error(f"Error creating MarketMover for {data['symbol']}: {e}")
                    continue
                    
            logger.info(f"Returning {len(market_movers)} {mover_type}")
            return market_movers
            
        except Exception as e:
            logger.error(f"Error in market movers screening: {e}")
            return []
    
    def _get_screening_universe(self) -> List[str]:
        """Get universe of stocks for screening from configuration"""
        try:
            liquid_universe = get_default_screening_universe()
            
            if not liquid_universe:
                logger.error("No screening universe loaded from config, using minimal fallback")
                liquid_universe = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
            
            logger.info(f"Using configured screening universe of {len(liquid_universe)} symbols")
            return liquid_universe
            
        except Exception as e:
            logger.error(f"Error loading screening universe from config: {e}")
            fallback_universe = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
            logger.info(f"Using fallback universe of {len(fallback_universe)} symbols")
            return fallback_universe

    def get_company_info(self, asset: Asset) -> Optional[Dict[str, Any]]:
        """
        Get company information using Polygon ticker details
        
        Args:
            asset: Asset to get company info for
            
        Returns:
            Dictionary with company information or None
        """
        try:
            if asset.asset_type not in [AssetType.COMMON_STOCK, AssetType.PREFERRED_STOCK]:
                return None

            # Use light caching for company metadata
            company_info = cached_api_call(
                provider=self.provider_name,
                endpoint="company_info",
                params={"symbol": asset.symbol},
                api_function=lambda: self._fetch_ticker_details(asset.symbol),
                policy=CachePolicy.DAILY,
            )

            return company_info

        except Exception as e:
            logger.error(f"Error getting company info for {asset.symbol}: {e}")
            return None

    def _fetch_ticker_details(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch ticker details from Polygon"""
        endpoint = f"v3/reference/tickers/{symbol}"
        response = self._make_request(endpoint)
        
        if response and response.get("status") == "OK":
            return response.get("results")
        
        return None

    def health_check(self) -> bool:
        """
        Check if the Polygon API is accessible and working
        
        Returns:
            True if API is healthy, False otherwise
        """
        try:
            # Try to get a simple snapshot for a well-known ticker
            test_data = self._get_market_snapshot("AAPL")
            return test_data is not None
        except Exception as e:
            logger.error(f"Polygon health check failed: {e}")
            return False

    def get_historical_quotes(
        self,
        asset: Asset,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1d",
    ) -> List[PriceData]:
        """Alias for get_historical_prices"""
        return self.get_historical_prices(asset, start_date, end_date, interval)

    def scan_volume_leaders(
        self, assets: List[Asset], min_volume_ratio: Decimal = Decimal("2.0")
    ) -> List[MarketQuote]:
        """Volume scanning not implemented for basic version"""
        logger.info("Volume scanning not implemented for Polygon basic version")
        return []

    def get_fundamental_data(self, asset: Asset) -> Dict[str, any]:
        """Get fundamental company data (uses company info for now)"""
        try:
            return self.get_company_info(asset) or {}
        except Exception as e:
            logger.error(f"Error getting fundamental data for {asset.symbol}: {e}")
            return {}