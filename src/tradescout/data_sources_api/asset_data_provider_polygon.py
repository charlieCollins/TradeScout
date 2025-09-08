"""
Polygon.io Adapter - Implementation of AssetDataProvider using Polygon.io API

Uses Polygon.io API for high-quality market data with intelligent caching
to optimize API usage and improve performance.
Specializes in extended hours data via snapshot endpoint.
"""

import json
import logging
import os
import requests
import yaml
from datetime import datetime, timedelta, time
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..caches.api_cache import APICache, CachePolicy, cached_api_call
from ..data_models.domain_models_core import (
    Asset,
    AssetType,
    CompanyFundamentals,
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

    def __init__(
        self, api_key: str, cache: Optional[APICache] = None, request_delay: float = 0.2
    ):
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

        # Centralized market data cache - in memory for performance
        self._market_snapshot_data = None
        self._market_snapshot_timestamp = None
        self._market_data_ttl_minutes = self._load_cache_ttl()

        # Filesystem cache for persistence between CLI runs
        self._cache_dir = Path("data/cache/polygon")
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._market_cache_file = self._cache_dir / "market_snapshot.json"

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
            after_hours_end=time(20, 0),
        )

        # Load cached market data on startup
        self._load_market_cache_from_disk()

    def _load_cache_ttl(self) -> int:
        """Load cache TTL from configuration file"""
        try:
            config_path = Path(__file__).parent.parent / "config" / "cache_config.yaml"
            if not config_path.exists():
                logger.warning(
                    f"Cache config file not found: {config_path}, using default 15 minutes"
                )
                return 15

            with open(config_path) as f:
                config_data = yaml.safe_load(f)

            if "cache_policies" not in config_data:
                logger.warning(
                    "cache_policies section missing from cache_config.yaml, using default 15 minutes"
                )
                return 15

            real_time_ttl = config_data["cache_policies"].get("real_time", 15)
            logger.debug(f"Loaded market data TTL from config: {real_time_ttl} minutes")
            return real_time_ttl

        except Exception as e:
            logger.warning(
                f"Error loading cache configuration: {e}, using default 15 minutes"
            )
            return 15

    def _is_market_data_fresh(self) -> bool:
        """Check if cached market snapshot data is still fresh"""
        if not self._market_snapshot_data or not self._market_snapshot_timestamp:
            return False

        age_minutes = (
            datetime.now() - self._market_snapshot_timestamp
        ).total_seconds() / 60
        return age_minutes < self._market_data_ttl_minutes

    def _get_fresh_market_data(
        self, force_refresh: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Get market snapshot data, using database as primary cache"""
        try:
            from ..storage.asset_universe_manager import AssetUniverseManager
            manager = AssetUniverseManager()
            
            # Check if we need fresh data (database-based cache check)
            needs_fresh_data = force_refresh or self._is_database_cache_stale()
            
            if not needs_fresh_data:
                # Try to load from database first
                cached_data = self._load_from_database_cache()
                if cached_data:
                    logger.debug(f"Using database cached market data ({len(cached_data):,} symbols)")
                    self._market_snapshot_data = cached_data
                    return cached_data
            
            # Need fresh data - fetch from API
            logger.debug("Fetching fresh market snapshot from Polygon API...")
            snapshot_data = self._get_full_market_snapshot()

            if snapshot_data:
                self._market_snapshot_data = snapshot_data
                self._market_snapshot_timestamp = datetime.now()
                logger.debug(f"Refreshed market data: {len(snapshot_data):,} symbols")

                # Save to database (primary cache) and disk (backup)
                self._save_to_database_cache(snapshot_data)
                self._save_market_cache_to_disk()
                
            else:
                logger.warning("Failed to fetch market snapshot, trying database fallback")
                # Fallback to database even if stale
                fallback_data = self._load_from_database_cache()
                if fallback_data:
                    logger.info(f"Using stale database cache ({len(fallback_data):,} symbols)")
                    self._market_snapshot_data = fallback_data
                    return fallback_data

            return snapshot_data
            
        except Exception as e:
            logger.error(f"Error in _get_fresh_market_data: {e}")
            # Final fallback to in-memory cache
            return self._market_snapshot_data

    def get_market_data_status(self) -> Dict[str, Any]:
        """Get current market data cache status for display"""
        if not self._market_snapshot_data:
            return {"status": "empty", "symbols": 0}

        age_minutes = 0
        if self._market_snapshot_timestamp:
            age_minutes = (
                datetime.now() - self._market_snapshot_timestamp
            ).total_seconds() / 60

        return {
            "status": "cached" if self._is_market_data_fresh() else "stale",
            "symbols": len(self._market_snapshot_data),
            "age_minutes": age_minutes,
            "timestamp": self._market_snapshot_timestamp,
        }

    def _load_market_cache_from_disk(self) -> None:
        """Load cached market snapshot data from filesystem"""
        try:
            if not self._market_cache_file.exists():
                logger.debug("No market cache file found on disk")
                return

            with open(self._market_cache_file, "r") as f:
                cache_data = json.load(f)

            # Verify cache structure and freshness
            if "data" in cache_data and "timestamp" in cache_data:
                cached_timestamp = datetime.fromisoformat(cache_data["timestamp"])
                age_minutes = (datetime.now() - cached_timestamp).total_seconds() / 60

                if age_minutes < self._market_data_ttl_minutes:
                    # Cache is still fresh, load it
                    self._market_snapshot_data = cache_data["data"]
                    self._market_snapshot_timestamp = cached_timestamp
                    logger.debug(
                        f"Loaded market cache from disk: {len(cache_data['data']):,} symbols ({age_minutes:.1f} min old)"
                    )
                else:
                    logger.debug(
                        f"Market cache on disk is stale ({age_minutes:.1f} min old), will refresh"
                    )
            else:
                logger.warning("Invalid cache file structure, will refresh")

        except Exception as e:
            logger.warning(f"Error loading market cache from disk: {e}")

    def _save_market_cache_to_disk(self) -> None:
        """Save current market snapshot data to filesystem"""
        try:
            if not self._market_snapshot_data or not self._market_snapshot_timestamp:
                return

            cache_data = {
                "data": self._market_snapshot_data,
                "timestamp": self._market_snapshot_timestamp.isoformat(),
                "symbols": len(self._market_snapshot_data),
                "provider": "polygon",
            }

            with open(self._market_cache_file, "w") as f:
                json.dump(cache_data, f, indent=2)

            logger.debug(
                f"Saved market cache to disk: {len(self._market_snapshot_data):,} symbols"
            )

        except Exception as e:
            logger.warning(f"Error saving market cache to disk: {e}")

    def _update_database_with_snapshot(self, snapshot_data: Dict[str, Any]) -> None:
        """Update database with new symbols from market snapshot"""
        try:
            from ..storage.asset_universe_manager import AssetUniverseManager
            manager = AssetUniverseManager()
            
            new_symbols_count = 0
            updated_symbols_count = 0
            
            # Process each symbol in the snapshot
            for symbol, ticker_data in snapshot_data.items():
                if not symbol or not isinstance(symbol, str):
                    continue
                
                # Check if asset exists in database
                existing_asset = manager.get_asset(symbol)
                
                if not existing_asset:
                    # Add new asset to database
                    try:
                        # Extract basic info from ticker data
                        asset_id = manager.add_asset(
                            symbol=symbol,
                            name=None,  # Polygon snapshot doesn't include company names
                            asset_type="COMMON_STOCK",
                            is_active=True,
                            is_tradeable=True
                        )
                        
                        # Add to default universe for discovery
                        manager.add_to_universe(
                            symbol, 
                            "default_liquid_universe", 
                            "Auto-added from market snapshot"
                        )
                        
                        new_symbols_count += 1
                        logger.debug(f"Added new symbol to database: {symbol}")
                        
                    except Exception as e:
                        logger.warning(f"Failed to add symbol {symbol} to database: {e}")
                        continue
                
                # Save current market snapshot data
                try:
                    snapshot_time = datetime.now()
                    
                    # Extract price data from ticker structure
                    price = None
                    change_percent = None
                    change_dollars = None
                    volume = None
                    day_open = None
                    day_high = None  
                    day_low = None
                    previous_close = None
                    
                    # Parse ticker data structure
                    if "day" in ticker_data and ticker_data["day"]:
                        day_data = ticker_data["day"]
                        price = day_data.get("c")  # close price
                        day_open = day_data.get("o")
                        day_high = day_data.get("h")
                        day_low = day_data.get("l")
                        volume = day_data.get("v")
                    
                    if "prevDay" in ticker_data and ticker_data["prevDay"]:
                        previous_close = ticker_data["prevDay"].get("c")
                    
                    change_percent = ticker_data.get("todaysChangePerc")
                    change_dollars = ticker_data.get("todaysChange")
                    
                    # Prepare snapshot data
                    snapshot_item = {
                        'symbol': symbol,
                        'price': price,
                        'change_percent': change_percent,
                        'change_dollars': change_dollars,
                        'volume': volume,
                        'day_open': day_open,
                        'day_high': day_high,
                        'day_low': day_low,
                        'previous_close': previous_close
                    }
                    
                    # Skip saving individual snapshots - do it in batch at the end
                    # This is just for tracking updated symbols count
                    if any([price, change_percent, volume]):  # Only count if we have meaningful data
                        updated_symbols_count += 1
                    
                except Exception as e:
                    logger.debug(f"Failed to save snapshot data for {symbol}: {e}")
                    continue
            
            if new_symbols_count > 0 or updated_symbols_count > 0:
                logger.info(f"Database updated: {new_symbols_count} new symbols, {updated_symbols_count} snapshots saved")
            else:
                logger.debug("No database updates needed for market snapshot")
                
        except Exception as e:
            logger.warning(f"Error updating database with snapshot: {e}")

    def _is_database_cache_stale(self) -> bool:
        """Check if database cache is stale (older than TTL)"""
        try:
            from ..storage.asset_universe_manager import AssetUniverseManager
            manager = AssetUniverseManager()
            conn = manager._get_connection()
            cursor = conn.cursor()
            
            # Get most recent snapshot time
            cursor.execute("""
                SELECT MAX(snapshot_time) as latest_snapshot
                FROM market_snapshots
            """)
            
            result = cursor.fetchone()
            conn.close()
            
            if not result or not result['latest_snapshot']:
                return True  # No cache data exists
            
            latest_snapshot = datetime.fromisoformat(result['latest_snapshot'])
            age_minutes = (datetime.now() - latest_snapshot).total_seconds() / 60
            
            return age_minutes >= self._market_data_ttl_minutes
            
        except Exception as e:
            logger.debug(f"Error checking database cache staleness: {e}")
            return True  # Assume stale on error

    def _load_from_database_cache(self) -> Optional[Dict[str, Any]]:
        """Load market snapshot from database cache"""
        try:
            from ..storage.asset_universe_manager import AssetUniverseManager
            manager = AssetUniverseManager()
            conn = manager._get_connection()
            cursor = conn.cursor()
            
            # Get the most recent snapshot time
            cursor.execute("""
                SELECT MAX(snapshot_time) as latest_snapshot
                FROM market_snapshots
            """)
            
            result = cursor.fetchone()
            if not result or not result['latest_snapshot']:
                conn.close()
                return None
            
            latest_snapshot_time = result['latest_snapshot']
            
            # Get all symbols from that snapshot time
            cursor.execute("""
                SELECT a.symbol, ms.*
                FROM market_snapshots ms
                JOIN assets a ON ms.asset_id = a.id
                WHERE ms.snapshot_time = ?
            """, (latest_snapshot_time,))
            
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                return None
            
            # Convert to the format expected by the rest of the system
            snapshot_data = {}
            for row in rows:
                symbol = row['symbol']
                # Create ticker data structure similar to Polygon API
                snapshot_data[symbol] = {
                    'ticker': symbol,
                    'todaysChangePerc': row['change_percent'],
                    'todaysChange': row['change_dollars'],
                    'day': {
                        'c': row['price'],  # close
                        'o': row['day_open'],  # open
                        'h': row['day_high'],  # high
                        'l': row['day_low'],   # low
                        'v': row['volume']     # volume
                    } if row['price'] else None,
                    'prevDay': {
                        'c': row['previous_close']
                    } if row['previous_close'] else None
                }
            
            # Update in-memory timestamp
            self._market_snapshot_timestamp = datetime.fromisoformat(latest_snapshot_time)
            
            return snapshot_data
            
        except Exception as e:
            logger.debug(f"Error loading from database cache: {e}")
            return None

    def _save_to_database_cache(self, snapshot_data: Dict[str, Any]) -> None:
        """Save market snapshot to database cache and add new symbols"""
        try:
            from ..storage.asset_universe_manager import AssetUniverseManager
            manager = AssetUniverseManager()
            
            snapshot_time = datetime.now()
            new_symbols_count = 0
            snapshot_records = []
            
            # Process each symbol in the snapshot
            for symbol, ticker_data in snapshot_data.items():
                if not symbol or not isinstance(symbol, str):
                    continue
                
                # Check if asset exists, add if not
                existing_asset = manager.get_asset(symbol)
                
                if not existing_asset:
                    try:
                        # Add new symbol to database
                        manager.add_asset(
                            symbol=symbol,
                            name=None,  # Polygon snapshot doesn't include names
                            asset_type="COMMON_STOCK",
                            is_active=True,
                            is_tradeable=True
                        )
                        
                        # Add to default universe for discovery
                        manager.add_to_universe(
                            symbol, 
                            "default_liquid_universe", 
                            "Auto-added from market snapshot"
                        )
                        
                        new_symbols_count += 1
                        logger.debug(f"Added new symbol to database: {symbol}")
                        
                    except Exception as e:
                        logger.warning(f"Failed to add symbol {symbol}: {e}")
                        continue
                
                # Prepare snapshot record
                price = None
                change_percent = None
                change_dollars = None
                volume = None
                day_open = None
                day_high = None  
                day_low = None
                previous_close = None
                
                # Parse ticker data structure
                if "day" in ticker_data and ticker_data["day"]:
                    day_data = ticker_data["day"]
                    price = day_data.get("c")
                    day_open = day_data.get("o")
                    day_high = day_data.get("h")
                    day_low = day_data.get("l")
                    volume = day_data.get("v")
                
                if "prevDay" in ticker_data and ticker_data["prevDay"]:
                    previous_close = ticker_data["prevDay"].get("c")
                
                change_percent = ticker_data.get("todaysChangePerc")
                change_dollars = ticker_data.get("todaysChange")
                
                snapshot_records.append({
                    'symbol': symbol,
                    'price': price,
                    'change_percent': change_percent,
                    'change_dollars': change_dollars,
                    'volume': volume,
                    'day_open': day_open,
                    'day_high': day_high,
                    'day_low': day_low,
                    'previous_close': previous_close
                })
            
            # Save all snapshot records in batch
            if snapshot_records:
                saved_count = manager.save_market_snapshot(snapshot_records, snapshot_time)
                logger.info(f"Database cache updated: {new_symbols_count} new symbols, {saved_count} snapshots saved")
            
        except Exception as e:
            logger.warning(f"Error saving to database cache: {e}")

    def _get_ticker_data(
        self, symbol: str, force_refresh: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Get ticker data from centralized market snapshot"""
        market_data = self._get_fresh_market_data(force_refresh)
        if not market_data:
            return None

        return market_data.get(symbol.upper())

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

    def _make_request(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
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
                logger.warning(
                    f"Polygon API error {response.status_code}: {response.text}"
                )
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
            if asset.asset_type not in [
                AssetType.COMMON_STOCK,
                AssetType.PREFERRED_STOCK,
            ]:
                logger.warning(f"Polygon only supports stocks, got {asset.asset_type}")
                return None

            # Use centralized market data instead of individual API call
            ticker_data = self._get_ticker_data(asset.symbol)
            if not ticker_data:
                return None

            return self._convert_snapshot_to_quote(ticker_data, asset)

        except Exception as e:
            logger.error(f"Error getting current quote for {asset.symbol}: {e}")
            return None

    def _convert_snapshot_to_quote(
        self, snapshot_data: Dict[str, Any], asset: Asset
    ) -> MarketQuote:
        """Convert Polygon snapshot data to our MarketQuote format"""
        try:
            # Get current price from snapshot
            # Priority: min.c (latest minute close) > day.c (current day close) > prevDay.c
            current_price = None
            volume = 0
            timestamp = datetime.now()

            # Get most recent price from minute data if available
            has_min = "min" in snapshot_data
            min_data_exists = snapshot_data.get("min") if has_min else None
            logger.debug(
                f"Checking {asset.symbol}: has_min={has_min}, min_data={min_data_exists}"
            )

            if "min" in snapshot_data and snapshot_data["min"]:
                min_data = snapshot_data["min"]
                min_close = min_data.get("c", 0)
                logger.debug(
                    f"Found min data for {asset.symbol}: close={min_close}, type={type(min_close)}"
                )
                current_price = Decimal(str(min_close))
                if "t" in min_data:
                    timestamp = datetime.fromtimestamp(min_data["t"] / 1000)
            elif "day" in snapshot_data and snapshot_data["day"]:
                day_data = snapshot_data["day"]
                current_price = Decimal(str(day_data.get("c", 0)))

            # Always use day volume for the accumulated intraday volume
            day_data = snapshot_data.get("day", {})
            volume = int(day_data.get("v", 0)) if day_data else 0

            if not current_price or current_price <= 0:
                logger.warning(
                    f"No trading activity yet today for {asset.symbol} (price={current_price})"
                )
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

            # Get previous close and average volume from snapshot
            previous_close = None
            average_volume = None

            if "prevDay" in snapshot_data and snapshot_data["prevDay"]:
                prev_day = snapshot_data["prevDay"]
                previous_close = Decimal(str(prev_day.get("c", 0)))
                # Use previous day's volume as a proxy for average volume
                # This is not perfect but better than nothing
                average_volume = int(prev_day.get("v", 0))

            return MarketQuote(
                asset=asset,
                price_data=price_data,
                previous_close=previous_close,
                average_volume=average_volume,
            )

        except Exception as e:
            logger.error(f"Error converting Polygon snapshot data: {e}")
            raise

    def get_extended_hours_data(
        self, asset: Asset, session: MarketStatus, force_refresh: bool = False
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
            if asset.asset_type not in [
                AssetType.COMMON_STOCK,
                AssetType.PREFERRED_STOCK,
            ]:
                return None

            # Get ticker data from centralized market snapshot
            ticker_data = self._get_ticker_data(asset.symbol, force_refresh)
            if not ticker_data:
                return None

            # Extract current price (prefer minute data for most recent)
            current_price = None
            volume = 0
            timestamp = datetime.now()

            if "min" in ticker_data and ticker_data["min"]:
                min_data = ticker_data["min"]
                current_price = Decimal(str(min_data.get("c", 0)))
                volume = int(min_data.get("v", 0))
                if "t" in min_data:
                    timestamp = datetime.fromtimestamp(min_data["t"] / 1000)
            elif "day" in ticker_data and ticker_data["day"]:
                day_data = ticker_data["day"]
                current_price = Decimal(str(day_data.get("c", 0)))
                volume = int(day_data.get("v", 0))

            # Get previous close
            prev_close = None
            if "prevDay" in ticker_data and ticker_data["prevDay"]:
                prev_close = Decimal(str(ticker_data["prevDay"].get("c", 0)))

            if not current_price or not prev_close or prev_close <= 0:
                logger.debug(
                    f"Missing price data for {asset.symbol}: current={current_price}, prev={prev_close}"
                )
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
            if asset.asset_type not in [
                AssetType.COMMON_STOCK,
                AssetType.PREFERRED_STOCK,
            ]:
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

            return [
                self._convert_to_price_data(record, asset) for record in historical_data
            ]

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
        self,
        symbol: str,
        start_date: datetime,
        end_date: datetime,
        multiplier: int,
        timespan: str,
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

    def get_market_gainers(
        self, limit: Optional[int] = 20, force_refresh: bool = False
    ) -> List[MarketMover]:
        """
        Get top market gainers using Polygon snapshot screening

        Args:
            limit: Maximum number of gainers to return
            force_refresh: Force refresh (ignored for now)

        Returns:
            List of MarketMover objects
        """
        try:
            return self._convert_market_movers("gainers", limit, force_refresh)
        except Exception as e:
            logger.error(f"Error getting market gainers: {e}")
            return []

    def get_market_losers(
        self, limit: Optional[int] = 20, force_refresh: bool = False
    ) -> List[MarketMover]:
        """
        Get top market losers using Polygon snapshot screening

        Args:
            limit: Maximum number of losers to return
            force_refresh: Force refresh (ignored for now)

        Returns:
            List of MarketMover objects
        """
        try:
            return self._convert_market_movers("losers", limit, force_refresh)
        except Exception as e:
            logger.error(f"Error getting market losers: {e}")
            return []

    def _convert_market_movers(
        self, mover_type: str, limit: Optional[int], force_refresh: bool = False
    ) -> List[MarketMover]:
        """
        Convert market snapshot data to sorted MarketMover objects
        Args:
            mover_type: 'gainers' or 'losers'
            limit: Maximum number of movers to return
            force_refresh: Force refresh of market data
        Returns:
            List of MarketMover objects sorted by percentage change
        """
        try:
            # Get fresh market data
            market_data = self._get_fresh_market_data(force_refresh)
            if not market_data:
                logger.error("No market data available for calculating movers")
                return []

            # Calculate percentage changes for all symbols
            movers_data = []
            for symbol, ticker_data in market_data.items():
                try:
                    # Get current price from day.c (today's close)
                    current_price = 0
                    if "day" in ticker_data and ticker_data["day"]:
                        current_price = ticker_data["day"].get("c", 0)

                    # Get previous close from prevDay.c
                    prev_close = 0
                    if "prevDay" in ticker_data and ticker_data["prevDay"]:
                        prev_close = ticker_data["prevDay"].get("c", 0)

                    # Calculate change
                    if not current_price or not prev_close:
                        continue

                    change_amount = current_price - prev_close
                    change_pct = (change_amount / prev_close) * 100

                    # Get volume
                    volume = 0
                    if "day" in ticker_data and ticker_data["day"]:
                        volume = ticker_data["day"].get("v", 0)

                    movers_data.append(
                        {
                            "symbol": symbol,
                            "current_price": current_price,
                            "prev_close": prev_close,
                            "change_amount": change_amount,
                            "change_pct": change_pct,
                            "volume": volume,
                        }
                    )

                except Exception as e:
                    logger.debug(f"Error processing {symbol}: {e}")
                    continue

            # Sort by percentage change
            reverse_sort = mover_type == "gainers"
            sorted_movers = sorted(
                movers_data, key=lambda x: x["change_pct"], reverse=reverse_sort
            )

            # Convert to MarketMover objects
            market_movers = []
            for mover_data in sorted_movers[
                : limit if limit is not None else len(sorted_movers)
            ]:
                try:
                    asset = Asset(
                        symbol=mover_data["symbol"],
                        name=mover_data["symbol"],
                        asset_type=AssetType.COMMON_STOCK,
                        market=self.default_market,
                        currency="USD",
                    )

                    market_mover = MarketMover(
                        asset=asset,
                        current_price=mover_data["current_price"],
                        price_change=mover_data["change_amount"],
                        price_change_percent=mover_data["change_pct"],
                        volume=mover_data["volume"],
                    )

                    market_movers.append(market_mover)

                except Exception as e:
                    logger.error(
                        f"Error creating MarketMover for {mover_data['symbol']}: {e}"
                    )
                    continue

            logger.debug(
                f"Converted {len(market_movers)} {mover_type} from {len(market_data)} symbols"
            )
            return market_movers

        except Exception as e:
            logger.error(f"Error converting market {mover_type}: {e}")
            return []

    def _get_full_market_snapshot(self) -> Optional[Dict[str, Any]]:
        """
        Get full market snapshot for all US stocks from Polygon.io.
        Returns current prices AND previous/today's close data.
        Single API call replaces thousands of individual quote calls.
        """
        try:
            # Use Polygon full market snapshot endpoint
            url = "https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers"
            params = {"apikey": self.api_key}

            logger.debug("Fetching full market snapshot from Polygon.io...")
            response = requests.get(url, params=params, timeout=30)

            if response.status_code != 200:
                logger.error(
                    f"Polygon snapshot API error: {response.status_code} - {response.text}"
                )
                return None

            data = response.json()

            if data.get("status") != "OK":
                logger.error(
                    f"Polygon snapshot API returned status: {data.get('status')}"
                )
                return None

            # Process results into symbol -> data mapping for easy lookup
            snapshot_dict = {}
            tickers = data.get("tickers", [])

            for ticker_data in tickers:
                symbol = ticker_data.get("ticker", "").upper()
                if symbol:
                    snapshot_dict[symbol] = ticker_data

            logger.debug(f"Retrieved snapshot data for {len(snapshot_dict)} symbols")
            return snapshot_dict

        except Exception as e:
            logger.error(f"Error getting full market snapshot: {e}")
            return None

    def _screen_market_movers(
        self, mover_type: str, limit: int, force_refresh: bool = False
    ) -> List[MarketMover]:
        """
        Get market movers using Polygon's dedicated batch endpoint - PROPER!

        Args:
            mover_type: 'gainers' or 'losers'
            limit: Maximum number of movers to return

        Returns:
            List of MarketMover objects sorted by percentage change
        """
        try:
            # 🚀 Use dedicated market movers endpoint with 15-minute caching
            logger.debug(
                f"Getting {mover_type} using dedicated Polygon batch endpoint (1 API call, cached 15min)"
            )

            # Define the API call function for caching
            def fetch_market_movers():
                try:
                    url = f"https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/{mover_type}"
                    params = {
                        "apikey": self.api_key,
                        "include_otc": "false",  # Exclude OTC securities
                    }

                    logger.debug(f"Making request to: {url}")
                    logger.debug(
                        f"API key starts with: {self.api_key[:10] if self.api_key else 'NONE'}..."
                    )

                    response = requests.get(url, params=params, timeout=30)

                    logger.debug(f"Response status: {response.status_code}")

                    if response.status_code != 200:
                        logger.error(
                            f"Polygon {mover_type} API error: {response.status_code} - {response.text}"
                        )
                        return None

                    data = response.json()

                    if data.get("status") != "OK":
                        logger.error(
                            f"Polygon {mover_type} API returned status: {data.get('status')}"
                        )
                        return None

                    tickers = data.get("tickers", [])
                    logger.debug(f"API returned {len(tickers)} tickers")
                    return tickers

                except Exception as e:
                    logger.error(f"Exception in fetch_market_movers: {e}")
                    return None

            # Just call the API directly for now - fuck caching
            results = fetch_market_movers()

            if not results:
                logger.error(
                    f"No {mover_type} data received from API (results is None or empty)"
                )
                return []
            logger.info(
                f"Retrieved {len(results)} {mover_type} from Polygon batch endpoint"
            )

            # Convert to MarketMover objects
            market_movers = []
            for ticker_data in results[
                : limit if limit is not None else len(results)
            ]:  # Respect the limit parameter
                try:
                    symbol = ticker_data.get("ticker", "").upper()
                    change_pct = ticker_data.get("todaysChangePerc", 0)
                    change_amount = ticker_data.get("todaysChange", 0)

                    # Get current price from day.c (today's close)
                    current_price = 0
                    if "day" in ticker_data and ticker_data["day"]:
                        current_price = ticker_data["day"].get("c", 0)

                    # Get previous close from prevDay.c
                    prev_close = 0
                    if "prevDay" in ticker_data and ticker_data["prevDay"]:
                        prev_close = ticker_data["prevDay"].get("c", 0)

                    # Get volume from day data
                    volume = 0
                    if "day" in ticker_data and ticker_data["day"]:
                        volume = ticker_data["day"].get("v", 0)

                    if not symbol or not current_price or not prev_close:
                        logger.debug(
                            f"Skipping {symbol}: current_price={current_price}, prev_close={prev_close}"
                        )
                        continue

                    asset = Asset(
                        symbol=symbol,
                        name=symbol,
                        asset_type=AssetType.COMMON_STOCK,
                        market=self.default_market,
                        currency="USD",
                    )

                    market_mover = MarketMover(
                        asset=asset,
                        current_price=current_price,
                        previous_close=prev_close,
                        price_change=change_amount,
                        price_change_percent=change_pct,
                        volume=volume,
                        timestamp=0,  # Endpoint doesn't provide specific timestamp
                    )

                    market_movers.append(market_mover)

                except Exception as e:
                    logger.debug(
                        f"Failed to process mover {ticker_data.get('ticker', 'unknown')}: {e}"
                    )
                    continue

            logger.info(
                f"Successfully converted {len(market_movers)} {mover_type} to MarketMover objects"
            )
            return market_movers

        except Exception as e:
            logger.error(f"Error getting {mover_type}: {e}")
            return []

    def _get_screening_universe(self) -> List[str]:
        """Get universe of stocks for screening from configuration"""
        try:
            liquid_universe = get_default_screening_universe()

            if not liquid_universe:
                raise RuntimeError(
                    "No screening universe loaded from config - cannot proceed"
                )

            logger.debug(
                f"Using configured screening universe of {len(liquid_universe)} symbols"
            )
            return liquid_universe

        except Exception as e:
            logger.error(f"Error loading screening universe from config: {e}")
            raise RuntimeError(f"Failed to load screening universe: {e}")

    def get_company_info(self, asset: Asset) -> Optional[Dict[str, Any]]:
        """
        Get company information using Polygon ticker details

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

    def _fetch_financial_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch financial data from Polygon financials endpoint"""
        try:
            # Use caching for financial data (quarterly refresh)
            financial_data = cached_api_call(
                provider=self.provider_name,
                endpoint="financials",
                params={"symbol": symbol, "timeframe": "ttm"},
                api_function=lambda: self._make_financials_request(symbol),
                policy=CachePolicy.DAILY,
            )

            return financial_data
        except Exception as e:
            logger.error(f"Error fetching financial data for {symbol}: {e}")
            return None

    def _make_financials_request(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Make request to Polygon financials API and extract key metrics"""
        endpoint = f"vX/reference/financials"
        params = {
            "ticker": symbol,
            "timeframe": "ttm",  # Trailing twelve months
            "limit": 1,
        }

        response = self._make_request(endpoint, params)

        if response and response.get("status") == "OK" and response.get("results"):
            result = response["results"][0]
            financials = result.get("financials", {})

            # Extract key financial metrics
            extracted_data = {}

            # Income statement metrics
            income_statement = financials.get("income_statement", {})
            balance_sheet = financials.get("balance_sheet", {})
            cash_flow = financials.get("cash_flow_statement", {})

            # Revenue and profitability
            if "revenues" in income_statement:
                extracted_data["total_revenue"] = income_statement["revenues"]["value"]
            if "net_income_loss" in income_statement:
                extracted_data["net_income"] = income_statement["net_income_loss"][
                    "value"
                ]
            if "gross_profit" in income_statement:
                extracted_data["gross_profit"] = income_statement["gross_profit"][
                    "value"
                ]
            if "operating_income_loss" in income_statement:
                extracted_data["operating_income"] = income_statement[
                    "operating_income_loss"
                ]["value"]

            # Balance sheet metrics
            if "assets" in balance_sheet:
                extracted_data["total_assets"] = balance_sheet["assets"]["value"]
            if "equity" in balance_sheet:
                extracted_data["total_equity"] = balance_sheet["equity"]["value"]
            if "current_assets" in balance_sheet:
                extracted_data["current_assets"] = balance_sheet["current_assets"][
                    "value"
                ]
            if "current_liabilities" in balance_sheet:
                extracted_data["current_liabilities"] = balance_sheet[
                    "current_liabilities"
                ]["value"]

            # Cash flow metrics
            if "net_cash_flow_from_operating_activities" in cash_flow:
                extracted_data["operating_cash_flow"] = cash_flow[
                    "net_cash_flow_from_operating_activities"
                ]["value"]
            if "net_cash_flow_from_financing_activities" in cash_flow:
                extracted_data["financing_cash_flow"] = cash_flow[
                    "net_cash_flow_from_financing_activities"
                ]["value"]

            # Calculate derived metrics
            if (
                "total_revenue" in extracted_data
                and "net_income" in extracted_data
                and extracted_data["total_revenue"]
            ):
                extracted_data["profit_margin"] = (
                    extracted_data["net_income"] / extracted_data["total_revenue"]
                ) * 100

            if (
                "current_assets" in extracted_data
                and "current_liabilities" in extracted_data
                and extracted_data["current_liabilities"]
            ):
                extracted_data["current_ratio"] = (
                    extracted_data["current_assets"]
                    / extracted_data["current_liabilities"]
                )

            if (
                "total_equity" in extracted_data
                and "total_assets" in extracted_data
                and extracted_data["total_assets"]
            ):
                extracted_data["equity_ratio"] = (
                    extracted_data["total_equity"] / extracted_data["total_assets"]
                ) * 100

            # Add filing metadata
            extracted_data["fiscal_period"] = result.get("fiscal_period")
            extracted_data["fiscal_year"] = result.get("fiscal_year")
            extracted_data["filing_date"] = result.get("filing_date")
            extracted_data["timeframe"] = result.get("timeframe")

            return extracted_data

        return None

    def _map_to_fundamentals_model(
        self, asset: Asset, raw_data: Dict[str, Any]
    ) -> CompanyFundamentals:
        """Map raw Polygon data to our CompanyFundamentals domain model"""
        from decimal import Decimal

        # Helper function to safely convert to Decimal
        def to_decimal(value) -> Optional[Decimal]:
            if value is None:
                return None
            try:
                return Decimal(str(value))
            except (ValueError, TypeError):
                return None

        # Helper function to safely convert to int
        def to_int(value) -> Optional[int]:
            if value is None:
                return None
            try:
                return int(value)
            except (ValueError, TypeError):
                return None

        # Determine reporting period
        timeframe = raw_data.get("timeframe", "").upper()
        fiscal_period = raw_data.get("fiscal_period", "")
        fiscal_year = raw_data.get("fiscal_year", "")

        if timeframe == "TTM":
            reporting_period = f"TTM {fiscal_year}".strip()
        elif fiscal_period and fiscal_year:
            reporting_period = f"{fiscal_period} {fiscal_year}"
        else:
            reporting_period = "Current"

        # Create CompanyFundamentals instance
        return CompanyFundamentals(
            asset=asset,
            reporting_period=reporting_period,
            fiscal_year=fiscal_year or None,
            # Company Information
            description=raw_data.get("description"),
            industry=raw_data.get("sic_description"),
            website=raw_data.get("homepage_url"),
            employees=to_int(raw_data.get("total_employees")),
            # Market Data
            market_cap=to_decimal(raw_data.get("market_cap")),
            shares_outstanding=to_int(
                raw_data.get("share_class_shares_outstanding")
                or raw_data.get("weighted_shares_outstanding")
            ),
            # Income Statement
            total_revenue=to_decimal(raw_data.get("total_revenue")),
            gross_profit=to_decimal(raw_data.get("gross_profit")),
            operating_income=to_decimal(raw_data.get("operating_income")),
            net_income=to_decimal(raw_data.get("net_income")),
            # Balance Sheet
            total_assets=to_decimal(raw_data.get("total_assets")),
            current_assets=to_decimal(raw_data.get("current_assets")),
            total_liabilities=to_decimal(
                raw_data.get("current_liabilities")
            ),  # Note: We only have current liabilities from Polygon
            current_liabilities=to_decimal(raw_data.get("current_liabilities")),
            shareholders_equity=to_decimal(raw_data.get("total_equity")),
            # Cash Flow Statement
            operating_cash_flow=to_decimal(raw_data.get("operating_cash_flow")),
            financing_cash_flow=to_decimal(raw_data.get("financing_cash_flow")),
            # Financial Ratios (calculated by Polygon or calculated here)
            current_ratio=to_decimal(raw_data.get("current_ratio")),
            net_margin=to_decimal(raw_data.get("profit_margin")),
            # Data source metadata
            data_source="polygon",
            data_quality="good",
            last_updated=datetime.now(),
        )

    def health_check(self) -> bool:
        """
        Check if the Polygon API is accessible and working

        Returns:
            True if API is healthy, False otherwise
        """
        try:
            # Try to get ticker data from centralized snapshot
            test_data = self._get_ticker_data("AAPL")
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

    def get_fundamental_data(self, asset: Asset) -> Optional[CompanyFundamentals]:
        """Get comprehensive fundamental data as domain model"""
        try:
            # Get basic company info
            company_data = self.get_company_info(asset) or {}

            # Get detailed financial data
            financial_data = self._fetch_financial_data(asset.symbol)

            # Merge both datasets
            raw_data = {}
            raw_data.update(company_data)
            if financial_data:
                raw_data.update(financial_data)

            if not raw_data:
                return None

            # Map to domain model
            return self._map_to_fundamentals_model(asset, raw_data)

        except Exception as e:
            logger.error(f"Error getting fundamental data for {asset.symbol}: {e}")
            return None

    def get_live_extended_hours_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get live extended hours pricing for a single symbol using Polygon custom bars endpoint.
        Uses hourly bars covering pre-market, regular market, and after-hours sessions.

        Args:
            symbol: Stock symbol to get live extended hours pricing for

        Returns:
            Dict with current extended hours price or None if error/no data
        """
        try:
            # Get today's date for the bars endpoint
            today = datetime.now().strftime("%Y-%m-%d")

            # Use Polygon custom bars endpoint for live extended hours data
            # This endpoint provides "aggregated historical OHLC... covering pre-market, regular market, and after-hours sessions"
            url = f"https://api.polygon.io/v2/aggs/ticker/{symbol.upper()}/range/1/hour/{today}/{today}"
            params = {
                "apikey": self.api_key,
                "adjusted": "true",
                "sort": "desc",  # Get most recent bars first
            }

            logger.debug(
                f"Fetching live extended hours data for {symbol} from Polygon custom bars API"
            )
            response = requests.get(url, params=params, timeout=10)

            if response.status_code != 200:
                logger.warning(
                    f"Polygon custom bars API error for {symbol}: {response.status_code}"
                )
                return None

            data = response.json()

            if data.get("status") != "OK" or not data.get("results"):
                logger.debug(f"No extended hours bar data for {symbol}")
                return None

            # Get the most recent bar (first in desc sorted results)
            latest_bar = data["results"][0]

            # Extract the close price as current price
            current_price = latest_bar.get("c")  # Close price of the most recent bar
            volume = latest_bar.get("v", 0)  # Volume
            timestamp_ms = latest_bar.get("t")  # Timestamp in milliseconds

            if not current_price:
                logger.debug(f"No close price in latest bar for {symbol}")
                return None

            # Convert timestamp from milliseconds to datetime
            timestamp = None
            if timestamp_ms:
                timestamp = datetime.fromtimestamp(timestamp_ms / 1000)

            # Return in format compatible with existing gap calculation code
            return {
                "symbol": symbol.upper(),
                "current_price": current_price,
                "midpoint": current_price,  # Use close price as midpoint for compatibility
                "volume": volume,
                "timestamp": timestamp,
                "bar_data": latest_bar,  # Include full bar data for debugging
            }

        except Exception as e:
            logger.error(f"Error getting live extended hours data for {symbol}: {e}")
            return None
