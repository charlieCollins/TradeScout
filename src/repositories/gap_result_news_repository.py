"""GapResultNews Repository - Business-focused data access for gap result news.

This repository provides domain-specific operations for GapResultNews data.
"""

import logging
from typing import List
from sqlmodel import Session, select
from models.sqlmodel.gap_result_news_sqlmodel import GapResultNewsSQLModel

logger = logging.getLogger(__name__)


class GapResultNewsRepository:
    """Repository for GapResultNews business operations.

    Responsibilities:
    - Business queries (by gap_result_id)
    - Persistence (save, bulk save)
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

    def find_by_gap_result_id(
        self,
        gap_result_id: int
    ) -> List[GapResultNewsSQLModel]:
        """Get news articles for a gap result.

        Args:
            gap_result_id: Gap result ID to query

        Returns:
            List of news articles for the gap
        """
        statement = select(GapResultNewsSQLModel).where(
            GapResultNewsSQLModel.gap_result_id == gap_result_id
        ).order_by(
            GapResultNewsSQLModel.news_published_at.desc()  # type: ignore
        )
        return list(self.session.exec(statement).all())

    # =========================================================================
    # PERSISTENCE OPERATIONS
    # =========================================================================

    def save(self, news: GapResultNewsSQLModel) -> GapResultNewsSQLModel:
        """Persist gap result news to database.

        Args:
            news: News article to save

        Returns:
            Saved news with ID
        """
        self.session.add(news)
        self.session.commit()
        self.session.refresh(news)
        logger.debug(f"Saved gap result news: {news.id}")
        return news

    def bulk_save(self, news_list: List[GapResultNewsSQLModel]) -> int:
        """Bulk persist multiple news articles.

        Args:
            news_list: List of news articles to save

        Returns:
            Number of news articles saved
        """
        self.session.add_all(news_list)
        self.session.commit()
        count = len(news_list)
        logger.debug(f"Bulk saved {count} gap result news articles")
        return count

    def get_all(self) -> List[GapResultNewsSQLModel]:
        """Get all gap result news articles.

        Business query: Backup operations need all records.

        Returns:
            List of all gap result news articles
        """
        statement = select(GapResultNewsSQLModel).order_by(
            GapResultNewsSQLModel.id
        )
        return list(self.session.exec(statement).all())

    def upsert(self, news: GapResultNewsSQLModel) -> tuple[GapResultNewsSQLModel, bool]:
        """Insert gap result news if doesn't exist, skip if exists.

        Args:
            news: News article to insert

        Returns:
            Tuple of (record, was_inserted) where was_inserted is True if new record inserted
        """
        if news.id is not None:
            existing = self.session.get(GapResultNewsSQLModel, news.id)
            if existing:
                logger.debug(f"Gap result news {news.id} already exists, skipping")
                return (existing, False)

        # Insert new record
        self.session.add(news)
        self.session.commit()
        self.session.refresh(news)
        logger.debug(f"Inserted gap result news: {news.id}")
        return (news, True)
