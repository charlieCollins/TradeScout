"""
Market Movers Provider - Phase 1 Implementation

Implements market gainers/losers functionality with:
- Primary: Alpha Vantage TOP_GAINERS_LOSERS (single API call)
- Fallback: YFinance S&P 500 processing (unlimited calls)
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional
from decimal import Decimal

from ..data_sources.smart_coordinator import SmartCoordinator
from ..data_models.domain_models_core import Asset, AssetType
from ..data_models.factories import MarketFactory
from .interfaces import (
    MarketWideDataProvider, 
    MarketMover, 
    MarketMoversReport, 
    SectorType, 
    SectorMetrics,
    IndexType,
    IndexData
)
from .providers.alpha_vantage_market import AlphaVantageMarketProvider

logger = logging.getLogger(__name__)


class MarketMoversProvider(MarketWideDataProvider):
    """
    Market movers provider implementing Phase 1 functionality
    
    Features:
    - Alpha Vantage TOP_GAINERS_LOSERS as primary source
    - YFinance S&P 500 processing as fallback
    - Aggressive 1-hour caching for rate limit protection
    - End-of-day analysis focus
    """
    
    def __init__(self, alpha_vantage_api_key: Optional[str] = None):
        """
        Initialize market movers provider
        
        Args:
            alpha_vantage_api_key: Alpha Vantage API key (from env if None)
        """
        # Initialize Alpha Vantage provider for market movers
        try:
            self.alpha_vantage = AlphaVantageMarketProvider(alpha_vantage_api_key)
            self.has_alpha_vantage = True
            logger.info("Alpha Vantage market provider initialized successfully")
        except Exception as e:
            logger.warning(f"Alpha Vantage initialization failed: {e}")
            self.alpha_vantage = None
            self.has_alpha_vantage = False
        
        # Initialize smart coordinator for fallback individual asset access
        self.smart_coordinator = SmartCoordinator()
        self.market_factory = MarketFactory()
        
        # S&P 500 symbols for fallback processing (subset for now)
        self.sp500_symbols = [
            "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "META", "BRK.B",
            "UNH", "JNJ", "XOM", "JPM", "V", "PG", "MA", "HD", "CVX", "ABBV",
            "PFE", "KO", "AVGO", "PEP", "TMO", "COST", "WMT", "DIS", "MRK", "ABT",
            "VZ", "ACN", "NFLX", "ADBE", "DHR", "BMY", "LIN", "NKE", "PM", "TXN"
        ]
    
    def get_market_gainers(self, limit: int = 20, force_refresh: bool = False) -> List[MarketMover]:
        """Get top market gainers"""
        # Try Alpha Vantage first
        if self.has_alpha_vantage:
            try:
                gainers = self.alpha_vantage.get_market_gainers(limit, force_refresh)
                if gainers:
                    logger.info(f"Retrieved {len(gainers)} gainers from Alpha Vantage")
                    return gainers
            except Exception as e:
                logger.warning(f"Alpha Vantage gainers failed: {e}")
        
        # Fallback to YFinance processing
        logger.info("Using YFinance fallback for market gainers")
        return self._get_movers_via_yfinance("gainers", limit)
    
    def get_market_losers(self, limit: int = 20, force_refresh: bool = False) -> List[MarketMover]:
        """Get top market losers"""
        # Try Alpha Vantage first
        if self.has_alpha_vantage:
            try:
                losers = self.alpha_vantage.get_market_losers(limit, force_refresh)
                if losers:
                    logger.info(f"Retrieved {len(losers)} losers from Alpha Vantage")
                    return losers
            except Exception as e:
                logger.warning(f"Alpha Vantage losers failed: {e}")
        
        # Fallback to YFinance processing
        logger.info("Using YFinance fallback for market losers")
        return self._get_movers_via_yfinance("losers", limit)
    
    def get_most_active(self, limit: int = 20, force_refresh: bool = False) -> List[MarketMover]:
        """Get most active stocks by volume"""
        # Try Alpha Vantage first
        if self.has_alpha_vantage:
            try:
                most_active = self.alpha_vantage.get_most_active(limit, force_refresh)
                if most_active:
                    logger.info(f"Retrieved {len(most_active)} most active from Alpha Vantage")
                    return most_active
            except Exception as e:
                logger.warning(f"Alpha Vantage most active failed: {e}")
        
        # Fallback to YFinance processing
        logger.info("Using YFinance fallback for most active")
        return self._get_movers_via_yfinance("most_active", limit)
    
    def get_market_movers_report(self, limit: int = 20, force_refresh: bool = False) -> MarketMoversReport:
        """Get comprehensive market movers report"""
        # Try Alpha Vantage bulk report first
        if self.has_alpha_vantage:
            try:
                report = self.alpha_vantage.get_market_movers_report(limit, force_refresh)
                if report:
                    logger.info("Retrieved complete market movers report from Alpha Vantage")
                    return report
            except Exception as e:
                logger.warning(f"Alpha Vantage report failed: {e}")
        
        # Fallback to individual YFinance processing
        logger.info("Using YFinance fallback for complete market movers report")
        gainers = self._get_movers_via_yfinance("gainers", limit)
        losers = self._get_movers_via_yfinance("losers", limit)
        most_active = self._get_movers_via_yfinance("most_active", limit)
        
        return MarketMoversReport(
            gainers=gainers,
            losers=losers,
            most_active=most_active,
            timestamp=datetime.now(),
            market_status=self._get_current_market_status()
        )
    
    def _get_movers_via_yfinance(self, mover_type: str, limit: int) -> List[MarketMover]:
        """
        Get market movers using YFinance individual asset processing
        
        Args:
            mover_type: 'gainers', 'losers', or 'most_active'
            limit: Maximum number of movers to return
            
        Returns:
            List of market movers from YFinance data
        """
        movers = []
        nasdaq = self.market_factory.create_nasdaq_market()
        
        # Process S&P 500 symbols to find movers
        for symbol in self.sp500_symbols[:50]:  # Limit to prevent excessive API calls
            try:
                asset = Asset(
                    symbol=symbol,
                    name=f"{symbol} Inc.",  # Placeholder name
                    asset_type=AssetType.COMMON_STOCK,
                    market=nasdaq,
                    currency="USD"
                )
                
                # Get current quote using symbol string
                quote = self.smart_coordinator.get_current_quote(symbol)
                if not quote:
                    continue
                
                # Create MarketMover
                market_mover = MarketMover(
                    asset=asset,
                    current_price=quote.price_data.price,
                    price_change=quote.price_change,
                    price_change_percent=quote.price_change_percent or Decimal("0"),
                    volume=quote.price_data.volume,
                    market_cap=None,  # Not available in basic quote
                    rank=0  # Will be set after sorting
                )
                
                movers.append(market_mover)
                
            except Exception as e:
                logger.debug(f"Error processing {symbol}: {e}")
                continue
        
        # Sort based on mover type
        if mover_type == "gainers":
            movers.sort(key=lambda m: m.price_change_percent, reverse=True)
        elif mover_type == "losers":
            movers.sort(key=lambda m: m.price_change_percent)
        elif mover_type == "most_active":
            movers.sort(key=lambda m: m.volume, reverse=True)
        
        # Set ranks and limit results
        result_movers = movers[:limit]
        for i, mover in enumerate(result_movers):
            mover.rank = i + 1
        
        logger.info(f"YFinance fallback found {len(result_movers)} {mover_type}")
        return result_movers
    
    def _get_current_market_status(self):
        """Get current market status (simplified implementation)"""
        from ..data_models.domain_models_core import MarketStatus
        
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
    
    # Phase 1: Stub implementations for sector and index methods
    def get_sector_performance(self, force_refresh: bool = False) -> Dict[SectorType, SectorMetrics]:
        """Phase 2 implementation - return empty dict for now"""
        logger.info("Sector performance analysis not implemented in Phase 1")
        return {}
    
    def get_sector_leaders(self, sector: SectorType, limit: int = 10) -> List:
        """Phase 2 implementation - return empty list for now"""
        logger.info("Sector leaders analysis not implemented in Phase 1")
        return []
    
    def get_major_indices(self, force_refresh: bool = False) -> Dict[IndexType, IndexData]:
        """Phase 3 implementation - return empty dict for now"""
        logger.info("Index tracking not implemented in Phase 1")
        return {}
    
    def get_index_performance(self, index: IndexType) -> Optional[IndexData]:
        """Phase 3 implementation - return None for now"""
        logger.info("Index performance not implemented in Phase 1")
        return None


# Convenience function for creating provider
def create_market_movers_provider(alpha_vantage_api_key: Optional[str] = None) -> MarketMoversProvider:
    """
    Create market movers provider
    
    Args:
        alpha_vantage_api_key: Alpha Vantage API key (uses environment variable if None)
        
    Returns:
        Configured MarketMoversProvider
    """
    return MarketMoversProvider(alpha_vantage_api_key)


if __name__ == "__main__":
    # Simple test of the market movers provider
    import os
    
    print("🧪 Testing Market Movers Provider...")
    
    provider = create_market_movers_provider()
    
    print("\\n📈 Testing Market Gainers:")
    gainers = provider.get_market_gainers(limit=5)
    for gainer in gainers:
        print(f"  {gainer.asset.symbol}: {gainer.price_change_percent:.2f}% (Rank: {gainer.rank})")
    
    print("\\n🔴 Testing Market Losers:")
    losers = provider.get_market_losers(limit=5)  
    for loser in losers:
        print(f"  {loser.asset.symbol}: {loser.price_change_percent:.2f}% (Rank: {loser.rank})")
    
    print("\\n📊 Testing Complete Report:")
    report = provider.get_market_movers_report(limit=3)
    print(f"Report generated at: {report.timestamp}")
    print(f"Market status: {report.market_status}")
    print(f"Gainers: {len(report.gainers)}, Losers: {len(report.losers)}, Most Active: {len(report.most_active)}")
    
    print("\\n✅ Market Movers Provider test completed!")