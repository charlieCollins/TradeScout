"""Market snapshot caching using asset_prices table and data_update_metadata."""

import logging
from typing import Optional, Dict, Any, Callable
from datetime import datetime
from models.snapshot import MarketSnapshot
from config.ttl_config import MARKET_SNAPSHOT_TTL_MINUTES
from .base_cache_manager import BaseCacheManager

logger = logging.getLogger(__name__)


class MarketSnapshotCache(BaseCacheManager):
    """Cache market snapshot operations using asset_prices table with operation-level TTL validation."""

    def _get_operation_type(self) -> str:
        """Get the operation type for TTL validation."""
        return "market_snapshots"

    def _get_ttl_seconds(self) -> int:
        """Get TTL in seconds for this cache type."""
        return MARKET_SNAPSHOT_TTL_MINUTES * 60

    def get_or_fetch(self, key: str, fetch_fn: Callable, **kwargs) -> Optional[MarketSnapshot]:
        """Get market snapshot, fetching fresh if operation-level cache is stale.

        Args:
            key: Not used for market snapshots (bulk operation)
            fetch_fn: Function to fetch fresh MarketSnapshot (stores to asset_prices)

        Returns:
            MarketSnapshot object or None if error
        """
        if self._is_cache_stale():
            logger.debug("Market snapshot operations are stale, fetching fresh data")

            # Fetch fresh data - this should update asset_prices table for multiple symbols
            fresh_snapshot = fetch_fn()
            if fresh_snapshot:
                return fresh_snapshot
            else:
                logger.error("Failed to fetch fresh market snapshot")
                return None
        else:
            logger.debug("Market snapshot operations are fresh")
            # Operations are fresh, so data should be current
            # The fetch_fn might construct MarketSnapshot from existing data or still fetch fresh
            return fetch_fn()

    def get(self, key: str, **kwargs) -> Optional[MarketSnapshot]:
        """Not applicable for market snapshots - data is in asset_prices table."""
        logger.debug("get() method not used for market snapshots - data stored in asset_prices")
        return None

    def set(self, key: str, data: MarketSnapshot, **kwargs):
        """Not applicable for market snapshots - data stored in asset_prices table."""
        logger.debug("set() method not used for market snapshots - data stored in asset_prices")

    def invalidate(self, key: str = None):
        """For market snapshots, invalidation is handled via operation-level TTL."""
        logger.info("Market snapshot cache invalidation relies on operation-level TTL validation")

    def clear_all(self):
        """For market snapshots, clearing relies on operation-level TTL."""
        logger.info("Market snapshot cache clearing relies on operation-level TTL validation")

    def get_stats(self) -> Dict[str, Any]:
        """Get market snapshot cache statistics."""
        return {
            "operation_type": self._get_operation_type(),
            "ttl_minutes": MARKET_SNAPSHOT_TTL_MINUTES,
            "note": "Market snapshots store data in asset_prices table"
        }