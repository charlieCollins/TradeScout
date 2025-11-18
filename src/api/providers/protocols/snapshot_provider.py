"""Protocol for snapshot data providers."""

from typing import Protocol, Optional
from models.dataclass.snapshot import MarketSnapshot, TickerSnapshot


class SnapshotProvider(Protocol):
    """Protocol for snapshot data providers.

    Provides current/latest price snapshots for stocks.

    Implementations:
    - PolygonSnapshotAdapter (wraps PolygonSnapshotProvider)
    - YFinanceSnapshotAdapter (future)
    - IEXSnapshotAdapter (future)
    """

    def fetch_bulk_market_snapshot(self) -> Optional[MarketSnapshot]:
        """Fetch snapshots for ALL tickers in one call.

        Returns:
            MarketSnapshot containing all ticker snapshots, or None if error
        """
        ...

    def fetch_single_ticker_snapshot(self, symbol: str) -> Optional[TickerSnapshot]:
        """Fetch snapshot for a single ticker.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')

        Returns:
            TickerSnapshot or None if error
        """
        ...

    def get_provider_name(self) -> str:
        """Get provider name for logging/debugging.

        Returns:
            Provider identifier (e.g., 'polygon', 'yfinance')
        """
        ...
