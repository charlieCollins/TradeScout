"""GapPerformanceTracking Repository - Business-focused data access for gap performance tracking.

This repository provides domain-specific operations for GapPerformanceTracking data.
"""

import logging
from typing import List, Optional
from sqlmodel import Session, select, func
from models.sqlmodel.gap_performance_tracking_sqlmodel import GapPerformanceTrackingSQLModel

logger = logging.getLogger(__name__)


class GapPerformanceTrackingRepository:
    """Repository for GapPerformanceTracking business operations.

    Responsibilities:
    - Business queries (by gap_result_id, incomplete records)
    - Persistence (save, update, upsert, delete)
    - Performance statistics
    """

    def __init__(self, session: Session):
        """Initialize repository with database session.

        Args:
            session: SQLModel session for database operations
        """
        self.session = session

    # =========================================================================
    # BUSINESS QUERIES
    # =========================================================================

    def get_by_gap_result_id(
        self,
        gap_result_id: int
    ) -> Optional[GapPerformanceTrackingSQLModel]:
        """Get performance tracking for a gap result.

        Args:
            gap_result_id: Gap result ID to query

        Returns:
            Performance tracking if exists, None otherwise
        """
        statement = select(GapPerformanceTrackingSQLModel).where(
            GapPerformanceTrackingSQLModel.gap_result_id == gap_result_id
        )
        return self.session.exec(statement).first()

    def find_incomplete_records(self) -> List[GapPerformanceTrackingSQLModel]:
        """Get performance records that need updates.

        Business query: Backtest command needs incomplete records to update.

        Returns:
            List of incomplete performance tracking records
        """
        statement = select(GapPerformanceTrackingSQLModel).where(
            (GapPerformanceTrackingSQLModel.exit_price.is_(None)) |  # type: ignore
            (GapPerformanceTrackingSQLModel.gap_filled.is_(None))    # type: ignore
        )
        return list(self.session.exec(statement).all())

    # =========================================================================
    # PERSISTENCE OPERATIONS
    # =========================================================================

    def save(
        self,
        performance: GapPerformanceTrackingSQLModel
    ) -> GapPerformanceTrackingSQLModel:
        """Persist performance tracking to database.

        Args:
            performance: Performance tracking to save

        Returns:
            Saved performance tracking with ID
        """
        self.session.add(performance)
        self.session.commit()
        self.session.refresh(performance)
        logger.debug(f"Saved gap performance: {performance.id}")
        return performance

    def update(
        self,
        performance: GapPerformanceTrackingSQLModel
    ) -> GapPerformanceTrackingSQLModel:
        """Update existing performance tracking.

        Args:
            performance: Performance tracking to update

        Returns:
            Updated performance tracking
        """
        self.session.add(performance)
        self.session.commit()
        self.session.refresh(performance)
        logger.debug(f"Updated gap performance: {performance.id}")
        return performance

    def upsert(
        self,
        performance: GapPerformanceTrackingSQLModel
    ) -> GapPerformanceTrackingSQLModel:
        """Insert or update performance tracking.

        Args:
            performance: Performance tracking to upsert

        Returns:
            Saved/updated performance tracking
        """
        existing = self.get_by_gap_result_id(performance.gap_result_id)

        if existing:
            # Update existing record
            existing.entry_price = performance.entry_price
            existing.entry_timestamp = performance.entry_timestamp
            existing.exit_price = performance.exit_price
            existing.exit_timestamp = performance.exit_timestamp
            existing.max_intraday_price = performance.max_intraday_price
            existing.min_intraday_price = performance.min_intraday_price
            existing.realized_return_pct = performance.realized_return_pct
            existing.max_drawdown_pct = performance.max_drawdown_pct
            existing.max_upside_pct = performance.max_upside_pct
            existing.gap_filled = performance.gap_filled
            existing.gap_fill_timestamp = performance.gap_fill_timestamp
            existing.outcome = performance.outcome
            existing.trade_taken = performance.trade_taken
            existing.updated_at = performance.updated_at
            return self.update(existing)
        else:
            # Insert new record
            return self.save(performance)

    def delete_by_gap_result_id(self, gap_result_id: int) -> bool:
        """Delete performance tracking for a gap result.

        Args:
            gap_result_id: Gap result ID

        Returns:
            True if deleted, False if not found
        """
        performance = self.get_by_gap_result_id(gap_result_id)
        if performance:
            self.session.delete(performance)
            self.session.commit()
            logger.debug(f"Deleted gap performance for gap_result_id: {gap_result_id}")
            return True
        return False

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_statistics(self) -> dict:
        """Get performance tracking statistics.

        Returns:
            Dictionary with statistics
        """
        total_count = self.session.exec(
            select(func.count(GapPerformanceTrackingSQLModel.id))
        ).one()

        # Count by outcome
        outcome_counts = {}
        for outcome in ['winner', 'loser', 'breakeven', 'not_traded']:
            count = self.session.exec(
                select(func.count(GapPerformanceTrackingSQLModel.id)).where(
                    GapPerformanceTrackingSQLModel.outcome == outcome
                )
            ).one()
            if count > 0:
                outcome_counts[outcome] = count

        # Count incomplete
        incomplete_count = self.session.exec(
            select(func.count(GapPerformanceTrackingSQLModel.id)).where(
                (GapPerformanceTrackingSQLModel.exit_price.is_(None)) |  # type: ignore
                (GapPerformanceTrackingSQLModel.gap_filled.is_(None))    # type: ignore
            )
        ).one()

        return {
            "total_records": total_count,
            "by_outcome": outcome_counts,
            "incomplete_records": incomplete_count
        }
