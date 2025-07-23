"""
Market-wide data providers

Provider implementations for different data sources supporting
market-wide analysis capabilities.
"""

from .alpha_vantage_market import AlphaVantageMarketProvider

__all__ = ["AlphaVantageMarketProvider"]