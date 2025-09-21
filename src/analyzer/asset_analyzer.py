"""Asset analyzer for analyzing asset data."""

import logging
from typing import Optional, Tuple
from models.asset import Asset
from models.market import Market
from models.price import AssetPrice
from provider.data_provider import PolygonDataProvider

logger = logging.getLogger(__name__)


class AssetAnalyzer:
    """Analyzes asset data using data providers."""

    def __init__(self, data_provider: PolygonDataProvider):
        """Initialize with data provider."""
        self.data_provider = data_provider

    def get_asset_data(self, symbol: str) -> Optional[Tuple[Asset, Market]]:
        """Get asset and market data for a symbol."""
        return self.data_provider.get_asset_data(symbol)

    def get_asset_price_data(self, asset_id: int) -> Optional[AssetPrice]:
        """Get price data for an asset."""
        return self.data_provider.get_asset_price_data(asset_id)