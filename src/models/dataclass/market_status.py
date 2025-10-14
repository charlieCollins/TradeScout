"""MarketStatus domain model - represents current market status."""

from dataclasses import dataclass
from datetime import datetime
from typing import Dict


@dataclass
class MarketStatusSnapshot:
    """Domain model representing current market status.

    This is the clean interface between API providers and business logic.
    Providers transform their API responses into this standard format.
    """

    # Overall market status
    market: str  # "open", "closed", "extended-hours"
    server_time: datetime

    # Individual exchange statuses
    exchanges: Dict[str, str]  # {"nyse": "open", "nasdaq": "open", "otc": "closed"}

    # Currency market statuses
    currencies: Dict[str, str]  # {"fx": "open", "crypto": "open"}

    # Extended hours flags
    early_hours: bool = False  # True if premarket hours
    after_hours: bool = False  # True if aftermarket hours

    def is_market_open(self) -> bool:
        """Check if overall market is open."""
        return self.market == "open"

    def is_exchange_open(self, exchange: str) -> bool:
        """Check if specific exchange is open.

        Args:
            exchange: Exchange code (e.g., 'nyse', 'nasdaq')

        Returns:
            True if exchange is open, False otherwise
        """
        return self.exchanges.get(exchange.lower()) == "open"

    def is_extended_hours(self) -> bool:
        """Check if in extended hours trading."""
        return self.market == "extended-hours" or self.early_hours or self.after_hours
