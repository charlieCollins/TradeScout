"""Base database manager for unified database operations with TTL-based refresh logic."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, Callable, Dict
from models.data_update_metadata import DataUpdateMetadataType

logger = logging.getLogger(__name__)


class BaseManager(ABC):
    """Abstract base class for all database managers.

    Database managers handle:
    - Direct database read/write operations for their entity type
    - TTL-based refresh logic (when to fetch fresh data)
    - Metadata tracking for operation-level cache validation

    Database managers do NOT:
    - Make API calls (that's handled by api/provider classes)
    - Handle authentication or rate limiting (that's API provider responsibility)

    The fetch_fn callback is provided by the orchestration layer (DataService)
    which coordinates between database managers and API providers.
    """

    def __init__(self, db_manager, metadata_manager):
        """Initialize with database manager and metadata manager.

        Args:
            db_manager: Database manager instance for SQLite operations
            metadata_manager: DataUpdateMetadataManager for TTL tracking and update recording
        """
        self.db_manager = db_manager
        self.metadata_manager = metadata_manager

    # ============================================================================
    # PUBLIC INTERFACE
    # ============================================================================

    def get_or_fetch(
        self,
        key: str,
        fetch_fn: Callable,
        force_refresh: bool = False
    ) -> Optional[Any]:
        """Get data from database or fetch fresh data if stale.

        This is the main entry point for data access. It decides whether to:
        1. Force refresh (if force_refresh=True): Always call fetch_fn
        2. Use cached data (if TTL valid): Read from database
        3. Fetch fresh data (if TTL expired): Call fetch_fn and store result

        Args:
            key: Entity identifier (e.g., symbol, date, etc.)
            fetch_fn: Callback function that fetches fresh data (provided by orchestration layer)
            force_refresh: If True, bypass TTL check and always fetch fresh data

        Returns:
            Entity object or None if error
        """
        # Force refresh bypasses all TTL logic
        if force_refresh:
            logger.debug(
                f"Force refresh requested for {self.get_data_update_metadata_type().value}, "
                f"fetching fresh data for key {key}"
            )
            fresh_data = fetch_fn()
            if fresh_data:
                self.set_entity_to_database(key, fresh_data)
            return fresh_data

        # Normal TTL-based logic
        if self._is_data_stale():
            logger.debug(
                f"Data is stale for {self.get_data_update_metadata_type().value}, "
                f"fetching fresh data for key {key}"
            )
            # TTL expired - fetch fresh data
            fresh_data = fetch_fn()
            if fresh_data:
                # Store the fresh data to database
                self.set_entity_to_database(key, fresh_data)
                # Record the update in metadata for TTL tracking
                self._record_update()
            return fresh_data
        else:
            logger.debug(
                f"Data is fresh for {self.get_data_update_metadata_type().value}, "
                f"getting key {key} from database"
            )
            # TTL still valid - get from database without fetching
            return self.get_entity_from_database(key)

    def get_stats(self) -> Dict[str, Any]:
        """Get database manager statistics. Optional to override.

        Returns:
            Dictionary with manager statistics
        """
        return {
            "metadata_type": self.get_data_update_metadata_type().value,
            "ttl_seconds": self.get_ttl_seconds()
        }

    # ============================================================================
    # ABSTRACT INTERFACE - Must be implemented by subclasses
    # ============================================================================

    @abstractmethod
    def get_data_update_metadata_type(self) -> DataUpdateMetadataType:
        """Get the data update metadata type for TTL validation.

        Returns:
            DataUpdateMetadataType enum value
        """
        pass

    @abstractmethod
    def get_ttl_seconds(self) -> int:
        """Get TTL in seconds for this data type.

        Returns:
            TTL value in seconds
        """
        pass

    @abstractmethod
    def get_entity_from_database(self, key: str) -> Optional[Any]:
        """Get entity from database storage.

        Args:
            key: Entity identifier

        Returns:
            Entity object or None if not found
        """
        pass

    @abstractmethod
    def set_entity_to_database(self, key: str, entity: Any) -> bool:
        """Store entity to database storage.

        Args:
            key: Entity identifier
            entity: Entity object to store

        Returns:
            True if successful, False otherwise
        """
        pass

    # ============================================================================
    # PRIVATE HELPERS
    # ============================================================================

    def _is_data_stale(self) -> bool:
        """Check if data is stale using operation-level TTL validation.

        Returns:
            True if data is stale and needs refresh
        """
        if not self._check_dependencies():
            return True  # No dependencies, always refresh

        metadata_type = self.get_data_update_metadata_type()
        ttl_seconds = self.get_ttl_seconds()

        # Use metadata_manager for TTL validation
        if self.metadata_manager:
            return self.metadata_manager.is_stale(metadata_type, ttl_seconds)

        # No metadata manager - always refresh
        logger.warning(f"No metadata_manager available for {metadata_type}, assuming stale")
        return True

    def _record_update(self) -> None:
        """Record that a data update occurred for this entity type.

        This updates the metadata timestamp, enabling future TTL checks.
        """
        if self.metadata_manager:
            metadata_type = self.get_data_update_metadata_type()
            self.metadata_manager.record_update(metadata_type)
        else:
            logger.debug("No metadata_manager available to record update")

    def _check_dependencies(self) -> bool:
        """Check if required dependencies are available.

        Returns:
            True if dependencies are available
        """
        if not self.db_manager:
            logger.warning("Database manager not available")
            return False

        return True

    # ============================================================================
    # UTILITY METHODS - Helpers for common database operations
    # ============================================================================

    def _safe_execute_query(self, query: str, params: tuple = ()) -> Optional[Any]:
        """Safely execute a database query.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            Query result or None if error
        """
        if not self.db_manager:
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Database query error: {e}")
            return None

    def _safe_execute_update(self, query: str, params: tuple = ()) -> bool:
        """Safely execute a database update.

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            True if successful, False otherwise
        """
        if not self.db_manager:
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(query, params)
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Database update error: {e}")
            return False