"""
Data Sources Configuration Manager

Manages data source configuration from YAML file, providing intelligent
routing of different data types to appropriate providers with fallback strategies.
"""

import logging
import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple
from enum import Enum
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class FallbackStrategy(Enum):
    """Strategy for handling multiple data sources"""
    FIRST_SUCCESS = "first_success"
    MERGE_BEST = "merge_best"
    MERGE_ALL = "merge_all"
    ROUND_ROBIN = "round_robin"


class DataSourceType(Enum):
    """Types of data that can be requested"""
    CURRENT_QUOTES = "current_quotes"
    HISTORICAL_PRICES = "historical_prices"
    EXTENDED_HOURS = "extended_hours"
    COMPANY_FUNDAMENTALS = "company_fundamentals"
    FINANCIAL_STATEMENTS = "financial_statements"
    EARNINGS_DATA = "earnings_data"
    VOLUME_ANALYSIS = "volume_analysis"
    TECHNICAL_INDICATORS = "technical_indicators"
    MARKET_MOVERS = "market_movers"
    COMPANY_NEWS = "company_news"
    MARKET_NEWS = "market_news"
    SOCIAL_SENTIMENT = "social_sentiment"
    ANALYST_RATINGS = "analyst_ratings"


@dataclass
class ProviderConfig:
    """Configuration for a single data provider"""
    name: str
    provider_type: str  # free, freemium, paid
    rate_limit_per_minute: int
    api_key_required: bool
    priority: int
    enabled: bool
    supports_extended_hours: bool = False
    rate_limit_per_day: Optional[int] = None
    quality_weight: int = 5


@dataclass
class DataTypeConfig:
    """Configuration for a specific type of data"""
    description: str
    providers: List[str]
    fallback_strategy: FallbackStrategy
    cache_ttl_minutes: Optional[int] = None
    cache_ttl_hours: Optional[int] = None
    cache_ttl_days: Optional[int] = None
    
    @property
    def cache_ttl_seconds(self) -> int:
        """Get cache TTL in seconds"""
        if self.cache_ttl_minutes:
            return self.cache_ttl_minutes * 60
        elif self.cache_ttl_hours:
            return self.cache_ttl_hours * 3600
        elif self.cache_ttl_days:
            return self.cache_ttl_days * 86400
        else:
            return 300  # Default 5 minutes


@dataclass
class DataSourcesConfig:
    """Complete data sources configuration"""
    providers: Dict[str, ProviderConfig]
    data_types: Dict[str, DataTypeConfig]
    quality_weights: Dict[str, int]
    rate_limiting: Dict[str, Any]
    error_handling: Dict[str, Any]
    development: Dict[str, Any]


