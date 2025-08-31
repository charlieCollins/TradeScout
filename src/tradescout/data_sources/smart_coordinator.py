"""
Smart Data Collection Coordinator

Uses the data sources configuration to intelligently route different types
of data requests to appropriate providers with fallback strategies.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from ..config.data_sources_manager import (
    DataSourcesManager,
    DataSourceType,
    FallbackStrategy,
    get_data_sources_manager,
)
from ..data_models.domain_models_core import Asset, AssetType, ExtendedHoursData, MarketQuote, MarketStatus, PriceData
from ..data_models.factories import MarketFactory
from ..data_models.interfaces import AssetDataProvider
from ..data_models.market_wide_models import MarketMover, MarketMoversReport
from ..data_sources_api.asset_data_provider_alpha_vantage import AssetDataProviderAlphaVantage
from ..data_sources_api.asset_data_provider_alpha_vantage_market import AssetDataProviderAlphaVantageMarket
from ..data_sources_api.asset_data_provider_finnhub import AssetDataProviderFinnhub
from ..data_sources_api.asset_data_provider_polygon import AssetDataProviderPolygon
from ..data_sources_api.asset_data_provider_yfinance import AssetDataProviderYFinance
from ..data_sources_scraping.marketwatch_scraper import MarketWatchScraper
from ..data_sources_scraping.investing_com_scraper import InvestingComScraper
from ..data_sources_scraping.cnn_scraper import CNNScraper
from ..data_sources_scraping.tipranks_scraper import TipRanksScraper
from ..data_sources_scraping.advfn_scraper import ADVFNScraper
from ..data_sources_scraping.interfaces import AfterHoursWebScraper

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
        self._scraper_instances: Dict[str, AfterHoursWebScraper] = {}
        self._nasdaq_market = MarketFactory().create_nasdaq_market()

        # Initialize available providers
        self._initialize_providers()

    def _initialize_providers(self) -> None:
        """Initialize available data provider instances"""
        for provider_id in self.config_manager.config.providers:
            if self.config_manager.is_provider_enabled(provider_id):
                try:
                    provider_config = self._get_provider_config(provider_id)
                    if provider_config and provider_config.type == "web_scraper":
                        scraper = self._create_scraper_instance(provider_id)
                        if scraper:
                            self._scraper_instances[provider_id] = scraper
                            logger.info(f"Initialized web scraper: {provider_id}")
                    else:
                        instance = self._create_provider_instance(provider_id)
                        if instance:
                            self._provider_instances[provider_id] = instance
                            logger.info(f"Initialized API provider: {provider_id}")
                except Exception as e:
                    logger.error(f"Failed to initialize provider {provider_id}: {e}")

    def _get_provider_config(self, provider_id: str) -> Optional[Any]:
        """Get configuration for a provider from centralized config"""
        if provider_id not in self.config_manager.config.providers:
            return None
        return self.config_manager.config.providers[provider_id]

    def _create_provider_instance(
        self, provider_id: str
    ) -> Optional[AssetDataProvider]:
        """Create an instance of the specified provider"""
        try:
            # Get provider config
            provider_config = self._get_provider_config(provider_id)
            if not provider_config:
                logger.warning(f"No configuration found for provider: {provider_id}")
                return None

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
            elif provider_id == "alpha_vantage_market":
                import os
                api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
                if api_key:
                    return AssetDataProviderAlphaVantageMarket(api_key)
                else:
                    logger.warning("Alpha Vantage API key not found for market provider")
                    return None
            # Add other providers as needed
            else:
                logger.warning(f"Unknown provider: {provider_id}")
                return None
        except Exception as e:
            logger.error(f"Error creating provider {provider_id}: {e}")
            return None

    def _create_scraper_instance(
        self, provider_id: str
    ) -> Optional[AfterHoursWebScraper]:
        """Create an instance of the specified web scraper"""
        try:
            provider_config = self._get_provider_config(provider_id)
            if not provider_config:
                logger.warning(f"No configuration found for scraper: {provider_id}")
                return None
            
            timeout = provider_config.timeout_seconds
            
            if provider_id == "marketwatch_scraper":
                return MarketWatchScraper()
            elif provider_id == "investing_com_scraper":
                return InvestingComScraper()
            elif provider_id == "cnn_scraper":
                return CNNScraper()
            elif provider_id == "tipranks_scraper":
                return TipRanksScraper()
            elif provider_id == "advfn_scraper":
                return ADVFNScraper()
            else:
                logger.warning(f"Unknown web scraper: {provider_id}")
                return None
        except Exception as e:
            logger.error(f"Error creating web scraper {provider_id}: {e}")
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
            DataSourceType.CURRENT_QUOTES, self._get_quote_from_provider, symbol=symbol
        )

    def get_historical_data(self, symbol: str, **kwargs) -> List[PriceData]:
        """Get historical price data using smart provider selection"""
        return (
            self._get_data_with_strategy(
                DataSourceType.HISTORICAL_PRICES,
                self._get_historical_from_provider,
                symbol=symbol,
                **kwargs,
            )
            or []
        )

    def get_company_fundamentals(self, symbol: str) -> Dict[str, Any]:
        """Get company fundamental data using smart provider selection"""
        return (
            self._get_data_with_strategy(
                DataSourceType.COMPANY_FUNDAMENTALS,
                self._get_fundamentals_from_provider,
                symbol=symbol,
            )
            or {}
        )

    def get_volume_leaders(self, symbols: List[str], **kwargs) -> List[MarketQuote]:
        """Get volume leaders using smart provider selection"""
        return (
            self._get_data_with_strategy(
                DataSourceType.VOLUME_ANALYSIS,
                self._get_volume_leaders_from_provider,
                symbols=symbols,
                **kwargs,
            )
            or []
        )

    def _get_data_with_strategy(
        self, data_type: DataSourceType, fetch_function, **kwargs
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

        logger.debug(
            f"Getting {data_type.value} using {strategy.value} strategy from {len(providers)} providers"
        )

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
                        "data": result,
                        "quality": provider_config.quality_weight,
                        "priority": provider_config.priority,
                    }
                    self.config_manager.record_provider_success(provider_id)
                    logger.debug(
                        f"Got data from {provider_id} (quality: {provider_config.quality_weight})"
                    )
            except Exception as e:
                logger.warning(f"Error from provider {provider_id}: {e}")
                self.config_manager.record_provider_failure(provider_id)

        if not results:
            logger.error("No providers returned data for merge")
            return None

        # For now, return the highest quality result
        # In the future, this could be enhanced to actually merge data intelligently
        best_provider = max(results.keys(), key=lambda p: results[p]["quality"])
        logger.info(
            f"Using data from {best_provider} (best quality: {results[best_provider]['quality']})"
        )
        return results[best_provider]["data"]

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
        self, provider: AssetDataProvider, provider_id: str, symbol: str
    ) -> Optional[MarketQuote]:
        """Get quote from a specific provider"""
        asset = self._create_asset(symbol)
        return provider.get_current_quote(asset)

    def _get_historical_from_provider(
        self, provider: AssetDataProvider, provider_id: str, symbol: str, **kwargs
    ) -> List[PriceData]:
        """Get historical data from a specific provider"""
        asset = self._create_asset(symbol)
        # Extract parameters with defaults
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")
        interval = kwargs.get("interval", "1d")

        if start_date and end_date:
            return provider.get_historical_quotes(asset, start_date, end_date, interval)
        else:
            logger.warning("Start date and end date required for historical data")
            return []

    def _get_fundamentals_from_provider(
        self, provider: AssetDataProvider, provider_id: str, symbol: str
    ) -> Dict[str, Any]:
        """Get fundamental data from a specific provider"""
        asset = self._create_asset(symbol)
        return provider.get_fundamental_data(asset)

    def _get_volume_leaders_from_provider(
        self,
        provider: AssetDataProvider,
        provider_id: str,
        symbols: List[str],
        **kwargs,
    ) -> List[MarketQuote]:
        """Get volume leaders from a specific provider"""
        assets = [self._create_asset(symbol) for symbol in symbols]
        min_volume_ratio = kwargs.get("min_volume_ratio", Decimal("2.0"))
        return provider.scan_volume_leaders(assets, min_volume_ratio)

    def get_market_gainers(
        self, limit: int = 20, force_refresh: bool = False
    ) -> List[MarketMover]:
        """
        Get top market gainers using smart provider selection
        
        Args:
            limit: Maximum number of gainers to return
            force_refresh: Bypass cache and fetch fresh data
            
        Returns:
            List of top gaining stocks with performance data
        """
        return (
            self._get_data_with_strategy(
                DataSourceType.MARKET_MOVERS,
                self._get_market_gainers_from_provider,
                limit=limit,
                force_refresh=force_refresh,
            )
            or []
        )

    def get_market_losers(
        self, limit: int = 20, force_refresh: bool = False
    ) -> List[MarketMover]:
        """
        Get top market losers using smart provider selection
        
        Args:
            limit: Maximum number of losers to return
            force_refresh: Bypass cache and fetch fresh data
            
        Returns:
            List of top losing stocks with performance data
        """
        return (
            self._get_data_with_strategy(
                DataSourceType.MARKET_MOVERS,
                self._get_market_losers_from_provider,
                limit=limit,
                force_refresh=force_refresh,
            )
            or []
        )

    def get_most_active(
        self, limit: int = 20, force_refresh: bool = False
    ) -> List[MarketMover]:
        """
        Get most active stocks by volume using smart provider selection
        
        Args:
            limit: Maximum number of active stocks to return
            force_refresh: Bypass cache and fetch fresh data
            
        Returns:
            List of most active stocks by trading volume
        """
        return (
            self._get_data_with_strategy(
                DataSourceType.MARKET_MOVERS,
                self._get_most_active_from_provider,
                limit=limit,
                force_refresh=force_refresh,
            )
            or []
        )

    def get_market_movers_report(
        self, limit: int = 20, force_refresh: bool = False
    ) -> MarketMoversReport:
        """
        Get comprehensive market movers report using smart provider selection
        
        Args:
            limit: Maximum number of movers in each category
            force_refresh: Bypass cache and fetch fresh data
            
        Returns:
            Complete report with gainers, losers, and most active
        """
        # Try to get complete report from providers that support it
        report = self._get_data_with_strategy(
            DataSourceType.MARKET_MOVERS,
            self._get_market_movers_report_from_provider,
            limit=limit,
            force_refresh=force_refresh,
        )
        
        if report:
            return report
            
        # Fallback: build report from individual calls
        logger.info("Building market movers report from individual calls")
        gainers = self.get_market_gainers(limit, force_refresh)
        losers = self.get_market_losers(limit, force_refresh)
        most_active = self.get_most_active(limit, force_refresh)
        
        return MarketMoversReport(
            gainers=gainers,
            losers=losers,
            most_active=most_active,
            timestamp=datetime.now(),
            market_status=self._get_current_market_status(),
        )

    def _get_market_gainers_from_provider(
        self, provider: AssetDataProvider, provider_id: str, **kwargs
    ) -> List[MarketMover]:
        """Get market gainers from a specific provider"""
        # Check if provider has market movers capability
        if hasattr(provider, 'get_market_gainers'):
            return provider.get_market_gainers(**kwargs)
        return None

    def _get_market_losers_from_provider(
        self, provider: AssetDataProvider, provider_id: str, **kwargs
    ) -> List[MarketMover]:
        """Get market losers from a specific provider"""
        if hasattr(provider, 'get_market_losers'):
            return provider.get_market_losers(**kwargs)
        return None

    def _get_most_active_from_provider(
        self, provider: AssetDataProvider, provider_id: str, **kwargs
    ) -> List[MarketMover]:
        """Get most active stocks from a specific provider"""
        if hasattr(provider, 'get_most_active'):
            return provider.get_most_active(**kwargs)
        return None

    def _get_market_movers_report_from_provider(
        self, provider: AssetDataProvider, provider_id: str, **kwargs
    ) -> MarketMoversReport:
        """Get complete market movers report from a specific provider"""
        if hasattr(provider, 'get_market_movers_report'):
            return provider.get_market_movers_report(**kwargs)
        return None

    def _get_extended_hours_from_provider(
        self, provider: AssetDataProvider, provider_id: str, **kwargs
    ) -> Optional[ExtendedHoursData]:
        """Get extended hours data from a specific API provider"""
        symbol = kwargs.get("symbol")
        session = kwargs.get("session", MarketStatus.AFTER_HOURS)
        
        if not symbol:
            return None
            
        asset = self._create_asset(symbol)
        return provider.get_extended_hours_data(asset, session)

    def _get_extended_hours_movers(
        self, mover_type: str, limit: int, force_refresh: bool
    ) -> List[Dict[str, any]]:
        """Get extended hours movers using web scrapers with fallback strategy"""
        providers = self.config_manager.get_providers_for_data_type(
            DataSourceType.EXTENDED_HOURS
        )
        
        # Filter to only web scrapers for movers data
        scraper_providers = [
            (provider_id, config) for provider_id, config in providers
            if config.type == "web_scraper" and provider_id in self._scraper_instances
        ]
        
        if not scraper_providers:
            logger.warning("No web scraper providers available for extended hours movers")
            return []
        
        # Use first success strategy for web scrapers
        for provider_id, provider_config in scraper_providers:
            try:
                scraper = self._scraper_instances[provider_id]
                logger.info(f"Attempting to get {mover_type} from {provider_id}")
                
                if mover_type == "gainers":
                    result = scraper.get_after_hours_gainers(limit)
                elif mover_type == "losers":
                    result = scraper.get_after_hours_losers(limit)
                else:
                    continue
                    
                if result:
                    logger.info(f"Successfully got {len(result)} {mover_type} from {provider_id}")
                    self.config_manager.record_provider_success(provider_id)
                    return result
                    
            except Exception as e:
                logger.error(f"Error getting {mover_type} from {provider_id}: {e}")
                self.config_manager.record_provider_failure(provider_id)
                continue
        
        logger.warning(f"Failed to get {mover_type} from all available web scrapers")
        return []

    def _get_current_market_status(self) -> MarketStatus:
        """Determine current market status"""
        now = datetime.now()
        # Simple check - can be enhanced
        weekday = now.weekday()
        hour = now.hour
        
        # Market closed on weekends
        if weekday >= 5:
            return MarketStatus.CLOSED
            
        # Market hours: 9:30 AM - 4:00 PM ET
        if 9 <= hour < 16:
            return MarketStatus.OPEN
        elif hour < 9:
            return MarketStatus.PRE_MARKET
        elif hour < 20:
            return MarketStatus.AFTER_HOURS
        else:
            return MarketStatus.CLOSED

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

    def get_extended_hours_data(
        self, symbol: str, session: MarketStatus = MarketStatus.AFTER_HOURS
    ) -> Optional[ExtendedHoursData]:
        """Get extended hours trading data combining API providers and web scrapers"""
        return self._get_data_with_strategy(
            DataSourceType.EXTENDED_HOURS,
            self._get_extended_hours_from_provider,
            symbol=symbol,
            session=session,
        )
    
    def get_extended_hours_gainers(
        self, limit: int = 20, force_refresh: bool = False
    ) -> List[Dict[str, any]]:
        """Get extended hours gainers using web scrapers"""
        return self._get_extended_hours_movers("gainers", limit, force_refresh)
    
    def get_extended_hours_losers(
        self, limit: int = 20, force_refresh: bool = False
    ) -> List[Dict[str, any]]:
        """Get extended hours losers using web scrapers"""
        return self._get_extended_hours_movers("losers", limit, force_refresh)
    
    def get_available_data_types(self) -> List[str]:
        """Get list of available data types"""
        return self.config_manager.list_data_types()

    def reload_config(self) -> None:
        """Reload configuration and reinitialize providers"""
        logger.info("Reloading smart coordinator configuration...")
        self.config_manager.reload_config()
        self._provider_instances.clear()
        self._scraper_instances.clear()
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
