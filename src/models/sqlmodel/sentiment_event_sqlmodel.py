"""SentimentEvent SQLModel for database operations.

This model represents sentiment events in the database using SQLModel ORM.
"""

from datetime import datetime, date, time
from decimal import Decimal
from typing import Optional
from sqlmodel import Field, SQLModel


class SentimentEventSQLModel(SQLModel, table=True):
    """SQLModel for sentiment_events table.

    Represents a detected sentiment event for a specific asset.
    Examples:
    - News article with positive sentiment published before market open
    - Analyst upgrade announcement
    - Gap up price movement
    """

    __tablename__ = "sentiment_events"

    # Primary key
    id: Optional[int] = Field(default=None, primary_key=True)

    # Foreign keys
    asset_id: int = Field(foreign_key="assets.id", index=True)
    sentiment_type_id: int = Field(foreign_key="sentiment_types.id", index=True)

    # Event timing
    event_date: date = Field(index=True)
    event_time: Optional[time] = None
    session: Optional[str] = None  # 'premarket', 'regular', 'afterhours'

    # Event measurements
    value: Optional[Decimal] = None  # Sentiment score, gap percentage, etc.
    magnitude: Optional[str] = None  # 'small', 'medium', 'large', 'extreme'

    # Additional context (stored as JSON text)
    details: Optional[str] = None  # JSON string: '{"title": "...", "sentiment": "positive"}'

    # External ID (for deduplication)
    external_id: Optional[str] = None  # article_id from news API, etc.

    # Timestamp
    created_at: datetime = Field(default_factory=datetime.utcnow)
