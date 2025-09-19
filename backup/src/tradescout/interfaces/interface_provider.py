"""
Combined Data Provider Interface for TradeScout

This interface combines asset, market, sentiment, and analysis operations into
flexible provider interfaces. Providers can implement what they support.
"""

from abc import ABC
from typing import Optional

from .interface_asset import AssetDataInterface
from .interface_market import MarketDataInterface
from .interface_gap_analysis import GapAnalysisInterface


class DataProvider(AssetDataInterface, MarketDataInterface, ABC):
    """
    Combined interface for data providers supporting asset and market operations.

    This is the standard interface that most data providers should implement.
    """

    @property
    def provider_name(self) -> str:
        """Return the name of this data provider"""
        return self.__class__.__name__

    @property
    def supports_extended_hours(self) -> bool:
        """Return whether this provider supports extended hours data"""
        return False

    @property
    def rate_limit_per_minute(self) -> Optional[int]:
        """Return the rate limit for this provider (None for unlimited)"""
        return None
