"""Polygon adapter for market status and holidays."""

from typing import Optional, List
from api.providers.polygon_market_status_provider import PolygonMarketStatusProvider
from models.dataclass.market_status import MarketStatusSnapshot
from models.dataclass.market_holiday import MarketHoliday


class PolygonMarketStatusAdapter:
    """Adapter for Polygon Market Status API.

    Wraps PolygonMarketStatusProvider to implement MarketStatusProvider protocol.
    """

    def __init__(self, api_key: str):
        """Initialize adapter with Polygon API key.

        Args:
            api_key: Polygon API key

        Raises:
            ValueError: If API key is empty or None
        """
        if not api_key or not api_key.strip():
            raise ValueError("Polygon API key is required")
        self._provider = PolygonMarketStatusProvider(api_key)

    def fetch_market_status(self) -> Optional[MarketStatusSnapshot]:
        """Delegate to Polygon provider."""
        return self._provider.fetch_market_status()

    def fetch_upcoming_holidays(self) -> Optional[List[MarketHoliday]]:
        """Delegate to Polygon provider."""
        return self._provider.fetch_upcoming_holidays()

    def get_provider_name(self) -> str:
        """Return provider name."""
        return "polygon"
