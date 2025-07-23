"""
TradeScout Data Collection Interfaces

Abstract base classes that define the contracts for data collection.
All external API implementations will conform to these interfaces,
ensuring clean separation and easy testing/mocking.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Protocol
from decimal import Decimal

from .domain_models_core import (
    Asset,
    Market,
    MarketSegment,
    PriceData,
    MarketQuote,
    ExtendedHoursData,
    NewsItem,
    SocialSentiment,
    MarketStatus,
)
from .domain_models_analysis import (
    TradeSuggestion,
    ActualTrade,
    PerformanceMetrics,
    MarketEvent,
    TechnicalIndicators,
)


class AssetDataProvider(ABC):
    """Abstract interface for individual asset data providers (Polygon, yfinance, etc.)"""

    @abstractmethod
    def get_current_quote(self, asset: Asset) -> Optional[MarketQuote]:
        """
        Get current market quote for an asset

        Args:
            asset: Asset to get quote for

        Returns:
            Current market quote or None if unavailable
        """
        pass

    @abstractmethod
    def get_extended_hours_data(
        self, asset: Asset, session: MarketStatus
    ) -> Optional[ExtendedHoursData]:
        """
        Get extended hours trading data (pre-market or after-hours)

        Args:
            asset: Asset to get extended hours data for
            session: Market session (PRE_MARKET or AFTER_HOURS)

        Returns:
            Extended hours data or None if unavailable
        """
        pass

    @abstractmethod
    def get_historical_quotes(
        self,
        asset: Asset,
        start_date: datetime,
        end_date: datetime,
        interval: str = "1d",
    ) -> List[PriceData]:
        """
        Get historical price data

        Args:
            asset: Asset to get historical data for
            start_date: Start date for data
            end_date: End date for data
            interval: Data interval (1m, 5m, 1h, 1d, etc.)

        Returns:
            List of historical price data
        """
        pass

    @abstractmethod
    def scan_volume_leaders(
        self, assets: List[Asset], min_volume_ratio: Decimal = Decimal(2.0)
    ) -> List[MarketQuote]:
        """
        Scan for assets with unusual volume

        Args:
            assets: List of assets to scan
            min_volume_ratio: Minimum volume vs average ratio

        Returns:
            List of assets with volume surges
        """
        pass

    @abstractmethod
    def get_fundamental_data(self, asset: Asset) -> Dict[str, any]:
        """
        Get fundamental company data

        Args:
            asset: Asset to get fundamental data for

        Returns:
            Dictionary with fundamental metrics
        """
        pass

    @property
    @abstractmethod
    def rate_limit_per_minute(self) -> int:
        """Return the rate limit for this provider"""
        pass

    @property
    @abstractmethod
    def supports_extended_hours(self) -> bool:
        """Return whether provider supports extended hours data"""
        pass


class NewsProvider(ABC):
    """Abstract interface for news data providers"""

    @abstractmethod
    def get_latest_news(self, assets: List[Asset], limit: int = 50) -> List[NewsItem]:
        """
        Get latest news for given assets

        Args:
            assets: List of assets to get news for
            limit: Maximum number of news items

        Returns:
            List of news items
        """
        pass

    @abstractmethod
    def get_news_by_timeframe(
        self, symbols: List[str], start_time: datetime, end_time: datetime
    ) -> List[NewsItem]:
        """
        Get news within a specific timeframe

        Args:
            symbols: List of stock symbols
            start_time: Start of time window
            end_time: End of time window

        Returns:
            List of news items in timeframe
        """
        pass

    @abstractmethod
    def search_news_by_keywords(
        self, keywords: List[str], limit: int = 50
    ) -> List[NewsItem]:
        """
        Search news by keywords

        Args:
            keywords: List of keywords to search for
            limit: Maximum number of results

        Returns:
            List of matching news items
        """
        pass

    @property
    @abstractmethod
    def daily_request_limit(self) -> int:
        """Return the daily request limit for this provider"""
        pass


class SentimentProvider(ABC):
    """Abstract interface for social sentiment providers"""

    @abstractmethod
    def get_sentiment_data(
        self, symbol: str, lookback_hours: int = 24
    ) -> Optional[SocialSentiment]:
        """
        Get aggregated sentiment data for a symbol

        Args:
            symbol: Stock ticker symbol
            lookback_hours: Hours to look back for data

        Returns:
            Aggregated sentiment data or None
        """
        pass

    @abstractmethod
    def get_trending_symbols(self, limit: int = 20) -> List[str]:
        """
        Get currently trending stock symbols

        Args:
            limit: Maximum number of symbols to return

        Returns:
            List of trending symbols
        """
        pass

    @abstractmethod
    def get_sentiment_timeline(
        self, symbol: str, start_time: datetime, end_time: datetime
    ) -> List[SocialSentiment]:
        """
        Get sentiment data over time

        Args:
            symbol: Stock ticker symbol
            start_time: Start of time window
            end_time: End of time window

        Returns:
            List of sentiment data points
        """
        pass


class TechnicalAnalysisProvider(ABC):
    """Abstract interface for technical analysis providers"""

    @abstractmethod
    def calculate_indicators(
        self, symbol: str, timeframe: str = "1d"
    ) -> Optional[TechnicalIndicators]:
        """
        Calculate technical indicators for a symbol

        Args:
            symbol: Stock ticker symbol
            timeframe: Chart timeframe (1m, 5m, 1h, 1d, etc.)

        Returns:
            Technical indicators or None if data unavailable
        """
        pass

    @abstractmethod
    def detect_patterns(self, symbol: str, timeframe: str = "1d") -> List[str]:
        """
        Detect chart patterns

        Args:
            symbol: Stock ticker symbol
            timeframe: Chart timeframe

        Returns:
            List of detected pattern names
        """
        pass

    @abstractmethod
    def calculate_support_resistance(self, symbol: str) -> Dict[str, Decimal]:
        """
        Calculate support and resistance levels

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dictionary with support/resistance levels
        """
        pass


class EventProvider(ABC):
    """Abstract interface for market event providers"""

    @abstractmethod
    def get_upcoming_events(
        self, symbols: List[str], days_ahead: int = 7
    ) -> List[MarketEvent]:
        """
        Get upcoming market events

        Args:
            symbols: List of symbols to get events for
            days_ahead: Days to look ahead

        Returns:
            List of upcoming events
        """
        pass

    @abstractmethod
    def get_earnings_calendar(
        self, start_date: datetime, end_date: datetime
    ) -> List[MarketEvent]:
        """
        Get earnings calendar

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            List of earnings events
        """
        pass


class DataCollectionCoordinator(ABC):
    """
    Coordinates data collection from multiple providers
    Handles rate limiting, caching, and failover
    """

    @abstractmethod
    def collect_symbol_data(self, symbol: str) -> Dict[str, any]:
        """
        Collect comprehensive data for a symbol from all providers

        Args:
            symbol: Stock ticker symbol

        Returns:
            Dictionary with all collected data
        """
        pass

    @abstractmethod
    def collect_market_snapshot(self, symbols: List[str]) -> Dict[str, Dict[str, any]]:
        """
        Collect market snapshot for multiple symbols

        Args:
            symbols: List of symbols

        Returns:
            Dictionary mapping symbols to their data
        """
        pass

    @abstractmethod
    def collect_overnight_data(self) -> Dict[str, any]:
        """
        Collect overnight market activity data

        Returns:
            Dictionary with overnight analysis data
        """
        pass


# Protocol for data validation
class DataValidator(Protocol):
    """Protocol for validating collected data"""

    def validate_quote(self, quote: MarketQuote) -> bool:
        """Validate a market quote"""
        ...

    def validate_news(self, news: NewsItem) -> bool:
        """Validate a news item"""
        ...

    def validate_sentiment(self, sentiment: SocialSentiment) -> bool:
        """Validate sentiment data"""
        ...


# Protocol for data transformation
class DataTransformer(Protocol):
    """Protocol for transforming external API data to our models"""

    def transform_quote_data(self, raw_data: Dict[str, any]) -> MarketQuote:
        """Transform external quote data to our MarketQuote model"""
        ...

    def transform_news_data(self, raw_data: Dict[str, any]) -> NewsItem:
        """Transform external news data to our NewsItem model"""
        ...

    def transform_sentiment_data(self, raw_data: Dict[str, any]) -> SocialSentiment:
        """Transform external sentiment data to our model"""
        ...


# Helper class for rate limiting
class RateLimiter:
    """
    Helper class to manage API rate limits across providers
    """

    def __init__(self, calls_per_minute: int):
        self.calls_per_minute = calls_per_minute
        self.call_timestamps: List[datetime] = []

    def can_make_request(self) -> bool:
        """Check if we can make another request without hitting rate limit"""
        now = datetime.now()
        minute_ago = now - timedelta(minutes=1)

        # Remove old timestamps
        self.call_timestamps = [ts for ts in self.call_timestamps if ts > minute_ago]

        return len(self.call_timestamps) < self.calls_per_minute

    def record_request(self) -> None:
        """Record that a request was made"""
        self.call_timestamps.append(datetime.now())

    def time_until_next_request(self) -> timedelta:
        """Calculate time to wait before next request"""
        if self.can_make_request():
            return timedelta(0)

        oldest_call = min(self.call_timestamps)
        return (oldest_call + timedelta(minutes=1)) - datetime.now()


# Cache interface
class DataCache(ABC):
    """Abstract interface for data caching"""

    @abstractmethod
    def get(self, key: str) -> Optional[any]:
        """Get cached data"""
        pass

    @abstractmethod
    def set(self, key: str, value: any, ttl_seconds: int = 300) -> None:
        """Cache data with TTL"""
        pass

    @abstractmethod
    def invalidate(self, key: str) -> None:
        """Invalidate cached data"""
        pass

    @abstractmethod
    def clear_all(self) -> None:
        """Clear all cached data"""
        pass
