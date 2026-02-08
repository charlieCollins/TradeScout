"""FRED (Federal Reserve Economic Data) adapter for economic data.

Implements EconomicDataProvider protocol using the FRED API.
Free API with key signup at https://fred.stlouisfed.org/docs/api/api_key.html

FRED Series used:
- CPIAUCSL: Consumer Price Index (inflation)
- T5YIE: 5-Year Breakeven Inflation Rate (inflation expectations)
- DGS10: 10-Year Treasury Constant Maturity Rate
- DGS2: 2-Year Treasury Constant Maturity Rate
- DGS30: 30-Year Treasury Constant Maturity Rate
"""

import logging
from typing import List, Dict, Optional
from datetime import datetime, date, timedelta
from decimal import Decimal

import requests

from models.dataclass.fed_data import FedData
from api.providers.protocols.economic_data_provider import EconomicDataProvider

logger = logging.getLogger(__name__)

FRED_BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

# FRED series IDs
SERIES_CPI = "CPIAUCSL"
SERIES_INFLATION_EXPECTATIONS = "T5YIE"
SERIES_TREASURY_10Y = "DGS10"
SERIES_TREASURY_2Y = "DGS2"
SERIES_TREASURY_30Y = "DGS30"


class FREDEconomicAdapter(EconomicDataProvider):
    """Adapter for FRED (Federal Reserve Economic Data) API.

    Implements EconomicDataProvider protocol using the free FRED API.
    Requires a free API key from https://fred.stlouisfed.org/docs/api/api_key.html

    Capabilities:
    - CPI inflation data (monthly)
    - Inflation expectations (daily)
    - Treasury yields at multiple maturities (daily)
    """

    def __init__(self, api_key: str):
        if not api_key or not api_key.strip():
            raise ValueError(
                "FRED API key is required. "
                "Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html"
            )
        self.api_key = api_key

    def _fetch_series(
        self,
        series_id: str,
        limit: int = 10,
        sort_order: str = "desc"
    ) -> Optional[List[dict]]:
        """Fetch observations from a FRED series.

        Args:
            series_id: FRED series identifier
            limit: Number of observations to fetch
            sort_order: 'asc' or 'desc'

        Returns:
            List of observation dicts or None if error
        """
        try:
            params = {
                "series_id": series_id,
                "api_key": self.api_key,
                "file_type": "json",
                "sort_order": sort_order,
                "limit": limit,
            }

            response = requests.get(FRED_BASE_URL, params=params, timeout=15)
            response.raise_for_status()

            data = response.json()
            observations = data.get("observations", [])

            # Filter out observations with missing values
            valid = [
                obs for obs in observations
                if obs.get("value") and obs["value"] != "."
            ]

            return valid

        except requests.exceptions.RequestException as e:
            logger.error(f"FRED API request failed for {series_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error fetching FRED series {series_id}: {e}")
            return None

    def fetch_inflation(self, limit: int = 10) -> List[FedData]:
        """Fetch CPI inflation data from FRED.

        Uses CPIAUCSL series and calculates year-over-year change.

        Args:
            limit: Number of recent observations

        Returns:
            List of FedData objects with inflation data
        """
        # Fetch extra observations to calculate YoY
        observations = self._fetch_series(SERIES_CPI, limit=limit + 12, sort_order="desc")
        if not observations:
            return []

        results = []
        obs_by_date = {obs["date"]: float(obs["value"]) for obs in observations}
        sorted_dates = sorted(obs_by_date.keys(), reverse=True)

        for obs_date_str in sorted_dates[:limit]:
            obs_value = obs_by_date[obs_date_str]
            obs_date = date.fromisoformat(obs_date_str)

            # Calculate YoY: find value from ~12 months ago
            target_date = obs_date - timedelta(days=365)
            yoy_value = Decimal("0")

            # Find closest observation to 12 months ago
            prior_dates = [d for d in sorted_dates if d <= target_date.isoformat()]
            if prior_dates:
                prior_value = obs_by_date[prior_dates[0]]
                if prior_value > 0:
                    yoy_value = Decimal(str(
                        ((obs_value - prior_value) / prior_value) * 100
                    ))

            details = {
                "series_id": SERIES_CPI,
                "cpi": obs_value,
                "cpi_year_over_year": float(yoy_value),
            }

            results.append(FedData(
                id=0,
                data_type="inflation",
                observation_date=obs_date,
                value=yoy_value,
                details=details,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            ))

        return results

    def fetch_inflation_expectations(self, limit: int = 10) -> List[FedData]:
        """Fetch 5-Year Breakeven Inflation Rate from FRED.

        Uses T5YIE series (market-implied inflation expectations).

        Args:
            limit: Number of recent observations

        Returns:
            List of FedData objects with inflation expectations
        """
        observations = self._fetch_series(SERIES_INFLATION_EXPECTATIONS, limit=limit)
        if not observations:
            return []

        results = []
        for obs in observations:
            obs_date = date.fromisoformat(obs["date"])
            value = Decimal(obs["value"])

            details = {
                "series_id": SERIES_INFLATION_EXPECTATIONS,
                "market_5_year": float(value),
            }

            results.append(FedData(
                id=0,
                data_type="inflation_expectations",
                observation_date=obs_date,
                value=value,
                details=details,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            ))

        return results

    def fetch_treasury_yields(self, limit: int = 10) -> List[FedData]:
        """Fetch Treasury yield data from FRED.

        Fetches 2Y, 10Y, and 30Y yields and combines them per date.

        Args:
            limit: Number of recent observations

        Returns:
            List of FedData objects with treasury yield data
        """
        # Fetch all three maturities
        yields_10y = self._fetch_series(SERIES_TREASURY_10Y, limit=limit)
        yields_2y = self._fetch_series(SERIES_TREASURY_2Y, limit=limit)
        yields_30y = self._fetch_series(SERIES_TREASURY_30Y, limit=limit)

        if not yields_10y:
            return []

        # Index by date for joining
        y2_map = {obs["date"]: float(obs["value"]) for obs in (yields_2y or [])}
        y30_map = {obs["date"]: float(obs["value"]) for obs in (yields_30y or [])}

        results = []
        for obs in yields_10y:
            obs_date = date.fromisoformat(obs["date"])
            value_10y = float(obs["value"])
            value_2y = y2_map.get(obs["date"])
            value_30y = y30_map.get(obs["date"])

            details = {
                "yield_10_year": value_10y,
                "yield_2_year": value_2y,
                "yield_30_year": value_30y,
                "source": "FRED",
            }

            # Use 10Y as representative value
            results.append(FedData(
                id=0,
                data_type="treasury_yields",
                observation_date=obs_date,
                value=Decimal(str(value_10y)),
                details=details,
                created_at=datetime.now(),
                updated_at=datetime.now(),
            ))

        return results

    def fetch_all_fed_data(self, limit: int = 10) -> Dict[str, List[FedData]]:
        """Fetch all types of economic data from FRED.

        Args:
            limit: Number of recent observations per type

        Returns:
            Dict with keys: 'inflation', 'inflation_expectations', 'treasury_yields'
        """
        return {
            "inflation": self.fetch_inflation(limit),
            "inflation_expectations": self.fetch_inflation_expectations(limit),
            "treasury_yields": self.fetch_treasury_yields(limit),
        }

    def get_provider_name(self) -> str:
        return "fred"
