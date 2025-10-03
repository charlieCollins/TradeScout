"""Polygon API provider for ticker reference data and fundamentals.

Handles fetching ticker/asset data from Polygon's /v3/reference/tickers endpoint.

IMPORTANT: The /v3/reference/tickers/{symbol} endpoint returns BOTH:
- Ticker reference data (symbol, name, type, market) → used to create Asset models
- Fundamentals data (market cap, sector, shares outstanding) → used to create AssetFundamentals models

This means a single API call provides data for two different entities in our system.
The provider offers both parsed (Asset) and raw (dict) methods to support both use cases.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from models.asset import Asset, AssetType, AssetClass
from .base_provider import BaseAPIProvider

logger = logging.getLogger(__name__)


class PolygonTickersProvider(BaseAPIProvider):
    """API provider for Polygon tickers/reference data endpoints.

    Handles ONLY ticker reference API calls - no database operations, no caching.
    Fetches from /v3/reference/tickers endpoint and transforms to Asset models.
    """

    def __init__(self, api_key: str):
        """Initialize Polygon tickers provider.

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
    # TICKER REFERENCE API CALLS
    # ============================================================================

    def fetch_ticker_details(self, symbol: str) -> Optional[Asset]:
        """Fetch details for a single ticker from Polygon API.

        Endpoint: GET /v3/reference/tickers/{symbol}

        Args:
            symbol: Stock symbol (e.g., 'AAPL')

        Returns:
            Asset object or None if error
        """
        ticker_data = self.fetch_ticker_details_raw(symbol)
        if not ticker_data:
            return None

        return self._parse_ticker_to_asset(ticker_data)

    def fetch_ticker_details_raw(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Fetch raw ticker details from Polygon API.

        This method returns the raw API response data, which contains both
        asset reference data (symbol, name, type) and fundamentals data
        (market cap, sector, shares outstanding).

        Endpoint: GET /v3/reference/tickers/{symbol}

        Args:
            symbol: Stock symbol (e.g., 'AAPL')

        Returns:
            Raw ticker data dict from Polygon API or None if error
        """
        endpoint = f"/v3/reference/tickers/{symbol.upper()}"

        try:
            response = self._make_request(endpoint)

            if response.get("status") != "OK":
                logger.warning(f"Ticker {symbol} not found or API error")
                return None

            ticker_data = response.get("results")
            if not ticker_data:
                logger.warning(f"No ticker data returned for {symbol}")
                return None

            return ticker_data

        except Exception as e:
            logger.error(f"Error fetching ticker details for {symbol}: {e}")
            return None

    def fetch_all_tickers(
        self,
        market: str = "stocks",
        active: bool = True,
        limit: int = 1000,
        market_code_to_id: Optional[Dict[str, int]] = None
    ) -> List[Asset]:
        """Fetch all tickers from Polygon API (paginated).

        Endpoint: GET /v3/reference/tickers

        Args:
            market: Market type (default: "stocks")
            active: Only active tickers (default: True)
            limit: Results per page (default: 1000, max: 1000)
            market_code_to_id: Mapping of market codes (XNAS, XNYS) to database IDs

        Returns:
            List of Asset objects
        """
        endpoint = "/v3/reference/tickers"
        all_assets = []
        next_url = None

        params = {
            "market": market,
            "active": "true" if active else "false",
            "limit": min(limit, 1000),  # Polygon max is 1000
            "sort": "ticker",
            "order": "asc"
        }

        try:
            while True:
                if next_url:
                    # Use next_url from pagination (already includes params)
                    response = self._make_request_with_url(next_url)
                else:
                    response = self._make_request(endpoint, params)

                if response.get("status") != "OK":
                    logger.error(f"API error fetching tickers: {response}")
                    break

                tickers = response.get("results", [])
                if not tickers:
                    break

                # Parse each ticker to Asset
                for ticker_data in tickers:
                    try:
                        asset = self._parse_ticker_to_asset(ticker_data, market_code_to_id)
                        if asset:
                            all_assets.append(asset)
                    except Exception as e:
                        logger.warning(f"Failed to parse ticker {ticker_data.get('ticker', 'unknown')}: {e}")
                        continue

                # Check for pagination
                next_url = response.get("next_url")
                if not next_url:
                    break

                logger.debug(f"Fetched {len(all_assets)} tickers so far, continuing pagination...")

            logger.info(f"Fetched total of {len(all_assets)} tickers from Polygon")
            return all_assets

        except Exception as e:
            logger.error(f"Error fetching all tickers: {e}")
            return all_assets  # Return what we have so far

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    def _make_request_with_url(self, full_url: str) -> Dict[str, Any]:
        """Make request using full URL (for pagination).

        Args:
            full_url: Complete URL with parameters (from next_url)

        Returns:
            Parsed JSON response
        """
        import requests
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

        logger.debug(f"Making paginated request to {full_url}")

        # Parse URL and add API key to parameters
        parsed = urlparse(full_url)
        params = parse_qs(parsed.query)

        # Add API key (Polygon expects it as a query parameter)
        params['apikey'] = [self.api_key]

        # Reconstruct URL with API key
        new_query = urlencode(params, doseq=True)
        authenticated_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            new_query,
            parsed.fragment
        ))

        try:
            response = requests.get(authenticated_url)

            # Handle rate limiting
            if response.status_code == 429:
                logger.warning("Rate limit hit, waiting before retry...")
                self._handle_rate_limit(response)
                response = requests.get(authenticated_url)

            response.raise_for_status()
            return response.json()

        except requests.RequestException as e:
            logger.error(f"Request failed: {e}")
            raise

    def _parse_ticker_to_asset(
        self,
        ticker_data: Dict[str, Any],
        market_code_to_id: Optional[Dict[str, int]] = None
    ) -> Optional[Asset]:
        """Parse Polygon ticker data into Asset model.

        Args:
            ticker_data: Raw ticker data from Polygon API
            market_code_to_id: Mapping of market codes (XNAS, XNYS) to database IDs

        Returns:
            Asset object or None if parsing fails
        """
        try:
            symbol = ticker_data.get("ticker")
            if not symbol:
                logger.warning("Ticker data missing 'ticker' field")
                return None

            # Map Polygon ticker type to our AssetType
            polygon_type = ticker_data.get("type", "CS")
            asset_type = self._map_polygon_type_to_asset_type(polygon_type)

            # Map to AssetClass (simplified - all equity for now)
            asset_class = AssetClass.EQUITY

            # Get market_id from primary_exchange using the mapping
            primary_exchange = ticker_data.get("primary_exchange")

            if not primary_exchange:
                raise ValueError(f"Ticker {symbol} missing primary_exchange field - cannot assign to market")

            if not market_code_to_id:
                raise ValueError(f"No market mapping provided - cannot assign ticker {symbol} to market {primary_exchange}")

            market_id = market_code_to_id.get(primary_exchange)
            if not market_id:
                available_markets = list(market_code_to_id.keys())
                raise ValueError(
                    f"Market '{primary_exchange}' for ticker {symbol} not found in markets table. "
                    f"Available markets: {available_markets}. "
                    f"Run 'bootstrap-markets' to add missing exchanges."
                )

            # Provider ID for Polygon (hardcoded for now, will be fixed by bootstrap)
            provider_id = 1

            return Asset(
                id=0,  # Will be assigned by database
                symbol=symbol,
                name=ticker_data.get("name", symbol),
                asset_type=asset_type,
                asset_class=asset_class,
                market_id=market_id,
                currency=ticker_data.get("currency_name", "USD"),
                provider_id=provider_id,
                created_at=datetime.now(),
                updated_at=datetime.now(),
                lot_size=1,  # Default
                tick_size=None,
                is_active=ticker_data.get("active", True),
                is_delisted=ticker_data.get("delisted_utc") is not None,
                listing_date=None,  # Could parse from ticker_data if available
                delisting_date=None  # Could parse from ticker_data if available
            )

        except Exception as e:
            logger.error(f"Error parsing ticker data: {e}")
            return None

    def _map_polygon_type_to_asset_type(self, polygon_type: str) -> AssetType:
        """Map Polygon ticker type to our AssetType enum.

        Args:
            polygon_type: Polygon type code (CS, ETF, ADRC, etc.)

        Returns:
            AssetType enum value
        """
        # Polygon type codes:
        # CS = Common Stock
        # ETF = Exchange Traded Fund
        # ADRC = American Depository Receipt Common
        # ETS = Exchange Traded Security
        # etc.

        if polygon_type in ("CS", "ADRC", "PFD"):
            return AssetType.STOCK
        elif polygon_type in ("ETF", "ETS", "ETN"):
            return AssetType.ETF
        elif polygon_type in ("REIT", "REITS"):
            return AssetType.REIT
        elif polygon_type == "FUND":
            return AssetType.FUND
        elif polygon_type in ("WARRANT", "RIGHT"):
            return AssetType.WARRANT
        else:
            # Default to STOCK for unknown types
            logger.debug(f"Unknown Polygon type '{polygon_type}', defaulting to STOCK")
            return AssetType.STOCK

    # ============================================================================
    # PROVIDER INFO
    # ============================================================================

    def get_provider_info(self) -> Dict[str, Any]:
        """Get provider information.

        Returns:
            Dictionary with provider metadata
        """
        return {
            "name": "polygon_tickers",
            "base_url": self.base_url,
            "endpoints": {
                "ticker_details": "/v3/reference/tickers/{symbol}",
                "all_tickers": "/v3/reference/tickers"
            },
            "description": "Polygon.io ticker reference data provider"
        }
