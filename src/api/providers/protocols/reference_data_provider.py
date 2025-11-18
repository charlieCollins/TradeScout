"""Protocol for reference data providers (tickers, exchanges, fundamentals)."""

from typing import Protocol, Optional, List, Dict, Any
from models.dataclass.asset import Asset
from models.dataclass.market import Market


class ReferenceDataProvider(Protocol):
    """Protocol for reference data providers.

    Provides ticker metadata, exchange data, and fundamentals.

    Implementations:
    - PolygonReferenceAdapter (wraps PolygonTickersProvider + PolygonMarketsProvider)
    - YFinanceReferenceAdapter (future)
    """

    def fetch_ticker_details(
        self,
        symbol: str,
        market_code_to_id: Optional[Dict[str, int]] = None
    ) -> Optional[Asset]:
        """Fetch details for a single ticker.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            market_code_to_id: Mapping of market codes to database IDs

        Returns:
            Asset object or None if error
        """
        ...

    def fetch_ticker_details_raw(
        self,
        symbol: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch raw ticker details (includes fundamentals data).

        Args:
            symbol: Stock symbol (e.g., 'AAPL')

        Returns:
            Raw ticker data dict or None if error
        """
        ...

    def fetch_all_tickers(
        self,
        market: str = "stocks",
        active: bool = True,
        limit: Optional[int] = None,
        market_code_to_id: Optional[Dict[str, int]] = None
    ) -> List[Asset]:
        """Fetch all tickers (paginated).

        Args:
            market: Market type (e.g., "stocks")
            active: Only active tickers
            limit: Results per page
            market_code_to_id: Mapping of market codes to database IDs

        Returns:
            List of Asset objects
        """
        ...

    def fetch_all_exchanges(
        self,
        asset_class: str = "stocks",
        locale: str = "us"
    ) -> List[Market]:
        """Fetch all exchanges.

        Args:
            asset_class: Asset class to filter
            locale: Locale to filter

        Returns:
            List of Market objects
        """
        ...

    def get_provider_name(self) -> str:
        """Get provider name for logging/debugging."""
        ...
