"""TradeScout data models - Typed data structures for consistent API."""

from .asset import Asset, AssetType, AssetClass
from .market import Market
from .price import AssetPrice
from .provider import Provider
from .fundamentals import AssetFundamentals
from .snapshot import TickerSnapshot, MarketSnapshot
from .stats import DatabaseStats, OperationStats
from .universe import Universe, UniverseMembership, UniverseStats

__all__ = [
    'Asset',
    'AssetType',
    'AssetClass',
    'Market',
    'AssetPrice',
    'Provider',
    'AssetFundamentals',
    'TickerSnapshot',
    'MarketSnapshot',
    'DatabaseStats',
    'OperationStats',
    'Universe',
    'UniverseMembership',
    'UniverseStats',
]