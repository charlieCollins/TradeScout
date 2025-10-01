"""Sentiment event model for TradeScout."""

from dataclasses import dataclass
from datetime import datetime, date, time
from decimal import Decimal
from typing import Optional, Dict, Any


@dataclass(frozen=True)
class SentimentEvent:
    """Represents a detected sentiment event for a specific asset.

    Examples:
    - News article with positive sentiment published before market open
    - Analyst upgrade announcement
    - Earnings beat with raised guidance
    """

    # Primary identification
    id: int
    asset_id: int
    sentiment_type_id: int

    # Event timing
    event_date: date
    event_time: Optional[time]  # When event occurred/published
    session: Optional[str]  # 'premarket', 'regular', 'afterhours'

    # Event measurements
    value: Decimal  # Sentiment score, confidence level, magnitude
    magnitude: str  # 'small', 'medium', 'large', 'extreme'

    # Additional context (JSON)
    details: Dict[str, Any]  # {"title": "...", "reasoning": "...", "source": "..."}

    # Timestamp
    created_at: datetime

    @property
    def is_high_impact(self) -> bool:
        """Check if this is a high-impact sentiment event."""
        return self.magnitude in ("large", "extreme")

    @property
    def occurred_premarket(self) -> bool:
        """Check if event occurred during premarket hours."""
        return self.session == "premarket"

    @property
    def occurred_afterhours(self) -> bool:
        """Check if event occurred during after-hours."""
        return self.session == "afterhours"

    @property
    def occurred_regular_hours(self) -> bool:
        """Check if event occurred during regular trading hours."""
        return self.session == "regular"

    @property
    def has_details(self) -> bool:
        """Check if event has additional details."""
        return bool(self.details)

    def get_detail(self, key: str, default: Any = None) -> Any:
        """Get specific detail from details dict."""
        return self.details.get(key, default)
