"""
Market-wide data analysis module for TradeScout

Provides market-wide analysis capabilities including:
- Market gainers/losers tracking
- Sector performance analysis  
- Market indices monitoring
"""

from .interfaces import MarketWideDataProvider, MarketMover, MarketMoversReport
from .market_movers import MarketMoversProvider, create_market_movers_provider
from .providers.alpha_vantage_market import AlphaVantageMarketProvider

__all__ = [
    "MarketWideDataProvider", 
    "MarketMover",
    "MarketMoversReport",
    "MarketMoversProvider",
    "create_market_movers_provider",
    "AlphaVantageMarketProvider"
]