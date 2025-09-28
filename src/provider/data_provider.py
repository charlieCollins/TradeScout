"""Polygon API data provider for TradeScout."""

import requests
import time
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
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

logger = logging.getLogger(__name__)


class PolygonDataProvider:
    """Encapsulates all Polygon API interactions and database queries."""

    def __init__(self, db_manager=None):
        """Initialize with database manager, loads API key automatically."""
        from config.api_keys import POLYGON_API_KEY
        self.api_key = POLYGON_API_KEY
        if not self.api_key:
            raise ValueError("Polygon API key is required")

        self.base_url = "https://api.polygon.io"
        self.db_manager = db_manager
        self.update_tracker = DataUpdateTracker(db_manager) if db_manager else None
        self.fundamentals_cache = FundamentalsCacheManager()

    # ============================================================================
    # PUBLIC API METHODS
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

    def get_market_snapshot(self, symbols: List[str], progress_callback=None) -> Optional[MarketSnapshot]:
        """Get market snapshot for specified symbols using chunking."""
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
        """Get snapshot for a single ticker."""
        raw_data = self._make_request(f"/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}", {})
        if not raw_data or "ticker" not in raw_data:
            return None

        # Create a single-ticker MarketSnapshot and extract the ticker
        polygon_response = {"results": [raw_data["ticker"]], "status": "OK"}
        market_snapshot = MarketSnapshot.from_polygon_data(polygon_response)

        # Return the single ticker snapshot
        return market_snapshot.tickers.get(symbol) if market_snapshot else None

    def get_market_status(self) -> Dict[str, Any]:
        """Get current market status.

        Returns:
            Raw API response dict containing market status data.
        """
        return self._make_request("/v1/marketstatus/now", {})

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

    # ============================================================================
    # PUBLIC ASSET DATA METHODS
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

    # ============================================================================
    # PUBLIC ASSET PRICE DATA METHODS
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

        # Check if existing data is fresh
        if self.is_price_data_fresh(asset_id):
            logger.debug(f"Using cached price data for asset_id {asset_id} (fresh within TTL)")
            return self._get_cached_asset_price_data(asset_id)

        # Data is stale or missing, need to get symbol first then fetch fresh data
        symbol = self._get_symbol_for_asset_id(asset_id)
        if not symbol:
            logger.warning(f"Could not find symbol for asset_id {asset_id}, returning cached data if available")
            return self._get_cached_asset_price_data(asset_id)

        # Fetch fresh data
        logger.debug(f"Price data for asset_id {asset_id} ({symbol}) is stale or missing, fetching fresh data")
        fresh_data = self._fetch_and_store_current_asset_price_data(symbol, asset_id)

        if fresh_data:
            return fresh_data
        else:
            # Fallback to existing data if API fetch fails
            logger.warning(f"Failed to fetch fresh data for {symbol}, falling back to cached data")
            return self._get_cached_asset_price_data(asset_id)

    def is_price_data_fresh(self, asset_id: int, ttl_minutes: int = ASSET_PRICE_TTL_MINUTES) -> bool:
        """Check if price data for an asset is fresh (within TTL threshold)."""
        if not self.db_manager:
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT updated_at
                    FROM asset_prices
                    WHERE asset_id = ?
                    ORDER BY updated_at DESC
                    LIMIT 1
                """

                cursor.execute(query, (asset_id,))
                result = cursor.fetchone()

                if not result:
                    return False

                last_updated = datetime.fromisoformat(result[0])
                threshold = datetime.now() - timedelta(minutes=ttl_minutes)

                return last_updated > threshold

        except Exception as e:
            logger.error(f"Error checking price data freshness for asset_id {asset_id}: {e}")
            return False

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

            # Determine if we have recent trading activity
            has_recent_trading = ticker_snapshot.last_timestamp is not None

            # Set trade date
            if has_recent_trading:
                trade_date = ticker_snapshot.last_timestamp.date()
            else:
                trade_date = datetime.now().date()

            # Convert timestamps - if we have last_timestamp, convert to nanoseconds for provider_updated_at
            if ticker_snapshot.last_timestamp:
                provider_updated_at = int(ticker_snapshot.last_timestamp.timestamp() * 1_000_000_000)
            else:
                provider_updated_at = 0

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

                # Current day data (only if has_recent_trading)
                day_open=ticker_snapshot.open_price if has_recent_trading else None,
                day_high=ticker_snapshot.high_price if has_recent_trading else None,
                day_low=ticker_snapshot.low_price if has_recent_trading else None,
                day_close=ticker_snapshot.close_price if has_recent_trading else None,
                day_volume=ticker_snapshot.volume if has_recent_trading else None,
                day_vwap=ticker_snapshot.vwap if has_recent_trading else None,

                # Min data - we'll use last price info for this
                min_timestamp=int(ticker_snapshot.last_timestamp.timestamp() * 1_000_000_000) if ticker_snapshot.last_timestamp else None,
                min_open=ticker_snapshot.last_price if has_recent_trading else None,
                min_high=ticker_snapshot.last_price if has_recent_trading else None,
                min_low=ticker_snapshot.last_price if has_recent_trading else None,
                min_close=ticker_snapshot.last_price if has_recent_trading else None,
                min_volume=None,  # Not available at minute level
                min_vwap=None,    # Not available at minute level
                min_accumulated_volume=ticker_snapshot.volume if has_recent_trading else None,
                min_num_trades=None  # Not available
            )

        except Exception as e:
            logger.error(f"Error transforming TickerSnapshot for {symbol}: {e}")
            return None

    def transform_snapshot_to_asset_price(self, symbol: str, asset_id: int, snapshot_data: Dict[str, Any]) -> Optional[AssetPrice]:
        """Transform snapshot API response to AssetPrice model."""
        try:
            ticker_data = snapshot_data.get("ticker", {})
            if not ticker_data:
                logger.warning(f"No ticker data in snapshot response for {symbol}")
                return None

            # Extract data sections
            day_data = ticker_data.get("day", {})
            prevday_data = ticker_data.get("prevDay", {})
            min_data = ticker_data.get("min", {})
            updated_ns = ticker_data.get("updated")

            # Handle both updated and non-updated symbols
            has_recent_trading = updated_ns and updated_ns != 0

            # Always use the actual provider timestamp (could be 0 or None)
            provider_updated_at = updated_ns or 0

            if has_recent_trading:
                # Convert provider timestamp (nanoseconds) to trade date
                updated_seconds = updated_ns // 1_000_000_000
                trade_date = datetime.fromtimestamp(updated_seconds).date()
            else:
                # No recent trading - use current date for our database record
                trade_date = datetime.now().date()

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

            # Get polygon provider ID from database
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

            return AssetPrice(
                id=0,  # Will be set by database auto-increment
                asset_id=asset_id,
                symbol=symbol,
                provider_id=provider_id,
                provider_updated_at=provider_updated_at,
                trade_date=trade_date,
                updated_at=datetime.now(),

                # PrevDay data (always available)
                prevday_open=to_decimal(prevday_data.get("o")),
                prevday_high=to_decimal(prevday_data.get("h")),
                prevday_low=to_decimal(prevday_data.get("l")),
                prevday_close=to_decimal(prevday_data.get("c")),
                prevday_volume=to_int(prevday_data.get("v")),
                prevday_vwap=to_decimal(prevday_data.get("vw")),

                # Day data (only meaningful if has_recent_trading)
                day_open=to_decimal(day_data.get("o")) if has_recent_trading else None,
                day_high=to_decimal(day_data.get("h")) if has_recent_trading else None,
                day_low=to_decimal(day_data.get("l")) if has_recent_trading else None,
                day_close=to_decimal(day_data.get("c")) if has_recent_trading else None,
                day_volume=to_int(day_data.get("v")) if has_recent_trading else None,
                day_vwap=to_decimal(day_data.get("vw")) if has_recent_trading else None,

                # Min data (only meaningful if has_recent_trading)
                min_timestamp=to_int(min_data.get("t")) if has_recent_trading else None,
                min_open=to_decimal(min_data.get("o")) if has_recent_trading else None,
                min_high=to_decimal(min_data.get("h")) if has_recent_trading else None,
                min_low=to_decimal(min_data.get("l")) if has_recent_trading else None,
                min_close=to_decimal(min_data.get("c")) if has_recent_trading else None,
                min_volume=to_int(min_data.get("v")) if has_recent_trading else None,
                min_vwap=to_decimal(min_data.get("vw")) if has_recent_trading else None,
                min_accumulated_volume=to_int(min_data.get("av")) if has_recent_trading else None,
                min_num_trades=to_int(min_data.get("n")) if has_recent_trading else None
            )

        except Exception as e:
            logger.error(f"Error transforming snapshot data for {symbol}: {e}")
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
    # PRIVATE METHODS
    # ============================================================================

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

            # Get snapshot data from API
            snapshot_response = self.get_single_ticker_snapshot(symbol)
            if not snapshot_response:
                logger.error(f"Failed to get snapshot data for {symbol}")
                return None

            # Transform to AssetPrice model
            asset_price = self.transform_snapshot_to_asset_price(symbol, asset_id, snapshot_response)
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
    # CACHE MANAGEMENT METHODS
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