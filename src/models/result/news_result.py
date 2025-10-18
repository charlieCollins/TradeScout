"""Result models for news command outputs."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List


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
