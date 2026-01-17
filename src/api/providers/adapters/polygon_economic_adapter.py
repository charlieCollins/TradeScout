"""Polygon adapter for economic data (Fed, inflation, yields)."""

from typing import List, Dict
from api.providers.polygon_fed_provider import PolygonFedProvider
from models.dataclass.fed_data import FedData


class PolygonEconomicAdapter:
    """Adapter for Polygon Fed/Economic Data API.

    Wraps PolygonFedProvider to implement EconomicDataProvider protocol.
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
        self._provider = PolygonFedProvider(api_key)

    def fetch_inflation(self, limit: int = 10) -> List[FedData]:
        """Delegate to Polygon provider."""
        return self._provider.fetch_inflation(limit)

    def fetch_inflation_expectations(self, limit: int = 10) -> List[FedData]:
        """Delegate to Polygon provider."""
        return self._provider.fetch_inflation_expectations(limit)

    def fetch_treasury_yields(self, limit: int = 10) -> List[FedData]:
        """Delegate to Polygon provider."""
        return self._provider.fetch_treasury_yields(limit)

    def fetch_all_fed_data(self, limit: int = 10) -> Dict[str, List[FedData]]:
        """Delegate to Polygon provider."""
        return self._provider.fetch_all_fed_data(limit)

    def get_provider_name(self) -> str:
        """Return provider name."""
        return "polygon"
