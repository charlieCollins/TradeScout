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
            provider_name: Provider name (e.g., 'polygon', 'iex')

        Returns:
            API key from environment or None
        """
        env_var_map = {
            "polygon": "POLYGON_API_KEY",
            "finnhub": "FINNHUB_API_KEY",
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
        """Create snapshot provider based on config or override.

        Args:
            provider_name: Override provider name (default: from config)
            api_key: Override API key (default: from environment)

        Returns:
            SnapshotProvider implementation

        Raises:
            ValueError: If provider is unknown
        """
        # Load from config if not provided
        if not provider_name:
            try:
                config = ConfigLoader().load_yaml("providers.yaml")
                provider_name = config["providers"]["snapshot"]["default"]
            except Exception as e:
                logger.warning(f"Could not load provider config, using default: {e}")
                provider_name = "polygon"  # Default fallback

        # Get API key if not provided
        if not api_key:
            api_key = ProviderFactory._get_api_key(provider_name)

        # Create appropriate adapter
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

        else:
            raise ValueError(f"Unknown snapshot provider: {provider_name}")

    @staticmethod
    def create_aggregates_provider(provider_name: Optional[str] = None, api_key: Optional[str] = None):
        """Create aggregates provider based on config.

        Args:
            provider_name: Override provider name (default: from config)
            api_key: Override API key (default: from environment)

        Returns:
            AggregatesProvider implementation
        """
        if not provider_name:
            try:
                config = ConfigLoader().load_yaml("providers.yaml")
                provider_name = config["providers"]["aggregates"]["default"]
            except Exception as e:
                logger.warning(f"Could not load provider config, using default: {e}")
                provider_name = "polygon"

        if not api_key:
            api_key = ProviderFactory._get_api_key(provider_name)

        if provider_name == "polygon":
            from api.providers.adapters.polygon_aggregates_adapter import PolygonAggregatesAdapter
            if not api_key:
                raise ValueError("Polygon API key not found in environment (POLYGON_API_KEY)")
            logger.debug("Creating PolygonAggregatesAdapter")
            return PolygonAggregatesAdapter(api_key)

        else:
            raise ValueError(f"Unknown aggregates provider: {provider_name}")

    @staticmethod
    def create_news_provider(provider_name: Optional[str] = None, api_key: Optional[str] = None):
        """Create news provider based on config.

        Args:
            provider_name: Override provider name (default: from config)
            api_key: Override API key (default: from environment)

        Returns:
            NewsProvider implementation
        """
        if not provider_name:
            try:
                config = ConfigLoader().load_yaml("providers.yaml")
                provider_name = config["providers"]["news"]["default"]
            except Exception as e:
                logger.warning(f"Could not load provider config, using default: {e}")
                provider_name = "polygon"

        if not api_key:
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
                api_key = ProviderFactory._get_api_key("finnhub")
            if not api_key:
                raise ValueError("Finnhub API key not found in environment (FINNHUB_API_KEY)")
            logger.debug("Creating FinnhubNewsAdapter")
            return FinnhubNewsAdapter(api_key)

        else:
            raise ValueError(f"Unknown news provider: {provider_name}")

    @staticmethod
    def create_market_status_provider(provider_name: Optional[str] = None, api_key: Optional[str] = None):
        """Create market status provider based on config.

        Args:
            provider_name: Override provider name (default: from config)
            api_key: Override API key (default: from environment)

        Returns:
            MarketStatusProvider implementation
        """
        if not provider_name:
            try:
                config = ConfigLoader().load_yaml("providers.yaml")
                provider_name = config["providers"]["market_status"]["default"]
            except Exception as e:
                logger.warning(f"Could not load provider config, using default: {e}")
                provider_name = "polygon"

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
        """Create reference data provider based on config.

        Args:
            provider_name: Override provider name (default: from config)
            api_key: Override API key (default: from environment)

        Returns:
            ReferenceDataProvider implementation
        """
        if not provider_name:
            try:
                config = ConfigLoader().load_yaml("providers.yaml")
                provider_name = config["providers"]["reference"]["default"]
            except Exception as e:
                logger.warning(f"Could not load provider config, using default: {e}")
                provider_name = "polygon"

        if not api_key:
            api_key = ProviderFactory._get_api_key(provider_name)

        if provider_name == "polygon":
            from api.providers.adapters.polygon_reference_adapter import PolygonReferenceAdapter
            if not api_key:
                raise ValueError("Polygon API key not found in environment (POLYGON_API_KEY)")
            logger.debug("Creating PolygonReferenceAdapter")
            return PolygonReferenceAdapter(api_key)

        else:
            raise ValueError(f"Unknown reference provider: {provider_name}")

    @staticmethod
    def create_economic_provider(provider_name: Optional[str] = None, api_key: Optional[str] = None):
        """Create economic data provider based on config.

        Args:
            provider_name: Override provider name (default: from config)
            api_key: Override API key (default: from environment)

        Returns:
            EconomicDataProvider implementation
        """
        if not provider_name:
            try:
                config = ConfigLoader().load_yaml("providers.yaml")
                provider_name = config["providers"]["economic"]["default"]
            except Exception as e:
                logger.warning(f"Could not load provider config, using default: {e}")
                provider_name = "polygon"

        if not api_key:
            api_key = ProviderFactory._get_api_key(provider_name)

        if provider_name == "polygon":
            from api.providers.adapters.polygon_economic_adapter import PolygonEconomicAdapter
            if not api_key:
                raise ValueError("Polygon API key not found in environment (POLYGON_API_KEY)")
            logger.debug("Creating PolygonEconomicAdapter")
            return PolygonEconomicAdapter(api_key)

        else:
            raise ValueError(f"Unknown economic provider: {provider_name}")
