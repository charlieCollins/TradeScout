"""MarketHoliday SQLModel for database operations.

This model represents market holidays in the database using SQLModel ORM.
"""

from enum import Enum
from typing import Optional
from sqlmodel import Field, SQLModel


class HolidayStatus(Enum):
    """Market holiday status types."""
    CLOSED = "closed"           # Market fully closed
    EARLY_CLOSE = "early_close" # Market closes early


class MarketHolidaySQLModel(SQLModel, table=True):
    """SQLModel for market_holidays table.

    Tracks market closures and early close days.
    """

    __tablename__ = "market_holidays"

    id: Optional[int] = Field(default=None, primary_key=True)
    date: str = Field(unique=True, index=True)  # YYYY-MM-DD format
    name: Optional[str] = None  # Holiday name
    status: str  # 'closed' or 'early-close'
