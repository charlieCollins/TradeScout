"""Provider data model for TradeScout."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Provider:
    """Represents a data provider (API source)."""

    # Primary identification
    id: int
    name: str  # 'polygon', 'yfinance', 'alphavantage'

    # Status
    is_active: bool = True

    @property
    def display_name(self) -> str:
        """Get display name for the provider."""
        return self.name.title()