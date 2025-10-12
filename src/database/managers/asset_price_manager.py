"""Asset price database manager using asset_prices table and data_update_metadata."""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, Optional

from models.data_update_metadata import DataUpdateMetadataType
from models.price import AssetPrice
from utils.config_loader import get_config_loader

from .base_manager import BaseManager

logger = logging.getLogger(__name__)


class AssetPriceManager(BaseManager):
    """Database manager for asset price operations using asset_prices table with TTL validation.

    Note: Asset prices are derived from ticker snapshots. The provider for this manager
    would be PolygonSnapshotProvider, which fetches TickerSnapshot data that gets
    transformed into AssetPrice models.
    """

    def get_data_update_metadata_type(self) -> DataUpdateMetadataType:
        """Get the data update metadata type for TTL validation."""
        return DataUpdateMetadataType.ASSET_PRICES

    def get_ttl_seconds(self) -> int:
        """Get TTL in seconds for this cache type."""
        config_loader = get_config_loader()
        ttl_config = config_loader.load_database_ttl_config()
        return ttl_config['asset_price_ttl_minutes'] * 60

    def get_entity_from_database(self, key: str) -> Optional[AssetPrice]:
        """Get AssetPrice from asset_prices table.

        Args:
            key: Asset ID as string (e.g., '123')

        Returns:
            AssetPrice object or None if not found
        """
        try:
            asset_id = int(key)
        except ValueError:
            logger.error(f"Invalid asset_id key: {key}")
            return None

        if not self._check_dependencies():
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Get most recent price data for this asset
                cursor.execute(
                    """
                    SELECT
                        id, asset_id, symbol, provider_id, provider_updated_at, trade_date,
                        prevday_open, prevday_high, prevday_low, prevday_close, prevday_volume, prevday_vwap,
                        day_open, day_high, day_low, day_close, day_volume, day_vwap,
                        min_timestamp, min_open, min_high, min_low, min_close, min_volume,
                        min_vwap, min_accumulated_volume, min_num_trades, updated_at
                    FROM asset_prices
                    WHERE asset_id = ?
                    ORDER BY provider_updated_at DESC, updated_at DESC
                    LIMIT 1
                """,
                    (asset_id,),
                )

                row = cursor.fetchone()
                if not row:
                    logger.debug(f"No asset_prices data found for asset_id {asset_id}")
                    return None

                # Construct AssetPrice from database data
                return AssetPrice(
                    id=row[0],
                    asset_id=row[1],
                    symbol=row[2],
                    provider_id=row[3],
                    provider_updated_at=row[4],
                    trade_date=(
                        datetime.strptime(row[5], "%Y-%m-%d").date() if row[5] else None
                    ),
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
                    updated_at=datetime.fromisoformat(row[27]) if row[27] else None,
                )

        except Exception as e:
            logger.error(
                f"Error getting asset price from database for asset_id {asset_id}: {e}"
            )
            return None

    def set_entity_to_database(self, key: str, entity: AssetPrice) -> bool:
        """Store AssetPrice to asset_prices table.

        Args:
            key: Asset ID as string (e.g., '123')
            entity: AssetPrice object to store

        Returns:
            True if successful, False otherwise
        """
        if not self._check_dependencies():
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    INSERT OR IGNORE INTO asset_prices (
                        asset_id, symbol, provider_id, provider_updated_at, trade_date,
                        prevday_open, prevday_high, prevday_low, prevday_close, prevday_volume, prevday_vwap,
                        day_open, day_high, day_low, day_close, day_volume, day_vwap,
                        min_timestamp, min_open, min_high, min_low, min_close, min_volume,
                        min_vwap, min_accumulated_volume, min_num_trades, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """

                values = (
                    entity.asset_id,
                    entity.symbol,
                    entity.provider_id,
                    entity.provider_updated_at,
                    entity.trade_date.isoformat() if entity.trade_date else None,
                    # PrevDay data
                    float(entity.prevday_open) if entity.prevday_open else None,
                    float(entity.prevday_high) if entity.prevday_high else None,
                    float(entity.prevday_low) if entity.prevday_low else None,
                    float(entity.prevday_close) if entity.prevday_close else None,
                    entity.prevday_volume,
                    float(entity.prevday_vwap) if entity.prevday_vwap else None,
                    # Day data
                    float(entity.day_open) if entity.day_open else None,
                    float(entity.day_high) if entity.day_high else None,
                    float(entity.day_low) if entity.day_low else None,
                    float(entity.day_close) if entity.day_close else None,
                    entity.day_volume,
                    float(entity.day_vwap) if entity.day_vwap else None,
                    # Min data
                    entity.min_timestamp,
                    float(entity.min_open) if entity.min_open else None,
                    float(entity.min_high) if entity.min_high else None,
                    float(entity.min_low) if entity.min_low else None,
                    float(entity.min_close) if entity.min_close else None,
                    entity.min_volume,
                    float(entity.min_vwap) if entity.min_vwap else None,
                    entity.min_accumulated_volume,
                    entity.min_num_trades,
                    (
                        entity.updated_at.isoformat()
                        if entity.updated_at
                        else datetime.now().isoformat()
                    ),
                )

                cursor.execute(query, values)
                conn.commit()

                logger.debug(
                    f"Stored asset price for asset_id {entity.asset_id} ({entity.symbol})"
                )
                return True

        except Exception as e:
            logger.error(f"Error storing asset price for asset_id {key}: {e}")
            return False

    def batch_set_entities_to_database(
        self, entities: list[AssetPrice]
    ) -> tuple[int, int, int, int]:
        """Batch store AssetPrice objects to asset_prices table.

        Args:
            entities: List of AssetPrice objects to store

        Returns:
            Tuple of (new_records, duplicate_records, successful_count, failed_count)
        """
        if not entities:
            return 0, 0, 0, 0

        if not self._check_dependencies():
            return 0, 0, 0, len(entities)

        new_records = 0
        duplicate_records = 0
        successful = 0
        failed = 0

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # First, check which (asset_id, provider_id, provider_updated_at) combinations already exist
                # Build a query to check all combinations at once
                check_query = """
                    SELECT asset_id, provider_id, provider_updated_at
                    FROM asset_prices
                    WHERE (asset_id, provider_id, provider_updated_at) IN ({})
                """.format(
                    ",".join(
                        ["(?, ?, ?)"] * len(entities)
                    )
                )

                # Prepare check values
                check_values = []
                for entity in entities:
                    check_values.extend(
                        [entity.asset_id, entity.provider_id, entity.provider_updated_at]
                    )

                # Execute check query
                cursor.execute(check_query, check_values)
                existing_combinations = set(
                    (row[0], row[1], row[2]) for row in cursor.fetchall()
                )

                # Now categorize entities
                for entity in entities:
                    key = (entity.asset_id, entity.provider_id, entity.provider_updated_at)
                    if key in existing_combinations:
                        duplicate_records += 1
                    else:
                        new_records += 1

                # Insert only new records, ignore duplicates (same unique key = same data)
                query = """
                    INSERT OR IGNORE INTO asset_prices (
                        asset_id, symbol, provider_id, provider_updated_at, trade_date,
                        prevday_open, prevday_high, prevday_low, prevday_close, prevday_volume, prevday_vwap,
                        day_open, day_high, day_low, day_close, day_volume, day_vwap,
                        min_timestamp, min_open, min_high, min_low, min_close, min_volume,
                        min_vwap, min_accumulated_volume, min_num_trades, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """

                # Prepare all values
                values_list = []
                for entity in entities:
                    values = (
                        entity.asset_id,
                        entity.symbol,
                        entity.provider_id,
                        entity.provider_updated_at,
                        entity.trade_date.isoformat() if entity.trade_date else None,
                        # PrevDay data
                        float(entity.prevday_open) if entity.prevday_open else None,
                        float(entity.prevday_high) if entity.prevday_high else None,
                        float(entity.prevday_low) if entity.prevday_low else None,
                        float(entity.prevday_close) if entity.prevday_close else None,
                        entity.prevday_volume,
                        float(entity.prevday_vwap) if entity.prevday_vwap else None,
                        # Day data
                        float(entity.day_open) if entity.day_open else None,
                        float(entity.day_high) if entity.day_high else None,
                        float(entity.day_low) if entity.day_low else None,
                        float(entity.day_close) if entity.day_close else None,
                        entity.day_volume,
                        float(entity.day_vwap) if entity.day_vwap else None,
                        # Min data
                        entity.min_timestamp,
                        float(entity.min_open) if entity.min_open else None,
                        float(entity.min_high) if entity.min_high else None,
                        float(entity.min_low) if entity.min_low else None,
                        float(entity.min_close) if entity.min_close else None,
                        entity.min_volume,
                        float(entity.min_vwap) if entity.min_vwap else None,
                        entity.min_accumulated_volume,
                        entity.min_num_trades,
                        (
                            entity.updated_at.isoformat()
                            if entity.updated_at
                            else datetime.now().isoformat()
                        ),
                    )
                    values_list.append(values)

                # Execute batch insert
                cursor.executemany(query, values_list)
                conn.commit()
                successful = len(values_list)

                logger.debug(
                    f"Batch stored {successful} asset prices ({new_records} new, {duplicate_records} duplicates)"
                )

        except Exception as e:
            logger.error(f"Error in batch store asset prices: {e}")
            failed = len(entities)

        return new_records, duplicate_records, successful, failed

    def get_random_assets_with_prices(self, limit: int = 10) -> list[tuple]:
        """Get random assets that have recent price data.

        Args:
            limit: Number of random assets to return (default: 10)

        Returns:
            List of tuples: (symbol, asset_id, latest_asset_price_id)
        """
        if not self._check_dependencies():
            return []

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Get random assets with their latest price data
                # Return just the identifiers, caller can fetch full AssetPrice if needed
                cursor.execute(
                    """
                    SELECT a.symbol, ap.asset_id, ap.id
                    FROM asset_prices ap
                    JOIN assets a ON ap.asset_id = a.id
                    WHERE ap.id IN (
                        SELECT MAX(id)
                        FROM asset_prices
                        GROUP BY asset_id
                    )
                    AND (ap.min_accumulated_volume > 0 OR ap.day_volume > 0 OR ap.prevday_volume > 0)
                    ORDER BY RANDOM()
                    LIMIT ?
                """,
                    (limit,),
                )

                results = cursor.fetchall()
                logger.debug(f"Retrieved {len(results)} random assets with price data")
                return results

        except Exception as e:
            logger.error(f"Error getting random assets with prices: {e}")
            return []

    def get_latest_price_ids_for_symbols(self, symbols: list[str]) -> list[tuple]:
        """Get latest asset_price IDs for specific symbols.

        Args:
            symbols: List of ticker symbols (e.g., ['AAPL', 'NVDA'])

        Returns:
            List of tuples: (symbol, asset_id, latest_asset_price_id)
        """
        if not self._check_dependencies():
            return []

        if not symbols:
            return []

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Build placeholders for IN clause
                placeholders = ",".join("?" * len(symbols))

                cursor.execute(
                    f"""
                    SELECT a.symbol, ap.asset_id, ap.id
                    FROM asset_prices ap
                    JOIN assets a ON ap.asset_id = a.id
                    WHERE a.symbol IN ({placeholders})
                    AND ap.id = (
                        SELECT MAX(id)
                        FROM asset_prices
                        WHERE asset_id = a.id
                    )
                """,
                    symbols,
                )

                results = cursor.fetchall()
                logger.debug(f"Retrieved latest price IDs for {len(results)} symbols")
                return results

        except Exception as e:
            logger.error(f"Error getting latest price IDs for symbols: {e}")
            return []

    def get_stats(self) -> Dict[str, Any]:
        """Get database manager statistics.

        Returns:
            Dictionary with manager statistics
        """
        base_stats = super().get_stats()

        if not self._check_dependencies():
            return base_stats

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Count total asset prices
                cursor.execute("SELECT COUNT(*) FROM asset_prices")
                total_prices = cursor.fetchone()[0]

                # Get latest update timestamp
                cursor.execute(
                    """
                    SELECT MAX(updated_at) FROM asset_prices
                """
                )
                latest_update = cursor.fetchone()[0]

                base_stats.update(
                    {"total_asset_prices": total_prices, "latest_update": latest_update}
                )

        except Exception as e:
            logger.error(f"Error getting asset price stats: {e}")

        return base_stats
