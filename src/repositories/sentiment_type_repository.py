"""SentimentType Repository - Business-focused data access for sentiment types.

This repository provides domain-specific operations for SentimentType data.
"""

import logging
from typing import List, Optional
from sqlmodel import Session, select, func
from models.sqlmodel.sentiment_type_sqlmodel import SentimentTypeSQLModel

logger = logging.getLogger(__name__)


class SentimentTypeRepository:
    """Repository for SentimentType business operations.

    Responsibilities:
    - Business queries (by name, active types, by category)
    - Persistence (save, update)
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

    def get_by_id(self, sentiment_type_id: int) -> Optional[SentimentTypeSQLModel]:
        """Get sentiment type by ID.

        Args:
            sentiment_type_id: Sentiment type database ID

        Returns:
            SentimentTypeSQLModel if found, None otherwise
        """
        return self.session.get(SentimentTypeSQLModel, sentiment_type_id)

    def get_by_name(self, name: str) -> Optional[SentimentTypeSQLModel]:
        """Get sentiment type by name.

        Args:
            name: Sentiment type name (e.g., 'news_positive')

        Returns:
            SentimentTypeSQLModel if found, None otherwise
        """
        statement = select(SentimentTypeSQLModel).where(
            SentimentTypeSQLModel.name == name
        )
        return self.session.exec(statement).first()

    def find_all(self) -> List[SentimentTypeSQLModel]:
        """Get all sentiment types.

        Business query: Configuration/admin needs all types.

        Returns:
            List of all sentiment types ordered by name
        """
        statement = select(SentimentTypeSQLModel).order_by(
            SentimentTypeSQLModel.name
        )
        return list(self.session.exec(statement).all())

    def find_all_active(self) -> List[SentimentTypeSQLModel]:
        """Get all active sentiment types.

        Business query: Runtime operations only use active types.

        Returns:
            List of active sentiment types ordered by name
        """
        statement = select(SentimentTypeSQLModel).where(
            SentimentTypeSQLModel.is_active == True
        ).order_by(SentimentTypeSQLModel.name)

        return list(self.session.exec(statement).all())

    def find_by_category(self, category: str) -> List[SentimentTypeSQLModel]:
        """Get sentiment types by category.

        Business query: Group types by category (news, analyst, price_action).

        Args:
            category: Category name

        Returns:
            List of sentiment types in category
        """
        statement = select(SentimentTypeSQLModel).where(
            SentimentTypeSQLModel.category == category,
            SentimentTypeSQLModel.is_active == True
        ).order_by(SentimentTypeSQLModel.name)

        return list(self.session.exec(statement).all())

    # =========================================================================
    # PERSISTENCE OPERATIONS
    # =========================================================================

    def save(self, sentiment_type: SentimentTypeSQLModel) -> SentimentTypeSQLModel:
        """Persist sentiment type to database.

        Args:
            sentiment_type: Sentiment type to save

        Returns:
            Saved sentiment type with ID
        """
        self.session.add(sentiment_type)
        self.session.commit()
        self.session.refresh(sentiment_type)
        logger.debug(f"Saved sentiment type: {sentiment_type.name}")
        return sentiment_type

    def update(self, sentiment_type: SentimentTypeSQLModel) -> SentimentTypeSQLModel:
        """Update existing sentiment type.

        Args:
            sentiment_type: Sentiment type to update

        Returns:
            Updated sentiment type
        """
        self.session.add(sentiment_type)
        self.session.commit()
        self.session.refresh(sentiment_type)
        logger.debug(f"Updated sentiment type: {sentiment_type.name}")
        return sentiment_type

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def count_all(self) -> int:
        """Count total number of sentiment types.

        Returns:
            Total count
        """
        statement = select(func.count(SentimentTypeSQLModel.id))
        return self.session.exec(statement).one()

    def count_active(self) -> int:
        """Count active sentiment types.

        Returns:
            Active count
        """
        statement = select(func.count(SentimentTypeSQLModel.id)).where(
            SentimentTypeSQLModel.is_active == True
        )
        return self.session.exec(statement).one()

    def get_statistics(self) -> dict:
        """Get sentiment type statistics.

        Returns:
            Dictionary with statistics
        """
        total_count = self.count_all()
        active_count = self.count_active()

        # Count by category
        statement = select(
            SentimentTypeSQLModel.category,
            func.count(SentimentTypeSQLModel.id).label('count')
        ).where(
            SentimentTypeSQLModel.is_active == True
        ).group_by(SentimentTypeSQLModel.category)

        results = self.session.exec(statement).all()
        by_category = {
            category: count
            for category, count in results
            if category is not None
        }

        return {
            "total_types": total_count,
            "active_types": active_count,
            "by_category": by_category
        }
