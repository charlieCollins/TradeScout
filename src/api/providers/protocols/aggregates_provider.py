"""Protocol for aggregates/bars data providers."""

from typing import Protocol, Optional, List, Dict
from datetime import datetime, date
from models.dataclass.price_bar import PriceBar


class AggregatesProvider(Protocol):
    """Protocol for historical aggregates/bars data providers.

    Provides historical OHLCV data at various timeframes.

    Implementations:
    - PolygonAggregatesAdapter (wraps PolygonAggregatesProvider)
    - YFinanceAggregatesAdapter (future)
    """

    def fetch_minute_bars(
        self,
        symbol: str,
        from_datetime: datetime,
        to_datetime: datetime,
        adjusted: bool = True
    ) -> Optional[List[PriceBar]]:
        """Fetch minute-level bars for a symbol within a time range.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            from_datetime: Start datetime (inclusive)
            to_datetime: End datetime (inclusive)
            adjusted: Whether to return adjusted prices

        Returns:
            List of PriceBar objects, or None if error
        """
        ...

    def get_daily_aggregates(
        self,
        symbol: str,
        from_date: date,
        to_date: date,
        adjusted: bool = True
    ) -> Optional[List[PriceBar]]:
        """Fetch daily aggregates for a symbol within a date range.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            from_date: Start date (inclusive)
            to_date: End date (inclusive)
            adjusted: Whether to return adjusted prices

        Returns:
            List of PriceBar objects, or None if error
        """
        ...

    def fetch_grouped_daily_bars(
        self,
        target_date: date,
        adjusted: bool = True
    ) -> Optional[Dict[str, PriceBar]]:
        """Fetch end-of-day bars for all stocks traded on a specific date.

        Args:
            target_date: Trading date to fetch
            adjusted: Whether to return adjusted prices

        Returns:
            Dict mapping symbol -> PriceBar for all stocks, or None if error
        """
        ...

    def calculate_extended_hours_volume(
        self,
        symbol: str,
        trading_date: date,
        session: str = "afterhours"
    ) -> Optional[int]:
        """Calculate total volume for an extended hours session.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            trading_date: Trading date
            session: Session type - "premarket" or "afterhours"

        Returns:
            Total volume for the session, or None if error
        """
        ...

    def get_provider_name(self) -> str:
        """Get provider name for logging/debugging."""
        ...
