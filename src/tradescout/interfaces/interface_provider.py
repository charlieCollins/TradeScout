"""
Combined Data Provider Interface for TradeScout

This interface combines asset, market, sentiment, and analysis operations into 
flexible provider interfaces. Providers can implement what they support.
"""

from abc import ABC
from typing import Optional

from .interface_asset import AssetDataInterface
from .interface_market import MarketDataInterface
from .interface_analysis import AnalysisInterface
from .interface_sentiment import SentimentDataInterface


class DataProvider(AssetDataInterface, MarketDataInterface, SentimentDataInterface, ABC):
    """
    Combined interface for data providers supporting asset, market, and sentiment operations.
    
    This is the standard interface that most data providers should implement.
    Sentiment is included as it's a core data type alongside price data.
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
    def supports_sentiment(self) -> bool:
        """Return whether this provider supports sentiment data"""
        return False
    
    @property
    def rate_limit_per_minute(self) -> Optional[int]:
        """Return the rate limit for this provider (None for unlimited)"""
        return None


class FullProvider(AssetDataInterface, MarketDataInterface, SentimentDataInterface, AnalysisInterface, ABC):
    """
    Full-featured provider supporting data collection, sentiment, and analysis.
    This is for providers that offer raw data, sentiment, and analytical insights.
    """
    pass


class AssetOnlyProvider(AssetDataInterface, ABC):
    """Interface for providers that only support asset-specific operations"""
    pass


class MarketOnlyProvider(MarketDataInterface, ABC):
    """Interface for providers that only support market-wide operations"""
    pass


class SentimentOnlyProvider(SentimentDataInterface, ABC):
    """Interface for providers that only support sentiment operations"""
    pass


class AnalysisOnlyProvider(AnalysisInterface, ABC):
    """Interface for providers that only perform analysis on existing data"""
    pass