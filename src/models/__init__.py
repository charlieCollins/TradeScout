"""TradeScout data models - Typed data structures for consistent API."""

from .asset import Asset, AssetType, AssetClass
from .market import Market
from .price import AssetPrice
from .provider import Provider

__all__ = [
    'Asset',
    'AssetType',
    'AssetClass',
    'Market',
    'AssetPrice',
    'Provider',
]