"""Polygon API provider for markets/exchanges reference data.

Handles fetching market/exchange data from Polygon's /v3/reference/exchanges endpoint.
Transforms Polygon's exchange data into our Market models.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, time
from models.dataclass.market import Market
from .base_provider import BaseAPIProvider

logger = logging.getLogger(__name__)

# Default US market trading hours (Eastern Time)
DEFAULT_US_TRADING_HOURS = {
    "premarket_start_time": time(4, 0),
    "premarket_end_time": time(9, 30),
    "regular_open_time": time(9, 30),
    "regular_close_time": time(16, 0),
    "afterhours_start_time": time(16, 0),
    "afterhours_end_time": time(20, 0),
}


class PolygonMarketsProvider(BaseAPIProvider):
    """API provider for Polygon markets/exchanges reference data.

    Handles ONLY markets/exchanges API calls - no database operations, no caching.
    Fetches from /v3/reference/exchanges endpoint and transforms to Market models.
    """

    def __init__(self, api_key: str):
        """Initialize Polygon markets provider.

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
    # MARKETS/EXCHANGES API CALLS
    # ============================================================================

    def fetch_all_exchanges(
        self,
        asset_class: str = "stocks",
        locale: str = "us"
    ) -> List[Market]:
        """Fetch all exchanges from Polygon API.

        Endpoint: GET /v3/reference/exchanges

        Args:
            asset_class: Asset class to filter (default: "stocks")
            locale: Locale to filter (default: "us")

        Returns:
            List of Market objects
        """
        endpoint = "/v3/reference/exchanges"
        params = {}

        if asset_class:
            params["asset_class"] = asset_class
        if locale:
            params["locale"] = locale

        try:
            response = self._make_request(endpoint, params)

            if response.get("status") != "OK":
                logger.error(f"Exchanges API error: {response}")
                return []

            exchanges = response.get("results", [])
            if not exchanges:
                logger.warning("No exchanges returned from API")
                return []

            logger.info(f"Fetched {len(exchanges)} exchanges from Polygon")

            # Parse each exchange to Market
            markets = []
            for exchange_data in exchanges:
                try:
                    market = self._parse_exchange_to_market(exchange_data)
                    if market:
                        markets.append(market)
                except Exception as e:
                    logger.warning(f"Failed to parse exchange {exchange_data.get('mic', 'unknown')}: {e}")
                    continue

            logger.info(f"Successfully parsed {len(markets)} markets")
            return markets

        except Exception as e:
            logger.error(f"Error fetching exchanges: {e}")
            return []

    def fetch_exchange_by_mic(self, mic: str) -> Optional[Market]:
        """Fetch a specific exchange by MIC code.

        Since Polygon doesn't have a single-exchange endpoint, this fetches all
        and filters client-side.

        Args:
            mic: Market Identifier Code (e.g., 'XNYS', 'XNAS')

        Returns:
            Market object or None if not found
        """
        # Fetch all and filter
        all_markets = self.fetch_all_exchanges()

        for market in all_markets:
            if market.code.upper() == mic.upper():
                return market

        logger.warning(f"Exchange {mic} not found")
        return None

    # ============================================================================
    # HELPER METHODS
    # ============================================================================

    def _parse_exchange_to_market(self, exchange_data: Dict[str, Any]) -> Optional[Market]:
        """Parse Polygon exchange data into Market model.

        Args:
            exchange_data: Raw exchange data from Polygon API

        Returns:
            Market object or None if parsing fails
        """
        try:
            mic = exchange_data.get("mic")
            if not mic:
                logger.warning("Exchange data missing 'mic' field")
                return None

            name = exchange_data.get("name", mic)
            locale = exchange_data.get("locale", "us").upper()

            # Map locale to country code
            # Polygon uses lowercase locale codes: "us", "gb", "ca", etc.
            country = locale

            # Determine timezone and trading hours based on locale
            timezone, trading_hours = self._get_market_metadata(locale)

            # Provider ID for Polygon (hardcoded for now)
            # This would ideally come from providers table lookup
            provider_id = 1

            return Market(
                id=0,  # Will be assigned by database
                code=mic,
                name=name,
                country=country,
                timezone=timezone,
                currency=self._get_currency_for_locale(locale),
                **trading_hours,
                is_active=True,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )

        except Exception as e:
            logger.error(f"Error parsing exchange data: {e}")
            return None

    def _get_market_metadata(self, locale: str) -> tuple[str, Dict[str, Any]]:
        """Get timezone and trading hours for a given locale.

        Args:
            locale: Locale code (e.g., 'us', 'gb', 'ca')

        Returns:
            Tuple of (timezone, trading_hours_dict)
        """
        locale_lower = locale.lower()

        # US markets (default)
        if locale_lower == "us":
            return "America/New_York", DEFAULT_US_TRADING_HOURS

        # UK markets
        if locale_lower == "gb":
            return "Europe/London", {
                "premarket_start_time": None,
                "premarket_end_time": None,
                "regular_open_time": time(8, 0),
                "regular_close_time": time(16, 30),
                "afterhours_start_time": None,
                "afterhours_end_time": None,
            }

        # Canadian markets
        if locale_lower == "ca":
            return "America/Toronto", {
                "premarket_start_time": None,
                "premarket_end_time": None,
                "regular_open_time": time(9, 30),
                "regular_close_time": time(16, 0),
                "afterhours_start_time": None,
                "afterhours_end_time": None,
            }

        # Default to US hours for unknown locales
        logger.debug(f"Unknown locale '{locale}', using US trading hours")
        return "America/New_York", DEFAULT_US_TRADING_HOURS

    def _get_currency_for_locale(self, locale: str) -> str:
        """Get default currency for a given locale.

        Args:
            locale: Locale code (e.g., 'us', 'gb', 'ca')

        Returns:
            Currency code (e.g., 'USD', 'GBP', 'CAD')
        """
        locale_lower = locale.lower()

        currency_map = {
            "us": "USD",
            "gb": "GBP",
            "ca": "CAD",
            "eu": "EUR",
            "jp": "JPY",
            "au": "AUD",
            "hk": "HKD",
            "sg": "SGD",
        }

        return currency_map.get(locale_lower, "USD")

    # ============================================================================
    # PROVIDER INFO
    # ============================================================================

    def get_provider_info(self) -> Dict[str, Any]:
        """Get provider information.

        Returns:
            Dictionary with provider metadata
        """
        return {
            "name": "polygon_markets",
            "base_url": self.base_url,
            "endpoints": {
                "exchanges": "/v3/reference/exchanges"
            },
            "description": "Polygon.io markets/exchanges reference data provider"
        }
