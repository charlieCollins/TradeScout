"""Result objects for DataService operations.

These objects encapsulate operation results, separating business logic from output formatting.
DataService returns these structured results, and output adapters format them for display.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Optional


@dataclass
class BootstrapResult:
    """Result of a bootstrap operation (assets, fundamentals, markets, etc.)."""

    operation: str  # "assets", "fundamentals", "markets", etc.
    total_items: int
    successful: int
    failed: int
    fetch_errors: List[str] = field(default_factory=list)
    insert_errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        return self.successful / self.total_items if self.total_items > 0 else 0.0

    @property
    def total_errors(self) -> int:
        """Total number of errors (fetch + insert)."""
        return len(self.fetch_errors) + len(self.insert_errors)


@dataclass
class FetchResult:
    """Result of a data fetch operation (single asset, market data, etc.)."""

    source: str  # "cache", "api", "database"
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    is_new_data: bool = False  # True if newer than cached
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class UpdateResult:
    """Result of a bulk update operation (market update, universe refresh, etc.)."""

    operation: str  # "market_update", "universe_refresh", etc.
    new_records: int = 0
    duplicate_records: int = 0
    updated_records: int = 0
    errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def total_records(self) -> int:
        """Total records processed."""
        return self.new_records + self.duplicate_records + self.updated_records


@dataclass
class NewsResult:
    """Result of a news fetch and sentiment analysis operation."""

    symbol: str
    source: str  # "api"
    articles_found: int
    sentiment_events_created: int
    sentiment_events_stored: int
    sentiment_events_duplicates: int = 0  # Prevented by unique constraint
    sentiment_events: List[Any] = field(default_factory=list)  # List[SentimentEvent]
    errors: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def has_articles(self) -> bool:
        """Check if any articles were found."""
        return self.articles_found > 0

    @property
    def storage_success_rate(self) -> float:
        """Calculate sentiment storage success rate."""
        if self.sentiment_events_created == 0:
            return 0.0
        return self.sentiment_events_stored / self.sentiment_events_created
