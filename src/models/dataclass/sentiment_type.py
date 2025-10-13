"""Sentiment type model for TradeScout."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Any


@dataclass(frozen=True)
class SentimentType:
    """Represents a type of sentiment event that can be detected.

    Examples: 'news_positive', 'news_negative', 'analyst_upgrade', 'earnings_beat'
    """

    # Primary identification
    id: int
    name: str  # 'news_positive', 'analyst_upgrade', 'earnings_beat'
    description: str

    # Classification
    category: str  # 'news', 'analyst', 'earnings', 'regulatory', 'social'

    # Detection configuration (JSON)
    parameters: Dict[str, Any]  # {"min_confidence": 0.7, "sources": ["polygon"]}

    # Status and timestamps
    created_at: datetime

    # Status
    is_active: bool = True

    @property
    def display_name(self) -> str:
        """Get display name for the sentiment type."""
        return self.name.replace("_", " ").title()

    @property
    def is_news_sentiment(self) -> bool:
        """Check if this is a news sentiment type."""
        return self.category == "news"

    @property
    def is_earnings_sentiment(self) -> bool:
        """Check if this is an earnings-related sentiment type."""
        return self.category == "earnings"

    @property
    def is_analyst_sentiment(self) -> bool:
        """Check if this is an analyst-related sentiment type."""
        return self.category == "analyst"
