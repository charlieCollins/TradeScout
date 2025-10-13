"""Polygon API provider for market status and holidays.

Handles fetching market status and holiday calendar from Polygon's market status endpoints.
Transforms Polygon's market status data into our MarketContext and MarketHoliday models.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, date
from models.dataclass.market_holiday import MarketHoliday, HolidayStatus
from .base_provider import BaseAPIProvider

logger = logging.getLogger(__name__)


class PolygonMarketStatusProvider(BaseAPIProvider):
    """API provider for Polygon market status and holidays.

    Handles ONLY market status API calls - no database operations, no caching.
    Fetches from /v1/marketstatus/* endpoints and transforms to our models.
    """

    def __init__(self, api_key: str):
        """Initialize Polygon market status provider.

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
    # MARKET STATUS API CALLS
    # ============================================================================

    def fetch_market_status(self) -> Optional[Dict[str, Any]]:
        """Fetch current market status from Polygon API.

        Endpoint: GET /v1/marketstatus/now

        Returns raw market status data that can be used to construct MarketContext.
        The actual MarketContext construction is done in the service layer because
        it requires Market model data from the database.

        Returns:
            Raw API response dict with market status, or None if error

        Example response:
        {
            "market": "open",
            "serverTime": "2024-01-15T14:30:00-05:00",
            "exchanges": {
                "nyse": "open",
                "nasdaq": "open",
                "otc": "closed"
            },
            "currencies": {
                "fx": "open",
                "crypto": "open"
            }
        }
        """
        try:
            data = self._make_request("/v1/marketstatus/now")

            logger.debug(f"Fetched market status: {data.get('market', 'unknown')}")
            return data

        except Exception as e:
            logger.error(f"Error fetching market status: {e}")
            return None

    def fetch_upcoming_holidays(self) -> Optional[List[MarketHoliday]]:
        """Fetch upcoming market holidays from Polygon API.

        Endpoint: GET /v1/marketstatus/upcoming

        Returns:
            List of MarketHoliday objects, or None if error

        Example response from Polygon:
        [
            {
                "exchange": "NYSE",
                "name": "New Year's Day",
                "date": "2024-01-01",
                "status": "closed"
            },
            {
                "exchange": "NASDAQ",
                "name": "Day Before Independence Day",
                "date": "2024-07-03",
                "status": "early-close"
            }
        ]
        """
        try:
            data = self._make_request("/v1/marketstatus/upcoming")

            # Parse each holiday from the response
            # Note: Polygon returns one holiday per exchange (NYSE, NASDAQ, etc.)
            # We deduplicate by date since all US exchanges have same holidays
            holidays_by_date = {}
            for holiday_data in data:
                try:
                    holiday = MarketHoliday.from_polygon_data(holiday_data)
                    # Keep only first holiday for each date (they're all the same)
                    if holiday.date not in holidays_by_date:
                        holidays_by_date[holiday.date] = holiday
                except Exception as e:
                    logger.warning(f"Failed to parse holiday data {holiday_data}: {e}")
                    continue

            holidays = list(holidays_by_date.values())
            logger.debug(f"Fetched {len(holidays)} unique upcoming holidays")
            return holidays

        except Exception as e:
            logger.error(f"Error fetching upcoming holidays: {e}")
            return None

    # ============================================================================
    # PROVIDER INFO
    # ============================================================================

    def get_provider_name(self) -> str:
        """Get provider name for logging/debugging.

        Returns:
            Provider identifier string
        """
        return "polygon_market_status"

    def get_provider_info(self) -> Dict[str, Any]:
        """Get provider information.

        Returns:
            Dictionary with provider details
        """
        return {
            "name": self.get_provider_name(),
            "base_url": self.base_url,
            "endpoints": {
                "market_status": "/v1/marketstatus/now",
                "upcoming_holidays": "/v1/marketstatus/upcoming"
            }
        }
