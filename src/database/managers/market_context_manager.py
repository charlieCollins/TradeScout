"""Market context database manager for market status/session context operations.

Market context tracks the current market state (open/closed/session) and is used
for determining which price fields to use for calculations. Uses 5-minute TTL since
market state changes throughout the day.
"""

import logging
import json
from typing import Optional
from models.market_context import MarketContext
from models.data_update_metadata import DataUpdateMetadataType
from database.config.ttl_config import MARKET_CONTEXT_TTL_MINUTES
from .base_manager import BaseManager

logger = logging.getLogger(__name__)


class MarketContextManager(BaseManager):
    """Database manager for market context with TTL validation.

    Market context combines market info with current status (session, trading day, etc.).
    Updates frequently as market state changes, so uses 5-minute TTL.
    """

    def get_data_update_metadata_type(self) -> DataUpdateMetadataType:
        """Get the data update metadata type for TTL validation."""
        return DataUpdateMetadataType.MARKET_CONTEXT

    def get_ttl_seconds(self) -> int:
        """Get TTL in seconds for this data type.

        Market context changes throughout the day as markets open/close.
        Use 5-minute TTL for reasonable freshness.
        """
        return MARKET_CONTEXT_TTL_MINUTES * 60

    def get_entity_from_database(self, key: str) -> Optional[MarketContext]:
        """Get MarketContext from database by market code.

        Args:
            key: Market code (e.g., 'XNYS', 'XNAS')

        Returns:
            MarketContext object or None if not found
        """
        if not self._check_dependencies():
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT market_code, context_data
                    FROM market_context_cache
                    WHERE market_code = ?
                """

                cursor.execute(query, (key.upper(),))
                row = cursor.fetchone()

                if not row:
                    logger.debug(f"No market context found for {key}")
                    return None

                # Deserialize JSON to MarketContext object
                context_data = json.loads(row[1])
                market_context = MarketContext.from_dict(context_data)

                logger.debug(f"Retrieved market context for {key}: {market_context.current_session.value}")
                return market_context

        except Exception as e:
            logger.error(f"Error getting market context from database for {key}: {e}")
            return None

    def set_entity_to_database(self, key: str, entity: MarketContext) -> bool:
        """Store MarketContext to database.

        Args:
            key: Market code - should match entity.market.code
            entity: MarketContext object to store

        Returns:
            True if successful, False otherwise
        """
        if not self._check_dependencies():
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Serialize MarketContext to JSON
                context_data = json.dumps(entity.to_dict())

                # Use INSERT OR REPLACE to handle updates
                query = """
                    INSERT OR REPLACE INTO market_context_cache (market_code, context_data)
                    VALUES (?, ?)
                """

                cursor.execute(query, (key.upper(), context_data))
                conn.commit()

                logger.debug(f"Stored market context for {key} (session: {entity.current_session.value})")
                return True

        except Exception as e:
            logger.error(f"Error storing market context for {key}: {e}")
            return False

    # ============================================================================
    # ADDITIONAL OPERATIONS
    # ============================================================================

    def clear_context(self, market_code: str) -> bool:
        """Clear cached context for a specific market.

        Args:
            market_code: Market code to clear

        Returns:
            True if successful, False otherwise
        """
        if not self._check_dependencies():
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM market_context_cache WHERE market_code = ?", (market_code.upper(),))
                conn.commit()
                logger.debug(f"Cleared market context for {market_code}")
                return True

        except Exception as e:
            logger.error(f"Error clearing market context for {market_code}: {e}")
            return False

    def clear_all_contexts(self) -> bool:
        """Clear all cached market contexts.

        Returns:
            True if successful, False otherwise
        """
        if not self._check_dependencies():
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM market_context_cache")
                conn.commit()
                logger.info("Cleared all market contexts from cache")
                return True

        except Exception as e:
            logger.error(f"Error clearing all market contexts: {e}")
            return False

    # ============================================================================
    # STATISTICS
    # ============================================================================

    def get_stats(self) -> dict:
        """Get statistics about market context cache.

        Returns:
            Dictionary with cache statistics
        """
        if not self._check_dependencies():
            return {
                "cached_contexts": 0,
                "ttl_seconds": self.get_ttl_seconds(),
                "last_update": None
            }

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Count cached contexts
                cursor.execute("SELECT COUNT(*) FROM market_context_cache")
                count = cursor.fetchone()[0]

                # Get last update time from metadata
                last_update = None
                if self.metadata_manager:
                    metadata_type = self.get_data_update_metadata_type()
                    last_update = self.metadata_manager.get_last_update_time(metadata_type)

                return {
                    "cached_contexts": count,
                    "ttl_seconds": self.get_ttl_seconds(),
                    "last_update": last_update.isoformat() if last_update else None
                }

        except Exception as e:
            logger.error(f"Error getting market context stats: {e}")
            return {
                "cached_contexts": 0,
                "ttl_seconds": self.get_ttl_seconds(),
                "last_update": None,
                "error": str(e)
            }
