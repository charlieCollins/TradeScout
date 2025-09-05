"""
Tiingo Adapter - Implementation of AssetDataProvider using Tiingo API

Uses tiingo library for high-quality market data with intelligent caching
to optimize API usage and improve performance.
"""

import logging
import requests
from datetime import datetime, timedelta, time
from decimal import Decimal
from typing import Any, Dict, List, Optional

from tiingo import TiingoClient

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


class AssetDataProviderTiingo(AssetDataProvider):
    """
    Tiingo adapter implementing our AssetDataProvider interface

    Features:
    - High-quality financial data from Tiingo
    - Intelligent caching with appropriate TTLs
    - Rate-friendly API calls with built-in delays
    - Extended hours data support where available
    - Comprehensive market data and fundamentals
    - Error handling and fallback strategies
    """

    def __init__(
        self, api_key: str, cache: Optional[APICache] = None, request_delay: float = 0.1
    ):
        """
        Initialize Tiingo adapter

        Args:
            api_key: Tiingo API key
            cache: API cache instance (creates default if None)
            request_delay: Delay between requests in seconds
        """
        self.cache = cache or APICache()
        self.request_delay = request_delay
        self.provider_name = "tiingo"
        self.api_key = api_key

        # Create default market for US stocks (using IEX data via Tiingo)
        # Tiingo uses IEX which includes all NASDAQ and NYSE symbols
        # Reference: https://iextrading.com/trading/eligible-symbols/
        self.default_market = Market(
            id="IEX",
            name="IEX Exchange (via Tiingo)",
            market_type=MarketType.STOCK,
            timezone="America/New_York",
            currency="USD",
            regular_open=time(9, 30),
            regular_close=time(16, 0),
            pre_market_start=time(4, 0),
            after_hours_end=time(20, 0),
        )

        # Initialize Tiingo client
        config = {
            "session": True,  # Reuse HTTP session for performance
            "api_key": api_key,
        }
        self.client = TiingoClient(config)

    @property
    def rate_limit_per_minute(self) -> int:
        """Return the rate limit for Tiingo commercial API (1000 per minute)"""
        return 1000

    @property
    def supports_extended_hours(self) -> bool:
        """Tiingo supports extended hours data through IEX integration"""
        return True

    @property
    def supports_market_movers(self) -> bool:
        """Tiingo supports market screening capabilities"""
        return True

    def get_current_quote(self, asset: Asset) -> Optional[MarketQuote]:
        """
        Get current market quote for an asset using intelligent caching

        Args:
            asset: Asset to get quote for

        Returns:
            MarketQuote with current pricing data or None if unavailable
        """
        try:
            if asset.asset_type not in [
                AssetType.COMMON_STOCK,
                AssetType.PREFERRED_STOCK,
            ]:
                logger.warning(f"Tiingo only supports stocks, got {asset.asset_type}")
                return None

            # NO CACHING for real-time quote data - always fetch fresh
            quote_data = self._fetch_current_quote(asset.symbol)

            if not quote_data:
                return None

            return self._convert_to_market_quote(quote_data, asset)

        except Exception as e:
            logger.error(f"Error getting current quote for {asset.symbol}: {e}")
            return None

    def _fetch_current_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch current quote from Tiingo API"""
        try:
            # Get latest price data from Tiingo
            latest_price = self.client.get_ticker_price(symbol, fmt="json")

            if not latest_price or len(latest_price) == 0:
                logger.warning(f"No price data returned for {symbol}")
                return None

            # Get the most recent price record
            price_data = (
                latest_price[-1] if isinstance(latest_price, list) else latest_price
            )

            # Also get ticker metadata for additional info
            try:
                metadata = self.client.get_ticker_metadata(symbol, fmt="json")
            except Exception as e:
                logger.warning(f"Could not get metadata for {symbol}: {e}")
                metadata = {}

            return {
                "price_data": price_data,
                "metadata": metadata,
                "symbol": symbol,
                "timestamp": datetime.now(),
            }

        except Exception as e:
            logger.error(f"Error fetching quote from Tiingo for {symbol}: {e}")
            return None

    def _convert_to_market_quote(
        self, quote_data: Dict[str, Any], asset: Asset
    ) -> MarketQuote:
        """Convert Tiingo quote data to our MarketQuote format"""
        try:
            price_data = quote_data["price_data"]
            metadata = quote_data.get("metadata", {})

            # Extract price information
            current_price = Decimal(
                str(price_data.get("close", price_data.get("adjClose", 0)))
            )

            # Calculate change from previous close if available
            open_price = Decimal(str(price_data.get("open", current_price)))
            high_price = Decimal(str(price_data.get("high", current_price)))
            low_price = Decimal(str(price_data.get("low", current_price)))

            # Volume
            volume = int(price_data.get("volume", 0))

            # Calculate change (simplified - using open as previous close approximation)
            price_change = current_price - open_price
            change_percent = (
                (price_change / open_price * 100) if open_price > 0 else Decimal("0")
            )

            # Create PriceData with required fields first
            price_data_obj = PriceData(
                asset=asset,
                timestamp=datetime.fromisoformat(
                    price_data["date"].replace("Z", "+00:00")
                ),
                price=current_price,
                volume=volume,
                open_price=open_price,
                high_price=high_price,
                low_price=low_price,
            )

            return MarketQuote(
                asset=asset,
                price_data=price_data_obj,
            )

        except Exception as e:
            logger.error(f"Error converting Tiingo quote data: {e}")
            raise

    def _fetch_iex_realtime_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Fetch real-time data from Tiingo IEX endpoint

        Args:
            symbol: Stock symbol

        Returns:
            Real-time IEX data including current price and previous close
        """
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Token {self.api_key}",
            }

            response = requests.get(
                f"https://api.tiingo.com/iex/{symbol}", headers=headers, timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and data:
                    return data[0]  # First item contains the quote data

            logger.warning(f"No IEX data returned for {symbol}")
            return None

        except Exception as e:
            logger.error(f"Error fetching IEX data for {symbol}: {e}")
            return None

    def get_extended_hours_data(
        self, asset: Asset, session: MarketStatus
    ) -> Optional[ExtendedHoursData]:
        """
        Get extended hours trading data with real-time gap calculation

        Used for individual stock analysis, not bulk gap screening
        (bulk gap screening uses market movers data)

        Args:
            asset: Asset to get extended hours data for
            session: Pre-market or after-hours session

        Returns:
            ExtendedHoursData with calculated gap metrics or None if unavailable
        """
        try:
            if asset.asset_type not in [
                AssetType.COMMON_STOCK,
                AssetType.PREFERRED_STOCK,
            ]:
                return None

            # Get real-time IEX data for this specific asset
            iex_data = self._fetch_iex_realtime_data(asset.symbol)
            if not iex_data:
                return None

            # Convert to ExtendedHoursData with gap calculation
            current_price = (
                iex_data.get("tngoLast")
                or iex_data.get("mid")
                or iex_data.get("bidPrice")
            )
            prev_close = iex_data.get("prevClose")

            if not current_price or not prev_close:
                return None

            current_price = Decimal(str(current_price))
            prev_close = Decimal(str(prev_close))

            # Create PriceData for current extended hours price
            price_data = PriceData(
                asset=asset,
                timestamp=datetime.now(),
                price=current_price,
                volume=int(iex_data.get("volume", 0)),
                open_price=current_price,
                high_price=current_price,
                low_price=current_price,
            )

            # Create ExtendedHoursData - gap calculation happens in __post_init__
            extended_hours_data = ExtendedHoursData(
                asset=asset,
                session_type=session,
                price_data=price_data,
                regular_session_close=prev_close,
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
        Get historical price data for an asset

        Args:
            asset: Asset to get historical data for
            start_date: Start date for historical data
            end_date: End date (defaults to today)
            interval: Data interval (1d, 1wk, 1mo)

        Returns:
            List of PriceData objects
        """
        try:
            if asset.asset_type not in [
                AssetType.COMMON_STOCK,
                AssetType.PREFERRED_STOCK,
            ]:
                return []

            end_date = end_date or datetime.now()

            # Light caching for historical data since it doesn't change often
            historical_data = cached_api_call(
                provider=self.provider_name,
                endpoint="historical_prices",
                params={
                    "symbol": asset.symbol,
                    "start_date": start_date.strftime("%Y-%m-%d"),
                    "end_date": end_date.strftime("%Y-%m-%d"),
                    "interval": interval,
                },
                api_function=lambda: self._fetch_historical_data(
                    asset.symbol, start_date, end_date
                ),
                policy=CachePolicy.DAILY,  # Keep daily cache - historical data doesn't change
            )

            if not historical_data:
                return []

            return [
                self._convert_to_price_data(price_record)
                for price_record in historical_data
            ]

        except Exception as e:
            logger.error(f"Error getting historical prices for {asset.symbol}: {e}")
            return []

    def _fetch_historical_data(
        self, symbol: str, start_date: datetime, end_date: datetime
    ) -> List[Dict[str, Any]]:
        """Fetch historical data from Tiingo"""
        try:
            historical_prices = self.client.get_ticker_price(
                symbol,
                startDate=start_date.strftime("%Y-%m-%d"),
                endDate=end_date.strftime("%Y-%m-%d"),
                fmt="json",
            )

            return historical_prices if isinstance(historical_prices, list) else []

        except Exception as e:
            logger.error(
                f"Error fetching historical data from Tiingo for {symbol}: {e}"
            )
            return []

    def _convert_to_price_data(self, price_record: Dict[str, Any]) -> PriceData:
        """Convert Tiingo historical price record to PriceData"""
        try:
            close_price = Decimal(
                str(price_record.get("close", price_record.get("adjClose", 0)))
            )
            open_price = Decimal(str(price_record.get("open", close_price)))
            high_price = Decimal(str(price_record.get("high", close_price)))
            low_price = Decimal(str(price_record.get("low", close_price)))
            volume = int(price_record.get("volume", 0))

            # Calculate change from open to close
            price_change = close_price - open_price
            change_percent = (
                (price_change / open_price * 100) if open_price > 0 else Decimal("0")
            )

            # Need asset and timestamp - these will need to be passed from caller
            # For now, create a minimal PriceData that can be used
            return PriceData(
                asset=None,  # Will be set by caller
                timestamp=datetime.now(),  # Will be updated by caller
                price=close_price,
                volume=volume,
                open_price=open_price,
                high_price=high_price,
                low_price=low_price,
            )

        except Exception as e:
            logger.error(f"Error converting Tiingo price record: {e}")
            # Return default PriceData
            return PriceData(
                asset=None,
                timestamp=datetime.now(),
                price=Decimal("0"),
                volume=0,
            )

    def get_market_gainers(
        self, limit: int = 20, force_refresh: bool = False
    ) -> List[MarketMover]:
        """
        Get top market gainers using custom screener

        Screens high-volume stocks for biggest percentage gainers

        Args:
            limit: Maximum number of gainers to return

        Returns:
            List of MarketMover objects
        """
        try:
            return self._screen_market_movers("gainers", limit)
        except Exception as e:
            logger.error(f"Error getting market gainers: {e}")
            return []

    def get_market_losers(
        self, limit: int = 20, force_refresh: bool = False
    ) -> List[MarketMover]:
        """
        Get top market losers using custom screener

        Screens high-volume stocks for biggest percentage losers

        Args:
            limit: Maximum number of losers to return

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
        Screen for real-time market movers using IEX data during extended hours

        Args:
            mover_type: 'gainers' or 'losers'
            limit: Maximum number of movers to return

        Returns:
            List of MarketMover objects sorted by percentage change (real-time gaps)
        """
        try:
            # Get liquid universe of stocks for screening
            screening_symbols = self._get_screening_universe()

            logger.info(
                f"Screening {len(screening_symbols)} symbols for real-time {mover_type}"
            )

            # Collect real-time IEX data for all symbols
            movers_data = []
            failed_symbols = 0

            for symbol in screening_symbols:
                try:
                    # Create asset for extended hours call
                    asset = Asset(
                        symbol=symbol,
                        name=symbol,
                        asset_type=AssetType.COMMON_STOCK,
                        market=self.default_market,
                        currency="USD",
                    )

                    # Use get_extended_hours_data - no duplication
                    extended_data = self.get_extended_hours_data(
                        asset, MarketStatus.AFTER_HOURS
                    )
                    if not extended_data:
                        failed_symbols += 1
                        continue

                    current_price = extended_data.price_data.price
                    prev_close = extended_data.regular_session_close
                    volume = extended_data.price_data.volume
                    gap_pct = extended_data.gap_percent

                    # Filter by minimum criteria
                    if volume < 100000 or current_price < 1.0:
                        continue

                    movers_data.append(
                        {
                            "symbol": symbol,
                            "current_price": current_price,
                            "previous_close": prev_close,
                            "change_pct": gap_pct,
                            "price_change": extended_data.gap_amount,
                            "volume": volume,
                            "timestamp": extended_data.price_data.timestamp,
                        }
                    )

                except Exception as e:
                    logger.debug(f"Failed to process {symbol}: {e}")
                    failed_symbols += 1
                    continue

            logger.info(
                f"Successfully processed {len(movers_data)} symbols, {failed_symbols} failed"
            )

            # Sort by change percentage
            reverse_sort = mover_type == "gainers"
            movers_data.sort(key=lambda x: x["change_pct"], reverse=reverse_sort)

            # Convert to MarketMover objects
            market_movers = []
            for data in movers_data[:limit]:
                try:
                    asset = Asset(
                        symbol=data["symbol"],
                        name=data["symbol"],  # We'd need metadata call for full name
                        asset_type=AssetType.COMMON_STOCK,
                        market=self.default_market,
                        currency=self.default_market.currency,
                    )

                    market_mover = MarketMover(
                        asset=asset,
                        current_price=data["current_price"],
                        price_change=data["price_change"],
                        price_change_percent=data["change_pct"],
                        volume=data["volume"],
                    )

                    market_movers.append(market_mover)

                except Exception as e:
                    logger.error(
                        f"Error creating MarketMover for {data['symbol']}: {e}"
                    )
                    continue

            logger.debug(f"Returning {len(market_movers)} {mover_type}")
            return market_movers

        except Exception as e:
            logger.error(f"Error in market movers screening: {e}")
            return []

    def _get_screening_universe(self) -> List[str]:
        """
        Get universe of stocks for screening from configuration

        Returns configured screening universe from YAML config
        """
        try:
            # Get symbols from configuration
            liquid_universe = get_default_screening_universe()

            if not liquid_universe:
                logger.error(
                    "No screening universe loaded from config, using minimal fallback"
                )
                liquid_universe = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]

            logger.info(
                f"Using configured screening universe of {len(liquid_universe)} symbols"
            )
            # TODO: Expand to full IEX universe (~14K symbols) for comprehensive screening
            # Reference: https://iextrading.com/trading/eligible-symbols/
            return liquid_universe

        except Exception as e:
            logger.error(f"Error loading screening universe from config: {e}")
            # Minimal fallback
            fallback_universe = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
            logger.info(f"Using fallback universe of {len(fallback_universe)} symbols")
            return fallback_universe

    def _get_previous_close(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get previous trading day close for comparison

        Args:
            symbol: Stock symbol

        Returns:
            Previous day's price data or None
        """
        try:
            # Get last 3 days to ensure we have previous trading day
            end_date = datetime.now()
            start_date = end_date - timedelta(days=5)

            hist_data = self.client.get_ticker_price(
                symbol,
                startDate=start_date.strftime("%Y-%m-%d"),
                endDate=end_date.strftime("%Y-%m-%d"),
                fmt="json",
            )

            if isinstance(hist_data, list) and len(hist_data) >= 2:
                # Return second to last record (previous trading day)
                return hist_data[-2]

            return None

        except Exception as e:
            logger.debug(f"Could not get previous close for {symbol}: {e}")
            return None

    def _determine_market_status(self) -> MarketStatus:
        """Determine current market status based on time"""
        # This is a simplified implementation
        # In production, you'd want to check actual market holidays and hours
        now = datetime.now()
        hour = now.hour
        weekday = now.weekday()

        if weekday >= 5:  # Weekend
            return MarketStatus.CLOSED
        elif 4 <= hour < 9:
            return MarketStatus.PRE_MARKET
        elif 9 <= hour < 16:
            return MarketStatus.OPEN
        elif 16 <= hour < 20:
            return MarketStatus.AFTER_HOURS
        else:
            return MarketStatus.CLOSED

    def get_company_info(self, asset: Asset) -> Optional[Dict[str, Any]]:
        """
        Get company information and metadata

        Args:
            asset: Asset to get company info for

        Returns:
            Dictionary with company information or None
        """
        try:
            if asset.asset_type not in [
                AssetType.COMMON_STOCK,
                AssetType.PREFERRED_STOCK,
            ]:
                return None

            # Light caching for company metadata since it changes infrequently
            metadata = cached_api_call(
                provider=self.provider_name,
                endpoint="company_info",
                params={"symbol": asset.symbol},
                api_function=lambda: self.client.get_ticker_metadata(
                    asset.symbol, fmt="json"
                ),
                policy=CachePolicy.DAILY,  # Keep daily cache - company info doesn't change often
            )

            return metadata

        except Exception as e:
            logger.error(f"Error getting company info for {asset.symbol}: {e}")
            return None

    def get_historical_quotes(
        self,
        asset: Asset,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1d",
    ) -> List[PriceData]:
        """
        Get historical price data (alias for get_historical_prices)

        Args:
            asset: Asset to get historical data for
            start_date: Start date for data
            end_date: End date for data
            interval: Data interval (1d, 1wk, 1mo)

        Returns:
            List of historical price data
        """
        return self.get_historical_prices(asset, start_date, end_date, interval)

    def scan_volume_leaders(
        self, assets: List[Asset], min_volume_ratio: Decimal = Decimal("2.0")
    ) -> List[MarketQuote]:
        """
        Scan for assets with unusual volume

        Note: This would require getting current quotes for all assets and
        comparing with historical volume averages. Not implemented in basic version.

        Args:
            assets: List of assets to scan
            min_volume_ratio: Minimum volume vs average ratio

        Returns:
            List of assets with volume surges (empty for now)
        """
        logger.info("Volume scanning not implemented for Tiingo free tier")
        return []

    def get_fundamental_data(self, asset: Asset) -> Dict[str, any]:
        """
        Get fundamental company data

        Args:
            asset: Asset to get fundamental data for

        Returns:
            Dictionary with fundamental metrics
        """
        try:
            if asset.asset_type not in [
                AssetType.COMMON_STOCK,
                AssetType.PREFERRED_STOCK,
            ]:
                return {}

            # Tiingo has fundamentals data but it requires a different API call
            # For now, return company metadata
            return self.get_company_info(asset) or {}

        except Exception as e:
            logger.error(f"Error getting fundamental data for {asset.symbol}: {e}")
            return {}

    def health_check(self) -> bool:
        """
        Check if the Tiingo API is accessible and working

        Returns:
            True if API is healthy, False otherwise
        """
        try:
            # Try to get a simple quote for a well-known ticker
            test_data = self.client.get_ticker_price("AAPL", fmt="json")
            return test_data is not None and len(test_data) > 0
        except Exception as e:
            logger.error(f"Tiingo health check failed: {e}")
            return False
