"""GapCandidate Repository - Business-focused data access for gap candidate analysis.

This repository provides domain-specific operations for GapCandidate data.
"""

import logging
from datetime import date, datetime
from typing import List, Optional, Tuple
from sqlmodel import Session, select, func
from models.sqlmodel.gap_candidate_sqlmodel import GapCandidateSQLModel
from models.sqlmodel.asset_sqlmodel import AssetSQLModel

logger = logging.getLogger(__name__)


class GapCandidateRepository:
    """Repository for GapCandidate business operations.

    Responsibilities:
    - Business queries (by date, status, quality tier)
    - Persistence (save gap candidates)
    - Statistics and aggregations
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

    def get_by_id(self, gap_candidate_id: int) -> Optional[GapCandidateSQLModel]:
        """Get gap candidate by ID.

        Args:
            gap_candidate_id: Gap candidate database ID

        Returns:
            GapCandidateSQLModel if found, None otherwise
        """
        return self.session.get(GapCandidateSQLModel, gap_candidate_id)

    def find_by_date(
        self,
        trading_date: date,
        session_type: Optional[str] = None
    ) -> List[GapCandidateSQLModel]:
        """Get gap results for a specific trading date.

        Business query: View all gaps detected on a specific date.

        Args:
            trading_date: Trading date to query
            session_type: Optional filter by 'premarket' or 'afterhours'

        Returns:
            List of gap results for the date
        """
        statement = select(GapCandidateSQLModel).where(
            GapCandidateSQLModel.trading_date == trading_date
        )

        if session_type:
            statement = statement.where(
                GapCandidateSQLModel.session_type == session_type
            )

        statement = statement.order_by(
            GapCandidateSQLModel.gap_percentage.desc()  # type: ignore
        )

        return list(self.session.exec(statement).all())

    def find_by_status(
        self,
        status: str,
        limit: int = 100
    ) -> List[GapCandidateSQLModel]:
        """Get gap results by status.

        Business query: Filter gaps by passed/rejected/warning status.

        Args:
            status: Status to filter by ('passed', 'rejected', 'warning')
            limit: Maximum results to return

        Returns:
            List of gap results matching status
        """
        statement = select(GapCandidateSQLModel).where(
            GapCandidateSQLModel.status == status
        ).order_by(
            GapCandidateSQLModel.analysis_timestamp.desc()  # type: ignore
        ).limit(limit)

        return list(self.session.exec(statement).all())

    def find_by_quality_tier(
        self,
        quality_tier: str,
        limit: int = 100
    ) -> List[GapCandidateSQLModel]:
        """Get gap results by quality tier.

        Business query: Filter gaps by quality assessment.

        Args:
            quality_tier: Quality tier ('excellent', 'good', 'fair', 'poor')
            limit: Maximum results to return

        Returns:
            List of gap results matching quality tier
        """
        statement = select(GapCandidateSQLModel).where(
            GapCandidateSQLModel.quality_tier == quality_tier
        ).order_by(
            GapCandidateSQLModel.analysis_timestamp.desc()  # type: ignore
        ).limit(limit)

        return list(self.session.exec(statement).all())

    def find_by_date_range_with_symbols(
        self,
        start_date: date,
        end_date: date,
        session_type: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Tuple[GapCandidateSQLModel, str, str]]:
        """Get gap results with asset symbols for date range.

        Business query: Report command needs gaps with symbols.

        Args:
            start_date: Start of date range
            end_date: End of date range
            session_type: Optional filter ('premarket', 'afterhours', or None for all)
            status: Optional filter ('passed', 'rejected', 'warning', or None for all)

        Returns:
            List of tuples (GapCandidateSQLModel, symbol, asset_name)
        """
        statement = select(
            GapCandidateSQLModel, AssetSQLModel.symbol, AssetSQLModel.name
        ).join(
            AssetSQLModel, GapCandidateSQLModel.asset_id == AssetSQLModel.id
        ).where(
            GapCandidateSQLModel.trading_date >= start_date,
            GapCandidateSQLModel.trading_date <= end_date
        )

        # Add optional filters
        if session_type and session_type != 'all':
            statement = statement.where(GapCandidateSQLModel.session_type == session_type)

        if status and status != 'all':
            statement = statement.where(GapCandidateSQLModel.status == status)

        # Order by date desc, session type, then gap percentage desc
        statement = statement.order_by(
            GapCandidateSQLModel.trading_date.desc(),  # type: ignore
            GapCandidateSQLModel.session_type,
            GapCandidateSQLModel.gap_percentage.desc()  # type: ignore
        )

        return list(self.session.exec(statement).all())

    def find_recent_with_symbols(
        self,
        num_days: int,
        specific_date: Optional[date] = None
    ) -> List[Tuple[GapCandidateSQLModel, str]]:
        """Get recent gap results with symbols.

        Business query: Backtest command needs recent gaps with symbols.

        Args:
            num_days: Number of recent days to fetch (ignored if specific_date provided)
            specific_date: Optional specific date to query

        Returns:
            List of tuples (GapCandidateSQLModel, symbol)
        """
        if specific_date:
            # Query specific date
            statement = select(
                GapCandidateSQLModel, AssetSQLModel.symbol
            ).join(
                AssetSQLModel, GapCandidateSQLModel.asset_id == AssetSQLModel.id
            ).where(
                GapCandidateSQLModel.trading_date == specific_date
            ).order_by(
                GapCandidateSQLModel.trading_date.desc(),  # type: ignore
                GapCandidateSQLModel.quality_score.desc()  # type: ignore
            )
        else:
            # Get recent dates first
            recent_dates_stmt = select(
                GapCandidateSQLModel.trading_date
            ).distinct().order_by(
                GapCandidateSQLModel.trading_date.desc()  # type: ignore
            ).limit(num_days)
            recent_dates = [row for row in self.session.exec(recent_dates_stmt).all()]

            # Query gaps for those dates
            statement = select(
                GapCandidateSQLModel, AssetSQLModel.symbol
            ).join(
                AssetSQLModel, GapCandidateSQLModel.asset_id == AssetSQLModel.id
            ).where(
                GapCandidateSQLModel.trading_date.in_(recent_dates)  # type: ignore
            ).order_by(
                GapCandidateSQLModel.trading_date.desc(),  # type: ignore
                GapCandidateSQLModel.quality_score.desc()  # type: ignore
            )

        return list(self.session.exec(statement).all())

    # =========================================================================
    # PERSISTENCE OPERATIONS
    # =========================================================================

    def save(self, gap_result: GapCandidateSQLModel) -> GapCandidateSQLModel:
        """Persist gap result to database.

        Args:
            gap_result: Gap result to save

        Returns:
            Saved gap result with ID populated
        """
        self.session.add(gap_result)
        self.session.commit()
        self.session.refresh(gap_result)
        logger.debug(f"Saved gap result: {gap_result.id}")
        return gap_result

    def get_all(self) -> List[GapCandidateSQLModel]:
        """Get all gap candidates.

        Business query: Backup operations need all records.

        Returns:
            List of all gap candidates
        """
        statement = select(GapCandidateSQLModel).order_by(
            GapCandidateSQLModel.id
        )
        return list(self.session.exec(statement).all())

    def upsert(self, gap_result: GapCandidateSQLModel) -> tuple[GapCandidateSQLModel, bool]:
        """Insert gap candidate if doesn't exist, skip if exists.

        Args:
            gap_result: Gap candidate to insert

        Returns:
            Tuple of (record, was_inserted) where was_inserted is True if new record inserted
        """
        if gap_result.id is not None:
            existing = self.session.get(GapCandidateSQLModel, gap_result.id)
            if existing:
                logger.debug(f"Gap candidate {gap_result.id} already exists, skipping")
                return (existing, False)

        # Insert new record
        self.session.add(gap_result)
        self.session.commit()
        self.session.refresh(gap_result)
        logger.debug(f"Inserted gap candidate: {gap_result.id}")
        return (gap_result, True)

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def get_statistics(self) -> dict:
        """Get gap results statistics.

        Business query: Dashboard/monitoring needs.

        Returns:
            Dictionary with statistics
        """
        # Total count
        total_count = self.session.exec(
            select(func.count(GapCandidateSQLModel.id))
        ).one()

        # Count by status
        status_counts = {}
        for status in ['passed', 'rejected', 'warning']:
            count = self.session.exec(
                select(func.count(GapCandidateSQLModel.id)).where(
                    GapCandidateSQLModel.status == status
                )
            ).one()
            status_counts[status] = count

        # Count by quality tier
        quality_counts = {}
        for tier in ['excellent', 'good', 'fair', 'poor']:
            count = self.session.exec(
                select(func.count(GapCandidateSQLModel.id)).where(
                    GapCandidateSQLModel.quality_tier == tier
                )
            ).one()
            if count > 0:
                quality_counts[tier] = count

        return {
            "total_results": total_count,
            "by_status": status_counts,
            "by_quality_tier": quality_counts
        }
