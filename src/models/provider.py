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

    @classmethod
    def from_db_row(cls, row: tuple) -> 'Provider':
        """Create Provider from database row."""
        return cls(
            id=row[0],
            name=row[1],
            display_name=row[2],
            base_url=row[3],
            api_key_required=bool(row[4]),
            is_active=bool(row[5]),
            created_at=datetime.fromisoformat(row[6]) if row[6] else None
        )