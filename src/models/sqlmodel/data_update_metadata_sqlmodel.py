"""DataUpdateMetadata SQLModel for database operations.

This model represents metadata for data update operations in the database using SQLModel ORM.
"""

from datetime import datetime
from typing import Optional
from sqlmodel import Field, SQLModel


class DataUpdateMetadataSQLModel(SQLModel, table=True):
    """SQLModel for data_update_metadata table.

    Represents metadata tracking for data update operations (bootstrap, refresh, fetch).
    """

    __tablename__ = "data_update_metadata"

    # Primary key
    id: Optional[int] = Field(default=None, primary_key=True)

    # Operation identification
    operation_type: str = Field(index=True)  # 'fundamentals', 'market_snapshots', etc.
    operation_subtype: Optional[str] = None  # 'bootstrap', 'refresh', 'fetch'

    # Timestamps
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Status
    status: str = Field(default="running")  # 'running', 'completed', 'failed', 'partial'

    # Statistics (stored as JSON text)
    stats: Optional[str] = None  # JSON string

    # Operation tracking
    total_items: Optional[int] = None
    processed_items: int = Field(default=0)
    failed_items: int = Field(default=0)
    api_calls_made: int = Field(default=0)

    # Additional context (stored as JSON text)
    operation_params: Optional[str] = None  # JSON string
    error_message: Optional[str] = None
