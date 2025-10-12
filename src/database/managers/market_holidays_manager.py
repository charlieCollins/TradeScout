"""Market holidays database manager for holiday calendar operations.

Market holidays track dates when markets are closed or close early.
Uses 30-day TTL since holiday calendars are published well in advance and change rarely.
"""

import logging
from typing import Optional, List
from datetime import date, datetime
from models.market_holiday import MarketHoliday, HolidayStatus
from models.data_update_metadata import DataUpdateMetadataType
from utils.config_loader import get_config_loader
from .base_manager import BaseManager

logger = logging.getLogger(__name__)


class MarketHolidaysManager(BaseManager):
    """Database manager for market holidays with TTL validation.

    Market holidays are fetched from Polygon's /v1/marketstatus/upcoming endpoint.
    They change very rarely (published annually), so uses 30-day TTL.
    """

    def get_data_update_metadata_type(self) -> DataUpdateMetadataType:
        """Get the data update metadata type for TTL validation."""
        return DataUpdateMetadataType.MARKET_HOLIDAYS

    def get_ttl_seconds(self) -> int:
        """Get TTL in seconds for this data type.

        Market holidays are published annually and change rarely.
        Use 30-day TTL.
        """
        config_loader = get_config_loader()
        ttl_config = config_loader.load_database_ttl_config()
        return ttl_config['market_holidays_ttl_days'] * 24 * 3600

    def get_entity_from_database(self, key: str) -> Optional[MarketHoliday]:
        """Get MarketHoliday from database by date.

        Args:
            key: Date string in ISO format (YYYY-MM-DD)

        Returns:
            MarketHoliday object or None if not found
        """
        if not self._check_dependencies():
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT date, name, status
                    FROM market_holidays
                    WHERE date = ?
                """

                cursor.execute(query, (key,))
                row = cursor.fetchone()

                if not row:
                    logger.debug(f"No holiday found for date {key}")
                    return None

                # Parse row into MarketHoliday object
                return MarketHoliday(
                    date=date.fromisoformat(row[0]),
                    name=row[1],
                    status=HolidayStatus(row[2])
                )

        except Exception as e:
            logger.error(f"Error getting holiday from database for date {key}: {e}")
            return None

    def set_entity_to_database(self, key: str, entity: MarketHoliday) -> bool:
        """Store MarketHoliday to database.

        Args:
            key: Date string (ISO format) - should match entity.date
            entity: MarketHoliday object to store

        Returns:
            True if successful, False otherwise
        """
        if not self._check_dependencies():
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Use INSERT OR REPLACE to handle updates
                query = """
                    INSERT OR REPLACE INTO market_holidays (date, name, status)
                    VALUES (?, ?, ?)
                """

                cursor.execute(
                    query,
                    (
                        entity.date.isoformat(),
                        entity.name,
                        entity.status.value
                    )
                )

                conn.commit()
                logger.debug(f"Stored holiday {entity.name} for {entity.date}")
                return True

        except Exception as e:
            logger.error(f"Error storing holiday {entity.name}: {e}")
            return False

    # ============================================================================
    # BULK OPERATIONS
    # ============================================================================

    def get_all_holidays(self) -> List[MarketHoliday]:
        """Get all holidays from database.

        Returns:
            List of MarketHoliday objects ordered by date
        """
        if not self._check_dependencies():
            return []

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT date, name, status
                    FROM market_holidays
                    ORDER BY date
                """

                cursor.execute(query)
                rows = cursor.fetchall()

                holidays = []
                for row in rows:
                    try:
                        holiday = MarketHoliday(
                            date=date.fromisoformat(row[0]),
                            name=row[1],
                            status=HolidayStatus(row[2])
                        )
                        holidays.append(holiday)
                    except Exception as e:
                        logger.warning(f"Failed to parse holiday row {row}: {e}")
                        continue

                logger.debug(f"Retrieved {len(holidays)} holidays from database")
                return holidays

        except Exception as e:
            logger.error(f"Error getting all holidays: {e}")
            return []

    def get_upcoming_holidays(self, from_date: Optional[date] = None) -> List[MarketHoliday]:
        """Get upcoming holidays from a specific date.

        Args:
            from_date: Start date (default: today)

        Returns:
            List of MarketHoliday objects for dates >= from_date
        """
        if not self._check_dependencies():
            return []

        if not from_date:
            from_date = date.today()

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT date, name, status
                    FROM market_holidays
                    WHERE date >= ?
                    ORDER BY date
                """

                cursor.execute(query, (from_date.isoformat(),))
                rows = cursor.fetchall()

                holidays = []
                for row in rows:
                    try:
                        holiday = MarketHoliday(
                            date=date.fromisoformat(row[0]),
                            name=row[1],
                            status=HolidayStatus(row[2])
                        )
                        holidays.append(holiday)
                    except Exception as e:
                        logger.warning(f"Failed to parse holiday row {row}: {e}")
                        continue

                logger.debug(f"Retrieved {len(holidays)} upcoming holidays from {from_date}")
                return holidays

        except Exception as e:
            logger.error(f"Error getting upcoming holidays: {e}")
            return []

    def store_holidays_bulk(self, holidays: List[MarketHoliday]) -> int:
        """Store multiple holidays to database (bulk replace).

        This clears existing holidays and replaces with the new list.
        Used when refreshing holiday calendar from API.

        Args:
            holidays: List of MarketHoliday objects to store

        Returns:
            Number of holidays successfully stored
        """
        if not self._check_dependencies():
            return 0

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Clear existing holidays
                cursor.execute("DELETE FROM market_holidays")

                # Insert new holidays
                stored_count = 0
                for holiday in holidays:
                    try:
                        query = """
                            INSERT INTO market_holidays (date, name, status)
                            VALUES (?, ?, ?)
                        """
                        cursor.execute(
                            query,
                            (
                                holiday.date.isoformat(),
                                holiday.name,
                                holiday.status.value
                            )
                        )
                        stored_count += 1
                    except Exception as e:
                        logger.warning(f"Failed to store holiday {holiday.name}: {e}")
                        continue

                conn.commit()
                logger.info(f"Stored {stored_count}/{len(holidays)} holidays in bulk operation")
                return stored_count

        except Exception as e:
            logger.error(f"Error in bulk holiday storage: {e}")
            return 0

    def clear_all_holidays(self) -> bool:
        """Clear all holidays from database.

        Returns:
            True if successful, False otherwise
        """
        if not self._check_dependencies():
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM market_holidays")
                conn.commit()
                logger.info("Cleared all holidays from database")
                return True

        except Exception as e:
            logger.error(f"Error clearing holidays: {e}")
            return False

    # ============================================================================
    # STATISTICS
    # ============================================================================

    def get_stats(self) -> dict:
        """Get statistics about holiday data.

        Returns:
            Dictionary with holiday statistics
        """
        if not self._check_dependencies():
            return {
                "total_holidays": 0,
                "upcoming_holidays": 0,
                "ttl_seconds": self.get_ttl_seconds(),
                "last_update": None
            }

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Total holidays count
                cursor.execute("SELECT COUNT(*) FROM market_holidays")
                total = cursor.fetchone()[0]

                # Upcoming holidays count
                today = date.today().isoformat()
                cursor.execute("SELECT COUNT(*) FROM market_holidays WHERE date >= ?", (today,))
                upcoming = cursor.fetchone()[0]

                # Last update time from metadata
                last_update = None
                if self.metadata_manager:
                    metadata_type = self.get_data_update_metadata_type()
                    last_update = self.metadata_manager.get_last_update_time(metadata_type)

                return {
                    "total_holidays": total,
                    "upcoming_holidays": upcoming,
                    "ttl_seconds": self.get_ttl_seconds(),
                    "last_update": last_update.isoformat() if last_update else None
                }

        except Exception as e:
            logger.error(f"Error getting holiday stats: {e}")
            return {
                "total_holidays": 0,
                "upcoming_holidays": 0,
                "ttl_seconds": self.get_ttl_seconds(),
                "last_update": None,
                "error": str(e)
            }
