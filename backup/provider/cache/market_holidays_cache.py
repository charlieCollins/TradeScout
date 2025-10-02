"""Market holidays caching using database and data_update_metadata."""

import logging
from typing import List, Dict, Any, Optional, Callable
from datetime import datetime
from config.ttl_config import MARKET_HOLIDAYS_TTL_DAYS
from .base_cache_manager import BaseCacheManager

logger = logging.getLogger(__name__)


class MarketHolidaysCache(BaseCacheManager):
    """Cache market holidays using database with operation-level TTL validation."""

    def _get_operation_type(self) -> str:
        """Get the operation type for TTL validation."""
        return "market_holidays"

    def _get_ttl_seconds(self) -> int:
        """Get TTL in seconds for this cache type."""
        return MARKET_HOLIDAYS_TTL_DAYS * 24 * 3600

    def get_or_fetch(self, key: str, fetch_fn: Callable, **kwargs) -> List[Dict[str, Any]]:
        """Get cached holidays or fetch fresh data.

        Args:
            key: Not used for holidays (global cache)
            fetch_fn: Function to fetch fresh holidays from API

        Returns:
            List of holiday dictionaries
        """
        if self._is_cache_stale():
            logger.debug("Market holidays cache is stale, fetching fresh data")

            fresh_holidays = fetch_fn()
            if fresh_holidays:
                self.set("holidays", fresh_holidays)
                return fresh_holidays
            else:
                logger.error("Failed to fetch fresh market holidays")
                # Return cached data as fallback
                return self.get("holidays") or []
        else:
            logger.debug("Using cached market holidays")
            return self.get("holidays") or []

    def get(self, key: str, **kwargs) -> Optional[List[Dict[str, Any]]]:
        """Get cached holidays without TTL check."""
        if not self._check_dependencies():
            return []

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT date, name, status FROM market_holidays ORDER BY date"
                )
                rows = cursor.fetchall()

                holidays = []
                for row in rows:
                    holidays.append({
                        'date': row[0],
                        'name': row[1],
                        'status': row[2]
                    })

                logger.debug(f"Retrieved {len(holidays)} cached holidays")
                return holidays

        except Exception as e:
            logger.error(f"Error retrieving cached holidays: {e}")
            return []

    def set(self, key: str, data: List[Dict[str, Any]], **kwargs):
        """Store holidays in cache (bulk replace)."""
        if not self._check_dependencies():
            return

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Clear existing holidays (bulk replace strategy)
                cursor.execute("DELETE FROM market_holidays")

                # Insert new holidays
                for holiday in data:
                    cursor.execute("""
                        INSERT INTO market_holidays (date, name, status)
                        VALUES (?, ?, ?)
                    """, (
                        holiday.get('date'),
                        holiday.get('name'),
                        holiday.get('status')
                    ))

                conn.commit()
                logger.debug(f"Stored {len(data)} holidays in cache")

        except Exception as e:
            logger.error(f"Error storing holidays: {e}")

    def invalidate(self, key: str = None):
        """Invalidate cached holidays."""
        if not self._check_dependencies():
            return

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM market_holidays")
                conn.commit()
                logger.info("Invalidated market holidays cache")

        except Exception as e:
            logger.error(f"Error invalidating holidays cache: {e}")

    def clear_all(self):
        """Clear all cached holidays."""
        self.invalidate()

    def get_stats(self) -> Dict[str, Any]:
        """Get holidays cache statistics."""
        if not self._check_dependencies():
            return {}

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM market_holidays")
                count = cursor.fetchone()[0]

                return {
                    "cached_holidays": count,
                    "ttl_days": MARKET_HOLIDAYS_TTL_DAYS,
                    "operation_type": self._get_operation_type()
                }

        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}

    def get_holidays(self) -> List[Dict[str, Any]]:
        """Get holidays directly from cache without TTL check.

        Returns:
            List of cached holiday dictionaries
        """
        return self.get("holidays") or []