class DataSourcesManager:
    """
    Manages data source configuration and routing
    
    Features:
    - Load configuration from YAML file
    - Route data requests to appropriate providers
    - Handle fallback strategies
    - Manage rate limiting and error handling
    - Support for development/testing modes
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize data sources manager
        
        Args:
            config_path: Path to configuration YAML file
        """
        if config_path is None:
            config_path = Path(__file__).parent / "data_sources_config.yaml"
        
        self.config_path = config_path
        self.config: Optional[DataSourcesConfig] = None
        self._load_config()
        
        # Track provider failures for circuit breaker
        self.provider_failures: Dict[str, List[datetime]] = {}
        self.disabled_providers: Dict[str, datetime] = {}
    
    def _load_config(self) -> None:
        """Load configuration from YAML file"""
        try:
            if not self.config_path.exists():
                logger.error(f"Configuration file not found: {self.config_path}")
                raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
            
            with open(self.config_path, 'r') as file:
                yaml_data = yaml.safe_load(file)
            
            # Parse providers
            providers = {}
            for provider_id, provider_data in yaml_data.get("providers", {}).items():
                providers[provider_id] = ProviderConfig(
                    name=provider_data.get("name", provider_id),
                    provider_type=provider_data.get("type", "unknown"),
                    rate_limit_per_minute=provider_data.get("rate_limit_per_minute", 60),
                    api_key_required=provider_data.get("api_key_required", False),
                    priority=provider_data.get("priority", 10),
                    enabled=provider_data.get("enabled", True),
                    supports_extended_hours=provider_data.get("supports_extended_hours", False),
                    rate_limit_per_day=provider_data.get("rate_limit_per_day"),
                )
            
            # Parse data types
            data_types = {}
            for data_type_id, data_type_data in yaml_data.get("data_types", {}).items():
                fallback_strategy = FallbackStrategy(data_type_data.get("fallback_strategy", "first_success"))
                
                data_types[data_type_id] = DataTypeConfig(
                    description=data_type_data.get("description", ""),
                    providers=data_type_data.get("providers", []),
                    fallback_strategy=fallback_strategy,
                    cache_ttl_minutes=data_type_data.get("cache_ttl_minutes"),
                    cache_ttl_hours=data_type_data.get("cache_ttl_hours"),
                    cache_ttl_days=data_type_data.get("cache_ttl_days"),
                )
            
            # Create configuration object
            self.config = DataSourcesConfig(
                providers=providers,
                data_types=data_types,
                quality_weights=yaml_data.get("quality_weights", {}),
                rate_limiting=yaml_data.get("rate_limiting", {}),
                error_handling=yaml_data.get("error_handling", {}),
                development=yaml_data.get("development", {}),
            )
            
            # Update provider quality weights
            for provider_id, weight in self.config.quality_weights.items():
                if provider_id in self.config.providers:
                    self.config.providers[provider_id].quality_weight = weight
            
            logger.info(f"Loaded data sources configuration from {self.config_path}")
            logger.info(f"Configured {len(self.config.providers)} providers and {len(self.config.data_types)} data types")
            
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise
    
    def get_providers_for_data_type(
        self, 
        data_type: Union[str, DataSourceType],
        filter_enabled: bool = True,
        filter_available: bool = True
    ) -> List[Tuple[str, ProviderConfig]]:
        """
        Get ordered list of providers for a specific data type
        
        Args:
            data_type: Type of data being requested
            filter_enabled: Only return enabled providers
            filter_available: Only return providers with available API keys
            
        Returns:
            List of (provider_id, provider_config) tuples in priority order
        """
        if isinstance(data_type, DataSourceType):
            data_type = data_type.value
        
        if data_type not in self.config.data_types:
            logger.warning(f"Unknown data type: {data_type}")
            return []
        
        data_config = self.config.data_types[data_type]
        providers = []
        
        for provider_id in data_config.providers:
            if provider_id not in self.config.providers:
                logger.warning(f"Provider {provider_id} not configured")
                continue
            
            provider_config = self.config.providers[provider_id]
            
            # Filter enabled providers
            if filter_enabled and not provider_config.enabled:
                continue
            
            # Filter available providers (check API keys)
            if filter_available and provider_config.api_key_required:
                api_key_var = f"{provider_id.upper()}_API_KEY"
                if not os.getenv(api_key_var):
                    logger.debug(f"API key not available for {provider_id}")
                    continue
            
            # Check if provider is temporarily disabled (circuit breaker)
            if provider_id in self.disabled_providers:
                disable_time = self.disabled_providers[provider_id]
                if datetime.now() - disable_time < timedelta(minutes=10):  # 10 minute timeout
                    logger.debug(f"Provider {provider_id} temporarily disabled")
                    continue
                else:
                    # Re-enable provider
                    del self.disabled_providers[provider_id]
                    logger.info(f"Re-enabled provider {provider_id}")
            
            providers.append((provider_id, provider_config))
        
        # Sort by priority (lower number = higher priority)
        providers.sort(key=lambda x: x[1].priority)
        
        return providers
    
    def get_fallback_strategy(self, data_type: Union[str, DataSourceType]) -> FallbackStrategy:
        """Get the fallback strategy for a data type"""
        if isinstance(data_type, DataSourceType):
            data_type = data_type.value
            
        if data_type not in self.config.data_types:
            return FallbackStrategy.FIRST_SUCCESS
            
        return self.config.data_types[data_type].fallback_strategy
    
    def get_cache_ttl(self, data_type: Union[str, DataSourceType]) -> int:
        """Get cache TTL in seconds for a data type"""
        if isinstance(data_type, DataSourceType):
            data_type = data_type.value
            
        if data_type not in self.config.data_types:
            return 300  # Default 5 minutes
            
        return self.config.data_types[data_type].cache_ttl_seconds
    
    def record_provider_failure(self, provider_id: str) -> None:
        """Record a provider failure for circuit breaker logic"""
        now = datetime.now()
        
        # Initialize failure list if needed
        if provider_id not in self.provider_failures:
            self.provider_failures[provider_id] = []
        
        # Add current failure
        self.provider_failures[provider_id].append(now)
        
        # Clean old failures (outside the window)
        failure_window = timedelta(minutes=self.config.error_handling.get("failure_window_minutes", 10))
        self.provider_failures[provider_id] = [
            failure_time for failure_time in self.provider_failures[provider_id]
            if now - failure_time < failure_window
        ]
        
        # Check if we should disable the provider
        max_failures = self.config.error_handling.get("max_failures_before_disable", 5)
        if len(self.provider_failures[provider_id]) >= max_failures:
            self.disabled_providers[provider_id] = now
            logger.warning(f"Disabled provider {provider_id} due to {max_failures} failures")
    
    def record_provider_success(self, provider_id: str) -> None:
        """Record a provider success (clears failure count)"""
        if provider_id in self.provider_failures:
            self.provider_failures[provider_id].clear()
    
    def is_provider_enabled(self, provider_id: str) -> bool:
        """Check if a provider is enabled and available"""
        if provider_id not in self.config.providers:
            return False
        
        provider_config = self.config.providers[provider_id]
        
        # Check basic enabled flag
        if not provider_config.enabled:
            return False
        
        # Check API key availability
        if provider_config.api_key_required:
            api_key_var = f"{provider_id.upper()}_API_KEY"
            if not os.getenv(api_key_var):
                return False
        
        # Check circuit breaker
        if provider_id in self.disabled_providers:
            disable_time = self.disabled_providers[provider_id]
            if datetime.now() - disable_time < timedelta(minutes=10):
                return False
        
        return True
    
    def get_provider_status(self) -> Dict[str, Any]:
        """Get status of all configured providers"""
        status = {
            "timestamp": datetime.now().isoformat(),
            "providers": {},
            "summary": {
                "total_configured": len(self.config.providers),
                "enabled": 0,
                "available": 0,
                "temporarily_disabled": 0,
            }
        }
        
        for provider_id, provider_config in self.config.providers.items():
            # Check API key
            api_key_available = True
            if provider_config.api_key_required:
                api_key_var = f"{provider_id.upper()}_API_KEY"
                api_key_available = bool(os.getenv(api_key_var))
            
            # Check circuit breaker status
            temporarily_disabled = provider_id in self.disabled_providers
            if temporarily_disabled:
                disable_time = self.disabled_providers[provider_id]
                if datetime.now() - disable_time >= timedelta(minutes=10):
                    temporarily_disabled = False
                    del self.disabled_providers[provider_id]
            
            is_available = (
                provider_config.enabled and 
                api_key_available and 
                not temporarily_disabled
            )
            
            provider_status = {
                "name": provider_config.name,
                "type": provider_config.provider_type,
                "enabled": provider_config.enabled,
                "api_key_required": provider_config.api_key_required,
                "api_key_available": api_key_available,
                "temporarily_disabled": temporarily_disabled,
                "available": is_available,
                "priority": provider_config.priority,
                "quality_weight": provider_config.quality_weight,
                "rate_limit_per_minute": provider_config.rate_limit_per_minute,
                "supports_extended_hours": provider_config.supports_extended_hours,
                "recent_failures": len(self.provider_failures.get(provider_id, [])),
            }
            
            status["providers"][provider_id] = provider_status
            
            # Update summary counts
            if provider_config.enabled:
                status["summary"]["enabled"] += 1
            if is_available:
                status["summary"]["available"] += 1
            if temporarily_disabled:
                status["summary"]["temporarily_disabled"] += 1
        
        return status
    
    def get_data_type_config(self, data_type: Union[str, DataSourceType]) -> Optional[DataTypeConfig]:
        """Get configuration for a specific data type"""
        if isinstance(data_type, DataSourceType):
            data_type = data_type.value
            
        return self.config.data_types.get(data_type)
    
    def list_data_types(self) -> List[str]:
        """Get list of all configured data types"""
        return list(self.config.data_types.keys())
    
    def reload_config(self) -> None:
        """Reload configuration from file"""
        logger.info("Reloading data sources configuration...")
        self._load_config()


