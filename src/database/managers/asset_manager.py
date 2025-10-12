"""Asset database manager for asset reference data operations."""

import logging
from typing import Optional, Dict, Any, List, Tuple
from models.asset import Asset
from datetime import datetime
from models.asset import Asset, AssetType, AssetClass
from models.data_update_metadata import DataUpdateMetadataType
from utils.config_loader import get_config_loader
from .base_manager import BaseManager

logger = logging.getLogger(__name__)


class AssetManager(BaseManager):
    """Database manager for asset reference data with TTL validation.

    Assets are relatively static reference data (symbol, name, type, etc.)
    that don't change frequently. Uses longer TTL (3 days) compared to
    real-time price data.
    """

    def get_data_update_metadata_type(self) -> DataUpdateMetadataType:
        """Get the data update metadata type for TTL validation."""
        return DataUpdateMetadataType.TICKERS

    def get_ttl_seconds(self) -> int:
        """Get TTL in seconds for this data type.

        Assets are reference data that changes infrequently (new listings,
        delistings, name changes). Use 3-day TTL.
        """
        config_loader = get_config_loader()
        ttl_config = config_loader.load_database_ttl_config()
        return ttl_config['assets_ttl_hours'] * 3600  # 72 hours = 3 days

    def get_entity_from_database(self, key: str) -> Optional[Asset]:
        """Get Asset from database by symbol.

        Args:
            key: Symbol (e.g., 'AAPL')

        Returns:
            Asset object or None if not found
        """
        symbol = key.upper()
        if not self._check_dependencies():
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT
                        id, symbol, name, market_id, asset_type,
                        asset_class, currency, lot_size, tick_size,
                        is_active, is_delisted, listing_date, delisting_date,
                        provider_id, created_at, updated_at
                    FROM assets
                    WHERE symbol = ? AND is_active = 1
                """

                cursor.execute(query, (symbol,))
                row = cursor.fetchone()

                if not row:
                    logger.debug(f"No asset data found for {symbol}")
                    return None

                # Construct Asset from database row
                return Asset(
                    id=row[0],
                    symbol=row[1],
                    name=row[2],
                    market_id=row[3],
                    asset_type=AssetType(row[4]),
                    asset_class=AssetClass(row[5]),
                    currency=row[6],
                    provider_id=row[13],
                    created_at=datetime.fromisoformat(row[14]),
                    updated_at=datetime.fromisoformat(row[15]),
                    lot_size=row[7] or 1,
                    tick_size=row[8],
                    is_active=bool(row[9]),
                    is_delisted=bool(row[10]),
                    listing_date=datetime.fromisoformat(row[11]) if row[11] else None,
                    delisting_date=datetime.fromisoformat(row[12]) if row[12] else None
                )

        except Exception as e:
            logger.error(f"Error getting asset from database for {symbol}: {e}")
            return None

    def set_entity_to_database(self, key: str, entity: Asset) -> bool:
        """Store Asset to database.

        Args:
            key: Symbol (e.g., 'AAPL')
            entity: Asset object to store

        Returns:
            True if successful, False otherwise
        """
        symbol = key.upper()
        if not self._check_dependencies() or not entity:
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Upsert asset - preserve ID if exists, update other fields
                query = """
                    INSERT INTO assets (
                        symbol, name, asset_type, asset_class, market_id,
                        currency, lot_size, tick_size,
                        is_active, is_delisted, listing_date, delisting_date,
                        provider_id, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(symbol) DO UPDATE SET
                        name = excluded.name,
                        asset_type = excluded.asset_type,
                        asset_class = excluded.asset_class,
                        market_id = excluded.market_id,
                        currency = excluded.currency,
                        lot_size = excluded.lot_size,
                        tick_size = excluded.tick_size,
                        is_active = excluded.is_active,
                        is_delisted = excluded.is_delisted,
                        listing_date = excluded.listing_date,
                        delisting_date = excluded.delisting_date,
                        provider_id = excluded.provider_id,
                        updated_at = excluded.updated_at
                """

                values = (
                    entity.symbol,
                    entity.name,
                    entity.asset_type.value,
                    entity.asset_class.value,
                    entity.market_id,
                    entity.currency,
                    entity.lot_size,
                    float(entity.tick_size) if entity.tick_size else None,
                    entity.is_active,
                    entity.is_delisted,
                    entity.listing_date.isoformat() if entity.listing_date else None,
                    entity.delisting_date.isoformat() if entity.delisting_date else None,
                    entity.provider_id,
                    entity.created_at.isoformat(),
                    datetime.now().isoformat()  # Update updated_at
                )

                cursor.execute(query, values)
                conn.commit()

                logger.debug(f"Successfully stored asset for {symbol}")
                return True

        except Exception as e:
            logger.error(f"Error storing asset to database for {symbol}: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get asset manager statistics."""
        if not self._check_dependencies():
            return {"error": "Dependencies not available"}

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Count total assets
                cursor.execute("SELECT COUNT(*) FROM assets WHERE is_active = 1")
                total_assets = cursor.fetchone()[0]

                # Count by asset type
                cursor.execute("""
                    SELECT asset_type, COUNT(*)
                    FROM assets
                    WHERE is_active = 1
                    GROUP BY asset_type
                """)
                by_type = dict(cursor.fetchall())

                # Get most recent update
                cursor.execute("SELECT MAX(updated_at) FROM assets")
                last_update = cursor.fetchone()[0]

                return {
                    "metadata_type": self.get_data_update_metadata_type().value,
                    "ttl_hours": ASSETS_TTL_HOURS,
                    "total_active_assets": total_assets,
                    "by_type": by_type,
                    "last_update": last_update,
                    "storage": "assets table"
                }

        except Exception as e:
            logger.error(f"Error getting asset manager stats: {e}")
            return {"error": str(e)}

    def get_all_active_asset_ids(self, limit: Optional[int] = None) -> List[Tuple[int, str]]:
        """Get list of all active asset IDs and symbols.

        Args:
            limit: Optional limit on number of results

        Returns:
            List of (asset_id, symbol) tuples
        """
        if not self._check_dependencies():
            return []

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT id, symbol FROM assets WHERE is_active = 1 ORDER BY symbol"
                if limit:
                    query += f" LIMIT {limit}"

                cursor.execute(query)
                return cursor.fetchall()

        except Exception as e:
            logger.error(f"Error getting all active asset IDs: {e}")
            return []

    def bulk_insert_assets(self, assets: List[Asset]) -> int:
        """Bulk insert/update assets in a single transaction.

        Args:
            assets: List of Asset objects to store

        Returns:
            Number of assets successfully stored
        """
        if not self._check_dependencies() or not assets:
            return 0

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    INSERT INTO assets (
                        symbol, name, asset_type, asset_class, market_id,
                        currency, lot_size, tick_size,
                        is_active, is_delisted, listing_date, delisting_date,
                        provider_id, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(symbol) DO UPDATE SET
                        name = excluded.name,
                        asset_type = excluded.asset_type,
                        asset_class = excluded.asset_class,
                        market_id = excluded.market_id,
                        currency = excluded.currency,
                        lot_size = excluded.lot_size,
                        tick_size = excluded.tick_size,
                        is_active = excluded.is_active,
                        is_delisted = excluded.is_delisted,
                        listing_date = excluded.listing_date,
                        delisting_date = excluded.delisting_date,
                        provider_id = excluded.provider_id,
                        updated_at = excluded.updated_at
                """

                # Prepare all values
                values_list = []
                for entity in assets:
                    values = (
                        entity.symbol,
                        entity.name,
                        entity.asset_type.value,
                        entity.asset_class.value,
                        entity.market_id,
                        entity.currency,
                        entity.lot_size,
                        float(entity.tick_size) if entity.tick_size else None,
                        entity.is_active,
                        entity.is_delisted,
                        entity.listing_date.isoformat() if entity.listing_date else None,
                        entity.delisting_date.isoformat() if entity.delisting_date else None,
                        entity.provider_id,
                        entity.created_at.isoformat(),
                        datetime.now().isoformat()
                    )
                    values_list.append(values)

                # Execute bulk insert
                cursor.executemany(query, values_list)
                conn.commit()

                logger.info(f"Bulk inserted {len(assets)} assets successfully")
                return len(assets)

        except Exception as e:
            logger.error(f"Error bulk inserting assets: {e}")
            return 0