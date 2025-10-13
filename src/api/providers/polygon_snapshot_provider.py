"""Polygon API provider for snapshot data."""

import logging
from typing import Optional, Dict, Any
from models.dataclass.snapshot import MarketSnapshot, TickerSnapshot
from .base_provider import BaseAPIProvider

logger = logging.getLogger(__name__)


class PolygonSnapshotProvider(BaseAPIProvider):
    """API provider for Polygon snapshot endpoints.

    Handles ONLY snapshot API calls - no database operations, no caching.
    """

    def __init__(self, api_key: str):
        """Initialize Polygon snapshot provider.

        Args:
            api_key: Polygon API key
        """
        super().__init__(api_key, "https://api.polygon.io")

    # ============================================================================
    # AUTHENTICATION
    # ============================================================================

    def _add_authentication(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add Polygon API key to request parameters.

        Args:
            params: Request parameters

        Returns:
            Parameters with apikey added
        """
        params["apikey"] = self.api_key
        return params

    def _get_health_endpoint(self) -> str:
        """Get health check endpoint.

        Returns:
            Endpoint for health checking
        """
        return "/v1/marketstatus/now"

    # ============================================================================
    # SNAPSHOT API CALLS
    # ============================================================================

    def fetch_single_ticker_snapshot(self, symbol: str) -> Optional[TickerSnapshot]:
        """Fetch snapshot for a single ticker from Polygon API.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')

        Returns:
            TickerSnapshot object or None if error
        """
        try:
            endpoint = f"/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}"
            raw_data = self._make_request(endpoint, {})

            if not raw_data or "ticker" not in raw_data:
                logger.warning(f"No ticker data in response for {symbol}")
                return None

            # Polygon returns: {"status": "OK", "ticker": {...}}
            # We need to wrap it in the expected format for MarketSnapshot
            polygon_response = {
                "results": [raw_data["ticker"]],
                "status": "OK"
            }

            # Parse through MarketSnapshot and extract the single ticker
            market_snapshot = MarketSnapshot.from_polygon_data(polygon_response)

            if not market_snapshot:
                logger.warning(f"Failed to parse MarketSnapshot for {symbol}")
                return None

            # Return the single ticker snapshot
            ticker_snapshot = market_snapshot.tickers.get(symbol)

            if not ticker_snapshot:
                logger.warning(f"Ticker {symbol} not found in parsed MarketSnapshot")
                return None

            logger.debug(f"Successfully fetched snapshot for {symbol}")
            return ticker_snapshot

        except Exception as e:
            logger.error(f"Error fetching ticker snapshot for {symbol}: {e}")
            return None

    def fetch_bulk_market_snapshot(self, symbols: Optional[list] = None) -> Optional[MarketSnapshot]:
        """Fetch snapshots for all tickers or specified symbols.

        Args:
            symbols: Optional list of symbols to fetch (None = all tickers)

        Returns:
            MarketSnapshot object containing all ticker snapshots, or None if error
        """
        try:
            endpoint = "/v2/snapshot/locale/us/markets/stocks/tickers"
            params = {}

            if symbols:
                # Polygon accepts comma-separated tickers
                params["tickers"] = ",".join(symbols)

            raw_data = self._make_request(endpoint, params)

            if not raw_data:
                logger.warning("No data in bulk snapshot response")
                return None

            # Parse the bulk response
            market_snapshot = MarketSnapshot.from_polygon_data(raw_data)

            if market_snapshot:
                logger.debug(f"Successfully fetched bulk snapshot with {len(market_snapshot.tickers)} tickers")
            else:
                logger.warning("Failed to parse bulk MarketSnapshot")

            return market_snapshot

        except Exception as e:
            logger.error(f"Error fetching bulk market snapshot: {e}")
            return None

    # ============================================================================
    # PROVIDER INFO
    # ============================================================================

    def get_provider_name(self) -> str:
        """Get provider name.

        Returns:
            Provider name string
        """
        return "polygon"

    def get_provider_info(self) -> Dict[str, Any]:
        """Get provider information.

        Returns:
            Dictionary with provider details
        """
        return {
            "name": self.get_provider_name(),
            "base_url": self.base_url,
            "endpoints": {
                "single_ticker": "/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}",
                "bulk_snapshot": "/v2/snapshot/locale/us/markets/stocks/tickers"
            }
        }