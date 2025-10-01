"""Data update metadata manager for tracking operation timestamps and staleness."""

import logging
from typing import Optional
from datetime import datetime, timedelta
from models.data_update_metadata import DataUpdateMetadataType

logger = logging.getLogger(__name__)


class DataUpdateMetadataManager:
    """Manages data update metadata tracking for TTL-based staleness detection.

    This manager handles:
    - Recording when data operations complete
    - Checking if data is stale based on TTL
    - Querying last update timestamps

    It does NOT handle complex operation tracking (progress, stats, etc.) -
    that's still handled by DataUpdateTracker for bootstrap operations.
    """

    def __init__(self, db_manager):
        """Initialize with database manager.

        Args:
            db_manager: Database manager for SQLite operations
        """
        self.db_manager = db_manager

    # ============================================================================
    # RECORD UPDATES
    # ============================================================================

    def record_update(
        self,
        operation_type: DataUpdateMetadataType,
        operation_subtype: str = "fetch"
    ) -> bool:
        """Record that a data update operation completed.

        This inserts/updates a metadata record with the current timestamp,
        enabling future TTL-based staleness checks.

        Args:
            operation_type: Type of operation (e.g., TICKER_SNAPSHOTS)
            operation_subtype: Subtype of operation (default: "fetch")

        Returns:
            True if recorded successfully, False otherwise
        """
        if not self.db_manager:
            logger.warning("Database manager not available")
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Use INSERT OR REPLACE to handle both new and existing records
                cursor.execute("""
                    INSERT OR REPLACE INTO data_update_metadata (
                        operation_type,
                        operation_subtype,
                        started_at,
                        completed_at,
                        status,
                        total_items,
                        processed_items
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    operation_type.value,
                    operation_subtype,
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                    "completed",
                    1,  # Simple operations process 1 "item"
                    1
                ))

                conn.commit()
                logger.debug(f"Recorded update for {operation_type.value}/{operation_subtype}")
                return True

        except Exception as e:
            logger.error(f"Failed to record update for {operation_type.value}: {e}")
            return False

    # ============================================================================
    # STALENESS CHECKS
    # ============================================================================

    def is_stale(
        self,
        operation_type: DataUpdateMetadataType,
        ttl_seconds: int
    ) -> bool:
        """Check if data is stale based on TTL.

        Args:
            operation_type: Type of operation to check
            ttl_seconds: Time-to-live in seconds

        Returns:
            True if data is stale (needs refresh), False if fresh
        """
        last_update = self.get_last_update_time(operation_type)

        if not last_update:
            # No record found - data is stale
            logger.debug(f"No metadata found for {operation_type.value}, considering stale")
            return True

        # Calculate staleness
        age = datetime.now() - last_update
        is_stale = age.total_seconds() > ttl_seconds

        if is_stale:
            logger.debug(
                f"Data for {operation_type.value} is stale "
                f"(age: {age.total_seconds():.0f}s, TTL: {ttl_seconds}s)"
            )
        else:
            logger.debug(
                f"Data for {operation_type.value} is fresh "
                f"(age: {age.total_seconds():.0f}s, TTL: {ttl_seconds}s)"
            )

        return is_stale

    def get_last_update_time(
        self,
        operation_type: DataUpdateMetadataType
    ) -> Optional[datetime]:
        """Get the timestamp of the last successful update.

        Args:
            operation_type: Type of operation to query

        Returns:
            Datetime of last update, or None if no record found
        """
        if not self.db_manager:
            logger.warning("Database manager not available")
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Get most recent completed operation of this type
                cursor.execute("""
                    SELECT completed_at
                    FROM data_update_metadata
                    WHERE operation_type = ?
                      AND status = 'completed'
                      AND completed_at IS NOT NULL
                    ORDER BY completed_at DESC
                    LIMIT 1
                """, (operation_type.value,))

                result = cursor.fetchone()

                if result and result[0]:
                    # Parse ISO format timestamp
                    return datetime.fromisoformat(result[0])

                return None

        except Exception as e:
            logger.error(f"Failed to get last update time for {operation_type.value}: {e}")
            return None

    # ============================================================================
    # STATISTICS
    # ============================================================================

    def get_update_stats(self, operation_type: DataUpdateMetadataType) -> dict:
        """Get statistics about updates for an operation type.

        Args:
            operation_type: Type of operation to query

        Returns:
            Dictionary with update statistics
        """
        if not self.db_manager:
            return {"error": "Database manager not available"}

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Count total updates
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM data_update_metadata
                    WHERE operation_type = ?
                      AND status = 'completed'
                """, (operation_type.value,))

                total_updates = cursor.fetchone()[0]

                # Get last update time
                last_update = self.get_last_update_time(operation_type)

                return {
                    "operation_type": operation_type.value,
                    "total_updates": total_updates,
                    "last_update": last_update.isoformat() if last_update else None,
                    "age_seconds": (datetime.now() - last_update).total_seconds() if last_update else None
                }

        except Exception as e:
            logger.error(f"Failed to get update stats for {operation_type.value}: {e}")
            return {"error": str(e)}