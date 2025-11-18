"""Protocol for economic data providers (Fed, inflation, yields)."""

from typing import Protocol, List, Dict
from models.dataclass.fed_data import FedData


class EconomicDataProvider(Protocol):
    """Protocol for economic data providers.

    Provides Federal Reserve data, inflation metrics, treasury yields.

    Implementations:
    - PolygonEconomicAdapter (wraps PolygonFedProvider)
    - FREDAdapter (future - official Federal Reserve API)
    """

    def fetch_inflation(self, limit: int = 10) -> List[FedData]:
        """Fetch recent inflation data.

        Args:
            limit: Number of recent observations to fetch

        Returns:
            List of FedData objects with inflation data
        """
        ...

    def fetch_inflation_expectations(self, limit: int = 10) -> List[FedData]:
        """Fetch recent inflation expectations data.

        Args:
            limit: Number of recent observations to fetch

        Returns:
            List of FedData objects with inflation expectations
        """
        ...

    def fetch_treasury_yields(self, limit: int = 10) -> List[FedData]:
        """Fetch recent treasury yields data.

        Args:
            limit: Number of recent observations to fetch

        Returns:
            List of FedData objects with treasury yields
        """
        ...

    def fetch_all_fed_data(self, limit: int = 10) -> Dict[str, List[FedData]]:
        """Fetch all types of Fed data in one call.

        Args:
            limit: Number of recent observations per type

        Returns:
            Dict with keys: 'inflation', 'inflation_expectations', 'treasury_yields'
        """
        ...

    def get_provider_name(self) -> str:
        """Get provider name for logging/debugging."""
        ...
