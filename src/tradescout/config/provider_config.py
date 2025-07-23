"""
Provider Configuration Manager

Handles configuration and initialization of market data providers
based on available API keys and user preferences.
"""

import logging
import os
from typing import Optional, List, Tuple
from pathlib import Path

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Look for .env file in project root (two levels up from this file)
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logging.getLogger(__name__).info(f"Loaded .env from {env_path}")
except ImportError:
    logging.getLogger(__name__).warning("python-dotenv not installed, environment variables from .env will not be loaded")

from .local_config import API_CONFIG
from ..data_sources.multi_provider_coordinator import MultiProviderCoordinator
from ..data_sources.asset_data_provider_yfinance import AssetDataProviderYFinance
from ..data_sources.asset_data_provider_polygon import AssetDataProviderPolygon
from ..data_sources.asset_data_provider_finnhub import AssetDataProviderFinnhub

logger = logging.getLogger(__name__)


class ProviderConfigManager:
    """
    Manages configuration and initialization of market data providers
    
    Features:
    - Automatically detects available API keys
    - Creates providers in priority order
    - Provides fallback configurations
    - Validates provider configurations
    """
    
    def __init__(self):
        """Initialize provider configuration manager"""
        self.api_config = API_CONFIG
    
    def get_available_providers(self) -> List[Tuple[str, dict, bool]]:
        """
        Get list of available providers based on configuration
        
        Returns:
            List of tuples: (provider_name, config, is_available)
        """
        providers = []
        
        # Check Polygon.io
        polygon_config = self.api_config.get("polygon", {})
        polygon_available = bool(polygon_config.get("api_key"))
        providers.append(("polygon", polygon_config, polygon_available))
        
        # Check Yahoo Finance (always available)
        yfinance_config = self.api_config.get("yfinance", {})
        providers.append(("yfinance", yfinance_config, True))
        
        # Check Finnhub
        finnhub_config = self.api_config.get("finnhub", {})
        finnhub_available = bool(finnhub_config.get("api_key"))
        providers.append(("finnhub", finnhub_config, finnhub_available))
        
        # Check Alpha Vantage
        alpha_config = self.api_config.get("alpha_vantage", {})
        alpha_available = bool(alpha_config.get("api_key"))
        providers.append(("alpha_vantage", alpha_config, alpha_available))
        
        return providers
    
    def create_coordinator(self, preferred_providers: Optional[List[str]] = None) -> MultiProviderCoordinator:
        """
        Create a configured MultiProviderCoordinator
        
        Args:
            preferred_providers: List of provider names in preferred order
                               If None, uses configuration priorities
        
        Returns:
            Configured MultiProviderCoordinator
        """
        coordinator = MultiProviderCoordinator()
        available_providers = self.get_available_providers()
        
        # Sort by preference or priority
        if preferred_providers:
            # Sort by user preference
            def sort_key(item):
                name, config, available = item
                if not available:
                    return 999  # Put unavailable providers at the end
                try:
                    return preferred_providers.index(name)
                except ValueError:
                    return len(preferred_providers)  # Put non-preferred at end
        else:
            # Sort by configured priority
            def sort_key(item):
                name, config, available = item
                if not available:
                    return 999  # Put unavailable providers at the end
                return config.get("priority", 10)
        
        sorted_providers = sorted(available_providers, key=sort_key)
        
        # Add available providers to coordinator
        for provider_name, config, is_available in sorted_providers:
            if not is_available:
                logger.info(f"Skipping {provider_name} - API key not configured")
                continue
            
            try:
                provider_instance = self._create_provider_instance(provider_name, config)
                if provider_instance:
                    priority = config.get("priority", 10)
                    coordinator.add_provider(provider_name, provider_instance, priority)
                    logger.info(f"Added {provider_name} provider with priority {priority}")
            except Exception as e:
                logger.error(f"Failed to create {provider_name} provider: {e}")
                continue
        
        # Ensure we have at least one provider
        if not coordinator.providers:
            logger.warning("No providers configured, adding YFinance as fallback")
            yfinance = AssetDataProviderYFinance()
            coordinator.add_provider("yfinance_fallback", yfinance, 1)
        
        return coordinator
    
    def _create_provider_instance(self, provider_name: str, config: dict):
        """Create a provider instance based on name and config"""
        
        if provider_name == "polygon":
            api_key = config.get("api_key")
            if not api_key:
                logger.warning("Polygon API key not configured")
                return None
            return AssetDataProviderPolygon(api_key)
        
        elif provider_name == "yfinance":
            return AssetDataProviderYFinance()
        
        elif provider_name == "finnhub":
            api_key = config.get("api_key")
            if not api_key:
                logger.warning("Finnhub API key not configured")
                return None
            return AssetDataProviderFinnhub(api_key)
        
        elif provider_name == "alpha_vantage":
            # Import here to avoid circular imports
            try:
                from ..data_sources.asset_data_provider_alpha_vantage import AssetDataProviderAlphaVantage
                api_key = config.get("api_key")
                if not api_key:
                    logger.warning("Alpha Vantage API key not configured")
                    return None
                return AssetDataProviderAlphaVantage(api_key)
            except ImportError:
                logger.warning("Alpha Vantage adapter not available")
                return None
        
        else:
            logger.error(f"Unknown provider: {provider_name}")
            return None
    
    def get_provider_status(self) -> dict:
        """
        Get status of all configured providers
        
        Returns:
            Dictionary with provider status information
        """
        status = {
            "timestamp": logging.time.time(),
            "providers": {},
            "summary": {
                "total_configured": 0,
                "available": 0,
                "unavailable": 0,
            }
        }
        
        available_providers = self.get_available_providers()
        
        for provider_name, config, is_available in available_providers:
            status["providers"][provider_name] = {
                "configured": True,
                "available": is_available,
                "api_key_present": bool(config.get("api_key")),
                "priority": config.get("priority", 10),
                "rate_limit_per_minute": config.get("rate_limit_per_minute", "unknown"),
                "supports_extended_hours": config.get("supports_extended_hours", False),
            }
            
            status["summary"]["total_configured"] += 1
            if is_available:
                status["summary"]["available"] += 1
            else:
                status["summary"]["unavailable"] += 1
        
        return status
    
    def validate_configuration(self) -> List[str]:
        """
        Validate provider configuration and return any issues
        
        Returns:
            List of validation issues/warnings
        """
        issues = []
        available_providers = self.get_available_providers()
        
        # Check if we have at least one provider
        has_available = any(available for _, _, available in available_providers)
        if not has_available:
            issues.append("No market data providers are configured with valid API keys")
        
        # Check for missing API keys
        for provider_name, config, is_available in available_providers:
            if provider_name != "yfinance" and not is_available:
                issues.append(f"{provider_name} API key not configured (set {provider_name.upper()}_API_KEY)")
        
        # Check for conflicting priorities
        priorities = [config.get("priority", 10) for _, config, available in available_providers if available]
        if len(priorities) != len(set(priorities)):
            issues.append("Multiple providers have the same priority - may cause unpredictable ordering")
        
        return issues


