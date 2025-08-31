"""
Alpha Vantage Market Data Provider

Direct implementation for Alpha Vantage market movers data that works
with the SmartCoordinator by implementing the AssetDataProvider interface.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

import requests

from ..caches.api_cache import CachePolicy, cached_api_call
from ..data_models.domain_models_core import Asset, AssetType, MarketStatus
from ..data_models.factories import MarketFactory
from ..data_models.interfaces import AssetDataProvider
from ..data_models.market_wide_models import MarketMover, MarketMoversReport

logger = logging.getLogger(__name__)


class AssetDataProviderAlphaVantageMarket(AssetDataProvider):
    """
    Alpha Vantage market movers data provider
    
    Provides market movers functionality (gainers, losers, most active)
    using Alpha Vantage's TOP_GAINERS_LOSERS API endpoint.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Alpha Vantage market data provider
        
        Args:
            api_key: Alpha Vantage API key (from env if None)
        """
        super().__init__()
        import os
        
        self.api_key = api_key or os.getenv("ALPHA_VANTAGE_API_KEY")
        if not self.api_key:
            logger.error("Alpha Vantage API key required. Set ALPHA_VANTAGE_API_KEY environment variable.")
            self.available = False
            return
            
        self.base_url = "https://www.alphavantage.co/query"
        self.provider_name = "alpha_vantage_market"
        self.market_factory = MarketFactory()
        self.available = True
    
    def _fetch_market_data(self, force_refresh: bool = False) -> Optional[Dict]:
        """Fetch market movers data from Alpha Vantage"""
        def fetch_data():
            params = {"function": "TOP_GAINERS_LOSERS", "apikey": self.api_key}
            response = requests.get(self.base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            if "Error Message" in data or "Note" in data:
                logger.warning(f"Alpha Vantage API issue: {data}")
                return None
                
            if not all(key in data for key in ["top_gainers", "top_losers", "most_actively_traded"]):
                logger.error(f"Unexpected API response structure: {list(data.keys())}")
                return None
                
            return data
        
        cache_policy = CachePolicy.ONE_HOUR if not force_refresh else CachePolicy.BYPASS
        return cached_api_call(
            provider=self.provider_name,
            endpoint="top_gainers_losers", 
            params={},
            api_function=fetch_data,
            policy=cache_policy
        )
    
    def _parse_mover_data(self, raw_data: List[Dict], mover_type: str) -> List[MarketMover]:
        """Parse raw Alpha Vantage data into MarketMover objects"""
        movers = []
        nasdaq = self.market_factory.create_nasdaq_market()
        
        for i, item in enumerate(raw_data):
            try:
                asset = Asset(
                    symbol=item["ticker"],
                    name=item.get("ticker", "Unknown"),  
                    asset_type=AssetType.COMMON_STOCK,
                    market=nasdaq,
                    currency="USD"
                )
                
                mover = MarketMover(
                    asset=asset,
                    current_price=Decimal(item["price"]),
                    price_change=Decimal(item["change_amount"]),
                    price_change_percent=Decimal(item["change_percentage"].rstrip("%")),
                    volume=int(item["volume"]),
                    rank=i + 1
                )
                movers.append(mover)
            except (KeyError, ValueError, TypeError) as e:
                logger.debug(f"Error parsing {mover_type} item {i}: {e}")
                continue
                
        return movers
    
    def get_market_gainers(self, limit: int = 20, force_refresh: bool = False) -> List[MarketMover]:
        """Get top market gainers"""
        if not self.available:
            return []
            
        data = self._fetch_market_data(force_refresh)
        if not data:
            return []
            
        return self._parse_mover_data(data["top_gainers"][:limit], "gainers")
    
    def get_market_losers(self, limit: int = 20, force_refresh: bool = False) -> List[MarketMover]:
        """Get top market losers"""
        if not self.available:
            return []
            
        data = self._fetch_market_data(force_refresh)
        if not data:
            return []
            
        return self._parse_mover_data(data["top_losers"][:limit], "losers")
    
    def get_most_active(self, limit: int = 20, force_refresh: bool = False) -> List[MarketMover]:
        """Get most active stocks by volume"""
        if not self.available:
            return []
            
        data = self._fetch_market_data(force_refresh)
        if not data:
            return []
            
        return self._parse_mover_data(data["most_actively_traded"][:limit], "most_active")
    
    def get_market_movers_report(self, limit: int = 20, force_refresh: bool = False) -> Optional[MarketMoversReport]:
        """Get comprehensive market movers report"""
        if not self.available:
            return None
            
        data = self._fetch_market_data(force_refresh)
        if not data:
            return None
            
        gainers = self._parse_mover_data(data["top_gainers"][:limit], "gainers")
        losers = self._parse_mover_data(data["top_losers"][:limit], "losers")
        most_active = self._parse_mover_data(data["most_actively_traded"][:limit], "most_active")
        
        return MarketMoversReport(
            gainers=gainers,
            losers=losers,
            most_active=most_active,
            timestamp=datetime.now(),
            market_status=MarketStatus.OPEN  # Simplified for now
        )
    
    def get_provider_info(self) -> Dict[str, str]:
        """Get provider information"""
        return {
            "name": "Alpha Vantage Market",
            "type": "api",
            "data_types": "market_movers",
            "description": "Market gainers, losers, and most active stocks",
            "available": str(self.available),
        }