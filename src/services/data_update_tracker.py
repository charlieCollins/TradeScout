"""Data update tracking service for TradeScout operations."""

import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List
from database.database_manager import DatabaseManager
from config.ttl_config import FUNDAMENTALS_TTL_HOURS

logger = logging.getLogger(__name__)


class DataUpdateTracker:
    """Track data update operations across TradeScout."""

    def __init__(self, db_manager: DatabaseManager):
        """Initialize with database manager."""
        self.db_manager = db_manager

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
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                params_json = json.dumps(operation_params) if operation_params else None
                started_at = datetime.now().isoformat()

                cursor.execute("""
                    INSERT INTO data_update_metadata
                    (operation_type, operation_subtype, started_at, operation_params, total_items, status)
                    VALUES (?, ?, ?, ?, ?, 'running')
                """, (operation_type, operation_subtype, started_at, params_json, total_items))

                operation_id = cursor.lastrowid
                conn.commit()

                logger.debug(f"Started tracking operation {operation_type}.{operation_subtype} (ID: {operation_id})")
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
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

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
                    cursor.execute(query, update_values)
                    conn.commit()

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
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                completed_at = datetime.now().isoformat()
                stats_json = json.dumps(final_stats)

                cursor.execute("""
                    UPDATE data_update_metadata
                    SET completed_at = ?, status = ?, stats = ?
                    WHERE id = ?
                """, (completed_at, status, stats_json, operation_id))

                conn.commit()
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
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                completed_at = datetime.now().isoformat()

                cursor.execute("""
                    UPDATE data_update_metadata
                    SET completed_at = ?, status = 'failed', error_message = ?
                    WHERE id = ?
                """, (completed_at, error_message, operation_id))

                conn.commit()
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
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                if operation_subtype:
                    cursor.execute("""
                        SELECT completed_at FROM data_update_metadata
                        WHERE operation_type = ? AND operation_subtype = ?
                        AND status IN ('completed', 'partial')
                        ORDER BY completed_at DESC LIMIT 1
                    """, (operation_type, operation_subtype))
                else:
                    cursor.execute("""
                        SELECT completed_at FROM data_update_metadata
                        WHERE operation_type = ? AND status IN ('completed', 'partial')
                        ORDER BY completed_at DESC LIMIT 1
                    """, (operation_type,))

                result = cursor.fetchone()
                if result and result[0]:
                    return datetime.fromisoformat(result[0])
                return None

        except Exception as e:
            logger.error(f"Failed to get last update time: {e}")
            return None

    def get_operation_history(self, operation_type: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Get history of operations.

        Args:
            operation_type: Optional operation type to filter by
            limit: Maximum number of records to return

        Returns:
            List of operation records
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                if operation_type:
                    cursor.execute("""
                        SELECT operation_type, operation_subtype, started_at, completed_at,
                               status, stats, api_calls_made, total_items, processed_items
                        FROM data_update_metadata
                        WHERE operation_type = ?
                        ORDER BY started_at DESC LIMIT ?
                    """, (operation_type, limit))
                else:
                    cursor.execute("""
                        SELECT operation_type, operation_subtype, started_at, completed_at,
                               status, stats, api_calls_made, total_items, processed_items
                        FROM data_update_metadata
                        ORDER BY started_at DESC LIMIT ?
                    """, (limit,))

                rows = cursor.fetchall()
                history = []

                for row in rows:
                    record = {
                        'operation_type': row[0],
                        'operation_subtype': row[1],
                        'started_at': row[2],
                        'completed_at': row[3],
                        'status': row[4],
                        'stats': json.loads(row[5]) if row[5] else {},
                        'api_calls_made': row[6],
                        'total_items': row[7],
                        'processed_items': row[8]
                    }
                    history.append(record)

                return history

        except Exception as e:
            logger.error(f"Failed to get operation history: {e}")
            return []

    def get_current_running_operations(self) -> List[Dict[str, Any]]:
        """Get list of currently running operations.

        Returns:
            List of running operation records
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT id, operation_type, operation_subtype, started_at,
                           total_items, processed_items, api_calls_made
                    FROM data_update_metadata
                    WHERE status = 'running'
                    ORDER BY started_at DESC
                """)

                rows = cursor.fetchall()
                running_ops = []

                for row in rows:
                    record = {
                        'id': row[0],
                        'operation_type': row[1],
                        'operation_subtype': row[2],
                        'started_at': row[3],
                        'total_items': row[4],
                        'processed_items': row[5],
                        'api_calls_made': row[6]
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
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT operation_type,
                           MAX(completed_at) as last_completed,
                           COUNT(*) as total_runs,
                           SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as successful_runs
                    FROM data_update_metadata
                    WHERE status IN ('completed', 'partial', 'failed')
                    GROUP BY operation_type
                    ORDER BY operation_type
                """)

                rows = cursor.fetchall()
                summary = {}

                for row in rows:
                    op_type = row[0]
                    last_completed = row[1]
                    total_runs = row[2]
                    successful_runs = row[3]

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