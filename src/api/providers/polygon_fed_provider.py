"""Polygon Federal Reserve economic data provider.

Fetches Fed data from Polygon.io API endpoints:
- /fed/v1/inflation
- /fed/v1/inflation-expectations
- /fed/v1/treasury-yields
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import date, datetime

from .base_provider import BaseAPIProvider
from models.fed_data import FedData

logger = logging.getLogger(__name__)


class PolygonFedProvider(BaseAPIProvider):
    """Provider for Federal Reserve economic data from Polygon API."""

    def __init__(self, api_key: str):
        """Initialize Polygon Fed data provider.

        Args:
            api_key: Polygon.io API key
        """
        super().__init__(api_key, "https://api.polygon.io")

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
    # INFLATION DATA
    # ============================================================================

    def fetch_inflation(self, limit: int = 10) -> List[FedData]:
        """Fetch recent inflation data.

        Endpoint: GET /fed/v1/inflation

        Args:
            limit: Number of recent observations to fetch

        Returns:
            List of FedData objects with inflation data
        """
        try:
            params = {"limit": limit, "sort": "date.desc"}

            response = self._make_request("/fed/v1/inflation", params)

            if not response or "results" not in response:
                logger.warning("No inflation data in Polygon response")
                return []

            results = response["results"]
            fed_data_list = []

            for item in results:
                try:
                    obs_date = self._parse_date(item.get("date"))
                    if not obs_date:
                        logger.warning(f"Invalid date in inflation data: {item}")
                        continue

                    fed_data = FedData.from_polygon_data(
                        data_type="inflation",
                        polygon_data=item,
                        observation_date=obs_date,
                    )
                    fed_data_list.append(fed_data)

                except Exception as e:
                    logger.warning(f"Failed to parse inflation data point: {e}")
                    continue

            logger.info(f"Fetched {len(fed_data_list)} inflation data points")
            return fed_data_list

        except Exception as e:
            logger.error(f"Error fetching inflation data: {e}")
            return []

    # ============================================================================
    # INFLATION EXPECTATIONS DATA
    # ============================================================================

    def fetch_inflation_expectations(self, limit: int = 10) -> List[FedData]:
        """Fetch recent inflation expectations data.

        Endpoint: GET /fed/v1/inflation-expectations

        Args:
            limit: Number of recent observations to fetch

        Returns:
            List of FedData objects with inflation expectations data
        """
        try:
            params = {"limit": limit, "sort": "date.desc"}

            response = self._make_request("/fed/v1/inflation-expectations", params)

            if not response or "results" not in response:
                logger.warning("No inflation expectations data in Polygon response")
                return []

            results = response["results"]
            fed_data_list = []

            for item in results:
                try:
                    obs_date = self._parse_date(item.get("date"))
                    if not obs_date:
                        logger.warning(f"Invalid date in inflation expectations data: {item}")
                        continue

                    fed_data = FedData.from_polygon_data(
                        data_type="inflation_expectations",
                        polygon_data=item,
                        observation_date=obs_date,
                    )
                    fed_data_list.append(fed_data)

                except Exception as e:
                    logger.warning(f"Failed to parse inflation expectations data point: {e}")
                    continue

            logger.info(f"Fetched {len(fed_data_list)} inflation expectations data points")
            return fed_data_list

        except Exception as e:
            logger.error(f"Error fetching inflation expectations data: {e}")
            return []

    # ============================================================================
    # TREASURY YIELDS DATA
    # ============================================================================

    def fetch_treasury_yields(self, limit: int = 10) -> List[FedData]:
        """Fetch recent treasury yields data.

        Endpoint: GET /fed/v1/treasury-yields

        Args:
            limit: Number of recent observations to fetch

        Returns:
            List of FedData objects with treasury yields data
        """
        try:
            params = {"limit": limit, "sort": "date.desc"}

            response = self._make_request("/fed/v1/treasury-yields", params)

            if not response or "results" not in response:
                logger.warning("No treasury yields data in Polygon response")
                return []

            results = response["results"]
            fed_data_list = []

            for item in results:
                try:
                    obs_date = self._parse_date(item.get("date"))
                    if not obs_date:
                        logger.warning(f"Invalid date in treasury yields data: {item}")
                        continue

                    fed_data = FedData.from_polygon_data(
                        data_type="treasury_yields",
                        polygon_data=item,
                        observation_date=obs_date,
                    )
                    fed_data_list.append(fed_data)

                except Exception as e:
                    logger.warning(f"Failed to parse treasury yields data point: {e}")
                    continue

            logger.info(f"Fetched {len(fed_data_list)} treasury yields data points")
            return fed_data_list

        except Exception as e:
            logger.error(f"Error fetching treasury yields data: {e}")
            return []

    # ============================================================================
    # UTILITY METHODS
    # ============================================================================

    def _parse_date(self, date_str: Optional[str]) -> Optional[date]:
        """Parse date string from Polygon API.

        Args:
            date_str: Date string (YYYY-MM-DD format expected)

        Returns:
            date object or None if parsing fails
        """
        if not date_str:
            return None

        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            logger.warning(f"Could not parse date: {date_str}")
            return None

    def fetch_all_fed_data(self, limit: int = 10) -> Dict[str, List[FedData]]:
        """Fetch all types of Fed data in one call.

        Args:
            limit: Number of recent observations to fetch for each type

        Returns:
            Dictionary with keys 'inflation', 'inflation_expectations', 'treasury_yields'
        """
        return {
            "inflation": self.fetch_inflation(limit=limit),
            "inflation_expectations": self.fetch_inflation_expectations(limit=limit),
            "treasury_yields": self.fetch_treasury_yields(limit=limit),
        }