# Global instance for easy access
_data_sources_manager = None


def get_data_sources_manager() -> DataSourcesManager:
    """
    Get the global data sources manager
    
    Returns:
        DataSourcesManager instance
    """
    global _data_sources_manager
    if _data_sources_manager is None:
        _data_sources_manager = DataSourcesManager()
    return _data_sources_manager


if __name__ == "__main__":
    # Test the configuration manager
    print("🧪 Testing Data Sources Manager...")
    
    manager = get_data_sources_manager()
    
    # Show provider status
    print("\n📊 Provider Status:")
    status = manager.get_provider_status()
    for provider_id, info in status["providers"].items():
        status_str = "✅ Available" if info["available"] else "❌ Unavailable"
        print(f"  {provider_id} ({info['name']}): {status_str}")
        print(f"    Priority: {info['priority']}, Quality: {info['quality_weight']}")
    
    # Show data type configurations
    print("\n📋 Data Type Configurations:")
    for data_type in manager.list_data_types()[:5]:  # Show first 5
        config = manager.get_data_type_config(data_type)
        providers = manager.get_providers_for_data_type(data_type)
        provider_names = [p[0] for p in providers]
        print(f"  {data_type}: {provider_names} ({config.fallback_strategy.value})")
    
    print(f"\n📈 Summary:")
    print(f"  Total providers: {status['summary']['total_configured']}")
    print(f"  Available providers: {status['summary']['available']}")
    print(f"  Data types configured: {len(manager.list_data_types())}")
    
    print("\n✅ Data Sources Manager test completed!")