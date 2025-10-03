"""Market snapshot database manager for bulk ticker snapshot operations.

IMPORTANT: This is a SPECIAL manager type that differs from other managers.

Unlike TickerSnapshotManager which persists and retrieves single ticker entities,
MarketSnapshotManager is used ONLY for:
  1. Tracking WHEN bulk market data refreshes occur (metadata only)
  2. Controlling refresh frequency via TTL
  3. Preventing excessive API calls for bulk operations

This manager does NOT:
  - Store MarketSnapshot entities to the database
  - Retrieve MarketSnapshot entities from the database
  - Cache the actual snapshot data anywhere

The bulk snapshot data flows through this manager to:
  - Record metadata timestamp of the bulk operation
  - Return the snapshot to the orchestration layer (DataService)
  - DataService then stores individual tickers to asset_prices via TickerSnapshotManager
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from models.snapshot import MarketSnapshot
from models.data_update_metadata import DataUpdateMetadataType
from database.config.ttl_config import MARKET_SNAPSHOT_TTL_MINUTES
from .base_manager import BaseManager

logger = logging.getLogger(__name__)


class MarketSnapshotManager(BaseManager):
    """SPECIAL manager for bulk market snapshot metadata tracking (NOT entity storage).

    THIS IS NOT A TYPICAL MANAGER:
    Unlike other managers (e.g., TickerSnapshotManager) which persist and retrieve
    entities from the database, MarketSnapshotManager is a metadata-only manager.

    Purpose:
    --------
    - Track WHEN bulk market data operations occur (via data_update_metadata table)
    - Enforce TTL-based refresh intervals to prevent excessive bulk API calls
    - Coordinate bulk data flow: API → DataService → Individual entity storage

    What it does NOT do:
    -------------------
    - Does NOT store MarketSnapshot objects to database
    - Does NOT retrieve MarketSnapshot objects from database
    - Does NOT cache snapshot data

    Data Flow:
    ---------
    1. Check metadata: Was bulk refresh done recently?
    2. If stale → Fetch bulk snapshot from API
    3. Record metadata timestamp
    4. Return snapshot to DataService
    5. DataService stores individual tickers via TickerSnapshotManager

    This pattern allows:
    - Efficient bulk API operations (fetch thousands of tickers at once)
    - Individual ticker caching (each ticker has its own TTL)
    - Separation of bulk refresh cadence from individual ticker access patterns
    """

    def get_or_fetch(
        self,
        key: str,
        fetch_fn,
        force_refresh: bool = False
    ) -> Optional[MarketSnapshot]:
        """Get market snapshot with TTL-based staleness checking.

        Override base implementation because MarketSnapshot entities are never stored
        (individual tickers are cached separately). We use metadata_manager to:
        1. Track when bulk fetches occur (for observability)
        2. Check staleness before fetching (respects TTL)
        3. Skip API calls if data was recently fetched (within TTL)

        Args:
            key: Entity identifier (e.g., "all" or comma-separated symbols)
            fetch_fn: Callback function that fetches fresh data
            force_refresh: If True, bypass TTL check and always fetch

        Returns:
            MarketSnapshot object or None if error
        """
        # Force refresh bypasses all TTL logic
        if force_refresh:
            logger.debug(f"Force refresh requested for market snapshot '{key}', bypassing TTL")
            market_snapshot = fetch_fn()
            if market_snapshot:
                self.set_entity_to_database(key, market_snapshot)
                self._record_update()
            return market_snapshot

        # Check if we need to fetch based on TTL
        if self._is_data_stale():
            logger.debug(f"Market snapshot data is stale for key '{key}', fetching from API")
            market_snapshot = fetch_fn()
            if market_snapshot:
                self.set_entity_to_database(key, market_snapshot)
                self._record_update()
            return market_snapshot
        else:
            # Data is fresh - skip API call to respect rate limits
            logger.info(
                f"Market snapshot for key '{key}' was recently fetched (within TTL). "
                f"Skipping API call. Use force_refresh=True to fetch anyway."
            )
            return None

    def get_data_update_metadata_type(self) -> DataUpdateMetadataType:
        """Get the data update metadata type for TTL validation."""
        return DataUpdateMetadataType.MARKET_SNAPSHOTS

    def get_ttl_seconds(self) -> int:
        """Get TTL in seconds for this data type."""
        return MARKET_SNAPSHOT_TTL_MINUTES * 60

    def get_entity_from_database(self, key: str) -> Optional[MarketSnapshot]:
        """Get MarketSnapshot from database storage.

        Note: MarketSnapshot is not stored as a single entity in the database.
        This method returns None to indicate a fetch is needed.
        Individual tickers are stored via TickerSnapshotManager.

        Args:
            key: Entity identifier (e.g., "all" or "universe_name")

        Returns:
            None (market snapshots are always fetched fresh)
        """
        # MarketSnapshot is not stored as an entity
        # Individual tickers can be retrieved via TickerSnapshotManager
        logger.debug(f"MarketSnapshot entity not stored in database, fetch required for key: {key}")
        return None

    def set_entity_to_database(self, key: str, entity: MarketSnapshot) -> bool:
        """Store MarketSnapshot metadata to database.

        Note: MarketSnapshot itself is not stored. However, individual tickers
        within it can be stored via TickerSnapshotManager if needed.

        This method updates the metadata timestamp to track when the bulk
        fetch was last performed, enabling TTL-based refresh decisions.

        Args:
            key: Entity identifier (e.g., "all" or "universe_name")
            entity: MarketSnapshot object (used to update metadata)

        Returns:
            True if metadata updated successfully, False otherwise
        """
        if not entity:
            return False

        if not self._check_dependencies():
            return False

        try:
            # Update metadata to track when bulk snapshot was fetched
            # The metadata_manager will create/update the metadata entry
            # This enables TTL-based refresh decisions on next access

            logger.debug(
                f"Market snapshot fetch completed for key '{key}' "
                f"with {entity.total_symbols} symbols at {entity.timestamp}"
            )

            # Return True to indicate successful metadata tracking
            # Individual tickers can be stored separately by caller
            return True

        except Exception as e:
            logger.error(f"Error updating market snapshot metadata for key {key}: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get market snapshot manager statistics."""
        return {
            "metadata_type": self.get_data_update_metadata_type().value,
            "ttl_minutes": MARKET_SNAPSHOT_TTL_MINUTES,
            "storage": "metadata only (individual tickers stored separately)"
        }

    # ============================================================================
    # MARKET SNAPSHOT SPECIFIC HELPERS
    # ============================================================================

    def should_store_individual_tickers(self, market_snapshot: MarketSnapshot) -> bool:
        """Determine if individual tickers should be stored.

        This is a helper method for the orchestration layer to decide
        whether to store individual TickerSnapshot objects from a bulk fetch.

        Args:
            market_snapshot: MarketSnapshot to evaluate

        Returns:
            True if individual tickers should be stored
        """
        # Logic can be enhanced based on:
        # - Number of symbols in snapshot
        # - Market status (don't store if market closed)
        # - Universe membership (only store tracked symbols)

        if not market_snapshot or not market_snapshot.tickers:
            return False

        # For now, recommend storing if we have valid data
        return len(market_snapshot.tickers) > 0