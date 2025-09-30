"""Polygon API data provider for TradeScout."""

import requests
import time
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta, time as dt_time
from decimal import Decimal
from models.asset import Asset, AssetType, AssetClass
from models.market import Market
from services.data_update_tracker import DataUpdateTracker
from models.price import AssetPrice
from models.fundamentals import AssetFundamentals
from models.snapshot import MarketSnapshot, TickerSnapshot
from models.stats import DatabaseStats, OperationStats
from models.universe import Universe, UniverseMembership, UniverseStats
from config.ttl_config import ASSET_PRICE_TTL_MINUTES
from cache.fundamentals_cache import FundamentalsCacheManager
from provider.cache import MarketContextCache, MarketHolidaysCache, AssetPricesCache, TickerSnapshotCache, MarketSnapshotCache

logger = logging.getLogger(__name__)


class PolygonDataProvider:
    """Encapsulates all Polygon API interactions and database queries."""

    # ============================================================================
    # INITIALIZATION
    # ============================================================================

    def __init__(self, db_manager=None):
        """Initialize with database manager, loads API key automatically."""
        from config.api_keys import POLYGON_API_KEY
        self.api_key = POLYGON_API_KEY
        if not self.api_key:
            raise ValueError("Polygon API key is required")

        self.base_url = "https://api.polygon.io"
        self.db_manager = db_manager
        self.update_tracker = DataUpdateTracker(self) if db_manager else None
        self.fundamentals_cache = FundamentalsCacheManager()

        # Initialize cache managers
        self.market_context_cache = MarketContextCache(db_manager, self.update_tracker)
        self.market_holidays_cache = MarketHolidaysCache(db_manager, self.update_tracker)
        self.asset_prices_cache = AssetPricesCache(db_manager, self.update_tracker)
        self.ticker_snapshot_cache = TickerSnapshotCache(db_manager, self.update_tracker)
        self.market_snapshot_cache = MarketSnapshotCache(db_manager, self.update_tracker)

    # ============================================================================
    # PUBLIC API METHODS - External API Calls
    # ============================================================================

    def fetch_all_tickers(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch all active stock tickers with pagination."""
        all_tickers = []
        cursor = None
        page = 1

        logger.info("Starting ticker fetch from Polygon API")

        while True:
            logger.info(f"Fetching page {page}")

            params = {
                "market": "stocks",
                "active": "true",
                "limit": 1000
            }

            if cursor:
                params["cursor"] = cursor

            data = self._make_request("/v3/reference/tickers", params)

            if "results" not in data or not data["results"]:
                logger.info("No more results, pagination complete")
                break

            page_results = data["results"]
            all_tickers.extend(page_results)
            logger.debug(f"Page {page}: {len(page_results)} tickers")

            if limit and len(all_tickers) >= limit:
                all_tickers = all_tickers[:limit]
                logger.info(f"Reached limit of {limit} tickers, stopping fetch")
                break

            cursor = data.get("next_url")
            if cursor and "cursor=" in cursor:
                cursor = cursor.split("cursor=")[1].split("&")[0]
            else:
                logger.info("No next cursor, pagination complete")
                break

            page += 1

        logger.info(f"Total tickers fetched: {len(all_tickers)} across {page} pages")
        return all_tickers

    def get_market_snapshot_cached(self, symbols: List[str], progress_callback=None) -> Optional[MarketSnapshot]:
        """Get market snapshot for specified symbols with caching."""
        # Use hash of symbols as cache key for consistent lookup
        cache_key = f"market_snapshot_{len(symbols)}_{hash(tuple(sorted(symbols)))}"
        return self.market_snapshot_cache.get_or_fetch(
            cache_key,
            lambda: self._get_market_snapshot_direct(symbols, progress_callback)
        )

    def get_market_snapshot(self, symbols: List[str], progress_callback=None) -> Optional[MarketSnapshot]:
        """Get market snapshot for specified symbols using chunking."""
        return self._get_market_snapshot_direct(symbols, progress_callback)

    def _get_market_snapshot_direct(self, symbols: List[str], progress_callback=None) -> Optional[MarketSnapshot]:
        """Internal method to get market snapshot directly from API."""
        if not symbols:
            return None

        # Chunk symbols to avoid URI too large error
        chunk_size = 100
        all_results = []
        total_chunks = (len(symbols) + chunk_size - 1) // chunk_size  # Ceiling division

        logger.info(f"Fetching market snapshot for {len(symbols)} symbols in {total_chunks} chunks of {chunk_size}")

        for i in range(0, len(symbols), chunk_size):
            chunk_num = (i // chunk_size) + 1
            chunk = symbols[i:i + chunk_size]

            # Call progress callback if provided
            if progress_callback:
                progress_callback(chunk_num, total_chunks, len(chunk))

            symbol_list = ",".join(chunk)
            params = {"tickers": symbol_list}

            chunk_data = self._make_request("/v2/snapshot/locale/us/markets/stocks/tickers", params)

            if chunk_data and "tickers" in chunk_data:
                all_results.extend(chunk_data["tickers"])
                logger.debug(f"Chunk {chunk_num}/{total_chunks} completed: {len(chunk_data['tickers'])} results")
            else:
                logger.warning(f"Chunk {chunk_num}/{total_chunks} returned no data")

        logger.info(f"Market snapshot complete: {len(all_results)} total results from {total_chunks} chunks")

        # Create MarketSnapshot model from the aggregated results
        polygon_response = {"results": all_results, "status": "OK"}
        return MarketSnapshot.from_polygon_data(polygon_response)

    def get_single_ticker_snapshot(self, symbol: str) -> Optional[TickerSnapshot]:
        """Get snapshot for a single ticker with caching."""
        return self.ticker_snapshot_cache.get_or_fetch(symbol, lambda: self._fetch_single_ticker_snapshot(symbol))

    def _fetch_single_ticker_snapshot(self, symbol: str) -> Optional[TickerSnapshot]:
        """Fetch single ticker snapshot from API."""
        raw_data = self._make_request(f"/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}", {})
        if not raw_data or "ticker" not in raw_data:
            return None

        # Create a single-ticker MarketSnapshot and extract the ticker
        polygon_response = {"results": [raw_data["ticker"]], "status": "OK"}
        market_snapshot = MarketSnapshot.from_polygon_data(polygon_response)

        # Return the single ticker snapshot
        return market_snapshot.tickers.get(symbol) if market_snapshot else None

    def get_market_status(self) -> Dict[str, Any]:
        """Get current market status with caching.

        Returns:
            Raw API response dict containing market status data.
        """
        # This method returns raw status - used by market context service
        # Market context service handles its own caching of complete MarketContext objects
        return self._make_request("/v1/marketstatus/now", {})

    def get_market_holidays(self) -> List[Dict[str, Any]]:
        """Get upcoming market holidays with caching.

        Returns:
            List of holiday objects with date, exchange, name, status fields.
            Status can be 'closed' or 'early-close'.
        """
        # Use cache with 30-day TTL
        return self.market_holidays_cache.get_or_fetch(
            "holidays",
            lambda: self._make_request("/v1/marketstatus/upcoming", {})
        )

    def get_cached_market_context(self, market_code: str, fetch_fn):
        """Get cached MarketContext or fetch fresh using provided function.

        Args:
            market_code: Market code (e.g., 'XNYS')
            fetch_fn: Function to fetch fresh MarketContext from service

        Returns:
            MarketContext object or None if error
        """
        from models.market_context import MarketContext

        return self.market_context_cache.get_or_fetch(market_code, fetch_fn)

    def store_market_context(self, market_code: str, context) -> None:
        """Store MarketContext in cache.

        Args:
            market_code: Market code
            context: MarketContext object to cache
        """
        self.market_context_cache.set(market_code, context)

    def get_ticker_overview(self, symbol: str) -> Dict[str, Any]:
        """Get ticker overview with fundamentals data from Polygon API.

        Uses aggressive file-based caching to avoid repeated API calls.
        Cache TTL is configured via FUNDAMENTALS_TTL_HOURS.

        Args:
            symbol: Stock symbol (e.g., "AAPL")

        Returns:
            Raw API response dict containing ticker overview data.
            Use AssetFundamentals.from_polygon_data() to convert to typed model.

        Raises:
            Exception: If API request fails or ticker not found
        """
        symbol = symbol.upper()

        # Try cache first
        cached_data = self.fundamentals_cache.get_cached_data(symbol)
        if cached_data:
            logger.debug(f"Using cached fundamentals data for {symbol}")
            return cached_data

        # Cache miss - fetch from API
        logger.debug(f"Fetching fundamentals data from API for {symbol}")
        endpoint = f"/v3/reference/tickers/{symbol}"
        api_data = self._make_request(endpoint, {})

        # Cache the response for future use
        self.fundamentals_cache.cache_data(symbol, api_data)

        return api_data

    def get_current_market_session(self) -> str:
        """Get current market session.

        Returns:
            Session name: 'premarket', 'regular', 'afterhours', or 'closed'

        Raises:
            RuntimeError: If market status API call fails
        """
        try:
            market_status = self.get_market_status()

            # Parse Polygon market status response
            market = market_status.get('market', '').lower()
            early_hours = market_status.get('earlyHours', False)
            after_hours = market_status.get('afterHours', False)

            # Map Polygon market status to our session names
            if market == 'open':
                return "regular"
            elif market == 'extended-hours':
                if early_hours:
                    return "premarket"
                elif after_hours:
                    return "afterhours"
                else:
                    return "premarket"  # Default to premarket for extended hours
            elif market == 'closed':
                return "closed"
            else:
                raise RuntimeError(f"Unknown market status from Polygon API: {market}")

        except Exception as e:
            logger.error(f"Error getting current market session: {e}")
            raise RuntimeError("Failed to get market session from Polygon API")

    # ============================================================================
    # PUBLIC ASSET & MARKET DATA METHODS - Database Operations
    # ============================================================================

    def get_asset_data(self, symbol: str) -> Optional[Tuple[Asset, Market]]:
        """Retrieve asset and market data for a single symbol from database."""
        if not self.db_manager:
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT
                        -- Asset fields
                        a.id, a.symbol, a.name, a.market_id, a.asset_type,
                        a.asset_class, a.currency, a.lot_size, a.tick_size,
                        a.is_active, a.is_delisted, a.listing_date, a.delisting_date,
                        a.provider_id, a.created_at, a.updated_at,
                        -- Market fields
                        m.code, m.name, m.country, m.timezone, m.currency,
                        m.premarket_start_time, m.premarket_end_time,
                        m.regular_open_time, m.regular_close_time,
                        m.afterhours_start_time, m.afterhours_end_time,
                        m.is_active, m.created_at, m.updated_at
                    FROM assets a
                    JOIN markets m ON a.market_id = m.id
                    WHERE a.symbol = ? AND a.is_active = 1
                """

                cursor.execute(query, (symbol.upper(),))
                result = cursor.fetchone()

                if not result:
                    return None

                # Parse asset data
                asset = Asset(
                    id=result[0],
                    symbol=result[1],
                    name=result[2],
                    market_id=result[3],
                    asset_type=AssetType(result[4]),
                    asset_class=AssetClass(result[5]),
                    currency=result[6],
                    provider_id=result[13],
                    created_at=datetime.fromisoformat(result[14]),
                    updated_at=datetime.fromisoformat(result[15]),
                    lot_size=result[7] or 1,
                    tick_size=result[8],
                    is_active=bool(result[9]),
                    is_delisted=bool(result[10]),
                    listing_date=datetime.fromisoformat(result[11]) if result[11] else None,
                    delisting_date=datetime.fromisoformat(result[12]) if result[12] else None
                )

                # Parse market data
                market = Market(
                    id=result[3],  # market_id from asset
                    code=result[16],
                    name=result[17],
                    country=result[18],
                    timezone=result[19],
                    currency=result[20],
                    created_at=datetime.fromisoformat(result[28]),
                    updated_at=datetime.fromisoformat(result[29]),
                    premarket_start_time=result[21],
                    premarket_end_time=result[22],
                    regular_open_time=result[23],
                    regular_close_time=result[24],
                    afterhours_start_time=result[25],
                    afterhours_end_time=result[26],
                    is_active=bool(result[27])
                )

                return (asset, market)

        except Exception as e:
            logger.error(f"Error retrieving asset data for {symbol}: {e}")
            return None

    def get_active_universe_symbols(self) -> List[str]:
        """Get symbols from active universe memberships."""
        if not self.db_manager:
            return []

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT a.symbol
                    FROM assets a
                    JOIN universe_memberships um ON a.id = um.asset_id
                    JOIN universes u ON um.universe_id = u.id
                    WHERE um.is_active = 1
                    AND a.is_active = 1
                    AND u.is_active = 1
                    ORDER BY a.symbol
                """)
                return [row[0] for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error getting universe symbols: {e}")
            return []

    def get_market_by_code(self, market_code: str) -> Optional[Market]:
        """Get a market by its code.

        Args:
            market_code: Market code (e.g., 'XNYS', 'XNAS')

        Returns:
            Market object or None if not found
        """
        if not self.db_manager:
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, code, name, country, timezone, currency,
                           premarket_start_time, premarket_end_time,
                           regular_open_time, regular_close_time,
                           afterhours_start_time, afterhours_end_time,
                           is_active, created_at, updated_at
                    FROM markets
                    WHERE code = ? AND is_active = TRUE
                """, (market_code,))

                row = cursor.fetchone()
                if row:
                    # Convert time strings to time objects
                    def parse_time(time_str: Optional[str]) -> Optional[dt_time]:
                        if time_str:
                            try:
                                return datetime.strptime(time_str, '%H:%M:%S').time()
                            except ValueError:
                                return None
                        return None

                    return Market(
                        id=row[0],
                        code=row[1],
                        name=row[2],
                        country=row[3],
                        timezone=row[4],
                        currency=row[5],
                        premarket_start_time=parse_time(row[6]),
                        premarket_end_time=parse_time(row[7]),
                        regular_open_time=parse_time(row[8]) or dt_time(9, 30),
                        regular_close_time=parse_time(row[9]) or dt_time(16, 0),
                        afterhours_start_time=parse_time(row[10]),
                        afterhours_end_time=parse_time(row[11]),
                        is_active=bool(row[12]),
                        created_at=datetime.fromisoformat(row[13]) if row[13] else datetime.now(),
                        updated_at=datetime.fromisoformat(row[14]) if row[14] else datetime.now()
                    )

        except Exception as e:
            logger.error(f"Failed to fetch market {market_code}: {e}")

        return None

    def get_active_markets_by_codes(self, market_codes: List[str]) -> List[Tuple[str, str]]:
        """Get active markets by their codes.

        Args:
            market_codes: List of market codes to filter by

        Returns:
            List of tuples (market_code, market_name)
        """
        if not self.db_manager or not market_codes:
            return []

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                placeholders = ','.join('?' * len(market_codes))
                cursor.execute(
                    f"SELECT code, name FROM markets WHERE code IN ({placeholders}) AND is_active = TRUE ORDER BY code",
                    market_codes
                )
                return cursor.fetchall()

        except Exception as e:
            logger.error(f"Error getting active markets by codes: {e}")
            return []

    def upsert_assets(self, assets_data: List[Dict[str, Any]]) -> Dict[str, int]:
        """Upsert assets from ticker data into database using batch operations.

        Args:
            assets_data: List of asset dictionaries with keys: symbol, name, market_id, currency, is_active

        Returns:
            Dictionary with statistics: {"inserted": int, "updated": int, "errors": int}
        """
        if not self.db_manager:
            logger.error("No database manager available")
            return {"inserted": 0, "updated": 0, "errors": 0}

        stats = {"inserted": 0, "updated": 0, "errors": 0}

        if not assets_data:
            return stats

        logger.debug(f"Upserting {len(assets_data)} assets...")

        # Get provider ID for Polygon
        provider_id = self.get_polygon_provider_id()
        if provider_id is None:
            logger.error("Polygon provider not found")
            stats["errors"] = len(assets_data)
            return stats

        # Process in batches to avoid memory issues
        batch_size = 1000
        current_time = datetime.now().isoformat()

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                for i in range(0, len(assets_data), batch_size):
                    batch = assets_data[i:i + batch_size]
                    logger.debug(f"Processing batch {i // batch_size + 1}/{(len(assets_data) + batch_size - 1) // batch_size}")

                    # Use INSERT OR REPLACE for efficient batch upserts
                    upsert_sql = """
                        INSERT OR REPLACE INTO assets (
                            symbol, name, asset_type, asset_class, market_id,
                            currency, provider_id, is_active, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """

                    upsert_params = []
                    for asset_data in batch:
                        try:
                            # Default asset type and class for stocks (can be enhanced later)
                            asset_type = "stock"
                            asset_class = "equity"

                            upsert_params.append((
                                asset_data['symbol'],
                                asset_data['name'],
                                asset_type,
                                asset_class,
                                asset_data['market_id'],
                                asset_data['currency'],
                                provider_id,
                                asset_data['is_active'],
                                current_time,
                                current_time
                            ))

                        except KeyError as e:
                            logger.error(f"Missing required field {e} for asset {asset_data.get('symbol', 'unknown')}")
                            stats["errors"] += 1
                            continue

                    if upsert_params:
                        try:
                            cursor.executemany(upsert_sql, upsert_params)

                            # Count as inserted for simplicity (SQLite doesn't easily distinguish INSERT vs REPLACE)
                            stats["inserted"] += len(upsert_params)

                        except Exception as e:
                            logger.error(f"Batch upsert error: {e}")
                            stats["errors"] += len(upsert_params)

                conn.commit()

        except Exception as e:
            logger.error(f"Database error during assets upsert: {e}")
            stats["errors"] += len(assets_data)
            return stats

        logger.debug(f"Assets upsert complete: {stats}")
        return stats

    def get_market_id_by_exchange(self, exchange_code: str) -> int:
        """Get market ID by exchange code, with fallback to default market.

        Args:
            exchange_code: Exchange code (e.g., "XNAS", "XNYS")

        Returns:
            Market ID (defaults to 1 if not found)
        """
        if not self.db_manager:
            return 1  # Default fallback

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Try exact match first
                cursor.execute("SELECT id FROM markets WHERE code = ?", (exchange_code,))
                result = cursor.fetchone()

                if result:
                    return result[0]

                # Fallback to default market (assumes ID 1 exists)
                logger.warning(f"Exchange code '{exchange_code}' not found, using default market")
                return 1

        except Exception as e:
            logger.error(f"Error getting market ID for {exchange_code}: {e}")
            return 1  # Safe fallback

    # ============================================================================
    # PUBLIC ASSET PRICE DATA METHODS - Database Operations
    # ============================================================================

    def get_latest_asset_price(self, asset_id: int) -> Optional[AssetPrice]:
        """Get the most recent price record for an asset."""
        if not self.db_manager:
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Get record with highest provider_updated_at, then highest updated_at as tiebreaker
                query = """
                    SELECT * FROM asset_prices
                    WHERE asset_id = ?
                    ORDER BY provider_updated_at DESC, updated_at DESC
                    LIMIT 1
                """

                cursor.execute(query, (asset_id,))
                row = cursor.fetchone()

                if row:
                    # Convert row to AssetPrice object
                    return self._row_to_asset_price(row)

                return None

        except Exception as e:
            logger.error(f"Error getting latest asset price for asset_id {asset_id}: {e}")
            return None

    def get_latest_asset_prices_bulk(self, asset_ids: List[int]) -> Dict[int, AssetPrice]:
        """Get the most recent price records for multiple assets."""
        if not self.db_manager or not asset_ids:
            return {}

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Use window function to get latest record per asset
                placeholders = ','.join('?' * len(asset_ids))
                query = f"""
                    WITH latest_prices AS (
                        SELECT *,
                               ROW_NUMBER() OVER (
                                   PARTITION BY asset_id
                                   ORDER BY provider_updated_at DESC, updated_at DESC
                               ) as rn
                        FROM asset_prices
                        WHERE asset_id IN ({placeholders})
                    )
                    SELECT * FROM latest_prices WHERE rn = 1
                """

                cursor.execute(query, asset_ids)
                rows = cursor.fetchall()

                result = {}
                for row in rows:
                    asset_price = self._row_to_asset_price(row)
                    if asset_price:
                        result[asset_price.asset_id] = asset_price

                return result

        except Exception as e:
            logger.error(f"Error getting latest asset prices for {len(asset_ids)} assets: {e}")
            return {}

    def get_asset_price_data(self, asset_id: int) -> Optional[AssetPrice]:
        """Retrieve price data for an asset, fetching fresh data from API if needed."""
        if not self.db_manager:
            return None

        # Use unified cache system
        def fetch_fresh_price():
            symbol = self._get_symbol_for_asset_id(asset_id)
            if not symbol:
                logger.warning(f"Could not find symbol for asset_id {asset_id}")
                return None
            logger.debug(f"Fetching fresh price data for asset_id {asset_id} ({symbol})")
            fresh_data = self._fetch_and_store_current_asset_price_data(symbol, asset_id)
            if fresh_data:
                return fresh_data
            else:
                # Fallback to existing data if API fetch fails
                logger.warning(f"Failed to fetch fresh data for {symbol}, falling back to cached data")
                return self._get_cached_asset_price_data(asset_id)

        return self.asset_prices_cache.get_or_fetch(str(asset_id), fetch_fresh_price)

    def get_asset_price_data_force_refresh(self, asset_id: int) -> Optional[AssetPrice]:
        """Force refresh asset price data, bypassing cache."""
        if not self.db_manager:
            return None

        # Invalidate cache for this asset and fetch fresh
        symbol = self._get_symbol_for_asset_id(asset_id)
        if not symbol:
            logger.warning(f"Could not find symbol for asset_id {asset_id}")
            return None

        logger.debug(f"Force refreshing price data for asset_id {asset_id} ({symbol})")
        return self._fetch_and_store_current_asset_price_data(symbol, asset_id)

    def is_price_data_fresh(self, asset_id: int, ttl_minutes: int = ASSET_PRICE_TTL_MINUTES) -> bool:
        """Check if price data for an asset is fresh (within TTL threshold)."""
        if not self.db_manager:
            return False

        # Use cache manager's freshness check
        return self.asset_prices_cache.is_fresh(asset_id)

    def get_most_recent_volume(self, symbol: str) -> Optional[int]:
        """Get the most recent volume data for a symbol using cascade logic.

        Tries in order:
        1. min_volume (most recent if available)
        2. day_volume (current trading day)
        3. prevday_volume (previous trading day)

        Args:
            symbol: Stock symbol to get volume for

        Returns:
            Volume as integer, or None if no volume data available
        """
        if not self.db_manager:
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Get most recent price record for the symbol with volume cascade
                cursor.execute("""
                    SELECT
                        min_volume,
                        day_volume,
                        prevday_volume,
                        updated_at
                    FROM asset_prices
                    WHERE symbol = ?
                    ORDER BY updated_at DESC
                    LIMIT 1
                """, (symbol.upper(),))

                result = cursor.fetchone()
                if not result:
                    return None

                min_vol, day_vol, prevday_vol, updated_at = result

                # Apply cascade logic: min_volume -> day_volume -> prevday_volume
                if min_vol is not None and min_vol > 0:
                    logger.debug(f"Using min_volume for {symbol}: {min_vol}")
                    return min_vol

                if day_vol is not None and day_vol > 0:
                    logger.debug(f"Using day_volume for {symbol}: {day_vol}")
                    return day_vol

                if prevday_vol is not None and prevday_vol > 0:
                    logger.debug(f"Using prevday_volume for {symbol}: {prevday_vol}")
                    return prevday_vol

                logger.debug(f"No volume data available for {symbol}")
                return None

        except Exception as e:
            logger.error(f"Error getting most recent volume for {symbol}: {e}")
            return None

    def save_asset_price_data(self, asset_price: AssetPrice) -> bool:
        """Save asset price data to database using INSERT OR REPLACE."""
        if not self.db_manager:
            logger.error("No database manager available")
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    INSERT OR REPLACE INTO asset_prices (
                        asset_id, symbol, provider_id, provider_updated_at, trade_date,
                        prevday_open, prevday_high, prevday_low, prevday_close, prevday_volume, prevday_vwap,
                        day_open, day_high, day_low, day_close, day_volume, day_vwap,
                        min_timestamp, min_open, min_high, min_low, min_close, min_volume,
                        min_vwap, min_accumulated_volume, min_num_trades, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """

                values = (
                    asset_price.asset_id,
                    asset_price.symbol,
                    asset_price.provider_id,
                    asset_price.provider_updated_at,
                    asset_price.trade_date.isoformat(),
                    # PrevDay data
                    float(asset_price.prevday_open) if asset_price.prevday_open else None,
                    float(asset_price.prevday_high) if asset_price.prevday_high else None,
                    float(asset_price.prevday_low) if asset_price.prevday_low else None,
                    float(asset_price.prevday_close) if asset_price.prevday_close else None,
                    asset_price.prevday_volume,
                    float(asset_price.prevday_vwap) if asset_price.prevday_vwap else None,
                    # Day data
                    float(asset_price.day_open) if asset_price.day_open else None,
                    float(asset_price.day_high) if asset_price.day_high else None,
                    float(asset_price.day_low) if asset_price.day_low else None,
                    float(asset_price.day_close) if asset_price.day_close else None,
                    asset_price.day_volume,
                    float(asset_price.day_vwap) if asset_price.day_vwap else None,
                    # Min data
                    asset_price.min_timestamp,
                    float(asset_price.min_open) if asset_price.min_open else None,
                    float(asset_price.min_high) if asset_price.min_high else None,
                    float(asset_price.min_low) if asset_price.min_low else None,
                    float(asset_price.min_close) if asset_price.min_close else None,
                    asset_price.min_volume,
                    float(asset_price.min_vwap) if asset_price.min_vwap else None,
                    asset_price.min_accumulated_volume,
                    asset_price.min_num_trades,
                    asset_price.updated_at.isoformat()
                )

                cursor.execute(query, values)
                conn.commit()

                logger.debug(f"Saved price data for {asset_price.symbol} (asset_id: {asset_price.asset_id})")
                return True

        except Exception as e:
            logger.error(f"Error saving price data for {asset_price.symbol}: {e}")
            return False

    # ============================================================================
    # PUBLIC ASSET FUNDAMENTALS METHODS - Database Operations
    # ============================================================================

    def upsert_fundamentals(self, fundamentals_list: List[AssetFundamentals]) -> Dict[str, int]:
        """Upsert fundamentals into database using model objects.

        Args:
            fundamentals_list: List of AssetFundamentals model objects to upsert

        Returns:
            Dictionary with statistics: {"inserted": int, "updated": int, "errors": int}
        """
        if not self.db_manager:
            logger.error("No database manager available")
            return {"inserted": 0, "updated": 0, "errors": 0}

        stats = {"inserted": 0, "updated": 0, "errors": 0}

        if not fundamentals_list:
            return stats

        logger.debug(f"Upserting {len(fundamentals_list)} fundamentals records...")

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                for fundamentals in fundamentals_list:
                    try:
                        # Check if record exists
                        cursor.execute(
                            "SELECT asset_id FROM asset_fundamentals WHERE asset_id = ?",
                            (fundamentals.asset_id,)
                        )
                        exists = cursor.fetchone()

                        # Convert model to dict for database operations
                        fundamentals_dict = fundamentals.to_dict()

                        if exists:
                            # Update existing record
                            update_fields = []
                            update_values = []
                            for key, value in fundamentals_dict.items():
                                if key != "asset_id":  # Don't update the primary key
                                    update_fields.append(f"{key} = ?")
                                    update_values.append(value)

                            if update_fields:
                                update_values.append(fundamentals.asset_id)
                                query = f"UPDATE asset_fundamentals SET {', '.join(update_fields)} WHERE asset_id = ?"
                                cursor.execute(query, update_values)
                                stats["updated"] += 1
                        else:
                            # Insert new record
                            fields = list(fundamentals_dict.keys())
                            placeholders = ", ".join(["?" for _ in fields])
                            values = list(fundamentals_dict.values())

                            query = f"INSERT INTO asset_fundamentals ({', '.join(fields)}) VALUES ({placeholders})"
                            cursor.execute(query, values)
                            stats["inserted"] += 1

                    except Exception as e:
                        logger.error(f"Error upserting fundamentals for asset_id {fundamentals.asset_id}: {e}")
                        stats["errors"] += 1

                conn.commit()

        except Exception as e:
            logger.error(f"Database error during fundamentals upsert: {e}")
            stats["errors"] += len(fundamentals_list)
            return stats

        logger.debug(f"Fundamentals upsert complete: {stats}")
        return stats

    def get_polygon_provider_id(self) -> Optional[int]:
        """Get Polygon provider ID from database.

        Returns:
            Provider ID for Polygon, or None if not found
        """
        if not self.db_manager:
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM providers WHERE name = 'polygon'")
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting polygon provider ID: {e}")
            return None

    def ensure_polygon_provider_exists(self) -> bool:
        """Check if Polygon provider exists in database.

        Returns:
            True if provider exists, False otherwise
        """
        return self.get_polygon_provider_id() is not None

    def get_active_universe_asset_symbols(self) -> List[Dict[str, Any]]:
        """Get asset symbols and IDs from the active universe.

        Returns:
            List of dictionaries with id, symbol, universe_name keys
        """
        if not self.db_manager:
            return []

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Get assets from the active universe only
                cursor.execute("""
                    SELECT a.id, a.symbol, u.name as universe_name
                    FROM assets a
                    JOIN universe_memberships um ON a.id = um.asset_id
                    JOIN universes u ON um.universe_id = u.id
                    WHERE um.is_active = 1
                    AND u.is_active = 1
                    ORDER BY a.symbol
                """)

                results = cursor.fetchall()
                return [
                    {
                        "id": row[0],
                        "symbol": row[1],
                        "universe_name": row[2]
                    }
                    for row in results
                ]

        except Exception as e:
            logger.error(f"Error getting active universe asset symbols: {e}")
            return []

    # ============================================================================
    # PUBLIC DATA TRANSFORMATION METHODS
    # ============================================================================

    def transform_ticker_snapshot_to_asset_price(self, symbol: str, asset_id: int, ticker_snapshot: TickerSnapshot) -> Optional[AssetPrice]:
        """Transform TickerSnapshot model to AssetPrice model."""
        try:
            # Get provider ID
            provider_id = 1  # Default fallback
            if self.db_manager:
                try:
                    with self.db_manager.get_connection() as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT id FROM providers WHERE name = 'polygon'")
                        result = cursor.fetchone()
                        if result:
                            provider_id = result[0]
                except Exception as e:
                    logger.warning(f"Could not lookup polygon provider ID: {e}")

            # Use Polygon's updated timestamp or default to 0
            provider_updated_at = ticker_snapshot.updated_ns or 0

            # Determine trade date
            if provider_updated_at and provider_updated_at != 0:
                updated_seconds = provider_updated_at // 1_000_000_000
                trade_date = datetime.fromtimestamp(updated_seconds).date()
            elif ticker_snapshot.min_bar and ticker_snapshot.min_bar.timestamp:
                # Use min bar timestamp if available
                trade_date = datetime.fromtimestamp(ticker_snapshot.min_bar.timestamp / 1000).date()
            else:
                trade_date = datetime.now().date()

            return AssetPrice(
                id=0,  # Will be set by database auto-increment
                asset_id=asset_id,
                symbol=symbol,
                provider_id=provider_id,
                provider_updated_at=provider_updated_at,
                trade_date=trade_date,
                updated_at=datetime.now(),

                # Previous day data (always available)
                prevday_open=ticker_snapshot.prev_close,  # Using prev_close as we don't have separate prev_open
                prevday_high=ticker_snapshot.prev_close,  # Same limitation
                prevday_low=ticker_snapshot.prev_close,   # Same limitation
                prevday_close=ticker_snapshot.prev_close,
                prevday_volume=ticker_snapshot.prev_volume,
                prevday_vwap=None,  # Not available in TickerSnapshot

                # Current day data (store if present)
                day_open=ticker_snapshot.open_price,
                day_high=ticker_snapshot.high_price,
                day_low=ticker_snapshot.low_price,
                day_close=ticker_snapshot.close_price,
                day_volume=ticker_snapshot.volume,
                day_vwap=ticker_snapshot.vwap,

                # Min data - from min_bar if available (includes afterhours)
                min_timestamp=ticker_snapshot.min_bar.timestamp if ticker_snapshot.min_bar else None,
                min_open=ticker_snapshot.min_bar.open if ticker_snapshot.min_bar else None,
                min_high=ticker_snapshot.min_bar.high if ticker_snapshot.min_bar else None,
                min_low=ticker_snapshot.min_bar.low if ticker_snapshot.min_bar else None,
                min_close=ticker_snapshot.min_bar.close if ticker_snapshot.min_bar else None,
                min_volume=ticker_snapshot.min_bar.volume if ticker_snapshot.min_bar else None,
                min_vwap=ticker_snapshot.min_bar.vwap if ticker_snapshot.min_bar else None,
                min_accumulated_volume=ticker_snapshot.min_bar.accumulated_volume if ticker_snapshot.min_bar else None,
                min_num_trades=ticker_snapshot.min_bar.num_trades if ticker_snapshot.min_bar else None
            )

        except Exception as e:
            logger.error(f"Error transforming TickerSnapshot for {symbol}: {e}")
            return None


    # ============================================================================
    # PUBLIC UNIVERSE MANAGEMENT METHODS
    # ============================================================================

    def get_all_universes(self) -> List[Universe]:
        """Get all universes from the database."""
        if not self.db_manager:
            return []

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, description, is_active, min_market_cap, min_volume,
                       max_assets, last_updated, created_at, updated_at
                FROM universes
                ORDER BY name
            """)
            return [Universe.from_db_row(row) for row in cursor.fetchall()]

    def get_active_universe(self) -> Optional[Universe]:
        """Get the currently active universe."""
        if not self.db_manager:
            return None

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, name, description, is_active, min_market_cap, min_volume,
                       max_assets, last_updated, created_at, updated_at
                FROM universes
                WHERE is_active = 1
                LIMIT 1
            """)
            row = cursor.fetchone()
            return Universe.from_db_row(row) if row else None

    def set_active_universe(self, universe_name: str) -> bool:
        """Set the active universe by name."""
        if not self.db_manager:
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Deactivate all universes
                cursor.execute("UPDATE universes SET is_active = 0")

                # Activate the specified universe
                cursor.execute(
                    "UPDATE universes SET is_active = 1 WHERE name = ?",
                    (universe_name,)
                )

                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Error setting active universe: {e}")
            return False

    def get_universe_stats(self, universe_name: str) -> Optional[UniverseStats]:
        """Get statistics for a universe."""
        if not self.db_manager:
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Get universe ID
                cursor.execute("SELECT id FROM universes WHERE name = ?", (universe_name,))
                universe_result = cursor.fetchone()
                if not universe_result:
                    return None

                universe_id = universe_result[0]

                # Total members
                cursor.execute("""
                    SELECT COUNT(*) FROM universe_memberships
                    WHERE universe_id = ? AND is_active = 1
                """, (universe_id,))
                total_members = cursor.fetchone()[0]

                # Active vs inactive assets
                cursor.execute("""
                    SELECT a.is_active, COUNT(*)
                    FROM universe_memberships um
                    JOIN assets a ON um.asset_id = a.id
                    WHERE um.universe_id = ? AND um.is_active = 1
                    GROUP BY a.is_active
                """, (universe_id,))
                active_stats = dict(cursor.fetchall())

                # By asset type
                cursor.execute("""
                    SELECT a.asset_type, COUNT(*)
                    FROM universe_memberships um
                    JOIN assets a ON um.asset_id = a.id
                    WHERE um.universe_id = ? AND um.is_active = 1
                    GROUP BY a.asset_type
                """, (universe_id,))
                by_type = dict(cursor.fetchall())

                # By market
                cursor.execute("""
                    SELECT m.name, COUNT(*)
                    FROM universe_memberships um
                    JOIN assets a ON um.asset_id = a.id
                    JOIN markets m ON a.market_id = m.id
                    WHERE um.universe_id = ? AND um.is_active = 1
                    GROUP BY m.name
                """, (universe_id,))
                by_market = dict(cursor.fetchall())

                # Last updated
                cursor.execute("""
                    SELECT last_updated FROM universes WHERE id = ?
                """, (universe_id,))
                last_updated = cursor.fetchone()[0]

                return UniverseStats(
                    universe_name=universe_name,
                    total_members=total_members,
                    active_members=active_stats.get(1, 0),
                    inactive_members=active_stats.get(0, 0),
                    by_asset_type=by_type,
                    by_market=by_market,
                    last_updated=last_updated
                )

        except Exception as e:
            logger.error(f"Error getting universe stats: {e}")
            return None

    def get_universe_symbols(self, universe_name: str = "default_universe") -> List[str]:
        """Get all symbols in a universe."""
        if not self.db_manager:
            return []

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT a.symbol
                    FROM universe_memberships um
                    JOIN assets a ON um.asset_id = a.id
                    JOIN universes u ON um.universe_id = u.id
                    WHERE u.name = ? AND um.is_active = 1 AND a.is_active = 1
                    ORDER BY a.symbol
                """, (universe_name,))
                return [row[0] for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error getting universe symbols: {e}")
            return []

    def get_universe_market_breakdown(self, universe_name: str = "default_universe") -> List[Tuple[str, str, int]]:
        """Get market breakdown for a universe.

        Returns:
            List of tuples (market_code, market_name, asset_count)
        """
        if not self.db_manager:
            return []

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT m.code, m.name, COUNT(a.id) as asset_count
                    FROM markets m
                    JOIN assets a ON m.id = a.market_id
                    JOIN universe_memberships um ON a.id = um.asset_id
                    JOIN universes u ON um.universe_id = u.id
                    WHERE u.name = ?
                    GROUP BY m.id
                    ORDER BY asset_count DESC
                """, (universe_name,))
                return cursor.fetchall()

        except Exception as e:
            logger.error(f"Error getting universe market breakdown: {e}")
            return []

    def create_universe(self, name: str, description: Optional[str] = None,
                      min_market_cap: Optional[int] = None, min_volume: Optional[int] = None,
                      max_assets: Optional[int] = None) -> bool:
        """Create a new universe.

        Args:
            name: Universe name
            description: Optional description
            min_market_cap: Optional minimum market cap filter
            min_volume: Optional minimum volume filter
            max_assets: Optional maximum asset count

        Returns:
            True if created successfully, False otherwise
        """
        if not self.db_manager:
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Check if exists
                cursor.execute("SELECT id FROM universes WHERE name = ?", (name,))
                if cursor.fetchone():
                    return False  # Already exists

                # Create universe
                cursor.execute("""
                    INSERT INTO universes (name, description, min_market_cap, min_volume, max_assets, is_active)
                    VALUES (?, ?, ?, ?, ?, 1)
                """, (name, description, min_market_cap, min_volume, max_assets))

                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Error creating universe {name}: {e}")
            return False

    def delete_universe(self, name: str) -> Tuple[bool, int]:
        """Delete a universe and all its memberships.

        Args:
            name: Universe name to delete

        Returns:
            Tuple of (success, member_count_deleted)
        """
        if not self.db_manager:
            return False, 0

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Check if exists and get info
                cursor.execute("""
                    SELECT u.id, COUNT(um.asset_id)
                    FROM universes u
                    LEFT JOIN universe_memberships um ON u.id = um.universe_id
                    WHERE u.name = ?
                    GROUP BY u.id
                """, (name,))

                result = cursor.fetchone()
                if not result:
                    return False, 0  # Not found

                uid, member_count = result

                # Delete memberships first
                cursor.execute("DELETE FROM universe_memberships WHERE universe_id = ?", (uid,))

                # Delete universe
                cursor.execute("DELETE FROM universes WHERE id = ?", (uid,))

                conn.commit()
                return True, member_count

        except Exception as e:
            logger.error(f"Error deleting universe {name}: {e}")
            return False, 0

    # ============================================================================
    # PUBLIC MARKET SNAPSHOT METADATA METHODS
    # ============================================================================

    def get_market_snapshot_metadata(self) -> Optional[Dict[str, Any]]:
        """Get the latest market snapshot run metadata."""
        if not self.update_tracker:
            return None

        try:
            # Get the latest snapshot operation from DataUpdateTracker
            history = self.update_tracker.get_operation_history("snapshot", limit=1)
            if not history:
                return None

            operation = history[0]
            stats = operation.get('stats', {})

            return {
                "started_at": operation['started_at'],
                "completed_at": operation['completed_at'],
                "total_symbols": operation.get('total_items', 0),
                "successful_updates": stats.get('inserted', 0) + stats.get('updated', 0),
                "failed_updates": stats.get('errors', 0),
                "status": operation['status'],
                "error_message": None,  # Not stored in new system
                "api_calls_made": operation.get('api_calls_made', 0)
            }

        except Exception as e:
            logger.error(f"Error getting market snapshot metadata: {e}")
            return None

    def check_running_snapshot(self) -> Optional[datetime]:
        """Check if a market snapshot is currently running."""
        if not self.update_tracker:
            return None

        try:
            # Check for running snapshot operations
            running_ops = self.update_tracker.get_current_running_operations()
            snapshot_ops = [op for op in running_ops if op['operation_type'] == 'snapshot']

            if snapshot_ops:
                # Return the start time of the most recent running snapshot
                latest_op = max(snapshot_ops, key=lambda x: x['started_at'])
                return datetime.fromisoformat(latest_op['started_at'])

            return None

        except Exception as e:
            logger.error(f"Error checking running snapshot: {e}")
            return None

    def start_market_snapshot_run(self, total_symbols: int) -> Optional[int]:
        """Start a new market snapshot run and return operation ID for tracking."""
        if not self.update_tracker:
            return None

        try:
            operation_id = self.update_tracker.start_operation(
                operation_type="snapshot",
                operation_subtype="market_update",
                operation_params={"universe_symbols": total_symbols},
                total_items=total_symbols
            )
            return operation_id

        except Exception as e:
            logger.error(f"Error starting market snapshot run: {e}")
            return None

    def complete_market_snapshot_run(self, operation_id: int, successful: int, failed: int, api_calls: int = 1, error: str = None) -> bool:
        """Complete the market snapshot run with statistics."""
        if not self.update_tracker:
            return False

        try:
            stats = {
                "inserted": 0,  # New price records
                "updated": successful,  # Updated price records
                "errors": failed
            }

            if error:
                self.update_tracker.fail_operation(operation_id, error)
            else:
                status = 'completed' if failed == 0 else 'partial'
                self.update_tracker.complete_operation(operation_id, stats, status)

            return True

        except Exception as e:
            logger.error(f"Error completing market snapshot run: {e}")
            return False

    def get_all_assets_with_fundamentals(self) -> List[Dict[str, Any]]:
        """Fetch all assets with fundamentals data for universe creation.

        Returns:
            List of asset dictionaries with fundamentals and volume data
        """
        if not self.db_manager:
            return []

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Join with fundamentals table for sector, market cap data
                cursor.execute("""
                    SELECT a.id, a.symbol, a.name, a.asset_type, a.asset_class,
                           a.currency, a.is_active, a.provider_id,
                           m.code as market_code, m.name as market_name,
                           af.sector, af.market_cap
                    FROM assets a
                    JOIN markets m ON a.market_id = m.id
                    LEFT JOIN asset_fundamentals af ON a.id = af.asset_id
                """)

                rows = cursor.fetchall()
                assets = []

                for row in rows:
                    symbol = row[1]
                    # Get volume using existing method
                    volume = self.get_most_recent_volume(symbol)

                    assets.append({
                        'id': row[0],
                        'symbol': symbol,
                        'name': row[2],
                        'asset_type': row[3],
                        'asset_class': row[4],
                        'currency': row[5],
                        'is_active': bool(row[6]),
                        'provider_id': row[7],
                        'market_code': row[8],
                        'market_name': row[9],
                        'sector': row[10],
                        'market_cap': row[11],
                        'volume': volume
                    })

                return assets

        except Exception as e:
            logger.error(f"Error getting all assets with fundamentals: {e}")
            return []

    def get_or_create_universe(self, universe_name: str, config: Dict[str, Any]) -> Optional[int]:
        """Get existing universe ID or create new one.

        Args:
            universe_name: Name of the universe
            config: Universe configuration dictionary

        Returns:
            Universe ID, or None if error
        """
        if not self.db_manager:
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Check if universe exists
                cursor.execute("SELECT id FROM universes WHERE name = ?", (universe_name,))
                result = cursor.fetchone()

                if result:
                    universe_id = result[0]
                    # Update last_updated
                    cursor.execute("""
                        UPDATE universes SET
                            last_updated = ?,
                            description = ?,
                            updated_at = ?
                        WHERE id = ?
                    """, (
                        datetime.now().isoformat(),
                        config.get('description', 'Automated universe'),
                        datetime.now().isoformat(),
                        universe_id
                    ))
                else:
                    # Create new universe
                    cursor.execute("""
                        INSERT INTO universes (name, description, is_active, last_updated, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        universe_name,
                        config.get('description', 'Automated universe'),
                        True,
                        datetime.now().isoformat(),
                        datetime.now().isoformat(),
                        datetime.now().isoformat()
                    ))
                    universe_id = cursor.lastrowid

                conn.commit()
                return universe_id

        except Exception as e:
            logger.error(f"Error getting or creating universe {universe_name}: {e}")
            return None

    def clear_universe_memberships(self, universe_id: int) -> bool:
        """Clear existing memberships for a universe.

        Args:
            universe_id: ID of the universe to clear

        Returns:
            True if successful, False otherwise
        """
        if not self.db_manager:
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM universe_memberships WHERE universe_id = ?", (universe_id,))
                conn.commit()
                logger.debug(f"Cleared existing memberships for universe_id {universe_id}")
                return True

        except Exception as e:
            logger.error(f"Error clearing universe memberships for {universe_id}: {e}")
            return False

    def add_universe_memberships(self, universe_id: int, assets: List[Dict[str, Any]]) -> int:
        """Add assets to universe membership.

        Args:
            universe_id: ID of the universe
            assets: List of asset dictionaries with 'id' key

        Returns:
            Number of memberships added
        """
        if not self.db_manager or not assets:
            return 0

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                membership_data = [
                    (universe_id, asset['id'], datetime.now().date().isoformat(),
                     f"Added based on {len(assets)} asset criteria", True)
                    for asset in assets
                ]

                cursor.executemany("""
                    INSERT INTO universe_memberships (universe_id, asset_id, added_date, reason, is_active)
                    VALUES (?, ?, ?, ?, ?)
                """, membership_data)

                conn.commit()
                count = len(membership_data)
                logger.debug(f"Added {count} memberships to universe {universe_id}")
                return count

        except Exception as e:
            logger.error(f"Error adding universe memberships: {e}")
            return 0

    # ============================================================================
    # PUBLIC CACHE MANAGEMENT METHODS
    # ============================================================================

    def get_fundamentals_cache_stats(self) -> Dict[str, Any]:
        """Get fundamentals cache statistics.

        Returns:
            Dict with cache stats including hits, misses, size, etc.
        """
        return self.fundamentals_cache.get_cache_stats()

    def clear_fundamentals_cache(self):
        """Clear all fundamentals cache data."""
        self.fundamentals_cache.clear_cache()
        logger.info("Cleared fundamentals cache")

    def cleanup_expired_fundamentals_cache(self) -> int:
        """Clean up expired fundamentals cache entries.

        Returns:
            Number of expired entries removed
        """
        return self.fundamentals_cache.cleanup_expired()

    def invalidate_fundamentals_cache(self, symbol: str):
        """Invalidate fundamentals cache for specific symbol.

        Args:
            symbol: Stock symbol to invalidate
        """
        self.fundamentals_cache.invalidate_cache(symbol)


    # ============================================================================
    # PUBLIC UTILITY METHODS
    # ============================================================================

    def execute_screener_query(self, query: str) -> List[Dict[str, Any]]:
        """Execute a screener SQL query and return results as dictionaries.

        Args:
            query: SQL query to execute

        Returns:
            List of dictionaries representing query results
        """
        if not self.db_manager:
            logger.error("No database manager available")
            return []

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query)

                # Get column names
                columns = [description[0] for description in cursor.description]

                # Fetch results
                rows = cursor.fetchall()

                # Convert to list of dictionaries
                results = []
                for row in rows:
                    result = dict(zip(columns, row))
                    results.append(result)

                return results

        except Exception as e:
            logger.error(f"Error executing screener query: {e}")
            return []

    def execute_metadata_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """Execute a metadata query (for DataUpdateTracker) and return results as dictionaries.

        Args:
            query: SQL query to execute
            params: Optional query parameters

        Returns:
            List of dictionaries representing query results
        """
        if not self.db_manager:
            logger.error("No database manager available")
            return []

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)

                # Get column names
                columns = [description[0] for description in cursor.description]

                # Fetch results
                rows = cursor.fetchall()

                # Convert to list of dictionaries
                results = []
                for row in rows:
                    result = dict(zip(columns, row))
                    results.append(result)

                return results

        except Exception as e:
            logger.error(f"Error executing metadata query: {e}")
            return []

    def execute_metadata_update(self, query: str, params: tuple = None) -> int:
        """Execute a metadata update/insert query and return the last row ID or affected rows.

        Args:
            query: SQL query to execute
            params: Optional query parameters

        Returns:
            Last row ID for INSERT queries, or number of affected rows for UPDATE queries
        """
        if not self.db_manager:
            logger.error("No database manager available")
            return 0

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)

                conn.commit()

                # Return lastrowid for INSERT, rowcount for UPDATE/DELETE
                return cursor.lastrowid or cursor.rowcount

        except Exception as e:
            logger.error(f"Error executing metadata update: {e}")
            return 0

    def get_database_stats(self) -> Optional[DatabaseStats]:
        """Get database statistics and health information."""
        if not self.db_manager:
            return None

        try:
            table_counts = {}
            tables = [
                "asset_fundamentals", "asset_prices", "assets", "data_update_metadata",
                "markets", "providers", "schema_versions", "sentiment_events",
                "sentiment_types", "universe_memberships", "universes"
            ]

            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Get schema version
                cursor.execute("SELECT version FROM schema_versions ORDER BY id DESC LIMIT 1")
                schema_result = cursor.fetchone()
                schema_version = schema_result[0] if schema_result else "unknown"

                # Count records in each table
                for table in tables:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        table_counts[table] = cursor.fetchone()[0]
                    except Exception as e:
                        table_counts[table] = f"Error: {e}"

                total_records = sum(count for count in table_counts.values() if isinstance(count, int))

                return DatabaseStats(
                    database_path=str(self.db_manager.db_path),
                    schema_version=schema_version,
                    status="healthy",
                    table_counts=table_counts,
                    total_records=total_records,
                    last_updated=datetime.now()
                )

        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return DatabaseStats(
                database_path=str(self.db_manager.db_path) if self.db_manager else "unknown",
                schema_version="unknown",
                status="error",
                table_counts={},
                total_records=0,
                error_message=str(e)
            )

    # ============================================================================
    # PRIVATE HELPER METHODS
    # ============================================================================

    def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Make authenticated request to Polygon API."""
        params["apikey"] = self.api_key
        url = f"{self.base_url}{endpoint}"

        response = requests.get(url, params=params)

        if response.status_code == 429:
            logger.warning("Rate limit hit, waiting 60 seconds...")
            time.sleep(60)
            response = requests.get(url, params=params)

        if response.status_code != 200:
            raise Exception(f"API error: {response.status_code} - {response.text}")

        return response.json()

    def _row_to_asset_price(self, row) -> Optional[AssetPrice]:
        """Convert database row to AssetPrice object."""
        try:
            return AssetPrice(
                id=row[0],
                asset_id=row[1],
                symbol=row[2],
                provider_id=row[3],
                provider_updated_at=row[4],
                trade_date=datetime.strptime(row[5], '%Y-%m-%d').date() if row[5] else None,
                prevday_open=Decimal(str(row[6])) if row[6] is not None else None,
                prevday_high=Decimal(str(row[7])) if row[7] is not None else None,
                prevday_low=Decimal(str(row[8])) if row[8] is not None else None,
                prevday_close=Decimal(str(row[9])) if row[9] is not None else None,
                prevday_volume=row[10],
                prevday_vwap=Decimal(str(row[11])) if row[11] is not None else None,
                day_open=Decimal(str(row[12])) if row[12] is not None else None,
                day_high=Decimal(str(row[13])) if row[13] is not None else None,
                day_low=Decimal(str(row[14])) if row[14] is not None else None,
                day_close=Decimal(str(row[15])) if row[15] is not None else None,
                day_volume=row[16],
                day_vwap=Decimal(str(row[17])) if row[17] is not None else None,
                min_timestamp=row[18],
                min_open=Decimal(str(row[19])) if row[19] is not None else None,
                min_high=Decimal(str(row[20])) if row[20] is not None else None,
                min_low=Decimal(str(row[21])) if row[21] is not None else None,
                min_close=Decimal(str(row[22])) if row[22] is not None else None,
                min_volume=row[23],
                min_vwap=Decimal(str(row[24])) if row[24] is not None else None,
                min_accumulated_volume=row[25],
                min_num_trades=row[26],
                updated_at=datetime.fromisoformat(row[27]) if row[27] else None
            )
        except Exception as e:
            logger.error(f"Error converting row to AssetPrice: {e}")
            return None

    def _get_symbol_for_asset_id(self, asset_id: int) -> Optional[str]:
        """Get symbol for an asset_id."""
        if not self.db_manager:
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT symbol FROM assets WHERE id = ?", (asset_id,))
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting symbol for asset_id {asset_id}: {e}")
            return None

    def _get_cached_asset_price_data(self, asset_id: int) -> Optional[AssetPrice]:
        """Retrieve cached price data from database without freshness check."""
        if not self.db_manager:
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT
                        id, asset_id, symbol, provider_id, provider_updated_at, trade_date,
                        prevday_open, prevday_high, prevday_low, prevday_close, prevday_volume, prevday_vwap,
                        day_open, day_high, day_low, day_close, day_volume, day_vwap,
                        min_timestamp, min_open, min_high, min_low, min_close, min_volume,
                        min_vwap, min_accumulated_volume, min_num_trades, updated_at
                    FROM asset_prices
                    WHERE asset_id = ?
                    ORDER BY updated_at DESC
                    LIMIT 1
                """

                cursor.execute(query, (asset_id,))
                result = cursor.fetchone()

                if not result:
                    return None

                return AssetPrice(
                    id=result[0],
                    asset_id=result[1],
                    symbol=result[2],
                    provider_id=result[3],
                    provider_updated_at=result[4],
                    trade_date=datetime.fromisoformat(result[5]).date() if result[5] else None,
                    updated_at=datetime.fromisoformat(result[27]),
                    # PrevDay fields
                    prevday_open=result[6],
                    prevday_high=result[7],
                    prevday_low=result[8],
                    prevday_close=result[9],
                    prevday_volume=result[10],
                    prevday_vwap=result[11],
                    # Day fields
                    day_open=result[12],
                    day_high=result[13],
                    day_low=result[14],
                    day_close=result[15],
                    day_volume=result[16],
                    day_vwap=result[17],
                    # Min fields
                    min_timestamp=result[18],
                    min_open=result[19],
                    min_high=result[20],
                    min_low=result[21],
                    min_close=result[22],
                    min_volume=result[23],
                    min_vwap=result[24],
                    min_accumulated_volume=result[25],
                    min_num_trades=result[26]
                )

        except Exception as e:
            logger.error(f"Error retrieving cached price data for asset_id {asset_id}: {e}")
            return None

    def _fetch_and_store_current_asset_price_data(self, symbol: str, asset_id: int) -> Optional[AssetPrice]:
        """Fetch current price data from API and store in database."""
        try:
            logger.info(f"Fetching fresh price data for {symbol}")

            # Get snapshot data from API (returns TickerSnapshot model)
            ticker_snapshot = self.get_single_ticker_snapshot(symbol)
            if not ticker_snapshot:
                logger.error(f"Failed to get snapshot data for {symbol}")
                return None

            # Transform to AssetPrice model
            asset_price = self.transform_ticker_snapshot_to_asset_price(symbol, asset_id, ticker_snapshot)
            if not asset_price:
                logger.error(f"Failed to transform snapshot data for {symbol}")
                return None

            # Save to database
            if not self.save_asset_price_data(asset_price):
                logger.error(f"Failed to save price data for {symbol}")
                return None

            logger.info(f"Successfully fetched and stored fresh price data for {symbol}")
            return asset_price

        except Exception as e:
            logger.error(f"Error fetching and storing price data for {symbol}: {e}")
            return None