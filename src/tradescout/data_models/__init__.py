"""
Data Models Package

Core domain models and interfaces for TradeScout:
- Domain models (Asset, Market, MarketSegment, etc.)
- Data provider interfaces (AssetDataProvider, NewsProvider, etc.)
- Factory classes for creating domain entities
- Support for multiple API providers (Polygon.io, yfinance, Finnhub, Alpha Vantage, NewsAPI)
"""

# Analysis models
from .models_analysis import (
    ConfidenceLevel,
    TradeSide,
    TradeStatus,
    TradeSuggestion,
)

# Asset models
from .models_asset import (
    Asset,
    AssetType,
    MarketQuote,
    PriceData,
)

# Base models
from .models_base import (
    Market,
    MarketStatus,
)

# Market models  
from .models_market import (
    MarketMover,
)

# Sentiment models
from .models_sentiment import (
    NewsItem,
    SocialMention,
    AssetSentiment,
    MarketSentiment,
)

# Factory classes moved to tests directory since only tests use fake data


# Future adapter implementations will be imported here:
# Legacy adapter references - now handled by data_sources_api package
