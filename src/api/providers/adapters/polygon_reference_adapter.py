"""Polygon adapter for reference data (tickers, exchanges, fundamentals)."""

from typing import Optional, List, Dict, Any
from api.providers.polygon_tickers_provider import PolygonTickersProvider
from api.providers.polygon_markets_provider import PolygonMarketsProvider
from models.dataclass.asset import Asset
from models.dataclass.market import Market


class PolygonReferenceAdapter:
    """Adapter for Polygon Reference Data APIs.

    Wraps PolygonTickersProvider and PolygonMarketsProvider to implement
    ReferenceDataProvider protocol.

    This adapter combines two Polygon providers since reference data
    comes from multiple endpoints.
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
        self._tickers_provider = PolygonTickersProvider(api_key)
        self._markets_provider = PolygonMarketsProvider(api_key)

    def fetch_ticker_details(
        self,
        symbol: str,
        market_code_to_id: Optional[Dict[str, int]] = None
    ) -> Optional[Asset]:
        """Delegate to Polygon tickers provider."""
        return self._tickers_provider.fetch_ticker_details(symbol, market_code_to_id)

    def fetch_ticker_details_raw(
        self,
        symbol: str
    ) -> Optional[Dict[str, Any]]:
        """Delegate to Polygon tickers provider."""
        return self._tickers_provider.fetch_ticker_details_raw(symbol)

    def fetch_all_tickers(
        self,
        market: str = "stocks",
        active: bool = True,
        limit: Optional[int] = None,
        market_code_to_id: Optional[Dict[str, int]] = None
    ) -> List[Asset]:
        """Delegate to Polygon tickers provider."""
        return self._tickers_provider.fetch_all_tickers(market, active, limit, market_code_to_id)

    def fetch_all_exchanges(
        self,
        asset_class: str = "stocks",
        locale: str = "us"
    ) -> List[Market]:
        """Delegate to Polygon markets provider."""
        return self._markets_provider.fetch_all_exchanges(asset_class, locale)

    def get_provider_name(self) -> str:
        """Return provider name."""
        return "polygon"
