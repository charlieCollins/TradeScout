"""Base class for composite providers that route methods to different providers.

Composite providers implement protocol interfaces and route each method call
to a configured underlying provider based on YAML configuration.

This enables mixing providers at the method level, e.g.:
- fetch_bulk_market_snapshot() → routes to Alpaca
- fetch_single_ticker_snapshot() → routes to Tiingo (fallback)
"""

import logging
import os
from typing import Optional, List, Any, Dict

logger = logging.getLogger(__name__)


class CompositeProvider:
    """Base class for composite providers that route methods to different providers.

    Subclasses implement protocol interfaces and route each method call
    to a configured provider based on YAML configuration.

    Example:
        class CompositeSnapshotProvider(CompositeProvider, SnapshotProvider):
            def __init__(self, config: dict):
                super().__init__("snapshot", config)

            def fetch_bulk_market_snapshot(self) -> Optional[MarketSnapshot]:
                return self._route_call('fetch_bulk_market_snapshot')
    """

    def __init__(self, protocol_name: str, method_config: dict):
        """Initialize composite provider.

        Args:
            protocol_name: Name of protocol (e.g., 'snapshot', 'aggregates')
            method_config: Method routing configuration from providers.yaml
                          Format: {method_name: {provider: 'alpaca', fallback: [...]}}
        """
        self.protocol_name = protocol_name
        self.method_config = method_config
        self._provider_cache: Dict[str, Any] = {}  # Cache instantiated providers

    def _get_provider_for_method(self, method_name: str) -> Any:
        """Get provider instance for a specific method.

        Args:
            method_name: Name of method being called

        Returns:
            Provider instance that implements this method

        Raises:
            ValueError: If no provider configured for this method
        """
        # Get method config
        if method_name not in self.method_config:
            raise ValueError(
                f"No provider configured for {self.protocol_name}.{method_name}. "
                f"Check configs/providers.yaml"
            )

        method_cfg = self.method_config[method_name]
        provider_name = method_cfg.get('provider')

        if not provider_name:
            raise ValueError(
                f"No provider specified for {self.protocol_name}.{method_name} in config"
            )

        # Get or create provider instance
        cache_key = f"{self.protocol_name}:{provider_name}"
        if cache_key not in self._provider_cache:
            logger.debug(f"Instantiating {provider_name} for {self.protocol_name}")
            self._provider_cache[cache_key] = self._instantiate_provider(
                provider_name,
                self.protocol_name
            )

        return self._provider_cache[cache_key]

    def _instantiate_provider(self, provider_name: str, protocol_name: str) -> Any:
        """Instantiate a specific provider adapter.

        Args:
            provider_name: Provider name (e.g., 'polygon', 'alpaca', 'yfinance')
            protocol_name: Protocol name (e.g., 'snapshot', 'aggregates')

        Returns:
            Provider adapter instance

        Raises:
            ValueError: If provider or protocol combination is unknown
        """
        # Map provider + protocol to adapter class
        if provider_name == "polygon":
            return self._create_polygon_provider(protocol_name)
        elif provider_name == "alpaca":
            return self._create_alpaca_provider(protocol_name)
        elif provider_name == "tiingo":
            return self._create_tiingo_provider(protocol_name)
        elif provider_name == "finnhub":
            return self._create_finnhub_provider(protocol_name)
        elif provider_name == "pandas_market_calendars":
            return self._create_pandas_market_calendar_provider(protocol_name)
        else:
            raise ValueError(f"Unknown provider: {provider_name}")

    def _create_polygon_provider(self, protocol_name: str) -> Any:
        """Create Polygon provider for given protocol."""
        api_key = os.getenv("POLYGON_API_KEY")
        if not api_key:
            raise ValueError("POLYGON_API_KEY not found in environment")

        if protocol_name == "snapshot":
            from api.providers.adapters.polygon_snapshot_adapter import PolygonSnapshotAdapter
            return PolygonSnapshotAdapter(api_key)

        elif protocol_name == "aggregates":
            from api.providers.adapters.polygon_aggregates_adapter import PolygonAggregatesAdapter
            return PolygonAggregatesAdapter(api_key)

        elif protocol_name == "news":
            from api.providers.adapters.polygon_news_adapter import PolygonNewsAdapter
            return PolygonNewsAdapter(api_key)

        elif protocol_name == "market_status":
            from api.providers.adapters.polygon_market_status_adapter import PolygonMarketStatusAdapter
            return PolygonMarketStatusAdapter(api_key)

        elif protocol_name == "reference":
            from api.providers.adapters.polygon_reference_adapter import PolygonReferenceAdapter
            return PolygonReferenceAdapter(api_key)

        elif protocol_name == "economic":
            from api.providers.adapters.polygon_economic_adapter import PolygonEconomicAdapter
            return PolygonEconomicAdapter(api_key)

        else:
            raise ValueError(f"Polygon does not support protocol: {protocol_name}")

    def _create_alpaca_provider(self, protocol_name: str) -> Any:
        """Create Alpaca provider for given protocol."""
        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")

        if not api_key or not secret_key:
            raise ValueError("ALPACA_API_KEY or ALPACA_SECRET_KEY not found in environment")

        if protocol_name == "snapshot":
            from api.providers.adapters.alpaca_snapshot_adapter import AlpacaSnapshotAdapter
            return AlpacaSnapshotAdapter(api_key, secret_key)

        else:
            # Note: AlpacaAggregatesAdapter not yet implemented
            raise ValueError(f"Alpaca does not support protocol: {protocol_name}")

    def _create_tiingo_provider(self, protocol_name: str) -> Any:
        """Create Tiingo provider for given protocol.

        Note: Tiingo adapters are not yet implemented. This is a placeholder
        for future provider expansion.
        """
        api_key = os.getenv("TIINGO_API_KEY")
        if not api_key:
            raise ValueError("TIINGO_API_KEY not found in environment")

        # Note: Tiingo adapters not yet implemented
        raise ValueError(
            f"Tiingo provider for {protocol_name} is not yet implemented. "
            f"Available providers: polygon, alpaca (snapshot only), finnhub (news only), "
            f"pandas_market_calendars (market_status only)"
        )

    def _create_finnhub_provider(self, protocol_name: str) -> Any:
        """Create Finnhub provider for given protocol."""
        api_key = os.getenv("FINNHUB_API_KEY")
        if not api_key:
            raise ValueError("FINNHUB_API_KEY not found in environment")

        if protocol_name == "news":
            from api.providers.adapters.finnhub_news_adapter import FinnhubNewsAdapter
            return FinnhubNewsAdapter(api_key)

        else:
            raise ValueError(f"Finnhub does not support protocol: {protocol_name}")

    def _create_pandas_market_calendar_provider(self, protocol_name: str) -> Any:
        """Create pandas_market_calendars provider for given protocol."""
        if protocol_name == "market_status":
            from api.providers.adapters.pandas_market_calendar_adapter import PandasMarketCalendarAdapter
            return PandasMarketCalendarAdapter()

        else:
            raise ValueError(f"pandas_market_calendars does not support protocol: {protocol_name}")

    def _route_call(self, method_name: str, *args, **kwargs) -> Any:
        """Route a method call to the configured provider.

        Args:
            method_name: Name of method being called
            *args, **kwargs: Method arguments

        Returns:
            Result from underlying provider

        Raises:
            Exception: If provider call fails
        """
        try:
            provider = self._get_provider_for_method(method_name)

            if not hasattr(provider, method_name):
                raise AttributeError(
                    f"Provider {provider.get_provider_name()} does not have method '{method_name}'"
                )

            method = getattr(provider, method_name)

            logger.debug(
                f"Routing {self.protocol_name}.{method_name} to {provider.get_provider_name()}"
            )

            return method(*args, **kwargs)

        except Exception as e:
            logger.error(
                f"Error routing {self.protocol_name}.{method_name}: {e}",
                exc_info=True
            )
            raise

    def _route_call_with_fallback(
        self,
        method_name: str,
        *args,
        **kwargs
    ) -> Any:
        """Route a method call with automatic fallback on failure.

        Tries primary provider first, then falls back to configured fallback providers.

        Args:
            method_name: Name of method being called
            *args, **kwargs: Method arguments

        Returns:
            Result from first successful provider

        Raises:
            Exception: If all providers fail
        """
        method_cfg = self.method_config.get(method_name, {})
        fallback_providers = method_cfg.get('fallback', [])

        # Try primary provider first
        try:
            return self._route_call(method_name, *args, **kwargs)
        except Exception as primary_error:
            logger.warning(
                f"Primary provider failed for {self.protocol_name}.{method_name}: {primary_error}"
            )

            # Try fallback providers
            for fallback_name in fallback_providers:
                try:
                    logger.info(f"Trying fallback provider: {fallback_name}")

                    # Temporarily override config to use fallback
                    original_provider = method_cfg.get('provider')
                    method_cfg['provider'] = fallback_name

                    try:
                        result = self._route_call(method_name, *args, **kwargs)
                        logger.info(f"Fallback provider {fallback_name} succeeded")
                        return result
                    finally:
                        # Restore original config
                        method_cfg['provider'] = original_provider

                except Exception as fallback_error:
                    logger.warning(
                        f"Fallback provider {fallback_name} failed: {fallback_error}"
                    )
                    continue

            # All providers failed
            raise Exception(
                f"All providers failed for {self.protocol_name}.{method_name}. "
                f"Primary error: {primary_error}"
            )

    def get_provider_name(self) -> str:
        """Get composite provider name.

        Returns:
            Provider name for logging/debugging
        """
        return f"composite_{self.protocol_name}"
