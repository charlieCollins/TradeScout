"""Database and operation statistics models for TradeScout."""

from dataclasses import dataclass
from typing import Dict, Optional
from datetime import datetime


@dataclass(frozen=True)
class DatabaseStats:
    """Database statistics and health information."""

    database_path: str
    status: str
    table_counts: Dict[str, int]
    total_records: int
    last_updated: Optional[datetime] = None
    error_message: Optional[str] = None

    @property
    def is_healthy(self) -> bool:
        """Check if database is in healthy state."""
        return self.status == "healthy" and self.error_message is None


@dataclass(frozen=True)
class OperationStats:
    """Statistics for data operations like bootstrapping."""

    operation_type: str
    operation_subtype: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]
    status: str
    total_items: Optional[int]
    processed_items: int
    successful_items: int
    failed_items: int
    api_calls_made: int
    error_message: Optional[str] = None

    @property
    def is_running(self) -> bool:
        """Check if operation is currently running."""
        return self.status == 'running' and self.completed_at is None

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.processed_items == 0:
            return 0.0
        return (self.successful_items / self.processed_items) * 100

    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate operation duration in seconds."""
        if self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


@dataclass(frozen=True)
class MarketSnapshotUpdateStats:
    """Statistics for market snapshot update operations."""

    total_tickers: int  # Total tickers received from API
    matched_symbols: int  # Symbols we have in our database
    unmatched_symbols: int  # Symbols from Polygon we don't have
    transformed: int  # Successfully transformed to AssetPrice
    invalid: int  # Rejected due to invalid data
    saved: int  # New records saved to database
    duplicates: int  # Records skipped (already in database)
    data_was_fresh: bool = False  # True if TTL check passed and no API call was made