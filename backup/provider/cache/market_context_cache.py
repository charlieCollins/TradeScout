"""Market context caching using database and data_update_metadata."""

import json
import logging
from typing import Optional, Dict, Any, Callable
from datetime import datetime
from models.market_context import MarketContext
from config.ttl_config import MARKET_CONTEXT_TTL_MINUTES
from .base_cache_manager import BaseCacheManager

logger = logging.getLogger(__name__)


class MarketContextCache(BaseCacheManager):
    """Cache MarketContext objects using database with operation-level TTL validation."""

    def _get_operation_type(self) -> str:
        """Get the operation type for TTL validation."""
        return "market_context"

    def _get_ttl_seconds(self) -> int:
        """Get TTL in seconds for this cache type."""
        return MARKET_CONTEXT_TTL_MINUTES * 60

    def get_or_fetch(self, key: str, fetch_fn: Callable, **kwargs) -> Optional[MarketContext]:
        """Get cached MarketContext or fetch fresh data.

        Args:
            key: Market code (e.g., 'XNYS')
            fetch_fn: Function to fetch fresh MarketContext

        Returns:
            MarketContext object or None if error
        """
        market_code = key

        if self._is_cache_stale():
            logger.debug(f"Market context cache is stale, fetching fresh data for {market_code}")

            fresh_context = fetch_fn()
            if fresh_context:
                self.set(market_code, fresh_context)
                return fresh_context
            else:
                logger.error(f"Failed to fetch fresh market context for {market_code}")
                return None
        else:
            logger.debug(f"Using cached market context for {market_code}")
            return self.get(market_code)

    def get(self, key: str, **kwargs) -> Optional[MarketContext]:
        """Get cached MarketContext without TTL check."""
        market_code = key

        if not self._check_dependencies():
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT context_data FROM market_context_cache WHERE market_code = ?",
                    (market_code,)
                )
                row = cursor.fetchone()

                if row:
                    context_data = json.loads(row[0])
                    return MarketContext.from_dict(context_data)
                else:
                    logger.debug(f"No cached market context found for {market_code}")
                    return None

        except Exception as e:
            logger.error(f"Error retrieving cached market context for {market_code}: {e}")
            return None

    def set(self, key: str, data: MarketContext, **kwargs):
        """Store MarketContext in cache."""
        market_code = key

        if not self._check_dependencies():
            return

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                context_json = json.dumps(data.to_dict())
                cursor.execute("""
                    INSERT OR REPLACE INTO market_context_cache (market_code, context_data)
                    VALUES (?, ?)
                """, (market_code, context_json))
                conn.commit()
                logger.debug(f"Stored market context in cache for {market_code}")

        except Exception as e:
            logger.error(f"Error storing market context for {market_code}: {e}")

    def invalidate(self, key: str = None):
        """Invalidate cached market context."""
        if not self._check_dependencies():
            return

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                if key:
                    cursor.execute(
                        "DELETE FROM market_context_cache WHERE market_code = ?",
                        (key,)
                    )
                    logger.info(f"Invalidated market context cache for {key}")
                else:
                    cursor.execute("DELETE FROM market_context_cache")
                    logger.info("Invalidated all market context cache")

                conn.commit()

        except Exception as e:
            logger.error(f"Error invalidating market context cache: {e}")

    def clear_all(self):
        """Clear all cached market contexts."""
        self.invalidate()

    def get_stats(self) -> Dict[str, Any]:
        """Get market context cache statistics."""
        if not self._check_dependencies():
            return {}

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM market_context_cache")
                count = cursor.fetchone()[0]

                return {
                    "cached_markets": count,
                    "ttl_minutes": MARKET_CONTEXT_TTL_MINUTES,
                    "operation_type": self._get_operation_type()
                }

        except Exception as e:
            logger.error(f"Error getting cache stats: {e}")
            return {}