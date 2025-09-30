"""Base cache manager for unified caching interface."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional, Callable, Dict, Union
from models.data_update_metadata import DataUpdateMetadataType

logger = logging.getLogger(__name__)


class BaseCacheManager(ABC):
    """Abstract base class for all cache managers providing unified caching interface."""

    def __init__(self, db_manager, update_tracker):
        """Initialize with database manager and update tracker.

        Args:
            db_manager: Database manager instance
            update_tracker: Data update tracker for TTL validation
        """
        self.db_manager = db_manager
        self.update_tracker = update_tracker

    # ============================================================================
    # ABSTRACT INTERFACE - Must be implemented by subclasses
    # ============================================================================

    def get_or_fetch(self, key: str, fetch_fn: Callable, **kwargs) -> Optional[Any]:
        """Get cached data or fetch fresh data if stale.

        Args:
            key: Cache key identifier
            fetch_fn: Function to fetch fresh data (makes API call)
            **kwargs: Additional arguments

        Returns:
            Cached or fresh data, None if error
        """
        if self._is_cache_stale():
            logger.debug(f"Cache is stale for {self.get_data_update_metadata_type().value}, fetching fresh data for key {key}")
            # TTL expired - fetch fresh data from API
            fresh_data = fetch_fn()
            if fresh_data:
                # Store the fresh data to database
                self.set_entity_to_database(key, fresh_data)
            return fresh_data
        else:
            logger.debug(f"Cache is fresh for {self.get_data_update_metadata_type().value}, getting key {key} from database")
            # TTL still valid - get from database without API call
            return self.get_entity_from_database(key)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics. Optional to override.

        Returns:
            Dictionary with cache statistics
        """
        return {
            "metadata_type": self.get_data_update_metadata_type().value,
            "ttl_seconds": self.get_ttl_seconds()
        }

    # ============================================================================
    # OPERATION-LEVEL TTL VALIDATION (using data_update_metadata)
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
        """Get TTL in seconds for this cache type.

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

    def _is_cache_stale(self) -> bool:
        """Check if cache is stale using operation-level TTL validation.

        Returns:
            True if cache is stale and needs refresh
        """
        if not self._check_dependencies():
            return True  # No dependencies, always refresh

        metadata_type = self.get_data_update_metadata_type()
        ttl_seconds = self.get_ttl_seconds()

        return self.update_tracker.is_data_stale(metadata_type.value, ttl_seconds)

    # ============================================================================
    # UTILITY METHODS
    # ============================================================================

    def _check_dependencies(self) -> bool:
        """Check if required dependencies are available.

        Returns:
            True if dependencies are available
        """
        if not self.db_manager:
            logger.warning("Database manager not available")
            return False

        if not self.update_tracker:
            logger.warning("Update tracker not available")
            return False

        return True

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

