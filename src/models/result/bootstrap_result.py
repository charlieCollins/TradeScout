"""Result models for bootstrap command outputs."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List


@dataclass
class BootstrapResult:
    """Result of a bootstrap operation (tickers, fundamentals, markets, etc.)."""

    operation: str  # "tickers", "fundamentals", "markets", etc.
    total_items: int
    successful: int
    failed: int
    fetch_errors: List[str] = field(default_factory=list)
    insert_errors: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    from_database: int = 0  # Count of items from database (fresh)
    from_cache: int = 0  # Count of items from file cache
    from_api: int = 0  # Count of items from API
    new_items: int = 0  # Count of new items added
    updated_items: int = 0  # Count of existing items updated
    deprecated_items: int = 0  # Count of items in DB but not in source

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        return self.successful / self.total_items if self.total_items > 0 else 0.0

    @property
    def total_errors(self) -> int:
        """Total number of errors (fetch + insert)."""
        return len(self.fetch_errors) + len(self.insert_errors)

    @property
    def cache_hit_rate(self) -> float:
        """Calculate cache hit rate (database + file cache) as percentage."""
        total_fetched = self.from_database + self.from_cache + self.from_api
        if total_fetched == 0:
            return 0.0
        return ((self.from_database + self.from_cache) / total_fetched) * 100
