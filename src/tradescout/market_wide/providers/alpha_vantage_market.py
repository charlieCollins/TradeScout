"""
Alpha Vantage Market Provider - Market-wide data using Alpha Vantage API

Implements market gainers/losers functionality using Alpha Vantage's
TOP_GAINERS_LOSERS endpoint for efficient market-wide analysis.
"""

import logging
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any
from decimal import Decimal

from ...data_models.domain_models_core import Asset, AssetType, MarketStatus
from ...data_models.factories import MarketFactory
from ...caches.api_cache import cached_api_call, CachePolicy
from ..interfaces import MarketMover, MarketMoversReport

logger = logging.getLogger(__name__)


class AlphaVantageMarketProvider:
    """
    Alpha Vantage provider for market-wide data
    
    Features:
    - Single API call for gainers, losers, and most active
    - 25 calls/day free tier - aggressive 1-hour caching
    - Perfect for end-of-day market analysis
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Alpha Vantage market provider
        
        Args:
            api_key: Alpha Vantage API key (get from environment if None)
        """
        import os
        self.api_key = api_key or os.getenv("ALPHA_VANTAGE_API_KEY")
        if not self.api_key:
            raise ValueError("Alpha Vantage API key required. Set ALPHA_VANTAGE_API_KEY environment variable.")
        
        self.base_url = "https://www.alphavantage.co/query"
        self.provider_name = "alpha_vantage"
        
        # Create market factory for asset creation
        self.market_factory = MarketFactory()
    
    def get_market_movers_report(self, limit: int = 20, force_refresh: bool = False) -> Optional[MarketMoversReport]:
        """
        Get complete market movers report using TOP_GAINERS_LOSERS
        
        Args:
            limit: Maximum number of movers in each category
            force_refresh: Bypass cache and fetch fresh data
            
        Returns:
            Complete market movers report or None if API fails
        """
        try:
            def fetch_market_movers() -> Optional[Dict[str, Any]]:
                """Fetch market movers from Alpha Vantage API"""
                params = {
                    "function": "TOP_GAINERS_LOSERS",
                    "apikey": self.api_key
                }
                
                response = requests.get(self.base_url, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                # Check for API errors
                if "Error Message" in data:
                    logger.error(f"Alpha Vantage API error: {data['Error Message']}")
                    return None
                
                if "Note" in data:
                    logger.warning(f"Alpha Vantage API limit: {data['Note']}")
                    return None
                
                # Validate expected structure
                if not all(key in data for key in ["top_gainers", "top_losers", "most_actively_traded"]):
                    logger.error(f"Unexpected API response structure: {list(data.keys())}")
                    return None
                
                return data
            
            # Use aggressive caching (1 hour) to protect API quota
            raw_data = cached_api_call(
                provider=self.provider_name,
                endpoint="top_gainers_losers",
                params={"limit": limit},
                api_function=fetch_market_movers,
                policy=CachePolicy.INTRADAY,
                force_refresh=force_refresh,
            )
            
            if not raw_data:
                logger.error("Failed to fetch market movers from Alpha Vantage")
                return None
            
            # Process the data into our format
            gainers = self._process_movers_list(raw_data.get("top_gainers", []), limit)
            losers = self._process_movers_list(raw_data.get("top_losers", []), limit)
            most_active = self._process_movers_list(raw_data.get("most_actively_traded", []), limit)
            
            return MarketMoversReport(
                gainers=gainers,
                losers=losers,
                most_active=most_active,
                timestamp=datetime.now(),
                market_status=self._get_current_market_status()
            )
            
        except Exception as e:
            logger.error(f"Error getting market movers report: {e}")
            return None
    
    def get_market_gainers(self, limit: int = 20, force_refresh: bool = False) -> List[MarketMover]:
        """Get market gainers from complete report"""
        report = self.get_market_movers_report(limit, force_refresh)
        return report.gainers if report else []
    
    def get_market_losers(self, limit: int = 20, force_refresh: bool = False) -> List[MarketMover]:
        """Get market losers from complete report"""
        report = self.get_market_movers_report(limit, force_refresh)
        return report.losers if report else []
    
    def get_most_active(self, limit: int = 20, force_refresh: bool = False) -> List[MarketMover]:
        """Get most active stocks from complete report"""
        report = self.get_market_movers_report(limit, force_refresh)
        return report.most_active if report else []
    
    def _process_movers_list(self, raw_movers: List[Dict], limit: int) -> List[MarketMover]:
        """
        Convert Alpha Vantage raw movers data to MarketMover objects
        
        Args:
            raw_movers: Raw API data for movers
            limit: Maximum number of movers to process
            
        Returns:
            List of processed MarketMover objects
        """
        processed_movers = []
        
        for i, mover_data in enumerate(raw_movers[:limit]):
            try:
                # Create asset (assume NASDAQ for now - could be enhanced)
                nasdaq = self.market_factory.create_nasdaq_market()
                asset = Asset(
                    symbol=mover_data.get("ticker", ""),
                    name=mover_data.get("ticker", ""),  # Alpha Vantage doesn't provide company name
                    asset_type=AssetType.COMMON_STOCK,
                    market=nasdaq,
                    currency="USD"
                )
                
                # Parse numeric values safely
                current_price = self._safe_decimal(mover_data.get("price", "0"))
                change_amount = self._safe_decimal(mover_data.get("change_amount", "0"))
                change_percent = self._safe_decimal(mover_data.get("change_percentage", "0%").rstrip("%"))
                volume = self._safe_int(mover_data.get("volume", "0"))
                
                market_mover = MarketMover(
                    asset=asset,
                    current_price=current_price,
                    price_change=change_amount,
                    price_change_percent=change_percent,
                    volume=volume,
                    rank=i + 1
                )
                
                processed_movers.append(market_mover)
                
            except Exception as e:
                logger.warning(f"Error processing mover {mover_data.get('ticker', 'unknown')}: {e}")
                continue
        
        return processed_movers
    
    def _safe_decimal(self, value: str) -> Decimal:
        """Safely convert string to Decimal"""
        try:
            # Remove any non-numeric characters except decimal point and minus
            import re
            clean_value = re.sub(r"[^\d.-]", "", str(value))
            return Decimal(clean_value) if clean_value else Decimal("0")
        except (ValueError, TypeError, Exception) as e:
            logger.warning(f"Error converting '{value}' to Decimal: {e}")
            return Decimal("0")
    
    def _safe_int(self, value: str) -> int:
        """Safely convert string to int"""
        try:
            # Remove any non-numeric characters
            import re
            clean_value = re.sub(r"[^\d]", "", str(value))
            return int(clean_value) if clean_value else 0
        except (ValueError, TypeError, Exception) as e:
            logger.warning(f"Error converting '{value}' to int: {e}")
            return 0
    
    def _get_current_market_status(self) -> MarketStatus:
        """Determine current market status (simplified)"""
        now = datetime.now()
        hour = now.hour
        
        # Simplified market hours (Eastern Time approximation)
        if 4 <= hour < 9.5:
            return MarketStatus.PRE_MARKET
        elif 9.5 <= hour < 16:
            return MarketStatus.OPEN
        elif 16 <= hour < 20:
            return MarketStatus.AFTER_HOURS
        else:
            return MarketStatus.CLOSED
    
    @property
    def rate_limit_per_day(self) -> int:
        """Return daily rate limit"""
        return 25  # Free tier limit
    
    @property
    def supports_market_movers(self) -> bool:
        """Return whether provider supports market movers"""
        return True


# Convenience function for creating provider
def create_alpha_vantage_market_provider(api_key: Optional[str] = None) -> AlphaVantageMarketProvider:
    """
    Create Alpha Vantage market provider
    
    Args:
        api_key: Alpha Vantage API key (uses environment variable if None)
        
    Returns:
        Configured AlphaVantageMarketProvider
    """
    return AlphaVantageMarketProvider(api_key)


if __name__ == "__main__":
    # Simple test of the provider
    import os
    
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        print("❌ ALPHA_VANTAGE_API_KEY environment variable not set")
        exit(1)
    
    print("🧪 Testing Alpha Vantage Market Provider...")
    
    provider = create_alpha_vantage_market_provider()
    
    print("\\n📈 Market Movers Report:")
    report = provider.get_market_movers_report(limit=5)
    if report:
        print(f"Timestamp: {report.timestamp}")
        print(f"Market Status: {report.market_status}")
        
        print("\\n🟢 Top Gainers:")
        for gainer in report.gainers[:3]:
            print(f"  {gainer.asset.symbol}: {gainer.price_change_percent:.2f}% (${gainer.current_price})")
        
        print("\\n🔴 Top Losers:")
        for loser in report.losers[:3]:
            print(f"  {loser.asset.symbol}: {loser.price_change_percent:.2f}% (${loser.current_price})")
        
        print("\\n📊 Most Active:")
        for active in report.most_active[:3]:
            print(f"  {active.asset.symbol}: {active.volume:,} shares (${active.current_price})")
    else:
        print("Failed to get market movers report")
    
    print("\\n✅ Alpha Vantage Market Provider test completed!")