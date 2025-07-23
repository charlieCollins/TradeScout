"""
Smart Data Collection Coordinator

Uses the data sources configuration to intelligently route different types
of data requests to appropriate providers with fallback strategies.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from decimal import Decimal

from ..config.data_sources_manager import (
    get_data_sources_manager, 
    DataSourceType, 
    FallbackStrategy,
    DataSourcesManager
)
from ..data_models.interfaces import AssetDataProvider
from ..data_models.domain_models_core import Asset, MarketQuote, PriceData, AssetType
from ..data_models.factories import MarketFactory
from .asset_data_provider_yfinance import AssetDataProviderYFinance
from .asset_data_provider_finnhub import AssetDataProviderFinnhub
from .asset_data_provider_polygon import AssetDataProviderPolygon
from .asset_data_provider_alpha_vantage import AssetDataProviderAlphaVantage

logger = logging.getLogger(__name__)


class SmartCoordinator:
    """
    Intelligent data collection coordinator that routes requests based on configuration
    
    Features:
    - Configuration-driven provider selection
    - Multiple fallback strategies (first_success, merge_best, merge_all)
    - Automatic circuit breaking for failing providers
    - Quality-based data merging
    - Comprehensive error handling and logging
    """
    
    def __init__(self, config_manager: Optional[DataSourcesManager] = None):
        """
        Initialize smart coordinator
        
        Args:
            config_manager: Data sources configuration manager
        """
        self.config_manager = config_manager or get_data_sources_manager()
        self._provider_instances: Dict[str, AssetDataProvider] = {}
        self._nasdaq_market = MarketFactory().create_nasdaq_market()
        
        # Initialize available providers
        self._initialize_providers()
    
    def _initialize_providers(self) -> None:
        """Initialize available data provider instances"""
        for provider_id in self.config_manager.config.providers:
            if self.config_manager.is_provider_enabled(provider_id):
                try:
                    instance = self._create_provider_instance(provider_id)
                    if instance:
                        self._provider_instances[provider_id] = instance
                        logger.info(f"Initialized provider: {provider_id}")
                except Exception as e:
                    logger.error(f"Failed to initialize provider {provider_id}: {e}")
    
    def _create_provider_instance(self, provider_id: str) -> Optional[AssetDataProvider]:
        """Create an instance of the specified provider"""
        try:
            if provider_id == "yfinance":
                return AssetDataProviderYFinance()
            elif provider_id == "finnhub":
                import os
                api_key = os.getenv("FINNHUB_API_KEY")
                if api_key:
                    return AssetDataProviderFinnhub(api_key)
                else:
                    logger.warning("Finnhub API key not found")
                    return None
            elif provider_id == "polygon":
                import os
                api_key = os.getenv("POLYGON_API_KEY")
                if api_key:
                    return AssetDataProviderPolygon(api_key)
                else:
                    logger.warning("Polygon API key not found")
                    return None
            elif provider_id == "alpha_vantage":
                import os
                api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
                if api_key:
                    return AssetDataProviderAlphaVantage(api_key)
                else:
                    logger.warning("Alpha Vantage API key not found")
                    return None
            # Add other providers as needed
            else:
                logger.warning(f"Unknown provider: {provider_id}")
                return None
        except Exception as e:
            logger.error(f"Error creating provider {provider_id}: {e}")
            return None
    
    def get_current_quote(self, symbol: str) -> Optional[MarketQuote]:
        """
        Get current quote using smart provider selection
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            MarketQuote or None if all providers fail
        """
        return self._get_data_with_strategy(
            DataSourceType.CURRENT_QUOTES,
            self._get_quote_from_provider,
            symbol=symbol
        )
    
    def get_historical_data(self, symbol: str, **kwargs) -> List[PriceData]:
        """Get historical price data using smart provider selection"""
        return self._get_data_with_strategy(
            DataSourceType.HISTORICAL_PRICES,
            self._get_historical_from_provider,
            symbol=symbol,
            **kwargs
        ) or []
    
    def get_company_fundamentals(self, symbol: str) -> Dict[str, Any]:
        """Get company fundamental data using smart provider selection"""
        return self._get_data_with_strategy(
            DataSourceType.COMPANY_FUNDAMENTALS,
            self._get_fundamentals_from_provider,
            symbol=symbol
        ) or {}
    
    def get_volume_leaders(self, symbols: List[str], **kwargs) -> List[MarketQuote]:
        """Get volume leaders using smart provider selection"""
        return self._get_data_with_strategy(
            DataSourceType.VOLUME_ANALYSIS,
            self._get_volume_leaders_from_provider,
            symbols=symbols,
            **kwargs
        ) or []
    
    def _get_data_with_strategy(
        self, 
        data_type: DataSourceType, 
        fetch_function, 
        **kwargs
    ) -> Any:
        """
        Get data using the configured fallback strategy
        
        Args:
            data_type: Type of data being requested
            fetch_function: Function to fetch data from a provider
            **kwargs: Arguments to pass to fetch function
            
        Returns:
            Data from providers based on fallback strategy
        """
        providers = self.config_manager.get_providers_for_data_type(data_type)
        strategy = self.config_manager.get_fallback_strategy(data_type)
        
        if not providers:
            logger.warning(f"No providers configured for {data_type.value}")
            return None
        
        logger.debug(f"Getting {data_type.value} using {strategy.value} strategy from {len(providers)} providers")
        
        if strategy == FallbackStrategy.FIRST_SUCCESS:
            return self._first_success_strategy(providers, fetch_function, **kwargs)
        elif strategy == FallbackStrategy.MERGE_BEST:
            return self._merge_best_strategy(providers, fetch_function, **kwargs)
        elif strategy == FallbackStrategy.MERGE_ALL:
            return self._merge_all_strategy(providers, fetch_function, **kwargs)
        elif strategy == FallbackStrategy.ROUND_ROBIN:
            return self._round_robin_strategy(providers, fetch_function, **kwargs)
        else:
            logger.error(f"Unknown fallback strategy: {strategy}")
            return self._first_success_strategy(providers, fetch_function, **kwargs)
    
    def _first_success_strategy(self, providers, fetch_function, **kwargs) -> Any:
        """Try providers in order until one succeeds"""
        for provider_id, provider_config in providers:
            if provider_id not in self._provider_instances:
                continue
            
            provider = self._provider_instances[provider_id]
            
            try:
                logger.debug(f"Trying provider {provider_id}")
                result = fetch_function(provider, provider_id, **kwargs)
                if result is not None:
                    logger.info(f"Got data from {provider_id}")
                    self.config_manager.record_provider_success(provider_id)
                    return result
                else:
                    logger.debug(f"No data from {provider_id}")
            except Exception as e:
                logger.warning(f"Error from provider {provider_id}: {e}")
                self.config_manager.record_provider_failure(provider_id)
        
        logger.error("All providers failed")
        return None
    
    def _merge_best_strategy(self, providers, fetch_function, **kwargs) -> Any:
        """Get data from multiple providers and merge based on quality"""
        results = {}
        
        for provider_id, provider_config in providers:
            if provider_id not in self._provider_instances:
                continue
                
            provider = self._provider_instances[provider_id]
            
            try:
                logger.debug(f"Getting data from {provider_id} for merge")
                result = fetch_function(provider, provider_id, **kwargs)
                if result is not None:
                    results[provider_id] = {
                        'data': result,
                        'quality': provider_config.quality_weight,
                        'priority': provider_config.priority
                    }
                    self.config_manager.record_provider_success(provider_id)
                    logger.debug(f"Got data from {provider_id} (quality: {provider_config.quality_weight})")
            except Exception as e:
                logger.warning(f"Error from provider {provider_id}: {e}")
                self.config_manager.record_provider_failure(provider_id)
        
        if not results:
            logger.error("No providers returned data for merge")
            return None
        
        # For now, return the highest quality result
        # In the future, this could be enhanced to actually merge data intelligently
        best_provider = max(results.keys(), key=lambda p: results[p]['quality'])
        logger.info(f"Using data from {best_provider} (best quality: {results[best_provider]['quality']})")
        return results[best_provider]['data']
    
    def _merge_all_strategy(self, providers, fetch_function, **kwargs) -> List[Any]:
        """Get data from all providers and return combined results"""
        all_results = []
        
        for provider_id, provider_config in providers:
            if provider_id not in self._provider_instances:
                continue
                
            provider = self._provider_instances[provider_id]
            
            try:
                result = fetch_function(provider, provider_id, **kwargs)
                if result is not None:
                    # If result is a list, extend; if single item, append
                    if isinstance(result, list):
                        all_results.extend(result)
                    else:
                        all_results.append(result)
                    self.config_manager.record_provider_success(provider_id)
                    logger.debug(f"Added data from {provider_id}")
            except Exception as e:
                logger.warning(f"Error from provider {provider_id}: {e}")
                self.config_manager.record_provider_failure(provider_id)
        
        logger.info(f"Combined data from {len(all_results)} sources")
        return all_results
    
    def _round_robin_strategy(self, providers, fetch_function, **kwargs) -> Any:
        """Use round-robin selection of providers"""
        # For now, just use first success
        # Could be enhanced to track usage and rotate
        return self._first_success_strategy(providers, fetch_function, **kwargs)
    
    def _get_quote_from_provider(
        self, 
        provider: AssetDataProvider, 
        provider_id: str, 
        symbol: str
    ) -> Optional[MarketQuote]:
        """Get quote from a specific provider"""
        asset = self._create_asset(symbol)
        return provider.get_current_quote(asset)
    
    def _get_historical_from_provider(
        self, 
        provider: AssetDataProvider, 
        provider_id: str, 
        symbol: str,
        **kwargs
    ) -> List[PriceData]:
        """Get historical data from a specific provider"""
        asset = self._create_asset(symbol)
        # Extract parameters with defaults
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')
        interval = kwargs.get('interval', '1d')
        
        if start_date and end_date:
            return provider.get_historical_quotes(asset, start_date, end_date, interval)
        else:
            logger.warning("Start date and end date required for historical data")
            return []
    
    def _get_fundamentals_from_provider(
        self, 
        provider: AssetDataProvider, 
        provider_id: str, 
        symbol: str
    ) -> Dict[str, Any]:
        """Get fundamental data from a specific provider"""
        asset = self._create_asset(symbol)
        return provider.get_fundamental_data(asset)
    
    def _get_volume_leaders_from_provider(
        self, 
        provider: AssetDataProvider, 
        provider_id: str, 
        symbols: List[str],
        **kwargs
    ) -> List[MarketQuote]:
        """Get volume leaders from a specific provider"""
        assets = [self._create_asset(symbol) for symbol in symbols]
        min_volume_ratio = kwargs.get('min_volume_ratio', Decimal("2.0"))
        return provider.scan_volume_leaders(assets, min_volume_ratio)
    
    def _create_asset(self, symbol: str) -> Asset:
        """Create a basic Asset object for the given symbol"""
        return Asset(
            symbol=symbol.upper(),
            name=f"{symbol.upper()} Corp",
            asset_type=AssetType.COMMON_STOCK,
            market=self._nasdaq_market,
            currency="USD",
        )
    
    def get_provider_status(self) -> Dict[str, Any]:
        """Get status of all providers"""
        return self.config_manager.get_provider_status()
    
    def get_available_data_types(self) -> List[str]:
        """Get list of available data types"""
        return self.config_manager.list_data_types()
    
    def reload_config(self) -> None:
        """Reload configuration and reinitialize providers"""
        logger.info("Reloading smart coordinator configuration...")
        self.config_manager.reload_config()
        self._provider_instances.clear()
        self._initialize_providers()


# Convenience functions
def create_smart_coordinator() -> SmartCoordinator:
    """Create a smart coordinator with default configuration"""
    return SmartCoordinator()


if __name__ == "__main__":
    # Test the smart coordinator
    print("🧪 Testing Smart Coordinator...")
    
    import os
    os.environ["FINNHUB_API_KEY"] = "d1vutchr01qmbi8q9u50d1vutchr01qmbi8q9u5g"
    
    coordinator = create_smart_coordinator()
    
    print(f"\n📊 Initialized with {len(coordinator._provider_instances)} providers")
    for provider_id in coordinator._provider_instances:
        print(f"  - {provider_id}")
    
    # Test quote functionality
    print(f"\n📈 Testing quote for AAPL...")
    quote = coordinator.get_current_quote("AAPL")
    if quote:
        print(f"Price: ${quote.price_data.price}")
        print(f"Change: {quote.price_change_percent:.2f}%")
    else:
        print("Failed to get quote")
    
    # Test fundamentals
    print(f"\n📊 Testing fundamentals for AAPL...")
    fundamentals = coordinator.get_company_fundamentals("AAPL")
    if fundamentals:
        print(f"Company: {fundamentals.get('company_name', 'N/A')}")
        print(f"Market Cap: ${fundamentals.get('market_cap', 0):,}")
    else:
        print("Failed to get fundamentals")
    
    print("\n✅ Smart Coordinator test completed!")