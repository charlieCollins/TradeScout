"""SentimentType SQLModel for database operations.

This model represents sentiment types in the database using SQLModel ORM.
"""

from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel


class SentimentTypeSQLModel(SQLModel, table=True):
    """SQLModel for sentiment_types table.

    Represents a type of sentiment event that can be detected.
    Examples: 'news_positive', 'news_negative', 'analyst_upgrade'
    """

    __tablename__ = "sentiment_types"

    # Primary key
    id: Optional[int] = Field(default=None, primary_key=True)

    # Type identification
    name: str = Field(index=True, unique=True)  # 'news_positive', 'gap_up', etc.
    description: Optional[str] = None
    category: Optional[str] = None  # 'news', 'analyst', 'price_action', etc.

    # Configuration (stored as JSON text)
    parameters: Optional[str] = None  # JSON string: '{"threshold": 0.02}'

    # Status
    is_active: bool = Field(default=True)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
