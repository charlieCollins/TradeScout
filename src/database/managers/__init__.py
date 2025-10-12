"""Database managers for TTL-based data storage and retrieval.

Database managers handle:
- Direct database read/write operations for their entity type
- TTL-based refresh logic (when to fetch fresh data)
- Metadata tracking for operation-level cache validation

Database managers do NOT make API calls - that's handled by api/provider classes.
"""

from .base_manager import BaseManager
from .ticker_snapshot_manager import TickerSnapshotManager
from .market_snapshot_manager import MarketSnapshotManager
from .asset_manager import AssetManager
from .asset_price_manager import AssetPriceManager
from .universe_manager import UniverseManager
from .provider_manager import ProviderManager
from .fundamentals_manager import FundamentalsManager
from .gap_results_manager import GapResultsManager
from .gap_performance_manager import GapPerformanceManager
from .markets_manager import MarketsManager
from .market_holidays_manager import MarketHolidaysManager
from .market_context_manager import MarketContextManager
from .data_update_metadata_manager import DataUpdateMetadataManager
from .sentiment_types_manager import SentimentTypesManager
from .sentiment_events_manager import SentimentEventsManager
from .fed_data_manager import FedDataManager

__all__ = [
    "BaseManager",
    "TickerSnapshotManager",
    "MarketSnapshotManager",
    "AssetManager",
    "AssetPriceManager",
    "UniverseManager",
    "ProviderManager",
    "FundamentalsManager",
    "GapResultsManager",
    "GapPerformanceManager",
    "MarketsManager",
    "MarketHolidaysManager",
    "MarketContextManager",
    "DataUpdateMetadataManager",
    "SentimentTypesManager",
    "SentimentEventsManager",
    "FedDataManager",
]