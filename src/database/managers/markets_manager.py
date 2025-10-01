"""Markets database manager for market/exchange reference data operations.

Markets represent trading venues/exchanges fetched from Polygon's /v3/reference/exchanges endpoint.
Includes exchange codes (MIC), names, trading hours, and metadata.

Markets data changes very rarely (new exchanges are infrequent), so uses 1-year TTL.
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, time
from models.market import Market
from models.data_update_metadata import DataUpdateMetadataType
from database.config.ttl_config import MARKETS_TTL_HOURS
from .base_manager import BaseManager

logger = logging.getLogger(__name__)


class MarketsManager(BaseManager):
    """Database manager for market/exchange reference data with TTL validation.

    Markets are relatively static reference data (exchange codes, names, trading hours)
    fetched from Polygon's /v3/reference/exchanges endpoint. Uses 1-year TTL since
    exchanges are added/changed very infrequently.
    """

    def get_data_update_metadata_type(self) -> DataUpdateMetadataType:
        """Get the data update metadata type for TTL validation."""
        return DataUpdateMetadataType.MARKETS

    def get_ttl_seconds(self) -> int:
        """Get TTL in seconds for this data type.

        Markets reference data (exchange codes, names, hours) is essentially
        static. Use 1-year TTL.
        """
        return MARKETS_TTL_HOURS * 3600  # 8760 hours = 1 year

    def get_entity_from_database(self, key: str) -> Optional[Market]:
        """Get Market from database by market code.

        Args:
            key: Market code as string (e.g., 'XNYS', 'XNAS')

        Returns:
            Market object or None if not found
        """
        if not self._check_dependencies():
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT id, code, name, country, timezone, currency,
                           premarket_start_time, premarket_end_time,
                           regular_open_time, regular_close_time,
                           afterhours_start_time, afterhours_end_time,
                           is_active, created_at, updated_at
                    FROM markets
                    WHERE code = ?
                """

                cursor.execute(query, (key.upper(),))
                row = cursor.fetchone()

                if not row:
                    logger.debug(f"No market found for code {key}")
                    return None

                return self._parse_market_row(row)

        except Exception as e:
            logger.error(f"Error getting market from database for code {key}: {e}")
            return None

    def set_entity_to_database(self, key: str, entity: Market) -> bool:
        """Store Market to database.

        Args:
            key: Market code as string (should match entity.code)
            entity: Market object to store

        Returns:
            True if successful, False otherwise
        """
        if not self._check_dependencies() or not entity:
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Use INSERT OR REPLACE to handle both new and existing markets
                query = """
                    INSERT OR REPLACE INTO markets (
                        code, name, country, timezone, currency,
                        premarket_start_time, premarket_end_time,
                        regular_open_time, regular_close_time,
                        afterhours_start_time, afterhours_end_time,
                        is_active, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """

                values = (
                    entity.code,
                    entity.name,
                    entity.country,
                    entity.timezone,
                    entity.currency,
                    entity.premarket_start_time.isoformat() if entity.premarket_start_time else None,
                    entity.premarket_end_time.isoformat() if entity.premarket_end_time else None,
                    entity.regular_open_time.isoformat(),
                    entity.regular_close_time.isoformat(),
                    entity.afterhours_start_time.isoformat() if entity.afterhours_start_time else None,
                    entity.afterhours_end_time.isoformat() if entity.afterhours_end_time else None,
                    entity.is_active,
                    entity.created_at.isoformat(),
                    entity.updated_at.isoformat()
                )

                cursor.execute(query, values)
                conn.commit()

                logger.debug(f"Successfully stored market {entity.code}")
                return True

        except Exception as e:
            logger.error(f"Error storing market to database for {entity.code}: {e}")
            return False

    # ============================================================================
    # MARKET-SPECIFIC METHODS
    # ============================================================================

    def get_all_markets(self, active_only: bool = True) -> List[Market]:
        """Get all markets from database.

        Args:
            active_only: If True, return only active markets

        Returns:
            List of Market objects
        """
        if not self._check_dependencies():
            return []

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT id, code, name, country, timezone, currency,
                           premarket_start_time, premarket_end_time,
                           regular_open_time, regular_close_time,
                           afterhours_start_time, afterhours_end_time,
                           is_active, created_at, updated_at
                    FROM markets
                """

                if active_only:
                    query += " WHERE is_active = 1"

                query += " ORDER BY code"

                cursor.execute(query)
                rows = cursor.fetchall()

                markets = []
                for row in rows:
                    try:
                        market = self._parse_market_row(row)
                        if market:
                            markets.append(market)
                    except Exception as e:
                        logger.warning(f"Failed to parse market row: {e}")
                        continue

                logger.debug(f"Retrieved {len(markets)} markets from database")
                return markets

        except Exception as e:
            logger.error(f"Error getting all markets: {e}")
            return []

    def get_market_by_id(self, market_id: int) -> Optional[Market]:
        """Get market by database ID.

        Args:
            market_id: Market database ID

        Returns:
            Market object or None if not found
        """
        if not self._check_dependencies():
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT id, code, name, country, timezone, currency,
                           premarket_start_time, premarket_end_time,
                           regular_open_time, regular_close_time,
                           afterhours_start_time, afterhours_end_time,
                           is_active, created_at, updated_at
                    FROM markets
                    WHERE id = ?
                """

                cursor.execute(query, (market_id,))
                row = cursor.fetchone()

                if not row:
                    logger.debug(f"No market found for id {market_id}")
                    return None

                return self._parse_market_row(row)

        except Exception as e:
            logger.error(f"Error getting market by id {market_id}: {e}")
            return None

    def get_market_id_by_code(self, market_code: str) -> Optional[int]:
        """Get market ID by market code.

        Args:
            market_code: Market code (e.g., 'XNYS')

        Returns:
            Market ID or None if not found
        """
        if not self._check_dependencies():
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("SELECT id FROM markets WHERE code = ?", (market_code.upper(),))
                row = cursor.fetchone()

                if row:
                    return row[0]

                logger.debug(f"No market found for code {market_code}")
                return None

        except Exception as e:
            logger.error(f"Error getting market ID for code {market_code}: {e}")
            return None

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    def _parse_market_row(self, row: tuple) -> Optional[Market]:
        """Parse database row into Market object.

        Args:
            row: Database row tuple

        Returns:
            Market object or None if parsing fails
        """
        try:
            def parse_time(time_str: Optional[str]) -> Optional[time]:
                """Parse time string to time object."""
                if not time_str:
                    return None
                try:
                    # Parse ISO format time (HH:MM:SS)
                    parts = time_str.split(':')
                    return time(int(parts[0]), int(parts[1]), int(parts[2]) if len(parts) > 2 else 0)
                except (ValueError, IndexError):
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
                regular_open_time=parse_time(row[8]) or time(9, 30),
                regular_close_time=parse_time(row[9]) or time(16, 0),
                afterhours_start_time=parse_time(row[10]),
                afterhours_end_time=parse_time(row[11]),
                is_active=bool(row[12]),
                created_at=datetime.fromisoformat(row[13]),
                updated_at=datetime.fromisoformat(row[14])
            )

        except Exception as e:
            logger.error(f"Error parsing market row: {e}")
            return None

    # ============================================================================
    # STATISTICS
    # ============================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get markets manager statistics."""
        if not self._check_dependencies():
            return {"error": "Dependencies not available"}

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Count total markets
                cursor.execute("SELECT COUNT(*) FROM markets")
                total_markets = cursor.fetchone()[0]

                # Count active markets
                cursor.execute("SELECT COUNT(*) FROM markets WHERE is_active = 1")
                active_markets = cursor.fetchone()[0]

                # Count by country
                cursor.execute("""
                    SELECT country, COUNT(*)
                    FROM markets
                    GROUP BY country
                    ORDER BY COUNT(*) DESC
                """)
                by_country = dict(cursor.fetchall())

                # Get most recent update
                cursor.execute("SELECT MAX(updated_at) FROM markets")
                last_update = cursor.fetchone()[0]

                return {
                    "metadata_type": self.get_data_update_metadata_type().value,
                    "ttl_hours": MARKETS_TTL_HOURS,
                    "total_markets": total_markets,
                    "active_markets": active_markets,
                    "by_country": by_country,
                    "last_update": last_update,
                    "storage": "markets table"
                }

        except Exception as e:
            logger.error(f"Error getting markets manager stats: {e}")
            return {"error": str(e)}
