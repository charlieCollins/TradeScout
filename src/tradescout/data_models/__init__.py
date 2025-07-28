"""
Data Collection Package

Handles all external data sources:
- Domain models (Asset, Market, MarketSegment, etc.)
- Data provider interfaces (AssetDataProvider, NewsProvider, etc.)
- Factory classes for creating domain entities
- External API adapters (Polygon.io, yfinance, NewsAPI, Reddit)
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
# from .yfinance_adapter import YFinanceAdapter
# from .polygon_adapter import PolygonAdapter
# from .news_api_adapter import NewsAPIAdapter
# from .reddit_adapter import RedditAdapter
