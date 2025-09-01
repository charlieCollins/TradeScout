"""
Data Models Package

Core domain models and interfaces for TradeScout:
- Domain models (Asset, Market, MarketSegment, etc.)
- Data provider interfaces (AssetDataProvider, NewsProvider, etc.)
- Factory classes for creating domain entities
- Support for multiple API providers (Polygon.io, yfinance, Finnhub, Alpha Vantage, NewsAPI)
"""

# Analysis models
from .domain_models_analysis import (
    ActualTrade,
    ConfidenceLevel,
    MarketEvent,
    PerformanceMetrics,
    TechnicalIndicators,
    TradeSide,
    TradeStatus,
    TradeSuggestion,
)

# Core domain models
from .domain_models_core import (
    Asset,
    AssetType,
    ExtendedHoursData,
    Market,
    MarketQuote,
    MarketSegment,
    MarketStatus,
    MarketType,
    NewsItem,
    PriceData,
    SocialSentiment,
)

# Factory classes
from .factories import (
    AssetFactory,
    MarketFactory,
    MarketSegmentFactory,
    get_common_assets,
    get_tech_segments,
    get_us_stock_market,
)

# Abstract interfaces
from .interfaces import (
    AssetDataProvider,
    DataCache,
    DataCollectionCoordinator,
    NewsProvider,
    RateLimiter,
    SentimentProvider,
)

# Future adapter implementations will be imported here:
# Legacy adapter references - now handled by data_sources_api package
