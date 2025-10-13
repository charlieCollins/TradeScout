"""SentimentEvent Repository - Business-focused data access for sentiment events.

This repository provides domain-specific operations for SentimentEvent data.
"""

import logging
from datetime import date
from typing import List, Optional
from sqlmodel import Session, select, func
from models.sqlmodel.sentiment_event_sqlmodel import SentimentEventSQLModel

logger = logging.getLogger(__name__)


class SentimentEventRepository:
    """Repository for SentimentEvent business operations.

    Responsibilities:
    - Business queries (by asset, by date range, by type)
    - Persistence (save, bulk save)
    - Statistics
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

    def get_by_id(self, event_id: int) -> Optional[SentimentEventSQLModel]:
        """Get sentiment event by ID.

        Args:
            event_id: Sentiment event database ID

        Returns:
            SentimentEventSQLModel if found, None otherwise
        """
        return self.session.get(SentimentEventSQLModel, event_id)

    def find_by_asset(
        self,
        asset_id: int,
        limit: Optional[int] = None
    ) -> List[SentimentEventSQLModel]:
        """Get sentiment events for an asset.

        Business query: Show all sentiment events for a specific asset.

        Args:
            asset_id: Asset database ID
            limit: Maximum events to return

        Returns:
            List of sentiment events ordered by date (newest first)
        """
        statement = select(SentimentEventSQLModel).where(
            SentimentEventSQLModel.asset_id == asset_id
        ).order_by(
            SentimentEventSQLModel.event_date.desc(),  # type: ignore
            SentimentEventSQLModel.event_time.desc()   # type: ignore
        )

        if limit:
            statement = statement.limit(limit)

        return list(self.session.exec(statement).all())

    def find_by_date_range(
        self,
        start_date: date,
        end_date: date,
        asset_id: Optional[int] = None
    ) -> List[SentimentEventSQLModel]:
        """Get sentiment events within date range.

        Business query: Analyze sentiment over time period.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)
            asset_id: Optional filter by asset

        Returns:
            List of sentiment events in date range
        """
        statement = select(SentimentEventSQLModel).where(
            SentimentEventSQLModel.event_date >= start_date,
            SentimentEventSQLModel.event_date <= end_date
        )

        if asset_id:
            statement = statement.where(
                SentimentEventSQLModel.asset_id == asset_id
            )

        statement = statement.order_by(
            SentimentEventSQLModel.event_date.desc(),  # type: ignore
            SentimentEventSQLModel.event_time.desc()   # type: ignore
        )

        return list(self.session.exec(statement).all())

    def find_by_sentiment_type(
        self,
        sentiment_type_id: int,
        limit: Optional[int] = None
    ) -> List[SentimentEventSQLModel]:
        """Get events of a specific sentiment type.

        Business query: Filter by type (news, analyst, price_action).

        Args:
            sentiment_type_id: Sentiment type database ID
            limit: Maximum events to return

        Returns:
            List of events of the specified type
        """
        statement = select(SentimentEventSQLModel).where(
            SentimentEventSQLModel.sentiment_type_id == sentiment_type_id
        ).order_by(
            SentimentEventSQLModel.event_date.desc(),  # type: ignore
            SentimentEventSQLModel.event_time.desc()   # type: ignore
        )

        if limit:
            statement = statement.limit(limit)

        return list(self.session.exec(statement).all())

    def find_by_external_id(self, external_id: str) -> Optional[SentimentEventSQLModel]:
        """Find event by external ID (for deduplication).

        Business query: Check if event already imported from external source.

        Args:
            external_id: External identifier (e.g., news article ID)

        Returns:
            SentimentEventSQLModel if found, None otherwise
        """
        statement = select(SentimentEventSQLModel).where(
            SentimentEventSQLModel.external_id == external_id
        )
        return self.session.exec(statement).first()

    def find_recent_by_asset(
        self,
        asset_id: int,
        days: int = 7,
        limit: Optional[int] = None
    ) -> List[SentimentEventSQLModel]:
        """Get recent sentiment events for an asset.

        Business query: Show sentiment activity in recent period.

        Args:
            asset_id: Asset database ID
            days: Number of days to look back
            limit: Maximum events to return

        Returns:
            List of recent events
        """
        from datetime import timedelta
        cutoff_date = date.today() - timedelta(days=days)

        statement = select(SentimentEventSQLModel).where(
            SentimentEventSQLModel.asset_id == asset_id,
            SentimentEventSQLModel.event_date >= cutoff_date
        ).order_by(
            SentimentEventSQLModel.event_date.desc(),  # type: ignore
            SentimentEventSQLModel.event_time.desc()   # type: ignore
        )

        if limit:
            statement = statement.limit(limit)

        return list(self.session.exec(statement).all())

    # =========================================================================
    # PERSISTENCE OPERATIONS
    # =========================================================================

    def save(self, event: SentimentEventSQLModel) -> SentimentEventSQLModel:
        """Persist sentiment event to database.

        Args:
            event: Sentiment event to save

        Returns:
            Saved event with ID
        """
        self.session.add(event)
        self.session.commit()
        self.session.refresh(event)
        logger.debug(f"Saved sentiment event: {event.id}")
        return event

    def bulk_save(self, events: List[SentimentEventSQLModel]) -> int:
        """Bulk persist multiple sentiment events.

        Args:
            events: List of events to save

        Returns:
            Number of events saved
        """
        self.session.add_all(events)
        self.session.commit()
        count = len(events)
        logger.debug(f"Bulk saved {count} sentiment events")
        return count

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def count_by_asset(self, asset_id: int) -> int:
        """Count sentiment events for an asset.

        Args:
            asset_id: Asset database ID

        Returns:
            Event count
        """
        statement = select(func.count(SentimentEventSQLModel.id)).where(
            SentimentEventSQLModel.asset_id == asset_id
        )
        return self.session.exec(statement).one()

    def count_by_type(self, sentiment_type_id: int) -> int:
        """Count events of a sentiment type.

        Args:
            sentiment_type_id: Sentiment type database ID

        Returns:
            Event count
        """
        statement = select(func.count(SentimentEventSQLModel.id)).where(
            SentimentEventSQLModel.sentiment_type_id == sentiment_type_id
        )
        return self.session.exec(statement).one()

    def get_statistics(self) -> dict:
        """Get sentiment event statistics.

        Returns:
            Dictionary with statistics
        """
        total_count = self.session.exec(
            select(func.count(SentimentEventSQLModel.id))
        ).one()

        # Count by magnitude
        statement = select(
            SentimentEventSQLModel.magnitude,
            func.count(SentimentEventSQLModel.id).label('count')
        ).group_by(SentimentEventSQLModel.magnitude)

        results = self.session.exec(statement).all()
        by_magnitude = {
            magnitude: count
            for magnitude, count in results
            if magnitude is not None
        }

        # Count by session
        statement = select(
            SentimentEventSQLModel.session,
            func.count(SentimentEventSQLModel.id).label('count')
        ).group_by(SentimentEventSQLModel.session)

        results = self.session.exec(statement).all()
        by_session = {
            session: count
            for session, count in results
            if session is not None
        }

        return {
            "total_events": total_count,
            "by_magnitude": by_magnitude,
            "by_session": by_session
        }
