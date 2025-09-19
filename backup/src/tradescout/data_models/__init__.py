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
    RiskLevel,
    GapType,
    GapRules,
    GapCandidate,
    GapAssessment,
)

# Asset models
from .models_asset import (
    Asset,
    AssetType,
    PriceData,
)

# Market models
from .models_market import (
    Market,
    MarketStatus,
    MarketType,
    MarketMover,
)
