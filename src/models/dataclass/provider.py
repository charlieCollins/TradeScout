"""Provider data model for TradeScout."""

from dataclasses import dataclass
from typing import Optional
from datetime import datetime


@dataclass(frozen=True)
class Provider:
    """Represents a data provider (API source)."""

    # Primary identification
    id: int
    name: str  # 'polygon', 'yfinance', 'alphavantage'
    display_name: str  # Human-readable name

    # Configuration
    base_url: Optional[str] = None
    api_key_required: bool = True

    # Status
    is_active: bool = True
    created_at: Optional[datetime] = None

    @property
    def name_display(self) -> str:
        """Get display name for the provider."""
        return self.display_name or self.name.title()