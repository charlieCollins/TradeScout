"""
Data Collection Package

Handles all external data sources:
- Domain models (Asset, Market, MarketSegment, etc.)
- Data provider interfaces (AssetDataProvider, NewsProvider, etc.)
- Factory classes for creating domain entities
- External API adapters (Polygon.io, yfinance, NewsAPI, Reddit)
"""

# Core domain models
from .domain_models_core import (
    Asset,
    Market,
    MarketSegment,
    PriceData,
    MarketQuote,
    ExtendedHoursData,
    NewsItem,
    SocialSentiment,
    AssetType,
    MarketType,
    MarketStatus,
)

# Analysis models
from .domain_models_analysis import (
    TradeSuggestion,
    ActualTrade,
    PerformanceMetrics,
    MarketEvent,
    TechnicalIndicators,
    TradeSide,
    TradeStatus,
    ConfidenceLevel,
)

# Factory classes
from .factories import (
    MarketFactory,
    MarketSegmentFactory,
    AssetFactory,
    get_us_stock_market,
    get_common_assets,
    get_tech_segments,
)

# Abstract interfaces
from .interfaces import (
    AssetDataProvider,
    NewsProvider,
    SentimentProvider,
    DataCollectionCoordinator,
    RateLimiter,
    DataCache,
)

# Future adapter implementations will be imported here:
# from .yfinance_adapter import YFinanceAdapter
# from .polygon_adapter import PolygonAdapter
# from .news_api_adapter import NewsAPIAdapter
# from .reddit_adapter import RedditAdapter
