"""Asset prices caching using database and data_update_metadata."""

import logging
from typing import Optional, Dict, Any, Callable, List
from datetime import datetime
from models.price import AssetPrice
from config.ttl_config import ASSET_PRICE_TTL_MINUTES
from .base_cache_manager import BaseCacheManager

logger = logging.getLogger(__name__)


class AssetPricesCache(BaseCacheManager):
    """Cache AssetPrice objects using existing asset_prices table with operation-level TTL validation."""

    def _get_operation_type(self) -> str:
        """Get the operation type for TTL validation."""
        return "asset_prices"

    def _get_ttl_seconds(self) -> int:
        """Get TTL in seconds for this cache type."""
        return ASSET_PRICE_TTL_MINUTES * 60

    def get_or_fetch(self, key: str, fetch_fn: Callable, **kwargs) -> Optional[AssetPrice]:
        """Get cached AssetPrice or fetch fresh data.

        Args:
            key: Asset ID as string
            fetch_fn: Function to fetch fresh AssetPrice

        Returns:
            AssetPrice object or None if error
        """
        asset_id = int(key)

        if self._is_cache_stale():
            logger.debug(f"Asset prices cache is stale, fetching fresh data for asset_id {asset_id}")

            fresh_price = fetch_fn()
            if fresh_price:
                # Note: fetch_fn should handle storing to asset_prices table
                return fresh_price
            else:
                logger.error(f"Failed to fetch fresh asset price for asset_id {asset_id}")
                return None
        else:
            logger.debug(f"Using cached asset price for asset_id {asset_id}")
            return self.get(key)

    def get(self, key: str, **kwargs) -> Optional[AssetPrice]:
        """Get cached AssetPrice without TTL check."""
        asset_id = int(key)

        if not self._check_dependencies():
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                # Get most recent price record for this asset
                cursor.execute("""
                    SELECT
                        id, asset_id, symbol, provider_id, provider_updated_at, trade_date, updated_at,
                        prevday_open, prevday_high, prevday_low, prevday_close, prevday_volume, prevday_vwap,
                        day_open, day_high, day_low, day_close, day_volume, day_vwap,
                        min_timestamp, min_open, min_high, min_low, min_close, min_volume, min_vwap,
                        min_accumulated_volume, min_num_trades
                    FROM asset_prices
                    WHERE asset_id = ?
                    ORDER BY provider_updated_at DESC, updated_at DESC
                    LIMIT 1
                """, (asset_id,))

                row = cursor.fetchone()
                if row:
                    return AssetPrice(*row)
                else:
                    logger.debug(f"No cached asset price found for asset_id {asset_id}")
                    return None

        except Exception as e:
            logger.error(f"Error retrieving cached asset price for asset_id {asset_id}: {e}")
            return None

    def set(self, key: str, data: AssetPrice, **kwargs):
        """Store AssetPrice in existing asset_prices table.

        Note: This method is typically not needed since DataProvider methods
        that fetch fresh price data already store to asset_prices table.
        """
        # The DataProvider's price fetching methods already handle storage
        # This is mainly for interface compliance
        logger.debug(f"AssetPrice storage handled by DataProvider methods for asset_id {key}")

    def invalidate(self, key: str = None):
        """Invalidate cached asset prices.

        For asset prices, we rely on operation-level TTL validation rather than
        individual record invalidation, since price data updates are batch operations.
        """
        if key:
            logger.info(f"Asset price invalidation for individual assets not implemented - use force refresh")
        else:
            logger.info("Asset price cache invalidation relies on operation-level TTL validation")

    def clear_all(self):
        """Clear all cached asset prices."""
        if not self._check_dependencies():
            return

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM asset_prices")
                conn.commit()
                logger.info("Cleared all asset prices")
        except Exception as e:
            logger.error(f"Error clearing asset prices: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get asset prices cache statistics."""
        if not self._check_dependencies():
            return {}

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Count total price records
                cursor.execute("SELECT COUNT(*) FROM asset_prices")
                total_records = cursor.fetchone()[0]

                # Count unique assets with price data
                cursor.execute("SELECT COUNT(DISTINCT asset_id) FROM asset_prices")
                unique_assets = cursor.fetchone()[0]

                # Get most recent update time
                cursor.execute("SELECT MAX(updated_at) FROM asset_prices")
                last_update = cursor.fetchone()[0]

                return {
                    "total_price_records": total_records,
                    "unique_assets": unique_assets,
                    "last_update": last_update,
                    "ttl_minutes": ASSET_PRICE_TTL_MINUTES,
                    "operation_type": self._get_operation_type()
                }

        except Exception as e:
            logger.error(f"Error getting asset prices cache stats: {e}")
            return {}

    def is_fresh(self, asset_id: int) -> bool:
        """Check if asset price data is fresh for a specific asset.

        This checks both operation-level staleness and individual asset freshness.

        Args:
            asset_id: Asset ID to check

        Returns:
            True if data is fresh
        """
        # First check operation-level staleness
        if self._is_cache_stale():
            return False

        # Then check if this specific asset has recent data
        if not self._check_dependencies():
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT updated_at FROM asset_prices
                    WHERE asset_id = ?
                    ORDER BY updated_at DESC
                    LIMIT 1
                """, (asset_id,))

                row = cursor.fetchone()
                if not row:
                    return False

                last_update = datetime.fromisoformat(row[0])
                elapsed_seconds = (datetime.now() - last_update).total_seconds()
                return elapsed_seconds <= self._get_ttl_seconds()

        except Exception as e:
            logger.error(f"Error checking asset price freshness for asset_id {asset_id}: {e}")
            return False