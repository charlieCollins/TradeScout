"""Ticker snapshot database manager using asset_prices table and data_update_metadata."""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from decimal import Decimal
from models.snapshot import TickerSnapshot, MinuteBar
from models.data_update_metadata import DataUpdateMetadataType
from database.config.ttl_config import TICKER_SNAPSHOT_TTL_MINUTES
from .base_manager import BaseManager

logger = logging.getLogger(__name__)


class TickerSnapshotManager(BaseManager):
    """Database manager for ticker snapshot operations using asset_prices table with TTL validation."""

    def get_data_update_metadata_type(self) -> DataUpdateMetadataType:
        """Get the data update metadata type for TTL validation."""
        return DataUpdateMetadataType.TICKER_SNAPSHOTS

    def get_ttl_seconds(self) -> int:
        """Get TTL in seconds for this cache type."""
        return TICKER_SNAPSHOT_TTL_MINUTES * 60

    def get_entity_from_database(self, key: str) -> Optional[TickerSnapshot]:
        """Get TickerSnapshot from asset_prices table.

        Args:
            key: Symbol (e.g., 'AAPL')

        Returns:
            TickerSnapshot object or None if not found
        """
        symbol = key.upper()
        if not self._check_dependencies():
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Get most recent price data for this symbol
                cursor.execute("""
                    SELECT
                        symbol, updated_at,
                        prevday_open, prevday_high, prevday_low, prevday_close, prevday_volume, prevday_vwap,
                        day_open, day_high, day_low, day_close, day_volume, day_vwap,
                        min_timestamp, min_open, min_high, min_low, min_close, min_volume, min_vwap
                    FROM asset_prices
                    WHERE symbol = ?
                    ORDER BY provider_updated_at DESC, updated_at DESC
                    LIMIT 1
                """, (symbol,))

                row = cursor.fetchone()
                if not row:
                    logger.debug(f"No asset_prices data found for {symbol}")
                    return None

                # Construct MinuteBar from database data
                min_bar = None
                if row[14] is not None:  # min_timestamp
                    min_bar = MinuteBar(
                        timestamp=int(row[14]),
                        open=Decimal(str(row[15])) if row[15] else None,
                        high=Decimal(str(row[16])) if row[16] else None,
                        low=Decimal(str(row[17])) if row[17] else None,
                        close=Decimal(str(row[18])) if row[18] else None,
                        volume=int(row[19]) if row[19] else None,
                        vwap=Decimal(str(row[20])) if row[20] else None,
                        accumulated_volume=None,  # Not stored separately
                        num_trades=None  # Not stored separately
                    )

                # Construct TickerSnapshot directly from database data
                return TickerSnapshot(
                    symbol=symbol,
                    prev_close=Decimal(str(row[5])) if row[5] else None,
                    prev_volume=int(row[6]) if row[6] else None,
                    open_price=Decimal(str(row[8])) if row[8] else None,
                    high_price=Decimal(str(row[9])) if row[9] else None,
                    low_price=Decimal(str(row[10])) if row[10] else None,
                    close_price=Decimal(str(row[11])) if row[11] else None,
                    volume=int(row[12]) if row[12] else None,
                    vwap=Decimal(str(row[13])) if row[13] else None,
                    last_price=Decimal(str(row[18])) if row[18] else None,  # Use min.close as last_price
                    last_timestamp=datetime.fromtimestamp(row[14] / 1000) if row[14] else None,
                    min_bar=min_bar,
                    updated_ns=None,  # Could be derived from updated_at if needed
                    market_status=None  # Not stored in asset_prices table
                )

        except Exception as e:
            logger.error(f"Error getting ticker snapshot from database for {symbol}: {e}")
            return None

    def set_entity_to_database(self, key: str, entity: TickerSnapshot) -> bool:
        """Store TickerSnapshot to asset_prices table.

        Args:
            key: Symbol (e.g., 'AAPL')
            entity: TickerSnapshot object to store

        Returns:
            True if successful, False otherwise
        """
        symbol = key.upper()
        if not self._check_dependencies() or not entity:
            return False

        try:
            # Get asset_id for the symbol
            asset_id = self._get_asset_id_for_symbol(symbol)
            if not asset_id:
                logger.warning(f"No asset_id found for symbol {symbol}, cannot store to asset_prices")
                return False

            # Get provider ID
            provider_id = self._get_polygon_provider_id()

            # Use Polygon's updated timestamp or default to 0
            provider_updated_at = entity.updated_ns or 0

            # Determine trade date
            if provider_updated_at and provider_updated_at != 0:
                updated_seconds = provider_updated_at // 1_000_000_000
                trade_date = datetime.fromtimestamp(updated_seconds).date()
            elif entity.min_bar and entity.min_bar.timestamp:
                # Use min bar timestamp if available
                trade_date = datetime.fromtimestamp(entity.min_bar.timestamp / 1000).date()
            else:
                trade_date = datetime.now().date()

            # Direct database insert
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
                    asset_id,
                    symbol,
                    provider_id,
                    provider_updated_at,
                    trade_date.isoformat(),
                    # Previous day data (using prev_close for all OHLC as we don't have separate values)
                    float(entity.prev_close) if entity.prev_close else None,
                    float(entity.prev_close) if entity.prev_close else None,
                    float(entity.prev_close) if entity.prev_close else None,
                    float(entity.prev_close) if entity.prev_close else None,
                    entity.prev_volume,
                    None,  # prevday_vwap not available
                    # Current day data
                    float(entity.open_price) if entity.open_price else None,
                    float(entity.high_price) if entity.high_price else None,
                    float(entity.low_price) if entity.low_price else None,
                    float(entity.close_price) if entity.close_price else None,
                    entity.volume,
                    float(entity.vwap) if entity.vwap else None,
                    # Min bar data (includes afterhours)
                    entity.min_bar.timestamp if entity.min_bar else None,
                    float(entity.min_bar.open) if entity.min_bar and entity.min_bar.open else None,
                    float(entity.min_bar.high) if entity.min_bar and entity.min_bar.high else None,
                    float(entity.min_bar.low) if entity.min_bar and entity.min_bar.low else None,
                    float(entity.min_bar.close) if entity.min_bar and entity.min_bar.close else None,
                    entity.min_bar.volume if entity.min_bar else None,
                    float(entity.min_bar.vwap) if entity.min_bar and entity.min_bar.vwap else None,
                    entity.min_bar.accumulated_volume if entity.min_bar else None,
                    entity.min_bar.num_trades if entity.min_bar else None,
                    datetime.now().isoformat()
                )

                cursor.execute(query, values)
                conn.commit()

                logger.debug(f"Successfully stored ticker snapshot for {symbol} to asset_prices")
                return True

        except Exception as e:
            logger.error(f"Error storing ticker snapshot to asset_prices for {symbol}: {e}")
            return False

    def _get_asset_id_for_symbol(self, symbol: str) -> Optional[int]:
        """Get asset_id for a symbol from the assets table.

        Args:
            symbol: Symbol to look up

        Returns:
            Asset ID if found, None otherwise
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM assets WHERE symbol = ?", (symbol.upper(),))
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting asset_id for symbol {symbol}: {e}")
            return None

    def _get_polygon_provider_id(self) -> int:
        """Get Polygon provider ID from database.

        Returns:
            Provider ID for Polygon, defaults to 1 if not found
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM providers WHERE name = 'polygon'")
                result = cursor.fetchone()
                return result[0] if result else 1
        except Exception as e:
            logger.warning(f"Could not lookup polygon provider ID: {e}")
            return 1

    def get_stats(self) -> Dict[str, Any]:
        """Get ticker snapshot cache statistics."""
        if not self._check_dependencies():
            return {"error": "Dependencies not available"}

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Count total price records
                cursor.execute("SELECT COUNT(*) FROM asset_prices")
                total_records = cursor.fetchone()[0]

                # Count unique symbols
                cursor.execute("SELECT COUNT(DISTINCT symbol) FROM asset_prices")
                unique_symbols = cursor.fetchone()[0]

                # Get most recent update
                cursor.execute("SELECT MAX(updated_at) FROM asset_prices")
                last_update = cursor.fetchone()[0]

                return {
                    "metadata_type": self.get_data_update_metadata_type().value,
                    "ttl_minutes": TICKER_SNAPSHOT_TTL_MINUTES,
                    "total_records": total_records,
                    "unique_symbols": unique_symbols,
                    "last_update": last_update,
                    "storage": "asset_prices table"
                }

        except Exception as e:
            logger.error(f"Error getting ticker snapshot cache stats: {e}")
            return {"error": str(e)}