"""Polygon API data provider for TradeScout."""

import requests
import time
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from decimal import Decimal
from models.asset import Asset, AssetType, AssetClass
from models.market import Market
from models.price import AssetPrice
from config.ttl_config import ASSET_PRICE_TTL_MINUTES

logger = logging.getLogger(__name__)


class PolygonDataProvider:
    """Encapsulates all Polygon API interactions and database queries."""

    def __init__(self, api_key: str, db_manager=None):
        """Initialize with API key and optional database manager."""
        self.api_key = api_key
        if not self.api_key:
            raise ValueError("API key is required")

        self.base_url = "https://api.polygon.io"
        self.db_manager = db_manager

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

    def get_market_snapshot(self, symbols: List[str]) -> Dict[str, Any]:
        """Get market snapshot for multiple symbols."""
        if not symbols:
            return {}

        symbol_list = ",".join(symbols)
        params = {"tickers": symbol_list}

        return self._make_request("/v2/snapshot/locale/us/markets/stocks/tickers", params)

    def get_single_ticker_snapshot(self, symbol: str) -> Dict[str, Any]:
        """Get snapshot for a single ticker."""
        return self._make_request(f"/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}", {})

    def get_market_status(self) -> Dict[str, Any]:
        """Get current market status."""
        return self._make_request("/v1/marketstatus/now", {})

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

            if not updated_ns:
                logger.warning(f"No updated timestamp in snapshot response for {symbol}")
                return None

            # Convert provider timestamp (nanoseconds) to trade date
            updated_seconds = updated_ns // 1_000_000_000
            trade_date = datetime.fromtimestamp(updated_seconds).date()

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

            return AssetPrice(
                id=0,  # Will be set by database auto-increment
                asset_id=asset_id,
                symbol=symbol,
                provider_id=1,  # Assuming Polygon provider ID is 1
                provider_updated_at=updated_ns,
                trade_date=trade_date,
                updated_at=datetime.now(),

                # PrevDay data
                prevday_open=to_decimal(prevday_data.get("o")),
                prevday_high=to_decimal(prevday_data.get("h")),
                prevday_low=to_decimal(prevday_data.get("l")),
                prevday_close=to_decimal(prevday_data.get("c")),
                prevday_volume=to_int(prevday_data.get("v")),
                prevday_vwap=to_decimal(prevday_data.get("vw")),

                # Day data
                day_open=to_decimal(day_data.get("o")),
                day_high=to_decimal(day_data.get("h")),
                day_low=to_decimal(day_data.get("l")),
                day_close=to_decimal(day_data.get("c")),
                day_volume=to_int(day_data.get("v")),
                day_vwap=to_decimal(day_data.get("vw")),

                # Min data
                min_timestamp=to_int(min_data.get("t")),
                min_open=to_decimal(min_data.get("o")),
                min_high=to_decimal(min_data.get("h")),
                min_low=to_decimal(min_data.get("l")),
                min_close=to_decimal(min_data.get("c")),
                min_volume=to_int(min_data.get("v")),
                min_vwap=to_decimal(min_data.get("vw")),
                min_accumulated_volume=to_int(min_data.get("av")),
                min_num_trades=to_int(min_data.get("n"))
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

    def get_market_snapshot_metadata(self) -> Optional[Dict[str, Any]]:
        """Get the latest market snapshot run metadata."""
        if not self.db_manager:
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Get latest completed market snapshot run
                cursor.execute("""
                    SELECT
                        started_at, completed_at, total_symbols,
                        successful_updates, failed_updates, status,
                        error_message, api_calls_made
                    FROM market_snapshot_metadata
                    WHERE status IN ('completed', 'partial')
                    ORDER BY completed_at DESC
                    LIMIT 1
                """)
                result = cursor.fetchone()

                if result:
                    return {
                        "started_at": datetime.fromisoformat(result[0]),
                        "completed_at": datetime.fromisoformat(result[1]) if result[1] else None,
                        "total_symbols": result[2],
                        "successful_updates": result[3],
                        "failed_updates": result[4],
                        "status": result[5],
                        "error_message": result[6],
                        "api_calls_made": result[7]
                    }
                return None

        except Exception as e:
            logger.error(f"Error getting market snapshot metadata: {e}")
            return None

    def check_running_snapshot(self) -> Optional[datetime]:
        """Check if a market snapshot is currently running."""
        if not self.db_manager:
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT started_at FROM market_snapshot_metadata
                    WHERE status = 'running'
                    ORDER BY started_at DESC
                    LIMIT 1
                """)
                result = cursor.fetchone()
                return datetime.fromisoformat(result[0]) if result else None

        except Exception as e:
            logger.error(f"Error checking running snapshot: {e}")
            return None

    def start_market_snapshot_run(self, total_symbols: int) -> Optional[int]:
        """Start a new market snapshot run and return its ID."""
        if not self.db_manager:
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO market_snapshot_metadata (started_at, total_symbols, status)
                    VALUES (?, ?, 'running')
                """, (datetime.now().isoformat(), total_symbols))
                conn.commit()
                return cursor.lastrowid

        except Exception as e:
            logger.error(f"Error starting market snapshot run: {e}")
            return None

    def complete_market_snapshot_run(self, run_id: int, successful: int, failed: int, api_calls: int, error: str = None) -> bool:
        """Complete a market snapshot run with statistics."""
        if not self.db_manager:
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                status = 'completed' if failed == 0 else 'partial' if successful > 0 else 'failed'

                cursor.execute("""
                    UPDATE market_snapshot_metadata
                    SET completed_at = ?, successful_updates = ?, failed_updates = ?,
                        status = ?, api_calls_made = ?, error_message = ?
                    WHERE id = ?
                """, (datetime.now().isoformat(), successful, failed, status, api_calls, error, run_id))
                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Error completing market snapshot run: {e}")
            return False

    def get_active_universe_symbols(self) -> List[str]:
        """Get all active symbols in the universe."""
        if not self.db_manager:
            return []

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT symbol FROM assets
                    WHERE is_active = 1
                    ORDER BY symbol
                """)
                return [row[0] for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error getting universe symbols: {e}")
            return []


