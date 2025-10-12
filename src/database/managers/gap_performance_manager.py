"""Gap performance tracking database manager."""

import logging
from datetime import datetime
from typing import Optional, List
from models.gap_performance import GapPerformance, PerformanceOutcome

logger = logging.getLogger(__name__)


class GapPerformanceManager:
    """Manages gap_performance_tracking table.

    This manager does NOT use the BaseManager pattern because performance
    records are tracked metrics, not cached entities.
    """

    def __init__(self, db_manager):
        """Initialize gap performance manager.

        Args:
            db_manager: Database connection manager
        """
        self.db_manager = db_manager

    def save_performance(self, performance: GapPerformance) -> Optional[int]:
        """Save a gap performance record to the database.

        Args:
            performance: GapPerformance object with all metrics

        Returns:
            performance_id if successful, None otherwise
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO gap_performance_tracking (
                        gap_result_id,
                        entry_price, exit_price,
                        max_intraday_price, min_intraday_price,
                        gap_filled, gap_fill_timestamp,
                        realized_return_pct, max_upside_pct, max_drawdown_pct,
                        outcome
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    performance.gap_result_id,
                    performance.entry_price,
                    performance.exit_price,
                    performance.max_intraday_price,
                    performance.min_intraday_price,
                    performance.gap_filled,
                    performance.gap_fill_timestamp,
                    performance.realized_return_pct,
                    performance.max_upside_pct,
                    performance.max_drawdown_pct,
                    performance.outcome.value if performance.outcome else None
                ))

                conn.commit()
                return cursor.lastrowid

        except Exception as e:
            logger.error(f"Error saving gap performance for gap_result_id {performance.gap_result_id}: {e}")
            return None

    def update_performance(self, performance: GapPerformance) -> bool:
        """Update an existing gap performance record.

        Args:
            performance: GapPerformance object with updated metrics

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    UPDATE gap_performance_tracking SET
                        entry_price = ?,
                        exit_price = ?,
                        max_intraday_price = ?,
                        min_intraday_price = ?,
                        gap_filled = ?,
                        gap_fill_timestamp = ?,
                        realized_return_pct = ?,
                        max_upside_pct = ?,
                        max_drawdown_pct = ?,
                        outcome = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE gap_result_id = ?
                """, (
                    performance.entry_price,
                    performance.exit_price,
                    performance.max_intraday_price,
                    performance.min_intraday_price,
                    performance.gap_filled,
                    performance.gap_fill_timestamp,
                    performance.realized_return_pct,
                    performance.max_upside_pct,
                    performance.max_drawdown_pct,
                    performance.outcome.value if performance.outcome else None,
                    performance.gap_result_id
                ))

                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Error updating gap performance for gap_result_id {performance.gap_result_id}: {e}")
            return False

    def upsert_performance(self, performance: GapPerformance) -> Optional[int]:
        """Insert or update gap performance record.

        Args:
            performance: GapPerformance object with metrics

        Returns:
            performance_id if successful, None otherwise
        """
        existing = self.get_performance_for_gap(performance.gap_result_id)

        if existing:
            # Update existing record
            success = self.update_performance(performance)
            return existing['id'] if success else None
        else:
            # Insert new record
            return self.save_performance(performance)

    def get_performance_for_gap(self, gap_result_id: int) -> Optional[dict]:
        """Get performance record for a specific gap result.

        Args:
            gap_result_id: ID of the gap_results record

        Returns:
            Performance record dict or None if not found
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT * FROM gap_performance_tracking
                    WHERE gap_result_id = ?
                """, (gap_result_id,))

                row = cursor.fetchone()
                if not row:
                    return None

                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))

        except Exception as e:
            logger.error(f"Error getting performance for gap_result_id {gap_result_id}: {e}")
            return None

    def get_incomplete_performance_records(self) -> List[dict]:
        """Get performance records with missing data.

        Returns:
            List of incomplete performance records
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    SELECT * FROM gap_performance_tracking
                    WHERE entry_price IS NULL
                       OR exit_price IS NULL
                       OR max_intraday_price IS NULL
                       OR min_intraday_price IS NULL
                """)

                rows = cursor.fetchall()
                columns = [description[0] for description in cursor.description]

                return [dict(zip(columns, row)) for row in rows]

        except Exception as e:
            logger.error(f"Error getting incomplete performance records: {e}")
            return []

    def get_performance_statistics(self) -> dict:
        """Get overall performance statistics.

        Returns:
            Dictionary with performance statistics
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Total counts
                cursor.execute("SELECT COUNT(*) FROM gap_performance_tracking")
                total_records = cursor.fetchone()[0]

                # Outcome breakdown
                cursor.execute("""
                    SELECT outcome, COUNT(*) as count
                    FROM gap_performance_tracking
                    WHERE outcome IS NOT NULL
                    GROUP BY outcome
                """)
                outcomes = dict(cursor.fetchall())

                # Average returns
                cursor.execute("""
                    SELECT
                        AVG(realized_return_pct) as avg_return,
                        AVG(CASE WHEN outcome = 'winner' THEN realized_return_pct END) as avg_winner_return,
                        AVG(CASE WHEN outcome = 'loser' THEN realized_return_pct END) as avg_loser_return
                    FROM gap_performance_tracking
                """)
                row = cursor.fetchone()
                avg_return = row[0] if row[0] else 0.0
                avg_winner_return = row[1] if row[1] else 0.0
                avg_loser_return = row[2] if row[2] else 0.0

                # Gap fill rate
                cursor.execute("""
                    SELECT COUNT(*) FILTER (WHERE gap_filled = 1)
                    FROM gap_performance_tracking
                """)
                gap_filled_count = cursor.fetchone()[0]

                gap_fill_rate = (gap_filled_count / total_records * 100) if total_records > 0 else 0.0

                return {
                    'total_records': total_records,
                    'outcomes': outcomes,
                    'avg_return': avg_return,
                    'avg_winner_return': avg_winner_return,
                    'avg_loser_return': avg_loser_return,
                    'gap_fill_rate': gap_fill_rate,
                    'gap_filled_count': gap_filled_count
                }

        except Exception as e:
            logger.error(f"Error getting performance statistics: {e}")
            return {}

    def delete_performance(self, gap_result_id: int) -> bool:
        """Delete performance record for a gap result.

        Args:
            gap_result_id: ID of the gap_results record

        Returns:
            True if successful, False otherwise
        """
        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                cursor.execute("""
                    DELETE FROM gap_performance_tracking
                    WHERE gap_result_id = ?
                """, (gap_result_id,))

                conn.commit()
                return cursor.rowcount > 0

        except Exception as e:
            logger.error(f"Error deleting performance for gap_result_id {gap_result_id}: {e}")
            return False
