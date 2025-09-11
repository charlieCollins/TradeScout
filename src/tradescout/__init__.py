"""
TradeScout - Personal Market Research Assistant

A momentum trading analysis tool that provides morning trade suggestions
based on overnight market activity and technical analysis.
"""

__version__ = "0.1.0"
__author__ = "Charlie Collins"
__description__ = "Personal Market Research Assistant for Momentum Trading"

# Core public API exports
from .data_models import (
    Asset,
    AssetType,
    Market,
    MarketQuote,
    MarketStatus,
    PriceData,
)
__all__ = [
    "Asset",
    "AssetType",
    "Market",
    "MarketQuote",
    "MarketStatus",
    "PriceData",
]
