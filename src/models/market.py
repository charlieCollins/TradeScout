"""Market data model for TradeScout."""

from dataclasses import dataclass
from datetime import datetime, time
from typing import Optional


@dataclass(frozen=True)
class Market:
    """Represents a trading market/exchange."""

    # Primary identification
    id: int
    code: str  # 'XNYS', 'XNAS'
    name: str  # 'New York Stock Exchange'

    # Location details
    country: str  # 'US'
    timezone: str  # 'America/New_York'
    currency: str  # 'USD'

    # Status and timestamps (required fields)
    created_at: datetime
    updated_at: datetime

    # Trading hours (in market timezone) - optional fields with defaults
    premarket_start_time: Optional[time] = None  # '04:00:00'
    premarket_end_time: Optional[time] = None    # '09:30:00'
    regular_open_time: time = time(9, 30)        # '09:30:00'
    regular_close_time: time = time(16, 0)       # '16:00:00'
    afterhours_start_time: Optional[time] = None # '16:00:00'
    afterhours_end_time: Optional[time] = None   # '20:00:00'

    # Status
    is_active: bool = True

    @property
    def has_extended_hours(self) -> bool:
        """Check if market supports extended hours trading."""
        return (self.premarket_start_time is not None or
                self.afterhours_end_time is not None)

    @property
    def display_name(self) -> str:
        """Get display name for the market."""
        return f"{self.name} ({self.code})"