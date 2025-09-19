"""
Polygon.io Data Provider - Clean Implementation Using New Architecture

Implements the new DataProvider interface using only the new domain models.
Provides asset data, market data, and caching using Polygon.io API.
"""

import logging
import requests
import time
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from ..interfaces.interface_provider import DataProvider
from ..data_models.models_asset import Asset, AssetType, PriceData
from ..data_models.models_market import MarketMover
from ..data_models.models_market import Market, MarketType, MarketStatus
from ..storage.sqlite_repository import SQLiteDatabaseManager
from ..config.app_config import MARKET_SNAPSHOT_CONFIG

logger = logging.getLogger(__name__)


# SQL Queries - Centralized for maintainability
SQL_QUERIES = {
    "get_asset_by_symbol": """
        SELECT a.symbol, a.name, a.asset_type, a.market_id, a.currency,
               a.isin, a.cusip, a.is_active, a.min_order_size
        FROM assets a
        WHERE a.symbol = ?
    """,
    "get_market_by_id": """
        SELECT id, name, market_type, timezone, country, created_at
        FROM markets
        WHERE id = ?
    """,
    "get_cached_snapshot_metadata": """
        SELECT last_retrieved_at, symbols_count
        FROM market_snapshot_metadata
        WHERE snapshot_type = ? AND status = 'success'
        ORDER BY last_retrieved_at DESC LIMIT 1
    """,
    "upsert_snapshot_metadata": """
        INSERT OR REPLACE INTO market_snapshot_metadata
        (snapshot_type, last_retrieved_at, symbols_count, status)
        VALUES (?, ?, ?, 'success')
    """,
    "get_snapshot_data_from_db": """
        SELECT a.symbol, ms.current_price, ms.change_percent, ms.change_amount,
               ms.volume, ms.day_open, ms.day_high, ms.day_low, ms.previous_close,
               ms.minute_price, ms.minute_timestamp, ms.minute_volume
        FROM market_snapshots ms
        JOIN assets a ON ms.asset_id = a.id
        ORDER BY a.symbol
    """,
    "clear_market_snapshots": """
        DELETE FROM market_snapshots
    """,
    "get_asset_id_by_symbol": """
        SELECT id FROM assets WHERE symbol = ?
    """,
    "insert_market_snapshot": """
        INSERT INTO market_snapshots (
            snapshot_time, asset_id, current_price, previous_close,
            change_amount, change_percent, volume, day_open, day_high, day_low,
            minute_price, minute_timestamp, minute_volume
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
}


class DataProviderPolygon(DataProvider):
    """
    Polygon.io data provider using new architecture

    Features:
    - Clean interface implementation
    - SQLite-based caching
    - Market snapshot data for gap analysis
    - Extended hours support
    """

    def __init__(
        self, api_key: str, db_manager: Optional[SQLiteDatabaseManager] = None
    ):
        """
        Initialize Polygon provider

        Args:
            api_key: Polygon.io API key
            db_manager: Optional database manager for caching
        """
        self.api_key = api_key
        self.db_manager = db_manager
        self.base_url = "https://api.polygon.io"

        # Cache for asset and market lookups
        self._asset_cache = {}
        self._market_cache = {}

    # ========================================
    # Public Interface Properties
    # ========================================

    @property
    def provider_name(self) -> str:
        return "Polygon.io"

    @property
    def supports_extended_hours(self) -> bool:
        return True

    @property
    def rate_limit_per_minute(self) -> Optional[int]:
        return 5  # Free tier limit, premium has higher limits

    # ========================================
    # Helper Methods
    # ========================================

    def _extract_current_price_and_volume(
        self,
        ticker_data: Dict[str, Any],
        price_change: float = 0,
        allow_open: bool = False,
    ) -> Tuple[Optional[float], int, Optional[int]]:
        """
        Extract current price, volume, and timestamp from ticker data.

        Only uses min.c (minute close) for real-time price

        Args:
            ticker_data: Polygon ticker data
            price_change: Price change amount for fallback calculation (unused)
            allow_open: If True, fallback to opening price (unused)

        Returns:
            Tuple of (current_price, volume, timestamp) or (None, 0, None) if unavailable
        """
        current_price = None
        volume = 0
        timestamp = None

        if "min" in ticker_data and ticker_data["min"]:
            current_price = ticker_data["min"].get("c")
            volume = ticker_data["min"].get("v", 0)
            timestamp = ticker_data["min"].get("t")  # Unix timestamp in milliseconds

        return current_price, volume, timestamp

    # ========================================
    # AssetDataInterface Implementation
    # ========================================

    def get_current_quote(self, symbol: str) -> Optional[PriceData]:
        """Get current quote for a symbol"""
        try:
            # Get from market snapshot for better performance
            snapshot_data = self.get_market_snapshot()
            if not snapshot_data or symbol not in snapshot_data:
                return None

            ticker_data = snapshot_data[symbol]

            # Extract current price from snapshot
            current_price, volume, min_timestamp = self._extract_current_price_and_volume(
                ticker_data, allow_open=True
            )

            if not current_price:
                return None

            # Get previous close from snapshot
            prev_close = ticker_data.get("prevDay", {}).get("c")

            # Get asset from database
            asset = self._get_asset_from_db(symbol)
            if not asset:
                logger.warning(f"Asset {symbol} not found in database")
                return None

            # Convert Unix timestamp (milliseconds) to datetime
            if min_timestamp:
                timestamp = datetime.fromtimestamp(min_timestamp / 1000)
            else:
                timestamp = datetime.now()

            price_data = PriceData(
                asset=asset,
                timestamp=timestamp,
                volume=volume,
                current_price=Decimal(str(current_price)),
                prev_session_close_price=Decimal(str(prev_close)) if prev_close else None,
            )

            return price_data

        except Exception as e:
            logger.error(f"Error getting quote for {symbol}: {e}")
            return None

    def get_fundamentals(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get fundamental data for a symbol"""
        try:
            url = f"{self.base_url}/v3/reference/tickers/{symbol}"
            params = {"apikey": self.api_key}

            response = requests.get(url, params=params)
            time.sleep(0.12)  # Rate limiting

            if response.status_code != 200:
                return None

            data = response.json()
            if "results" not in data:
                return None

            ticker_info = data["results"]

            # Return simplified fundamentals dict
            return {
                "company_name": ticker_info.get("name"),
                "market_cap": ticker_info.get("market_cap"),
                "description": ticker_info.get("description"),
                "sector": ticker_info.get("sic_description"),
                "employees": ticker_info.get("total_employees"),
                "data_source": "polygon",
            }

        except Exception as e:
            logger.error(f"Error getting fundamentals for {symbol}: {e}")
            return None

    def get_ohlc(
        self, symbol: str, date: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get OHLC data for a date"""
        try:
            if not date:
                date = datetime.now().strftime("%Y-%m-%d")

            url = f"{self.base_url}/v1/open-close/{symbol}/{date}"
            params = {"apikey": self.api_key, "adjusted": "true"}

            response = requests.get(url, params=params)
            time.sleep(0.12)  # Rate limiting

            if response.status_code != 200:
                return None

            data = response.json()
            if "status" not in data or data["status"] != "OK":
                return None

            return {
                "open": data.get("open"),
                "high": data.get("high"),
                "low": data.get("low"),
                "close": data.get("close"),
                "volume": data.get("volume"),
                "date": date,
            }

        except Exception as e:
            logger.error(f"Error getting OHLC for {symbol}: {e}")
            return None

    # ========================================
    # MarketDataInterface Implementation
    # ========================================


    def get_market_gainers(
        self, limit: int = 100, force_refresh: bool = False
    ) -> List[MarketMover]:
        """
        Get top market gainers (no filtering applied).

        Returns stocks with highest percentage gains from previous close to current price.
        Should match results from stockanalysis.com/markets/gainers/

        Args:
            limit: Maximum number of gainers to return (default 100)
            force_refresh: Force fresh data from API

        Returns:
            List of MarketMover objects sorted by % change (highest first)
        """
        try:
            snapshot_data = self.get_market_snapshot(force_refresh)
            if not snapshot_data:
                return []

            # Calculate gainers from snapshot using todaysChangePerc
            movers = []
            for symbol, ticker_data in snapshot_data.items():
                try:
                    # Use API-provided change percentage
                    price_change_percent = ticker_data.get("todaysChangePerc", 0)
                    price_change = ticker_data.get("todaysChange", 0)

                    if price_change_percent <= 0:  # Gainers only
                        continue

                    # Get current price, volume and timestamp
                    current_price, volume, min_timestamp = self._extract_current_price_and_volume(
                        ticker_data, price_change
                    )

                    if not current_price:
                        continue

                    asset = self._get_asset_from_db(symbol)
                    if not asset:
                        continue

                    # Convert timestamp if available
                    timestamp = None
                    if min_timestamp:
                        timestamp = datetime.fromtimestamp(min_timestamp / 1000)

                    mover = MarketMover(
                        asset=asset,
                        current_price=Decimal(str(current_price)),
                        price_change=Decimal(str(price_change)),
                        price_change_percent=Decimal(str(price_change_percent)),
                        volume=volume,
                        rank=0,  # Will be set after sorting
                        timestamp=timestamp,
                    )
                    movers.append(mover)

                except Exception as e:
                    logger.debug(f"Error processing {symbol}: {e}")
                    continue

            # Sort by percentage change and assign ranks
            movers.sort(key=lambda x: x.price_change_percent, reverse=True)
            for i, mover in enumerate(movers[:limit], 1):
                mover.rank = i

            return movers[:limit]

        except Exception as e:
            logger.error(f"Error getting market gainers: {e}")
            return []

    def get_market_losers(
        self, limit: int = 100, force_refresh: bool = False
    ) -> List[MarketMover]:
        """
        Get top market losers (no filtering applied).

        Returns stocks with largest percentage losses from previous close to current price.
        Should match results from stockanalysis.com/markets/losers/

        Args:
            limit: Maximum number of losers to return (default 100)
            force_refresh: Force fresh data from API

        Returns:
            List of MarketMover objects sorted by % change (most negative first)
        """
        try:
            snapshot_data = self.get_market_snapshot(force_refresh)
            if not snapshot_data:
                return []

            # Calculate losers from snapshot using todaysChangePerc
            movers = []
            for symbol, ticker_data in snapshot_data.items():
                try:
                    # Use API-provided change percentage
                    price_change_percent = ticker_data.get("todaysChangePerc", 0)
                    price_change = ticker_data.get("todaysChange", 0)

                    if price_change_percent >= 0:  # Losers only
                        continue

                    # Get current price, volume and timestamp
                    current_price, volume, min_timestamp = self._extract_current_price_and_volume(
                        ticker_data, price_change
                    )

                    if not current_price:
                        continue

                    asset = self._get_asset_from_db(symbol)
                    if not asset:
                        continue

                    # Convert timestamp if available
                    timestamp = None
                    if min_timestamp:
                        timestamp = datetime.fromtimestamp(min_timestamp / 1000)

                    mover = MarketMover(
                        asset=asset,
                        current_price=Decimal(str(current_price)),
                        price_change=Decimal(str(price_change)),
                        price_change_percent=Decimal(str(price_change_percent)),  # Keep negative values
                        volume=volume,
                        rank=0,  # Will be set after sorting
                        timestamp=timestamp,
                    )
                    movers.append(mover)

                except Exception as e:
                    logger.debug(f"Error processing {symbol}: {e}")
                    continue

            # Sort by percentage change (most negative first)
            movers.sort(key=lambda x: x.price_change_percent)
            for i, mover in enumerate(movers[:limit], 1):
                mover.rank = i

            return movers[:limit]

        except Exception as e:
            logger.error(f"Error getting market losers: {e}")
            return []

    def get_market_snapshot(
        self, force_refresh: bool = False
    ) -> Optional[Dict[str, Any]]:
        """Get complete market snapshot with caching"""
        if (
            not force_refresh
            and self.db_manager
            and self._is_market_snapshot_cache_valid()
        ):
            snapshot_data = self._get_market_snapshot_from_db()
            if snapshot_data:
                return snapshot_data

        # Get fresh data from API
        snapshot_data = self._get_market_snapshot_from_api()
        return snapshot_data

    def get_market_data_status(self) -> Dict[str, Any]:
        """Get market data cache status for header display"""
        try:
            if not self.db_manager:
                return {"status": "no_cache", "symbols": 0}

            # Check if we have cached data and if it's valid
            if self._is_market_snapshot_cache_valid():
                # Get cached data to count symbols
                cached_data = self._get_market_snapshot_from_db()
                if cached_data:
                    # Get cache metadata for timing info
                    conn = self.db_manager.get_connection()
                    cursor = conn.cursor()
                    cursor.execute(
                        SQL_QUERIES["get_cached_snapshot_metadata"],
                        (MARKET_SNAPSHOT_CONFIG["snapshot_type"],),
                    )
                    result = cursor.fetchone()
                    conn.close()

                    if result:
                        last_retrieved_str, symbols_count = result
                        last_retrieved = datetime.fromisoformat(last_retrieved_str)
                        age_minutes = (
                            datetime.now() - last_retrieved
                        ).total_seconds() / 60
                        ttl_minutes = MARKET_SNAPSHOT_CONFIG["ttl_minutes"]
                        time_left_minutes = ttl_minutes - age_minutes

                        return {
                            "status": "cached",
                            "source": "database",
                            "symbols": len(cached_data),
                            "age_minutes": age_minutes,
                            "time_left_minutes": max(0, time_left_minutes),
                        }

            # Check if we have stale cached data
            cached_data = self._get_market_snapshot_from_db()
            if cached_data:
                return {
                    "status": "stale",
                    "source": "database",
                    "symbols": len(cached_data),
                }

            # No cached data
            return {"status": "empty", "symbols": 0}

        except Exception as e:
            logger.error(f"Error getting market data status: {e}")
            return {"status": "error", "symbols": 0}

    # ========================================
    # Private Methods
    # ========================================

    def _convert_polygon_snapshot_to_tradescout_model(
        self, polygon_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Convert Polygon API snapshot response to TradeScout model format"""
        snapshot_dict = {}

        for ticker in polygon_data.get("tickers", []):
            symbol = ticker.get("ticker", "").upper()
            if not symbol:
                continue

            day_data = ticker.get("day", {})
            prev_day_data = ticker.get("prevDay", {})
            min_data = ticker.get("min", {})

            snapshot_dict[symbol] = {
                "ticker": symbol,
                "todaysChangePerc": ticker.get("todaysChangePerc", 0),
                "todaysChange": ticker.get("todaysChange", 0),
                "day": {
                    "c": day_data.get("c"),
                    "o": day_data.get("o"),
                    "h": day_data.get("h"),
                    "l": day_data.get("l"),
                    "v": day_data.get("v"),
                },
                "prevDay": {"c": prev_day_data.get("c")},
                "min": (
                    {
                        "c": min_data.get("c"),
                        "t": min_data.get("t"),
                        "v": min_data.get("v"),
                    }
                    if min_data.get("c")
                    else None
                ),
            }

        return snapshot_dict

    def _is_market_snapshot_cache_valid(self) -> bool:
        """Check if market snapshot cache is within TTL"""
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                SQL_QUERIES["get_cached_snapshot_metadata"],
                (MARKET_SNAPSHOT_CONFIG["snapshot_type"],),
            )

            result = cursor.fetchone()
            conn.close()

            if not result:
                return False

            last_retrieved_str, symbols_count = result
            last_retrieved = datetime.fromisoformat(last_retrieved_str)

            ttl_minutes = MARKET_SNAPSHOT_CONFIG["ttl_minutes"]
            age_minutes = (datetime.now() - last_retrieved).total_seconds() / 60

            return age_minutes < ttl_minutes

        except Exception as e:
            return False

    def _update_market_snapshot_cache_metadata(self, symbols_count: int) -> None:
        """Update cache metadata with current timestamp"""
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()

            snapshot_time = datetime.now()
            cursor.execute(
                SQL_QUERIES["upsert_snapshot_metadata"],
                (
                    MARKET_SNAPSHOT_CONFIG["snapshot_type"],
                    snapshot_time.isoformat(),
                    symbols_count,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error updating cache metadata: {e}")

    def _get_market_snapshot_from_api(self) -> Optional[Dict[str, Any]]:
        """Get market snapshot from Polygon API and convert to our model format"""
        try:
            url = f"{self.base_url}/v2/snapshot/locale/us/markets/stocks/tickers"
            params = {"apikey": self.api_key}

            response = requests.get(url, params=params)
            time.sleep(0.2)  # Rate limiting for large request

            if response.status_code != 200:
                logger.error(f"Market snapshot API error: {response.status_code}")
                return None

            data = response.json()
            if "tickers" not in data:
                return None

            # Convert to our model format
            snapshot_dict = self._convert_polygon_snapshot_to_tradescout_model(data)

            # Log at debug level and let caller handle console output
            logger.debug(f"Retrieved {len(snapshot_dict)} symbols from market snapshot")

            # Store to database and update cache metadata if we have a database
            if snapshot_dict and self.db_manager:
                self._store_market_snapshot_to_db(snapshot_dict)
                self._update_market_snapshot_cache_metadata(len(snapshot_dict))

            return snapshot_dict

        except Exception as e:
            logger.error(f"Error getting market snapshot: {e}")
            return None

    def _get_market_snapshot_from_db(self) -> Optional[Dict[str, Any]]:
        """Get market snapshot data from database in TradeScout format"""
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()

            # Get all current market snapshot data
            cursor.execute(SQL_QUERIES["get_snapshot_data_from_db"])

            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return None

            # Convert to Polygon snapshot format
            snapshot_dict = {}
            for row in rows:
                symbol = row[0]
                current_price = row[1]
                change_percent = row[2]
                change_amount = row[3]
                volume = row[4]
                day_open = row[5]
                day_high = row[6]
                day_low = row[7]
                previous_close = row[8]
                minute_price = row[9]
                minute_timestamp = row[10]
                minute_volume = row[11]

                snapshot_dict[symbol] = {
                    "ticker": symbol,
                    "todaysChangePerc": change_percent,
                    "todaysChange": change_amount,
                    "day": {
                        "c": current_price,
                        "o": day_open,
                        "h": day_high,
                        "l": day_low,
                        "v": volume,
                    },
                    "prevDay": {"c": previous_close},
                    "min": (
                        {"c": minute_price, "t": minute_timestamp, "v": minute_volume}
                        if minute_price
                        else None
                    ),
                }

            # Log at debug level and let caller handle console output
            logger.debug(f"Retrieved {len(snapshot_dict)} symbols from database")
            return snapshot_dict

        except Exception as e:
            logger.error(f"Error getting market snapshot from database: {e}")
            return None

    def _store_market_snapshot_to_db(self, snapshot_data: Dict[str, Any]) -> None:
        """Store market snapshot data in database"""
        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()
            snapshot_time = datetime.now()

            # Clear existing snapshot data
            cursor.execute(SQL_QUERIES["clear_market_snapshots"])

            stored_count = 0
            for symbol, ticker_data in snapshot_data.items():
                try:
                    # Get asset ID for symbol
                    cursor.execute(SQL_QUERIES["get_asset_id_by_symbol"], (symbol,))
                    asset_result = cursor.fetchone()
                    if not asset_result:
                        continue

                    asset_id = asset_result[0]

                    # Extract data from our model format
                    current_price = ticker_data.get("day", {}).get("c")
                    previous_close = ticker_data.get("prevDay", {}).get("c")
                    change_amount = ticker_data.get("todaysChange")
                    change_percent = ticker_data.get("todaysChangePerc")

                    day_data = ticker_data.get("day", {})
                    min_data = (
                        ticker_data.get("min", {}) if ticker_data.get("min") else {}
                    )

                    # Insert snapshot record
                    cursor.execute(
                        SQL_QUERIES["insert_market_snapshot"],
                        (
                            snapshot_time.isoformat(),
                            asset_id,
                            current_price,
                            previous_close,
                            change_amount,
                            change_percent,
                            day_data.get("v"),
                            day_data.get("o"),
                            day_data.get("h"),
                            day_data.get("l"),
                            min_data.get("c"),
                            min_data.get("t"),
                            min_data.get("v"),
                        ),
                    )
                    stored_count += 1

                except Exception as e:
                    continue

            conn.commit()
            conn.close()
            # Log at debug level and let caller handle console output
            logger.debug(f"Stored {stored_count} symbols in database")

        except Exception as e:
            logger.error(f"Error storing market snapshot: {e}")

    def _get_asset_from_db(self, symbol: str) -> Optional[Asset]:
        """Get asset from database"""
        # Check cache first
        if symbol in self._asset_cache:
            return self._asset_cache[symbol]

        if not self.db_manager:
            # No database, return None (caller should handle)
            return None

        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()

            # Get asset with market info from database
            cursor.execute(SQL_QUERIES["get_asset_by_symbol"], (symbol,))

            row = cursor.fetchone()
            if not row:
                return None

            # Map database asset_type to AssetType enum
            asset_type_map = {
                "common_stock": AssetType.COMMON_STOCK,
                "preferred_stock": AssetType.PREFERRED_STOCK,
                "etf": AssetType.ETF,
                "mutual_fund": AssetType.MUTUAL_FUND,
                "option": AssetType.OPTION,
            }
            asset_type = asset_type_map.get(row[2], AssetType.COMMON_STOCK)

            # Get market data from the asset's actual market
            if not row[3]:  # market_id
                logger.error(f"Asset {symbol} has no market_id in database")
                return None

            market = self._get_market_from_db(row[3])
            if not market:
                logger.error(
                    f"Cannot create asset {symbol}: market {row[3]} not found in universe config"
                )
                return None

            asset = Asset(
                symbol=row[0],
                name=row[1] or f"{row[0]}",
                asset_type=asset_type,
                market=market,
                currency=row[4] or "USD",
                isin=row[5],
                cusip=row[6],
                is_active=bool(row[7]),
                min_order_size=Decimal(str(row[8])) if row[8] else Decimal("1"),
            )

            # Cache it
            self._asset_cache[symbol] = asset
            return asset

        except Exception as e:
            logger.error(f"Error getting asset {symbol} from database: {e}")
            return None
        finally:
            if "conn" in locals():
                conn.close()

    def _get_market_from_db(self, market_id: str) -> Optional[Market]:
        """Get market from database"""
        # Check cache first
        if market_id in self._market_cache:
            return self._market_cache[market_id]

        if not self.db_manager:
            return None

        try:
            conn = self.db_manager.get_connection()
            cursor = conn.cursor()

            cursor.execute(SQL_QUERIES["get_market_by_id"], (market_id,))
            row = cursor.fetchone()
            if not row:
                return None

            # Map database market_type to MarketType enum
            market_type_map = {
                "stock": MarketType.STOCK,
                "options": MarketType.OPTIONS,
                "futures": MarketType.FUTURES,
                "forex": MarketType.FOREX,
                "crypto": MarketType.CRYPTO,
            }
            market_type = market_type_map.get(row[2], MarketType.STOCK)

            # Get trading hours for this market
            trading_hours = self._get_trading_hours(row[0])

            market = Market(
                id=row[0],
                name=row[1],
                market_type=market_type,
                timezone=row[3] or "America/New_York",
                currency="USD",  # Default to USD
                regular_open=trading_hours["regular_open"],
                regular_close=trading_hours["regular_close"],
                pre_market_start=trading_hours.get("pre_market_start"),
                after_hours_end=trading_hours.get("after_hours_end"),
            )

            # Cache it
            self._market_cache[market_id] = market
            return market

        except Exception as e:
            logger.error(f"Error getting market {market_id} from database: {e}")
            return None
        finally:
            if "conn" in locals():
                conn.close()

    def _get_trading_hours(self, market_id: str) -> dict:
        """Get trading hours from universe config"""
        from ..config.universe_config import get_exchange_info
        from datetime import time

        exchange_info = get_exchange_info(market_id)
        if exchange_info:
            return {
                "regular_open": exchange_info["regular_open"],
                "regular_close": exchange_info["regular_close"],
                "pre_market_start": exchange_info.get("pre_market_start"),
                "after_hours_end": exchange_info.get("after_hours_end"),
            }
        else:
            # Default US market hours if not in config
            return {
                "regular_open": time(9, 30),
                "regular_close": time(16, 0),
                "pre_market_start": time(4, 0),
                "after_hours_end": time(20, 0),
            }
