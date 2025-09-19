"""
TradeScout Interfaces

Clean, minimal interfaces that define contracts for data providers and analysis engines.
Organized by data type and operation scope.
"""

from .interface_asset import AssetDataInterface
from .interface_market import MarketDataInterface
from .interface_gap_analysis import GapAnalysisInterface
from .interface_provider import DataProvider

__all__ = [
    # Core interfaces
    "AssetDataInterface",
    "MarketDataInterface",
    "GapAnalysisInterface",
    # Provider combinations
    "DataProvider",
]
