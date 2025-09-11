"""
TradeScout Interfaces

Clean, minimal interfaces that define contracts for data providers and analysis engines.
Organized by data type and operation scope.
"""

from .interface_asset import AssetDataInterface
from .interface_market import MarketDataInterface
from .interface_sentiment import SentimentDataInterface
from .interface_analysis import AnalysisInterface
from .interface_provider import (
    DataProvider,
    FullProvider,
    AssetOnlyProvider,
    MarketOnlyProvider,
    SentimentOnlyProvider,
    AnalysisOnlyProvider,
)

__all__ = [
    # Core interfaces
    "AssetDataInterface",
    "MarketDataInterface", 
    "SentimentDataInterface",
    "AnalysisInterface",
    
    # Provider combinations
    "DataProvider",
    "FullProvider",
    "AssetOnlyProvider",
    "MarketOnlyProvider",
    "SentimentOnlyProvider",
    "AnalysisOnlyProvider",
]