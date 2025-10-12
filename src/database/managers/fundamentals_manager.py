"""Fundamentals database manager for company fundamental data operations."""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from models.fundamentals import AssetFundamentals
from models.data_update_metadata import DataUpdateMetadataType
from utils.config_loader import get_config_loader
from .base_manager import BaseManager

logger = logging.getLogger(__name__)


class FundamentalsManager(BaseManager):
    """Database manager for asset fundamentals with TTL validation.

    Fundamentals are relatively static company data (market cap, sector, industry)
    that change infrequently. Uses 1-week TTL for refresh checks.

    Note: Fundamentals are fetched from Polygon's ticker details endpoint,
    which provides company overview data including market cap, sector, etc.
    """

    def get_data_update_metadata_type(self) -> DataUpdateMetadataType:
        """Get the data update metadata type for TTL validation."""
        return DataUpdateMetadataType.FUNDAMENTALS

    def get_ttl_seconds(self) -> int:
        """Get TTL in seconds for this data type.

        Fundamentals data (market cap, sector, shares outstanding) changes
        infrequently. Use 1-week TTL.
        """
        config_loader = get_config_loader()
        ttl_config = config_loader.load_database_ttl_config()
        return ttl_config['fundamentals_ttl_hours'] * 3600  # 168 hours = 1 week

    def get_entity_from_database(self, key: str) -> Optional[AssetFundamentals]:
        """Get AssetFundamentals from database by asset_id.

        Args:
            key: Asset ID as string (e.g., '1', '42')

        Returns:
            AssetFundamentals object or None if not found
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

                query = """
                    SELECT asset_id, company_name, sector, industry, sic_code,
                           market_cap, shares_outstanding, avg_volume_30d, beta,
                           pe_ratio, dividend_yield, provider_id, last_updated
                    FROM asset_fundamentals
                    WHERE asset_id = ?
                """

                cursor.execute(query, (asset_id,))
                row = cursor.fetchone()

                if not row:
                    logger.debug(f"No fundamentals found for asset_id {asset_id}")
                    return None

                return AssetFundamentals.from_db_row(row)

        except Exception as e:
            logger.error(f"Error getting fundamentals from database for asset_id {asset_id}: {e}")
            return None

    def get_fundamentals_by_symbol(self, symbol: str) -> Optional[AssetFundamentals]:
        """Get AssetFundamentals from database by symbol.

        Convenience method that looks up asset_id from symbol first.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')

        Returns:
            AssetFundamentals object or None if not found
        """
        if not self._check_dependencies():
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Join with assets table to get fundamentals by symbol
                query = """
                    SELECT f.asset_id, f.company_name, f.sector, f.industry, f.sic_code,
                           f.market_cap, f.shares_outstanding, f.avg_volume_30d, f.beta,
                           f.pe_ratio, f.dividend_yield, f.provider_id, f.last_updated
                    FROM asset_fundamentals f
                    JOIN assets a ON f.asset_id = a.id
                    WHERE a.symbol = ?
                """

                cursor.execute(query, (symbol.upper(),))
                row = cursor.fetchone()

                if not row:
                    logger.debug(f"No fundamentals found for symbol {symbol}")
                    return None

                return AssetFundamentals.from_db_row(row)

        except Exception as e:
            logger.error(f"Error getting fundamentals by symbol {symbol}: {e}")
            return None

    def set_entity_to_database(self, key: str, entity: AssetFundamentals) -> bool:
        """Store AssetFundamentals to database.

        Args:
            key: Asset ID as string (should match entity.asset_id)
            entity: AssetFundamentals object to store

        Returns:
            True if successful, False otherwise
        """
        if not self._check_dependencies() or not entity:
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Use INSERT OR REPLACE to handle both new and existing fundamentals
                query = """
                    INSERT OR REPLACE INTO asset_fundamentals (
                        asset_id, company_name, sector, industry, sic_code,
                        market_cap, shares_outstanding, avg_volume_30d, beta,
                        pe_ratio, dividend_yield, provider_id, last_updated
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """

                values = (
                    entity.asset_id,
                    entity.company_name,
                    entity.sector,
                    entity.industry,
                    entity.sic_code,
                    entity.market_cap,
                    entity.shares_outstanding,
                    entity.avg_volume_30d,
                    float(entity.beta) if entity.beta else None,
                    float(entity.pe_ratio) if entity.pe_ratio else None,
                    float(entity.dividend_yield) if entity.dividend_yield else None,
                    entity.provider_id,
                    entity.last_updated.isoformat()
                )

                cursor.execute(query, values)
                conn.commit()

                logger.debug(f"Successfully stored fundamentals for asset_id {entity.asset_id}")
                return True

        except Exception as e:
            logger.error(f"Error storing fundamentals to database for asset_id {entity.asset_id}: {e}")
            return False

    # ============================================================================
    # STATISTICS
    # ============================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get fundamentals manager statistics."""
        if not self._check_dependencies():
            return {"error": "Dependencies not available"}

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Count total fundamentals
                cursor.execute("SELECT COUNT(*) FROM asset_fundamentals")
                total_fundamentals = cursor.fetchone()[0]

                # Count by sector
                cursor.execute("""
                    SELECT sector, COUNT(*)
                    FROM asset_fundamentals
                    WHERE sector IS NOT NULL
                    GROUP BY sector
                    ORDER BY COUNT(*) DESC
                    LIMIT 10
                """)
                top_sectors = dict(cursor.fetchall())

                # Get most recent update
                cursor.execute("SELECT MAX(last_updated) FROM asset_fundamentals")
                last_update = cursor.fetchone()[0]

                # Count fundamentals with market cap
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM asset_fundamentals
                    WHERE market_cap IS NOT NULL
                """)
                with_market_cap = cursor.fetchone()[0]

                return {
                    "metadata_type": self.get_data_update_metadata_type().value,
                    "ttl_hours": FUNDAMENTALS_TTL_HOURS,
                    "total_fundamentals": total_fundamentals,
                    "with_market_cap": with_market_cap,
                    "top_sectors": top_sectors,
                    "last_update": last_update,
                    "storage": "asset_fundamentals table"
                }

        except Exception as e:
            logger.error(f"Error getting fundamentals manager stats: {e}")
            return {"error": str(e)}
