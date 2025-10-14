"""GapCandidateResult Repository - Business-focused data access for gap candidate results.

This repository provides domain-specific operations for GapCandidateResult data.
"""

import logging
from typing import List, Optional
from sqlmodel import Session, select, func
from models.sqlmodel.gap_candidate_result_sqlmodel import GapCandidateResultSQLModel

logger = logging.getLogger(__name__)


class GapCandidateResultRepository:
    """Repository for GapCandidateResult business operations.

    Responsibilities:
    - Business queries (by gap_candidate_id, incomplete records)
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

    def get_by_gap_candidate_id(
        self,
        gap_candidate_id: int
    ) -> Optional[GapCandidateResultSQLModel]:
        """Get performance tracking for a gap result.

        Args:
            gap_candidate_id: Gap result ID to query

        Returns:
            Performance tracking if exists, None otherwise
        """
        statement = select(GapCandidateResultSQLModel).where(
            GapCandidateResultSQLModel.gap_result_id == gap_candidate_id
        )
        return self.session.exec(statement).first()

    def find_incomplete_records(self) -> List[GapCandidateResultSQLModel]:
        """Get performance records that need updates.

        Business query: Backtest command needs incomplete records to update.

        Returns:
            List of incomplete performance tracking records
        """
        statement = select(GapCandidateResultSQLModel).where(
            (GapCandidateResultSQLModel.exit_price.is_(None)) |  # type: ignore
            (GapCandidateResultSQLModel.gap_filled.is_(None))    # type: ignore
        )
        return list(self.session.exec(statement).all())

    # =========================================================================
    # PERSISTENCE OPERATIONS
    # =========================================================================

    def save(
        self,
        performance: GapCandidateResultSQLModel
    ) -> GapCandidateResultSQLModel:
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
        performance: GapCandidateResultSQLModel
    ) -> GapCandidateResultSQLModel:
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
        performance: GapCandidateResultSQLModel
    ) -> GapCandidateResultSQLModel:
        """Insert or update performance tracking.

        Args:
            performance: Performance tracking to upsert

        Returns:
            Saved/updated performance tracking
        """
        existing = self.get_by_gap_candidate_id(performance.gap_result_id)

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

    def delete_by_gap_candidate_id(self, gap_candidate_id: int) -> bool:
        """Delete performance tracking for a gap result.

        Args:
            gap_candidate_id: Gap result ID

        Returns:
            True if deleted, False if not found
        """
        performance = self.get_by_gap_candidate_id(gap_candidate_id)
        if performance:
            self.session.delete(performance)
            self.session.commit()
            logger.debug(f"Deleted gap performance for gap_candidate_id: {gap_candidate_id}")
            return True
        return False

    def get_all(self) -> List[GapCandidateResultSQLModel]:
        """Get all gap candidate results.

        Business query: Backup operations need all records.

        Returns:
            List of all gap candidate results
        """
        statement = select(GapCandidateResultSQLModel).order_by(
            GapCandidateResultSQLModel.id
        )
        return list(self.session.exec(statement).all())

    def upsert_by_id(self, result: GapCandidateResultSQLModel) -> tuple[GapCandidateResultSQLModel, bool]:
        """Insert gap candidate result if doesn't exist, skip if exists (by ID).

        Args:
            result: Gap candidate result to insert

        Returns:
            Tuple of (record, was_inserted) where was_inserted is True if new record inserted
        """
        if result.id is not None:
            existing = self.session.get(GapCandidateResultSQLModel, result.id)
            if existing:
                logger.debug(f"Gap candidate result {result.id} already exists, skipping")
                return (existing, False)

        # Insert new record
        self.session.add(result)
        self.session.commit()
        self.session.refresh(result)
        logger.debug(f"Inserted gap candidate result: {result.id}")
        return (result, True)

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_statistics(self) -> dict:
        """Get performance tracking statistics.

        Returns:
            Dictionary with statistics
        """
        total_count = self.session.exec(
            select(func.count(GapCandidateResultSQLModel.id))
        ).one()

        # Count by outcome
        outcome_counts = {}
        for outcome in ['winner', 'loser', 'breakeven', 'not_traded']:
            count = self.session.exec(
                select(func.count(GapCandidateResultSQLModel.id)).where(
                    GapCandidateResultSQLModel.outcome == outcome
                )
            ).one()
            if count > 0:
                outcome_counts[outcome] = count

        # Count incomplete
        incomplete_count = self.session.exec(
            select(func.count(GapCandidateResultSQLModel.id)).where(
                (GapCandidateResultSQLModel.exit_price.is_(None)) |  # type: ignore
                (GapCandidateResultSQLModel.gap_filled.is_(None))    # type: ignore
            )
        ).one()

        return {
            "total_records": total_count,
            "by_outcome": outcome_counts,
            "incomplete_records": incomplete_count
        }
