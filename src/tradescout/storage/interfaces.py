"""
TradeScout Storage Interfaces

Abstract interfaces for data persistence.
Supports both local SQLite and cloud database implementations
with seamless migration capability.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from decimal import Decimal

from ..data_models.domain_models_core import (
    Asset,
    MarketQuote,
    ExtendedHoursData,
    NewsItem,
    SocialSentiment,
)
from ..data_models.domain_models_analysis import (
    TechnicalIndicators,
    TradeSuggestion,
    ActualTrade,
    PerformanceMetrics,
    MarketEvent,
)


class QuoteRepository(ABC):
    """Abstract interface for storing market quotes"""

    @abstractmethod
    def save_quote(self, quote: MarketQuote) -> bool:
        """
        Save a market quote

        Args:
            quote: Market quote to save

        Returns:
            True if saved successfully
        """
        pass

    @abstractmethod
    def get_latest_quote(self, symbol: str) -> Optional[MarketQuote]:
        """
        Get the most recent quote for a symbol

        Args:
            symbol: Stock symbol

        Returns:
            Latest quote or None if not found
        """
        pass

    @abstractmethod
    def get_quotes_by_timeframe(
        self, symbol: str, start_time: datetime, end_time: datetime
    ) -> List[MarketQuote]:
        """
        Get quotes within a time range

        Args:
            symbol: Stock symbol
            start_time: Start of time range
            end_time: End of time range

        Returns:
            List of quotes in timeframe
        """
        pass

    @abstractmethod
    def get_historical_quotes(self, symbol: str, days_back: int) -> List[MarketQuote]:
        """
        Get historical quotes for analysis

        Args:
            symbol: Stock symbol
            days_back: Number of days to look back

        Returns:
            List of historical quotes
        """
        pass

    @abstractmethod
    def bulk_save_quotes(self, quotes: List[MarketQuote]) -> int:
        """
        Save multiple quotes efficiently

        Args:
            quotes: List of quotes to save

        Returns:
            Number of quotes saved
        """
        pass

    @abstractmethod
    def delete_old_quotes(self, older_than_days: int) -> int:
        """
        Delete quotes older than specified days

        Args:
            older_than_days: Delete quotes older than this

        Returns:
            Number of quotes deleted
        """
        pass


class ExtendedHoursRepository(ABC):
    """Abstract interface for storing extended hours data"""

    @abstractmethod
    def save_extended_hours_data(self, data: ExtendedHoursData) -> bool:
        """Save extended hours trading data"""
        pass

    @abstractmethod
    def get_latest_extended_hours(self, symbol: str) -> Optional[ExtendedHoursData]:
        """Get latest extended hours data for symbol"""
        pass

    @abstractmethod
    def get_pre_market_gaps(
        self, min_gap_percent: Decimal, date: Optional[datetime] = None
    ) -> List[ExtendedHoursData]:
        """
        Get stocks with significant pre-market gaps

        Args:
            min_gap_percent: Minimum gap percentage
            date: Specific date (default: today)

        Returns:
            List of stocks with gaps
        """
        pass


class NewsRepository(ABC):
    """Abstract interface for storing news data"""

    @abstractmethod
    def save_news_item(self, news: NewsItem) -> bool:
        """Save a news item"""
        pass

    @abstractmethod
    def get_news_by_symbol(self, symbol: str, hours_back: int = 24) -> List[NewsItem]:
        """Get recent news for a symbol"""
        pass

    @abstractmethod
    def get_news_by_timeframe(
        self, start_time: datetime, end_time: datetime
    ) -> List[NewsItem]:
        """Get news within time range"""
        pass

    @abstractmethod
    def search_news_by_keywords(
        self, keywords: List[str], limit: int = 50
    ) -> List[NewsItem]:
        """Search news by keywords"""
        pass

    @abstractmethod
    def bulk_save_news(self, news_items: List[NewsItem]) -> int:
        """Bulk save news items"""
        pass

    @abstractmethod
    def get_news_sentiment_summary(
        self, symbol: str, hours_back: int = 24
    ) -> Dict[str, Any]:
        """Get aggregated sentiment from news"""
        pass


class SentimentRepository(ABC):
    """Abstract interface for storing sentiment data"""

    @abstractmethod
    def save_sentiment_data(self, sentiment: SocialSentiment) -> bool:
        """Save sentiment data"""
        pass

    @abstractmethod
    def get_latest_sentiment(self, symbol: str) -> Optional[SocialSentiment]:
        """Get latest sentiment for symbol"""
        pass

    @abstractmethod
    def get_sentiment_timeline(
        self, symbol: str, start_time: datetime, end_time: datetime
    ) -> List[SocialSentiment]:
        """Get sentiment data over time"""
        pass

    @abstractmethod
    def get_trending_symbols(self, limit: int = 20) -> List[str]:
        """Get symbols with highest sentiment activity"""
        pass


class TechnicalRepository(ABC):
    """Abstract interface for storing technical indicators"""

    @abstractmethod
    def save_technical_indicators(self, indicators: TechnicalIndicators) -> bool:
        """Save technical indicators"""
        pass

    @abstractmethod
    def get_latest_indicators(
        self, symbol: str, timeframe: str
    ) -> Optional[TechnicalIndicators]:
        """Get latest technical indicators"""
        pass

    @abstractmethod
    def get_indicator_history(
        self, symbol: str, timeframe: str, days_back: int
    ) -> List[TechnicalIndicators]:
        """Get historical technical indicators"""
        pass


class SuggestionRepository(ABC):
    """Abstract interface for storing trade suggestions"""

    @abstractmethod
    def save_suggestion(self, suggestion: TradeSuggestion) -> bool:
        """Save a trade suggestion"""
        pass

    @abstractmethod
    def get_suggestion_by_id(self, suggestion_id: str) -> Optional[TradeSuggestion]:
        """Get suggestion by ID"""
        pass

    @abstractmethod
    def get_suggestions_by_date(self, date: datetime) -> List[TradeSuggestion]:
        """Get all suggestions for a specific date"""
        pass

    @abstractmethod
    def get_active_suggestions(self) -> List[TradeSuggestion]:
        """Get currently active suggestions"""
        pass

    @abstractmethod
    def update_suggestion_performance(
        self,
        suggestion_id: str,
        max_profit: Decimal,
        max_loss: Decimal,
        current_price: Decimal,
    ) -> bool:
        """Update suggestion with current performance"""
        pass

    @abstractmethod
    def get_suggestion_performance_history(
        self, days_back: int = 30
    ) -> List[TradeSuggestion]:
        """Get suggestion performance history"""
        pass

    @abstractmethod
    def get_suggestions_by_confidence(
        self, min_confidence: Decimal
    ) -> List[TradeSuggestion]:
        """Get suggestions above confidence threshold"""
        pass


class TradeRepository(ABC):
    """Abstract interface for storing actual trades"""

    @abstractmethod
    def save_trade(self, trade: ActualTrade) -> bool:
        """Save an actual trade"""
        pass

    @abstractmethod
    def get_trade_by_id(self, trade_id: str) -> Optional[ActualTrade]:
        """Get trade by ID"""
        pass

    @abstractmethod
    def get_open_trades(self) -> List[ActualTrade]:
        """Get all open trades"""
        pass

    @abstractmethod
    def get_trades_by_date_range(
        self, start_date: datetime, end_date: datetime
    ) -> List[ActualTrade]:
        """Get trades within date range"""
        pass

    @abstractmethod
    def update_trade_exit(
        self, trade_id: str, exit_price: Decimal, exit_time: datetime, exit_reason: str
    ) -> bool:
        """Update trade with exit information"""
        pass

    @abstractmethod
    def get_trade_statistics(self, days_back: int = 30) -> Dict[str, Any]:
        """Get trading statistics"""
        pass


class PerformanceRepository(ABC):
    """Abstract interface for storing performance metrics"""

    @abstractmethod
    def save_performance_metrics(self, metrics: PerformanceMetrics) -> bool:
        """Save performance metrics"""
        pass

    @abstractmethod
    def get_latest_performance(self) -> Optional[PerformanceMetrics]:
        """Get latest performance metrics"""
        pass

    @abstractmethod
    def get_performance_history(self, months_back: int = 6) -> List[PerformanceMetrics]:
        """Get performance history"""
        pass

    @abstractmethod
    def calculate_rolling_performance(self, days: int = 30) -> PerformanceMetrics:
        """Calculate rolling performance metrics"""
        pass


class EventRepository(ABC):
    """Abstract interface for storing market events"""

    @abstractmethod
    def save_event(self, event: MarketEvent) -> bool:
        """Save a market event"""
        pass

    @abstractmethod
    def get_upcoming_events(
        self, symbol: str, days_ahead: int = 7
    ) -> List[MarketEvent]:
        """Get upcoming events for symbol"""
        pass

    @abstractmethod
    def get_events_by_date(self, date: datetime) -> List[MarketEvent]:
        """Get events for specific date"""
        pass

    @abstractmethod
    def get_earnings_calendar(
        self, start_date: datetime, end_date: datetime
    ) -> List[MarketEvent]:
        """Get earnings events in date range"""
        pass


class DatabaseManager(ABC):
    """Main database manager interface"""

    @abstractmethod
    def initialize_database(self) -> bool:
        """Initialize database schema"""
        pass

    @abstractmethod
    def migrate_schema(self, target_version: str) -> bool:
        """Migrate database schema to target version"""
        pass

    @abstractmethod
    def backup_database(self, backup_path: str) -> bool:
        """Create database backup"""
        pass

    @abstractmethod
    def restore_database(self, backup_path: str) -> bool:
        """Restore database from backup"""
        pass

    @abstractmethod
    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        pass

    @abstractmethod
    def cleanup_old_data(self, retention_days: int = 90) -> int:
        """Clean up old data beyond retention period"""
        pass

    @abstractmethod
    def execute_raw_query(
        self, query: str, params: Optional[List] = None
    ) -> List[Dict]:
        """Execute raw SQL query"""
        pass

    # Repository access methods
    @property
    @abstractmethod
    def quotes(self) -> QuoteRepository:
        """Get quotes repository"""
        pass

    @property
    @abstractmethod
    def extended_hours(self) -> ExtendedHoursRepository:
        """Get extended hours repository"""
        pass

    @property
    @abstractmethod
    def news(self) -> NewsRepository:
        """Get news repository"""
        pass

    @property
    @abstractmethod
    def sentiment(self) -> SentimentRepository:
        """Get sentiment repository"""
        pass

    @property
    @abstractmethod
    def technical(self) -> TechnicalRepository:
        """Get technical repository"""
        pass

    @property
    @abstractmethod
    def suggestions(self) -> SuggestionRepository:
        """Get suggestions repository"""
        pass

    @property
    @abstractmethod
    def trades(self) -> TradeRepository:
        """Get trades repository"""
        pass

    @property
    @abstractmethod
    def performance(self) -> PerformanceRepository:
        """Get performance repository"""
        pass

    @property
    @abstractmethod
    def events(self) -> EventRepository:
        """Get events repository"""
        pass


class CacheManager(ABC):
    """Abstract interface for data caching"""

    @abstractmethod
    def get_cached_quote(self, symbol: str) -> Optional[MarketQuote]:
        """Get cached quote if available and fresh"""
        pass

    @abstractmethod
    def cache_quote(self, quote: MarketQuote, ttl_seconds: int = 60) -> None:
        """Cache a quote with TTL"""
        pass

    @abstractmethod
    def invalidate_symbol_cache(self, symbol: str) -> None:
        """Invalidate all cached data for a symbol"""
        pass

    @abstractmethod
    def clear_expired_cache(self) -> int:
        """Clear expired cache entries"""
        pass

    @abstractmethod
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache hit/miss statistics"""
        pass
