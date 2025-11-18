"""Protocol for market status and holidays providers."""

from typing import Protocol, Optional, List
from models.dataclass.market_status import MarketStatusSnapshot
from models.dataclass.market_holiday import MarketHoliday


class MarketStatusProvider(Protocol):
    """Protocol for market status and holidays providers.

    Provides current market session status and trading calendar.

    Implementations:
    - PolygonMarketStatusAdapter (wraps PolygonMarketStatusProvider)
    - CustomMarketStatusProvider (future - hardcoded US hours)
    """

    def fetch_market_status(self) -> Optional[MarketStatusSnapshot]:
        """Fetch current market status.

        Returns:
            MarketStatusSnapshot with current session info, or None if error
        """
        ...

    def fetch_upcoming_holidays(self) -> Optional[List[MarketHoliday]]:
        """Fetch upcoming market holidays.

        Returns:
            List of MarketHoliday objects, or None if error
        """
        ...

    def get_provider_name(self) -> str:
        """Get provider name for logging/debugging."""
        ...
