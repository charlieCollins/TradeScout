"""GapResultNews SQLModel for database operations.

This model represents news associated with gap results in the database using SQLModel ORM.
"""

from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel


class GapResultNewsSQLModel(SQLModel, table=True):
    """SQLModel for gap_result_news table.

    Links news articles to gap analysis results.
    """

    __tablename__ = "gap_result_news"

    id: Optional[int] = Field(default=None, primary_key=True)
    gap_result_id: int = Field(index=True)
    news_headline: str
    news_source: Optional[str] = None
    news_published_at: Optional[datetime] = None
    news_sentiment: Optional[float] = None
    created_at: Optional[datetime] = None
