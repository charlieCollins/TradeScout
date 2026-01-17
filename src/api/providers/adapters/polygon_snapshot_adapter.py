"""Polygon adapter for snapshot data."""

from typing import Optional
from api.providers.polygon_snapshot_provider import PolygonSnapshotProvider
from models.dataclass.snapshot import MarketSnapshot, TickerSnapshot


class PolygonSnapshotAdapter:
    """Adapter for Polygon Snapshot API.

    Wraps PolygonSnapshotProvider to implement SnapshotProvider protocol.
    Simple delegation - no transformation needed.
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
        self._provider = PolygonSnapshotProvider(api_key)

    def fetch_bulk_market_snapshot(self) -> Optional[MarketSnapshot]:
        """Delegate to Polygon provider."""
        return self._provider.fetch_bulk_market_snapshot()

    def fetch_single_ticker_snapshot(self, symbol: str) -> Optional[TickerSnapshot]:
        """Delegate to Polygon provider."""
        return self._provider.fetch_single_ticker_snapshot(symbol)

    def get_provider_name(self) -> str:
        """Return provider name."""
        return "polygon"
