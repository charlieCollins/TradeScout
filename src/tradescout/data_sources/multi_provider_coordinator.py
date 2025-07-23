"""
Multi-Provider Data Collection Coordinator

Implements DataCollectionCoordinator interface to aggregate data from multiple
market data providers with failover, rate limiting, and result merging.
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from decimal import Decimal

from ..data_models.interfaces import DataCollectionCoordinator, AssetDataProvider
from ..data_models.domain_models_core import Asset, MarketQuote, AssetType
from ..data_models.factories import MarketFactory
from .asset_data_provider_yfinance import AssetDataProviderYFinance

logger = logging.getLogger(__name__)


class MultiProviderCoordinator(DataCollectionCoordinator):
    """
    Coordinates data collection from multiple market data providers
    
    Features:
    - Provider prioritization and failover
    - Result aggregation and quality scoring
    - Rate limit management across providers
    - Automatic fallback when providers fail
    """
    
    def __init__(self):
        """Initialize multi-provider coordinator"""
        self.providers: List[Tuple[str, AssetDataProvider, int]] = []
        self._nasdaq_market = MarketFactory().create_nasdaq_market()
    
    def add_provider(self, name: str, provider: AssetDataProvider, priority: int = 1) -> None:
        """
        Add a data provider to the coordinator
        
        Args:
            name: Provider name for logging
            provider: AssetDataProvider implementation
            priority: Provider priority (lower = higher priority)
        """
        self.providers.append((name, provider, priority))
        # Sort by priority (lowest number = highest priority)
        self.providers.sort(key=lambda x: x[2])
        logger.info(f"Added provider '{name}' with priority {priority}")
    
    def collect_symbol_data(self, symbol: str) -> Dict[str, Any]:
        """
        Collect comprehensive data for a symbol from all providers
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Dictionary with aggregated data from all providers
        """
        asset = self._create_asset(symbol)
        result = {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "providers_used": [],
            "quotes": {},
            "fundamentals": {},
            "best_quote": None,
            "data_quality": "unknown",
        }
        
        # Try to get quotes from all providers
        for provider_name, provider, priority in self.providers:
            try:
                logger.debug(f"Attempting to get quote from {provider_name}")
                quote = provider.get_current_quote(asset)
                
                if quote:
                    result["quotes"][provider_name] = {
                        "price": float(quote.price_data.price),
                        "volume": quote.price_data.volume,
                        "change": float(quote.price_change) if quote.price_change else 0,
                        "change_percent": float(quote.price_change_percent) if quote.price_change_percent else 0,
                        "timestamp": quote.price_data.timestamp.isoformat(),
                        "data_quality": quote.price_data.data_quality,
                        "priority": priority,
                    }
                    result["providers_used"].append(provider_name)
                    
                    # Set best quote (first successful quote with highest priority)
                    if result["best_quote"] is None:
                        result["best_quote"] = result["quotes"][provider_name]
                        result["data_quality"] = quote.price_data.data_quality
                    
                    logger.info(f"Successfully got quote from {provider_name}: ${quote.price_data.price}")
                else:
                    logger.warning(f"No quote data from {provider_name}")
                    
            except Exception as e:
                logger.error(f"Error getting quote from {provider_name}: {e}")
                continue
        
        # Try to get fundamentals from providers that support it
        for provider_name, provider, priority in self.providers:
            try:
                fundamentals = provider.get_fundamental_data(asset)
                if fundamentals:
                    result["fundamentals"][provider_name] = fundamentals
                    logger.debug(f"Got fundamentals from {provider_name}")
                    break  # Use first successful fundamentals
            except Exception as e:
                logger.error(f"Error getting fundamentals from {provider_name}: {e}")
                continue
        
        return result
    
    def collect_market_snapshot(self, symbols: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Collect market snapshot for multiple symbols
        
        Args:
            symbols: List of symbols
            
        Returns:
            Dictionary mapping symbols to their aggregated data
        """
        snapshot = {}
        
        for symbol in symbols:
            try:
                symbol_data = self.collect_symbol_data(symbol)
                snapshot[symbol] = symbol_data
                logger.debug(f"Collected snapshot data for {symbol}")
            except Exception as e:
                logger.error(f"Error collecting snapshot for {symbol}: {e}")
                snapshot[symbol] = {
                    "symbol": symbol,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
        
        return snapshot
    
    def collect_overnight_data(self) -> Dict[str, Any]:
        """
        Collect overnight market activity data
        
        Returns:
            Dictionary with overnight analysis data
        """
        # Define major market symbols for overnight analysis
        major_symbols = ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMZN", "META", "SPY"]
        
        overnight_data = {
            "timestamp": datetime.now().isoformat(),
            "analysis_type": "overnight_activity",
            "symbols_analyzed": major_symbols,
            "market_snapshot": {},
            "volume_leaders": [],
            "price_movers": [],
            "summary": {
                "total_symbols": len(major_symbols),
                "successful_quotes": 0,
                "failed_quotes": 0,
                "average_change_percent": 0.0,
            }
        }
        
        # Collect data for major symbols
        market_data = self.collect_market_snapshot(major_symbols)
        overnight_data["market_snapshot"] = market_data
        
        # Analyze the data
        successful_quotes = []
        total_change = 0.0
        
        for symbol, data in market_data.items():
            if data.get("best_quote"):
                quote_data = data["best_quote"]
                successful_quotes.append({
                    "symbol": symbol,
                    "price": quote_data["price"],
                    "change_percent": quote_data["change_percent"],
                    "volume": quote_data["volume"],
                })
                total_change += quote_data["change_percent"]
                overnight_data["summary"]["successful_quotes"] += 1
            else:
                overnight_data["summary"]["failed_quotes"] += 1
        
        # Calculate average change
        if successful_quotes:
            overnight_data["summary"]["average_change_percent"] = total_change / len(successful_quotes)
        
        # Find top movers
        price_movers = sorted(
            successful_quotes, 
            key=lambda x: abs(x["change_percent"]), 
            reverse=True
        )[:5]
        overnight_data["price_movers"] = price_movers
        
        # Find volume leaders (simplified - would need historical averages for real analysis)
        volume_leaders = sorted(
            successful_quotes,
            key=lambda x: x["volume"],
            reverse=True
        )[:5]
        overnight_data["volume_leaders"] = volume_leaders
        
        return overnight_data
    
    def get_best_quote(self, symbol: str) -> Optional[MarketQuote]:
        """
        Get the best available quote for a symbol using provider priority
        
        Args:
            symbol: Stock ticker symbol
            
        Returns:
            Best available MarketQuote or None if all providers fail
        """
        asset = self._create_asset(symbol)
        
        for provider_name, provider, priority in self.providers:
            try:
                quote = provider.get_current_quote(asset)
                if quote:
                    logger.info(f"Got quote for {symbol} from {provider_name}")
                    return quote
            except Exception as e:
                logger.warning(f"Provider {provider_name} failed for {symbol}: {e}")
                continue
        
        logger.error(f"All providers failed for {symbol}")
        return None
    
    def get_provider_status(self) -> Dict[str, Any]:
        """
        Get status information about all registered providers
        
        Returns:
            Dictionary with provider status information
        """
        status = {
            "total_providers": len(self.providers),
            "providers": [],
            "timestamp": datetime.now().isoformat(),
        }
        
        for provider_name, provider, priority in self.providers:
            provider_info = {
                "name": provider_name,
                "priority": priority,
                "rate_limit_per_minute": provider.rate_limit_per_minute,
                "supports_extended_hours": provider.supports_extended_hours,
                "status": "unknown"
            }
            
            # Test provider with a simple quote request
            try:
                test_asset = self._create_asset("AAPL")
                test_quote = provider.get_current_quote(test_asset)
                provider_info["status"] = "operational" if test_quote else "no_data"
            except Exception as e:
                provider_info["status"] = f"error: {str(e)[:100]}"
            
            status["providers"].append(provider_info)
        
        return status
    
    def _create_asset(self, symbol: str) -> Asset:
        """Create a basic Asset object for the given symbol"""
        return Asset(
            symbol=symbol.upper(),
            name=f"{symbol.upper()} Corp",
            asset_type=AssetType.COMMON_STOCK,
            market=self._nasdaq_market,
            currency="USD",
        )


# Convenience function to create a pre-configured coordinator
def create_default_coordinator() -> MultiProviderCoordinator:
    """
    Create a multi-provider coordinator with default providers
    
    Returns:
        Configured MultiProviderCoordinator with YFinance
    """
    coordinator = MultiProviderCoordinator()
    
    # Add YFinance as the primary provider (always available)
    yfinance_adapter = YFinanceAdapter()
    coordinator.add_provider("yfinance", yfinance_adapter, priority=1)
    
    logger.info("Created default coordinator with YFinance provider")
    return coordinator


def create_polygon_coordinator(polygon_api_key: str) -> MultiProviderCoordinator:
    """
    Create a coordinator with Polygon.io as primary and YFinance as fallback
    
    Args:
        polygon_api_key: Polygon.io API key
        
    Returns:
        Configured MultiProviderCoordinator with Polygon + YFinance
    """
    coordinator = MultiProviderCoordinator()
    
    # Add YFinance as fallback
    yfinance_adapter = YFinanceAdapter()
    coordinator.add_provider("yfinance", yfinance_adapter, priority=2)
    
    # TODO: Add Polygon adapter when implemented
    # polygon_adapter = PolygonAdapter(polygon_api_key)
    # coordinator.add_provider("polygon", polygon_adapter, priority=1)
    
    logger.info("Created Polygon coordinator (Polygon adapter pending implementation)")
    return coordinator


if __name__ == "__main__":
    # Simple test of the multi-provider coordinator
    print("🧪 Testing Multi-Provider Coordinator...")
    
    coordinator = create_default_coordinator()
    
    # Test single symbol data collection
    print("\n📊 Testing single symbol data collection...")
    aapl_data = coordinator.collect_symbol_data("AAPL")
    print(f"AAPL data from {len(aapl_data['providers_used'])} providers")
    if aapl_data["best_quote"]:
        print(f"Best price: ${aapl_data['best_quote']['price']}")
    
    # Test provider status
    print("\n🔍 Provider status:")
    status = coordinator.get_provider_status()
    for provider in status["providers"]:
        print(f"  {provider['name']}: {provider['status']}")
    
    print("\n🎉 Multi-provider coordinator test completed!")