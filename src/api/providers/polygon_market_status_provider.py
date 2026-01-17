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

    def add_authentication(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add Polygon API key to request parameters.

        Args:
            params: Request parameters

        Returns:
            Parameters with apikey added
        """
        params["apikey"] = self.api_key
        return params

    def get_health_endpoint(self) -> str:
        """Get health check endpoint.

        Returns:
            Endpoint for health checking
        """
        return "/v1/marketstatus/now"

    # ============================================================================
    # MARKET STATUS API CALLS
    # ============================================================================

    def fetch_market_status(self) -> Optional["MarketStatusSnapshot"]:
        """Fetch current market status from Polygon API.

        Endpoint: GET /v1/marketstatus/now

        Returns:
            MarketStatusSnapshot object, or None if error
        """
        from models.dataclass.market_status import MarketStatusSnapshot
        from datetime import datetime

        try:
            data = self._make_request("/v1/marketstatus/now")

            if not data:
                return None

            # Parse server time
            server_time_str = data.get("serverTime", "")
            try:
                # Polygon format: "2024-01-15T14:30:00-05:00"
                server_time = datetime.fromisoformat(server_time_str)
            except Exception:
                logger.warning(f"Failed to parse serverTime: {server_time_str}, using current time")
                server_time = datetime.now()

            # Create MarketStatusSnapshot
            market_status = MarketStatusSnapshot(
                market=data.get("market", "unknown"),
                server_time=server_time,
                exchanges=data.get("exchanges", {}),
                currencies=data.get("currencies", {}),
                early_hours=data.get("earlyHours", False),
                after_hours=data.get("afterHours", False)
            )

            logger.debug(f"Fetched market status: {market_status.market}")
            return market_status

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

            if not data:
                logger.warning("No data returned from holidays API")
                return None

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
