"""Data update tracking service for TradeScout operations."""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from database.config.ttl_config import FUNDAMENTALS_TTL_HOURS
from models.data_update_metadata import DataUpdateMetadata, OperationStatus

logger = logging.getLogger(__name__)


class DataUpdateTracker:
    """Track data update operations across TradeScout."""

    def __init__(self, data_provider):
        """Initialize with data provider."""
        self.data_provider = data_provider

    def start_operation(self, operation_type: str, operation_subtype: Optional[str] = None,
                       operation_params: Optional[Dict[str, Any]] = None,
                       total_items: Optional[int] = None) -> int:
        """Start tracking a data operation.

        Args:
            operation_type: Type of operation ('fundamentals', 'tickers', 'snapshot', 'universe')
            operation_subtype: Subtype ('bootstrap', 'refresh', 'single_symbol')
            operation_params: Parameters used for the operation
            total_items: Expected total number of items to process

        Returns:
            Operation ID for tracking progress
        """
        try:
            # Create metadata object
            metadata = DataUpdateMetadata(
                operation_type=operation_type,
                operation_subtype=operation_subtype,
                started_at=datetime.now(),
                operation_params=operation_params,
                total_items=total_items,
                status=OperationStatus.RUNNING
            )

            # Convert to dict for database
            data = metadata.to_dict()

            operation_id = self.data_provider.execute_metadata_update("""
                INSERT INTO data_update_metadata
                (operation_type, operation_subtype, started_at, operation_params, total_items, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (data['operation_type'], data['operation_subtype'], data['started_at'],
                  data['operation_params'], data['total_items'], data['status']))

            logger.debug(f"Started tracking operation {metadata.get_operation_name()} (ID: {operation_id})")
            return operation_id

        except Exception as e:
            logger.error(f"Failed to start operation tracking: {e}")
            raise

    def update_progress(self, operation_id: int, processed_items: Optional[int] = None,
                       api_calls_made: Optional[int] = None, stats: Optional[Dict[str, Any]] = None):
        """Update progress of an ongoing operation.

        Args:
            operation_id: ID of the operation to update
            processed_items: Number of items processed so far
            api_calls_made: Number of API calls made
            stats: Current statistics dictionary
        """
        try:
            update_fields = []
            update_values = []

            if processed_items is not None:
                update_fields.append("processed_items = ?")
                update_values.append(processed_items)

            if api_calls_made is not None:
                update_fields.append("api_calls_made = ?")
                update_values.append(api_calls_made)

            if stats is not None:
                update_fields.append("stats = ?")
                update_values.append(json.dumps(stats))

            if update_fields:
                update_values.append(operation_id)
                query = f"UPDATE data_update_metadata SET {', '.join(update_fields)} WHERE id = ?"
                self.data_provider.execute_metadata_update(query, tuple(update_values))

        except Exception as e:
            logger.error(f"Failed to update operation progress: {e}")

    def complete_operation(self, operation_id: int, final_stats: Dict[str, Any],
                          status: str = 'completed'):
        """Mark an operation as completed.

        Args:
            operation_id: ID of the operation to complete
            final_stats: Final statistics for the operation
            status: Final status ('completed', 'partial')
        """
        try:
            # Create metadata object for completion
            metadata = DataUpdateMetadata(
                operation_type="",  # Placeholder - not needed for update
                completed_at=datetime.now(),
                status=OperationStatus(status),
                stats=final_stats
            )

            data = metadata.to_dict()

            self.data_provider.execute_metadata_update("""
                UPDATE data_update_metadata
                SET completed_at = ?, status = ?, stats = ?
                WHERE id = ?
            """, (data['completed_at'], data['status'], data['stats'], operation_id))

            logger.info(f"Completed operation {operation_id} with status: {status}")

        except Exception as e:
            logger.error(f"Failed to complete operation: {e}")

    def fail_operation(self, operation_id: int, error_message: str):
        """Mark an operation as failed.

        Args:
            operation_id: ID of the operation that failed
            error_message: Error message describing the failure
        """
        try:
            # Create metadata object for failure
            metadata = DataUpdateMetadata(
                operation_type="",  # Placeholder - not needed for update
                completed_at=datetime.now(),
                status=OperationStatus.FAILED,
                error_message=error_message
            )

            data = metadata.to_dict()

            self.data_provider.execute_metadata_update("""
                UPDATE data_update_metadata
                SET completed_at = ?, status = ?, error_message = ?
                WHERE id = ?
            """, (data['completed_at'], data['status'], data['error_message'], operation_id))

            logger.error(f"Failed operation {operation_id}: {error_message}")

        except Exception as e:
            logger.error(f"Failed to mark operation as failed: {e}")

    def get_last_update(self, operation_type: str, operation_subtype: Optional[str] = None) -> Optional[datetime]:
        """Get the timestamp of the last successful update for an operation type.

        Args:
            operation_type: Type of operation to check
            operation_subtype: Optional subtype to filter by

        Returns:
            Datetime of last successful completion or None if never run
        """
        try:
            if operation_subtype:
                results = self.data_provider.execute_metadata_query("""
                    SELECT * FROM data_update_metadata
                    WHERE operation_type = ? AND operation_subtype = ?
                    AND status IN ('completed', 'partial')
                    ORDER BY completed_at DESC LIMIT 1
                """, (operation_type, operation_subtype))
            else:
                results = self.data_provider.execute_metadata_query("""
                    SELECT * FROM data_update_metadata
                    WHERE operation_type = ? AND status IN ('completed', 'partial')
                    ORDER BY completed_at DESC LIMIT 1
                """, (operation_type,))

            if results:
                metadata = DataUpdateMetadata.from_dict(results[0])
                return metadata.completed_at
            return None

        except Exception as e:
            logger.error(f"Failed to get last update metadata: {e}")
            return None

    def get_operation_history(self, operation_type: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Get history of operations.

        Args:
            operation_type: Optional operation type to filter by
            limit: Maximum number of records to return

        Returns:
            List of operation records as dictionaries
        """
        try:
            if operation_type:
                results = self.data_provider.execute_metadata_query("""
                    SELECT * FROM data_update_metadata
                    WHERE operation_type = ?
                    ORDER BY started_at DESC LIMIT ?
                """, (operation_type, limit))
            else:
                results = self.data_provider.execute_metadata_query("""
                    SELECT * FROM data_update_metadata
                    ORDER BY started_at DESC LIMIT ?
                """, (limit,))

            # Convert to metadata objects then back to dicts for backward compatibility
            history = []
            for row in results:
                metadata = DataUpdateMetadata.from_dict(row)
                # Convert back to dict format expected by callers
                record = {
                    'operation_type': metadata.operation_type,
                    'operation_subtype': metadata.operation_subtype,
                    'started_at': metadata.started_at.isoformat() if metadata.started_at else None,
                    'completed_at': metadata.completed_at.isoformat() if metadata.completed_at else None,
                    'status': metadata.status.value,
                    'stats': metadata.stats or {},
                    'api_calls_made': metadata.api_calls_made,
                    'total_items': metadata.total_items,
                    'processed_items': metadata.processed_items
                }
                history.append(record)
            return history

        except Exception as e:
            logger.error(f"Failed to get operation history: {e}")
            return []

    def get_current_running_operations(self) -> List[Dict[str, Any]]:
        """Get list of currently running operations.

        Returns:
            List of running operation records as dictionaries
        """
        try:
            results = self.data_provider.execute_metadata_query("""
                SELECT * FROM data_update_metadata
                WHERE status = 'running'
                ORDER BY started_at DESC
            """)

            # Convert to metadata objects then back to dicts for backward compatibility
            running_ops = []
            for row in results:
                metadata = DataUpdateMetadata.from_dict(row)
                # Convert back to dict format expected by callers
                record = {
                    'id': metadata.id,
                    'operation_type': metadata.operation_type,
                    'operation_subtype': metadata.operation_subtype,
                    'started_at': metadata.started_at.isoformat() if metadata.started_at else None,
                    'total_items': metadata.total_items,
                    'processed_items': metadata.processed_items,
                    'api_calls_made': metadata.api_calls_made
                }
                running_ops.append(record)
            return running_ops

        except Exception as e:
            logger.error(f"Failed to get running operations: {e}")
            return []

    def is_data_stale(self, operation_type: str, max_age_hours: int = FUNDAMENTALS_TTL_HOURS) -> bool:
        """Check if data is stale based on last update time.

        Args:
            operation_type: Type of operation to check
            max_age_hours: Maximum age in hours before considering stale (default: FUNDAMENTALS_TTL_HOURS = 1 week)

        Returns:
            True if data is stale or never updated, False if fresh
        """
        last_update = self.get_last_update(operation_type)
        if not last_update:
            return True  # Never updated = stale

        age_hours = (datetime.now() - last_update).total_seconds() / 3600
        return age_hours > max_age_hours

    def get_operation_summary(self) -> Dict[str, Any]:
        """Get summary of all operation types and their last update times.

        Returns:
            Dictionary with operation types and their status
        """
        try:
            results = self.data_provider.execute_metadata_query("""
                SELECT operation_type,
                       MAX(completed_at) as last_completed,
                       COUNT(*) as total_runs,
                       SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful_runs
                FROM data_update_metadata
                WHERE status IN ('completed', 'partial', 'failed')
                GROUP BY operation_type
                ORDER BY operation_type
            """)

            summary = {}

            for row in results:
                op_type = row['operation_type']
                last_completed = row['last_completed']
                total_runs = row['total_runs']
                successful_runs = row['successful_runs']

                summary[op_type] = {
                    'last_completed': last_completed,
                    'total_runs': total_runs,
                    'successful_runs': successful_runs,
                    'success_rate': successful_runs / total_runs if total_runs > 0 else 0,
                    'is_stale': self.is_data_stale(op_type)
                }

            return summary

        except Exception as e:
            logger.error(f"Failed to get operation summary: {e}")
            return {}