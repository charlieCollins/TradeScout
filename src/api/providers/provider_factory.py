"""Provider factory for creating data providers based on configuration."""

import logging
import os
from typing import Optional
from utils.config_loader import ConfigLoader

logger = logging.getLogger(__name__)


class ProviderFactory:
    """Factory for creating data providers based on configuration.

    Reads from configs/providers.yaml to determine which provider to use.
    Falls back to environment variables for API keys.

    Example usage:
        snapshot_provider = ProviderFactory.create_snapshot_provider()
        market_snapshot = snapshot_provider.fetch_bulk_market_snapshot()
    """

    @staticmethod
    def _get_api_key(provider_name: str) -> Optional[str]:
        """Get API key for a provider from environment variables.

        Args:
            provider_name: Provider name (e.g., 'polygon', 'finnhub', 'fred')

        Returns:
            API key from environment or None
        """
        env_var_map = {
            "polygon": "POLYGON_API_KEY",
            "finnhub": "FINNHUB_API_KEY",
            "fred": "FRED_API_KEY",
            "alpaca_key": "ALPACA_API_KEY",
            "alpaca_secret": "ALPACA_SECRET_KEY",
        }

        env_var = env_var_map.get(provider_name)
        if not env_var:
            return None

        api_key = os.getenv(env_var)
        if not api_key:
            logger.warning(f"API key not found in environment: {env_var}")

        return api_key

    @staticmethod
    def create_snapshot_provider(provider_name: Optional[str] = None, api_key: Optional[str] = None):
        """Create snapshot provider based on config or override."""
        if not provider_name:
            try:
                config = ConfigLoader().load_yaml("providers.yaml")
                provider_name = config["providers"]["snapshot"]["default"]
            except Exception as e:
                logger.warning(f"Could not load provider config, using default: {e}")
                provider_name = "yfinance"

        if not api_key:
            api_key = ProviderFactory._get_api_key(provider_name)

        if provider_name == "polygon":
            from api.providers.adapters.polygon_snapshot_adapter import PolygonSnapshotAdapter
            if not api_key:
                raise ValueError("Polygon API key not found in environment (POLYGON_API_KEY)")
            logger.debug("Creating PolygonSnapshotAdapter")
            return PolygonSnapshotAdapter(api_key)

        elif provider_name == "alpaca":
            from api.providers.adapters.alpaca_snapshot_adapter import AlpacaSnapshotAdapter
            alpaca_key = os.getenv("ALPACA_API_KEY")
            alpaca_secret = os.getenv("ALPACA_SECRET_KEY")
            if not alpaca_key or not alpaca_secret:
                raise ValueError("Alpaca API keys not found in environment (ALPACA_API_KEY, ALPACA_SECRET_KEY)")
            logger.debug("Creating AlpacaSnapshotAdapter")
            return AlpacaSnapshotAdapter(alpaca_key, alpaca_secret)

        elif provider_name == "yfinance":
            from api.providers.adapters.yfinance_snapshot_adapter import YFinanceSnapshotAdapter
            logger.debug("Creating YFinanceSnapshotAdapter (no API key needed)")
            return YFinanceSnapshotAdapter()

        else:
            raise ValueError(f"Unknown snapshot provider: {provider_name}")

    @staticmethod
    def create_aggregates_provider(provider_name: Optional[str] = None, api_key: Optional[str] = None):
        """Create aggregates provider based on config."""
        if not provider_name:
            try:
                config = ConfigLoader().load_yaml("providers.yaml")
                provider_name = config["providers"]["aggregates"]["default"]
            except Exception as e:
                logger.warning(f"Could not load provider config, using default: {e}")
                provider_name = "yfinance"

        if not api_key:
            api_key = ProviderFactory._get_api_key(provider_name)

        if provider_name == "polygon":
            from api.providers.adapters.polygon_aggregates_adapter import PolygonAggregatesAdapter
            if not api_key:
                raise ValueError("Polygon API key not found in environment (POLYGON_API_KEY)")
            logger.debug("Creating PolygonAggregatesAdapter")
            return PolygonAggregatesAdapter(api_key)

        elif provider_name == "yfinance":
            from api.providers.adapters.yfinance_aggregates_adapter import YFinanceAggregatesAdapter
            logger.debug("Creating YFinanceAggregatesAdapter (no API key needed)")
            return YFinanceAggregatesAdapter()

        else:
            raise ValueError(f"Unknown aggregates provider: {provider_name}")

    @staticmethod
    def create_news_provider(provider_name: Optional[str] = None, api_key: Optional[str] = None):
        """Create news provider based on config."""
        if not provider_name:
            try:
                config = ConfigLoader().load_yaml("providers.yaml")
                provider_name = config["providers"]["news"]["default"]
            except Exception as e:
                logger.warning(f"Could not load provider config, using default: {e}")
                provider_name = "finnhub"

        # Always resolve the correct key for the provider, not a passed-in key
        api_key = ProviderFactory._get_api_key(provider_name)

        if provider_name == "polygon":
            from api.providers.adapters.polygon_news_adapter import PolygonNewsAdapter
            if not api_key:
                raise ValueError("Polygon API key not found in environment (POLYGON_API_KEY)")
            logger.debug("Creating PolygonNewsAdapter")
            return PolygonNewsAdapter(api_key)

        elif provider_name == "finnhub":
            from api.providers.adapters.finnhub_news_adapter import FinnhubNewsAdapter
            if not api_key:
                raise ValueError("Finnhub API key not found in environment (FINNHUB_API_KEY)")
            logger.debug("Creating FinnhubNewsAdapter")
            return FinnhubNewsAdapter(api_key)

        else:
            raise ValueError(f"Unknown news provider: {provider_name}")

    @staticmethod
    def create_market_status_provider(provider_name: Optional[str] = None, api_key: Optional[str] = None):
        """Create market status provider based on config."""
        if not provider_name:
            try:
                config = ConfigLoader().load_yaml("providers.yaml")
                provider_name = config["providers"]["market_status"]["default"]
            except Exception as e:
                logger.warning(f"Could not load provider config, using default: {e}")
                provider_name = "pandas_market_calendars"

        if not api_key:
            api_key = ProviderFactory._get_api_key(provider_name)

        if provider_name == "polygon":
            from api.providers.adapters.polygon_market_status_adapter import PolygonMarketStatusAdapter
            if not api_key:
                raise ValueError("Polygon API key not found in environment (POLYGON_API_KEY)")
            logger.debug("Creating PolygonMarketStatusAdapter")
            return PolygonMarketStatusAdapter(api_key)

        elif provider_name == "pandas_market_calendars":
            from api.providers.adapters.pandas_market_calendar_adapter import PandasMarketCalendarAdapter
            logger.debug("Creating PandasMarketCalendarAdapter (no API key needed)")
            return PandasMarketCalendarAdapter()

        else:
            raise ValueError(f"Unknown market_status provider: {provider_name}")

    @staticmethod
    def create_reference_provider(provider_name: Optional[str] = None, api_key: Optional[str] = None):
        """Create reference data provider based on config."""
        if not provider_name:
            try:
                config = ConfigLoader().load_yaml("providers.yaml")
                provider_name = config["providers"]["reference"]["default"]
            except Exception as e:
                logger.warning(f"Could not load provider config, using default: {e}")
                provider_name = "yfinance"

        if not api_key:
            api_key = ProviderFactory._get_api_key(provider_name)

        if provider_name == "polygon":
            from api.providers.adapters.polygon_reference_adapter import PolygonReferenceAdapter
            if not api_key:
                raise ValueError("Polygon API key not found in environment (POLYGON_API_KEY)")
            logger.debug("Creating PolygonReferenceAdapter")
            return PolygonReferenceAdapter(api_key)

        elif provider_name in ("yfinance", "free"):
            from api.providers.adapters.free_reference_adapter import FreeReferenceAdapter
            logger.debug("Creating FreeReferenceAdapter (NASDAQ Trader + YFinance, no API key needed)")
            return FreeReferenceAdapter()

        else:
            raise ValueError(f"Unknown reference provider: {provider_name}")

    @staticmethod
    def create_economic_provider(provider_name: Optional[str] = None, api_key: Optional[str] = None):
        """Create economic data provider based on config."""
        if not provider_name:
            try:
                config = ConfigLoader().load_yaml("providers.yaml")
                provider_name = config["providers"]["economic"]["default"]
            except Exception as e:
                logger.warning(f"Could not load provider config, using default: {e}")
                provider_name = "fred"

        if not api_key:
            api_key = ProviderFactory._get_api_key(provider_name)

        if provider_name == "polygon":
            from api.providers.adapters.polygon_economic_adapter import PolygonEconomicAdapter
            if not api_key:
                raise ValueError("Polygon API key not found in environment (POLYGON_API_KEY)")
            logger.debug("Creating PolygonEconomicAdapter")
            return PolygonEconomicAdapter(api_key)

        elif provider_name == "fred":
            from api.providers.adapters.fred_economic_adapter import FREDEconomicAdapter
            if not api_key:
                logger.warning(
                    "FRED API key not found (FRED_API_KEY). "
                    "Economic data will be unavailable. "
                    "Get a free key at https://fred.stlouisfed.org/docs/api/api_key.html"
                )
                return _NoOpEconomicProvider()
            logger.debug("Creating FREDEconomicAdapter")
            return FREDEconomicAdapter(api_key)

        else:
            raise ValueError(f"Unknown economic provider: {provider_name}")


class _NoOpEconomicProvider:
    """Stub economic provider when no API key is configured."""

    def fetch_inflation(self, limit=10):
        return []

    def fetch_inflation_expectations(self, limit=10):
        return []

    def fetch_treasury_yields(self, limit=10):
        return []

    def fetch_all_fed_data(self, limit=10):
        return {"inflation": [], "inflation_expectations": [], "treasury_yields": []}

    def get_provider_name(self):
        return "none"
