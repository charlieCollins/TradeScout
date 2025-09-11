"""
TradeScout Storage Interfaces

Abstract interfaces for data persistence that align with our current domain models.
Supports local SQLite and future cloud database implementations.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set

from ..data_models import (
    Asset,
    MarketQuote,
    PriceData,
    TradeSuggestion,
)
from ..data_models.models_asset import Fundamentals
from ..data_models.models_base import Market, MarketSegment


class DatabaseManager(ABC):
    """Abstract interface for database connection management"""

    @abstractmethod
    def get_connection(self):
        """Get database connection"""
        pass

    @abstractmethod
    def execute_migration(self, name: str, sql: str) -> None:
        """Execute a database migration"""
        pass

    @abstractmethod
    def execute_migration_file(self, file_path: str) -> None:
        """Execute migration from SQL file"""
        pass


class MarketRepository(ABC):
    """Repository interface for market/exchange data"""

    @abstractmethod
    def create_market(self, market: Market) -> Optional[str]:
        """Create a new market, return market ID"""
        pass

    @abstractmethod
    def get_market_by_id(self, market_id: str) -> Optional[Market]:
        """Get market by ID"""
        pass

    @abstractmethod
    def get_all_markets(self) -> List[Market]:
        """Get all available markets"""
        pass

    @abstractmethod
    def update_market(self, market: Market) -> bool:
        """Update market information"""
        pass


class MarketSegmentRepository(ABC):
    """Repository interface for market segments"""

    @abstractmethod
    def create_segment(self, segment: MarketSegment) -> Optional[int]:
        """Create a new market segment"""
        pass

    @abstractmethod
    def get_segment_by_id(self, segment_id: int) -> Optional[MarketSegment]:
        """Get segment by ID"""
        pass

    @abstractmethod
    def get_segments_by_type(self, segment_type: str) -> List[MarketSegment]:
        """Get segments by type (e.g., 'sector', 'cap_size')"""
        pass

    @abstractmethod
    def get_all_segments(self) -> List[MarketSegment]:
        """Get all market segments"""
        pass


class AssetRepository(ABC):
    """Repository interface for asset management"""

    @abstractmethod
    def create_asset(self, asset: Asset) -> Optional[int]:
        """Create a new asset, return asset ID"""
        pass

    @abstractmethod
    def get_asset_by_id(self, asset_id: int) -> Optional[Asset]:
        """Get asset by database ID"""
        pass

    @abstractmethod
    def get_asset_by_symbol(self, symbol: str) -> Optional[Asset]:
        """Get asset by symbol"""
        pass

    @abstractmethod
    def update_asset(self, asset: Asset) -> bool:
        """Update asset information"""
        pass

    @abstractmethod
    def deactivate_asset(self, symbol: str) -> bool:
        """Mark asset as inactive"""
        pass

    @abstractmethod
    def get_assets_by_market(self, market_id: str) -> List[Asset]:
        """Get all assets in a specific market"""
        pass

    @abstractmethod
    def get_active_assets(self) -> List[Asset]:
        """Get all active assets"""
        pass

    @abstractmethod
    def add_asset_to_segment(self, symbol: str, segment_name: str) -> bool:
        """Add asset to a market segment"""
        pass

    @abstractmethod
    def remove_asset_from_segment(self, symbol: str, segment_name: str) -> bool:
        """Remove asset from a market segment"""
        pass

    @abstractmethod
    def get_asset_segments(self, symbol: str) -> Set[MarketSegment]:
        """Get all segments an asset belongs to"""
        pass

    @abstractmethod
    def get_segment_assets(self, segment_name: str) -> List[Asset]:
        """Get all assets in a segment"""
        pass


class PriceDataRepository(ABC):
    """Repository interface for price data storage"""

    @abstractmethod
    def save_price_data(self, price_data: PriceData) -> bool:
        """Save price data point"""
        pass

    @abstractmethod
    def bulk_save_price_data(self, price_data_list: List[PriceData]) -> int:
        """Bulk save price data, return count saved"""
        pass

    @abstractmethod
    def get_latest_price(self, symbol: str) -> Optional[PriceData]:
        """Get most recent price for symbol"""
        pass

    @abstractmethod
    def get_historical_prices(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        data_source: Optional[str] = None
    ) -> List[PriceData]:
        """Get historical prices in date range"""
        pass

    @abstractmethod
    def get_prices_by_timeframe(
        self,
        symbol: str,
        hours_back: int,
        data_source: Optional[str] = None
    ) -> List[PriceData]:
        """Get prices from last N hours"""
        pass

    @abstractmethod
    def delete_old_prices(self, older_than_days: int) -> int:
        """Delete price data older than specified days"""
        pass


class MarketQuoteRepository(ABC):
    """Repository interface for current market quotes"""

    @abstractmethod
    def save_quote(self, quote: MarketQuote) -> bool:
        """Save/update current market quote"""
        pass

    @abstractmethod
    def get_current_quote(self, symbol: str) -> Optional[MarketQuote]:
        """Get current quote for symbol"""
        pass

    @abstractmethod
    def get_multiple_quotes(self, symbols: List[str]) -> Dict[str, MarketQuote]:
        """Get current quotes for multiple symbols"""
        pass

    @abstractmethod
    def bulk_update_quotes(self, quotes: List[MarketQuote]) -> int:
        """Bulk update current quotes"""
        pass

    @abstractmethod
    def get_quotes_updated_since(self, since: datetime) -> List[MarketQuote]:
        """Get quotes updated after specific time"""
        pass


class FundamentalsRepository(ABC):
    """Repository interface for fundamental data"""

    @abstractmethod
    def save_fundamentals(self, fundamentals: Fundamentals) -> bool:
        """Save fundamental data for an asset"""
        pass

    @abstractmethod
    def get_latest_fundamentals(self, symbol: str) -> Optional[Fundamentals]:
        """Get most recent fundamentals for symbol"""
        pass

    @abstractmethod
    def get_fundamentals_by_date(
        self,
        symbol: str,
        report_date: datetime
    ) -> Optional[Fundamentals]:
        """Get fundamentals for specific report date"""
        pass

    @abstractmethod
    def get_fundamentals_history(
        self,
        symbol: str,
        quarters_back: int = 4
    ) -> List[Fundamentals]:
        """Get historical fundamentals"""
        pass

    @abstractmethod
    def get_fundamentals_for_screening(
        self,
        min_market_cap: Optional[Decimal] = None,
        max_pe_ratio: Optional[Decimal] = None,
        min_roe: Optional[Decimal] = None
    ) -> List[Fundamentals]:
        """Get fundamentals matching screening criteria"""
        pass


class MarketSnapshotRepository(ABC):
    """Repository interface for bulk market snapshot data"""

    @abstractmethod
    def save_market_snapshot(
        self,
        snapshot_time: datetime,
        snapshot_data: Dict[str, Dict[str, Any]]
    ) -> int:
        """Save complete market snapshot, return count saved"""
        pass

    @abstractmethod
    def get_latest_snapshot_time(self) -> Optional[datetime]:
        """Get timestamp of most recent snapshot"""
        pass

    @abstractmethod
    def get_snapshot_data(
        self,
        snapshot_time: datetime,
        symbols: Optional[List[str]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Get snapshot data for specific time and symbols"""
        pass

    @abstractmethod
    def get_top_movers(
        self,
        snapshot_time: datetime,
        limit: int = 20,
        mover_type: str = "gainers"  # "gainers", "losers", "active"
    ) -> List[Dict[str, Any]]:
        """Get top movers from snapshot"""
        pass

    @abstractmethod
    def cleanup_old_snapshots(self, keep_days: int = 7) -> int:
        """Remove snapshots older than specified days"""
        pass


