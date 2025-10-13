"""MarketHoliday Repository - Business-focused data access for market holidays.

This repository provides domain-specific operations for MarketHoliday data.
"""

import logging
from datetime import date
from typing import List, Optional
from sqlmodel import Session, select, func
from models.sqlmodel.market_holiday_sqlmodel import MarketHolidaySQLModel

logger = logging.getLogger(__name__)


class MarketHolidayRepository:
    """Repository for MarketHoliday business operations.

    Responsibilities:
    - Business queries (by date, upcoming holidays)
    - Persistence (save, bulk save, clear)
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

    def get_by_date(self, holiday_date: str) -> Optional[MarketHolidaySQLModel]:
        """Get holiday by date.

        Args:
            holiday_date: Date string in YYYY-MM-DD format

        Returns:
            MarketHolidaySQLModel if found, None otherwise
        """
        statement = select(MarketHolidaySQLModel).where(
            MarketHolidaySQLModel.date == holiday_date
        )
        return self.session.exec(statement).first()

    def get_all_holidays(self) -> List[MarketHolidaySQLModel]:
        """Get all market holidays.

        Business query: Calendar display needs.

        Returns:
            List of all holidays ordered by date
        """
        statement = select(MarketHolidaySQLModel).order_by(
            MarketHolidaySQLModel.date
        )
        return list(self.session.exec(statement).all())

    def get_upcoming_holidays(
        self,
        from_date: Optional[date] = None
    ) -> List[MarketHolidaySQLModel]:
        """Get upcoming holidays from a date.

        Business query: Market context needs upcoming holiday info.

        Args:
            from_date: Starting date (defaults to today)

        Returns:
            List of upcoming holidays
        """
        if from_date is None:
            from_date = date.today()

        from_date_str = from_date.strftime("%Y-%m-%d")

        statement = select(MarketHolidaySQLModel).where(
            MarketHolidaySQLModel.date >= from_date_str
        ).order_by(MarketHolidaySQLModel.date)

        return list(self.session.exec(statement).all())

    # =========================================================================
    # PERSISTENCE OPERATIONS
    # =========================================================================

    def save(self, holiday: MarketHolidaySQLModel) -> MarketHolidaySQLModel:
        """Persist market holiday to database.

        Args:
            holiday: Holiday to save

        Returns:
            Saved holiday with ID
        """
        self.session.add(holiday)
        self.session.commit()
        self.session.refresh(holiday)
        logger.debug(f"Saved market holiday: {holiday.date}")
        return holiday

    def bulk_save(self, holidays: List[MarketHolidaySQLModel]) -> int:
        """Bulk persist multiple holidays.

        Args:
            holidays: List of holidays to save

        Returns:
            Number of holidays saved
        """
        self.session.add_all(holidays)
        self.session.commit()
        count = len(holidays)
        logger.debug(f"Bulk saved {count} market holidays")
        return count

    def clear_all(self) -> int:
        """Delete all market holidays.

        Returns:
            Number of holidays deleted
        """
        statement = select(MarketHolidaySQLModel)
        holidays = list(self.session.exec(statement).all())
        count = len(holidays)

        for holiday in holidays:
            self.session.delete(holiday)

        self.session.commit()
        logger.debug(f"Cleared {count} market holidays")
        return count

    # =========================================================================
    # STATISTICS
    # =========================================================================

    def count_all(self) -> int:
        """Count total number of holidays.

        Returns:
            Total count
        """
        statement = select(func.count(MarketHolidaySQLModel.id))
        return self.session.exec(statement).one()

    def get_statistics(self) -> dict:
        """Get market holiday statistics.

        Returns:
            Dictionary with statistics
        """
        total_count = self.count_all()

        # Count by status
        closed_count = self.session.exec(
            select(func.count(MarketHolidaySQLModel.id)).where(
                MarketHolidaySQLModel.status == 'closed'
            )
        ).one()

        early_close_count = self.session.exec(
            select(func.count(MarketHolidaySQLModel.id)).where(
                MarketHolidaySQLModel.status == 'early-close'
            )
        ).one()

        return {
            "total_holidays": total_count,
            "closed": closed_count,
            "early_close": early_close_count
        }