# Global instance for easy access
_provider_config_manager = None


def get_provider_config_manager() -> ProviderConfigManager:
    """
    Get the global provider configuration manager
    
    Returns:
        ProviderConfigManager instance
    """
    global _provider_config_manager
    if _provider_config_manager is None:
        _provider_config_manager = ProviderConfigManager()
    return _provider_config_manager


def create_default_coordinator() -> MultiProviderCoordinator:
    """
    Create a default coordinator based on current configuration
    
    Returns:
        Configured MultiProviderCoordinator
    """
    manager = get_provider_config_manager()
    return manager.create_coordinator()


def create_polygon_first_coordinator() -> MultiProviderCoordinator:
    """
    Create a coordinator with Polygon as first choice, YFinance as fallback
    
    Returns:
        Configured MultiProviderCoordinator with Polygon priority
    """
    manager = get_provider_config_manager()
    return manager.create_coordinator(preferred_providers=["polygon", "yfinance", "alpha_vantage"])


if __name__ == "__main__":
    # Test the provider configuration
    print("🧪 Testing Provider Configuration...")
    
    manager = get_provider_config_manager()
    
    # Show provider status
    print("\n📊 Provider Status:")
    status = manager.get_provider_status()
    for name, info in status["providers"].items():
        status_str = "✅ Available" if info["available"] else "❌ Not configured"
        print(f"  {name}: {status_str} (Priority: {info['priority']})")
    
    # Validate configuration
    print("\n🔍 Configuration Validation:")
    issues = manager.validate_configuration()
    if issues:
        for issue in issues:
            print(f"  ⚠️  {issue}")
    else:
        print("  ✅ Configuration is valid")
    
    # Create coordinator
    print("\n🔧 Creating Coordinator:")
    coordinator = manager.create_coordinator()
    print(f"  Created coordinator with {len(coordinator.providers)} providers")
    
    for name, _, priority in coordinator.providers:
        print(f"    {priority}. {name}")
    
    print("\n🎉 Provider configuration test completed!")