class TradeSuggestionRepository(ABC):
    """Repository interface for trade suggestions"""

    @abstractmethod
    def save_suggestion(self, suggestion: TradeSuggestion) -> bool:
        """Save a trade suggestion"""
        pass

    @abstractmethod
    def get_suggestion_by_id(self, suggestion_id: str) -> Optional[TradeSuggestion]:
        """Get suggestion by ID"""
        pass

    @abstractmethod
    def get_suggestions_by_date(
        self,
        date: datetime,
        analysis_type: Optional[str] = None
    ) -> List[TradeSuggestion]:
        """Get suggestions for specific date, optionally filtered by type"""
        pass

    @abstractmethod
    def get_active_suggestions(self) -> List[TradeSuggestion]:
        """Get all suggestions that are still valid/active"""
        pass

    @abstractmethod
    def get_suggestions_by_symbol(
        self,
        symbol: str,
        days_back: int = 30
    ) -> List[TradeSuggestion]:
        """Get recent suggestions for a symbol"""
        pass

    @abstractmethod
    def update_suggestion_status(
        self,
        suggestion_id: str,
        new_status: str
    ) -> bool:
        """Update suggestion status (executed, expired, etc.)"""
        pass

    @abstractmethod
    def get_suggestions_by_confidence(
        self,
        min_confidence: str,  # ConfidenceLevel enum value
        limit: int = 50
    ) -> List[TradeSuggestion]:
        """Get high-confidence suggestions"""
        pass


class CacheMetadataRepository(ABC):
    """Repository interface for cache metadata (TTL tracking, etc.)"""

    @abstractmethod
    def set_cache_metadata(
        self,
        cache_type: str,
        last_updated: datetime,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Set cache metadata with timestamp"""
        pass

    @abstractmethod
    def get_cache_metadata(self, cache_type: str) -> Optional[Dict[str, Any]]:
        """Get cache metadata including last_updated timestamp"""
        pass

    @abstractmethod
    def is_cache_valid(self, cache_type: str, ttl_minutes: int) -> bool:
        """Check if cache is still valid based on TTL"""
        pass

    @abstractmethod
    def cleanup_expired_metadata(self) -> int:
        """Remove expired cache metadata entries"""
        pass