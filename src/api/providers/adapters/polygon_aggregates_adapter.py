"""Polygon adapter for aggregates/bars data."""

from typing import Optional, List, Dict
from datetime import datetime, date
from api.providers.polygon_aggregates_provider import PolygonAggregatesProvider
from models.dataclass.price_bar import PriceBar


class PolygonAggregatesAdapter:
    """Adapter for Polygon Aggregates API.

    Wraps PolygonAggregatesProvider to implement AggregatesProvider protocol.
    """

    def __init__(self, api_key: str):
        """Initialize adapter with Polygon API key.

        Args:
            api_key: Polygon API key
        """
        self._provider = PolygonAggregatesProvider(api_key)

    def fetch_minute_bars(
        self,
        symbol: str,
        from_datetime: datetime,
        to_datetime: datetime,
        adjusted: bool = True
    ) -> Optional[List[PriceBar]]:
        """Delegate to Polygon provider."""
        return self._provider.fetch_minute_bars(symbol, from_datetime, to_datetime, adjusted)

    def get_daily_aggregates(
        self,
        symbol: str,
        from_date: date,
        to_date: date,
        adjusted: bool = True
    ) -> Optional[List[PriceBar]]:
        """Delegate to Polygon provider."""
        return self._provider.get_daily_aggregates(symbol, from_date, to_date, adjusted)

    def fetch_grouped_daily_bars(
        self,
        target_date: date,
        adjusted: bool = True
    ) -> Optional[Dict[str, PriceBar]]:
        """Delegate to Polygon provider."""
        return self._provider.fetch_grouped_daily_bars(target_date, adjusted)

    def calculate_extended_hours_volume(
        self,
        symbol: str,
        trading_date: date,
        session: str = "afterhours"
    ) -> Optional[int]:
        """Delegate to Polygon provider."""
        return self._provider.calculate_extended_hours_volume(symbol, trading_date, session)

    def get_provider_name(self) -> str:
        """Return provider name."""
        return "polygon"
