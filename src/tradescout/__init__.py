"""
TradeScout - Personal Market Research Assistant

A momentum trading analysis tool that provides morning trade suggestions
based on overnight market activity and technical analysis.
"""

__version__ = "0.1.0"
__author__ = "Charlie Collins"
__description__ = "Personal Market Research Assistant for Momentum Trading"

# Core public API exports
from .data_models.domain_models_core import (
    Asset,
    Market,
    MarketSegment,
    PriceData,
    MarketQuote,
    AssetType,
    MarketType,
    MarketStatus,
)
from .data_models.interfaces import AssetDataProvider
from .data_sources.asset_data_provider_yfinance import AssetDataProviderYFinance

__all__ = [
    "Asset",
    "Market",
    "MarketSegment",
    "PriceData",
    "MarketQuote",
    "AssetType",
    "MarketType",
    "MarketStatus",
    "AssetDataProvider",
    "AssetDataProviderYFinance",
]
