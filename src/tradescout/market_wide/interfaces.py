"""
MarketWideDataProvider interface definitions

Core interfaces for market-wide analysis including market movers, 
sector performance, and index tracking.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional
from decimal import Decimal
from enum import Enum
from dataclasses import dataclass

from ..data_models.domain_models_core import Asset, MarketQuote, MarketStatus


class SectorType(Enum):
    """Market sectors for classification and analysis"""
    TECHNOLOGY = "Technology"
    HEALTHCARE = "Healthcare" 
    FINANCIALS = "Financials"
    ENERGY = "Energy"
    CONSUMER_DISCRETIONARY = "Consumer Discretionary"
    INDUSTRIALS = "Industrials"
    COMMUNICATION_SERVICES = "Communication Services"
    CONSUMER_STAPLES = "Consumer Staples"
    UTILITIES = "Utilities"
    REAL_ESTATE = "Real Estate"
    MATERIALS = "Materials"


class IndexType(Enum):
    """Major market indices"""
    SP500 = "S&P 500"
    NASDAQ = "NASDAQ Composite"  
    DOW = "Dow Jones"
    RUSSELL2000 = "Russell 2000"
    NASDAQ100 = "NASDAQ 100"
    SP500_ETF = "SPDR S&P 500 ETF (SPY)"
    NASDAQ_ETF = "Invesco QQQ (QQQ)"
    RUSSELL_ETF = "iShares Russell 2000 ETF (IWM)"


@dataclass
class MarketMover:
    """Individual stock that's a significant market mover"""
    asset: Asset
    current_price: Decimal
    price_change: Decimal
    price_change_percent: Decimal
    volume: int
    market_cap: Optional[int] = None
    rank: int = 0  # 1 = biggest gainer/loser


@dataclass
class MarketMoversReport:
    """Complete market movers report"""
    gainers: List[MarketMover]
    losers: List[MarketMover] 
    most_active: List[MarketMover]
    timestamp: datetime
    market_status: MarketStatus


@dataclass
class SectorMetrics:
    """Performance metrics for a market sector"""
    sector: SectorType
    total_market_cap: int
    avg_price_change_percent: Decimal
    top_performers: List[Asset]
    worst_performers: List[Asset]
    volume_leaders: List[Asset]
    constituent_count: int
    timestamp: datetime


@dataclass
class IndexData:
    """Market index performance data"""
    index: IndexType
    current_value: Decimal
    price_change: Decimal
    price_change_percent: Decimal
    volume: Optional[int] = None  # For ETF proxies
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    timestamp: Optional[datetime] = None


class MarketWideDataProvider(ABC):
    """
    Abstract interface for market-wide data analysis
    
    Provides market-wide capabilities beyond individual asset tracking:
    - Market gainers/losers identification  
    - Sector performance analysis
    - Market indices tracking
    
    Designed for end-of-day analysis and next-day trading preparation.
    """
    
    @abstractmethod
    def get_market_gainers(self, limit: int = 20, force_refresh: bool = False) -> List[MarketMover]:
        """
        Get top gaining stocks in the market
        
        Args:
            limit: Maximum number of gainers to return
            force_refresh: Bypass cache and fetch fresh data
            
        Returns:
            List of top gaining stocks with performance data
        """
        pass
    
    @abstractmethod
    def get_market_losers(self, limit: int = 20, force_refresh: bool = False) -> List[MarketMover]:
        """
        Get top losing stocks in the market
        
        Args:
            limit: Maximum number of losers to return
            force_refresh: Bypass cache and fetch fresh data
            
        Returns:
            List of top losing stocks with performance data
        """
        pass
    
    @abstractmethod  
    def get_most_active(self, limit: int = 20, force_refresh: bool = False) -> List[MarketMover]:
        """
        Get most active stocks by volume
        
        Args:
            limit: Maximum number of active stocks to return
            force_refresh: Bypass cache and fetch fresh data
            
        Returns:
            List of most active stocks by trading volume
        """
        pass
    
    @abstractmethod
    def get_market_movers_report(self, limit: int = 20, force_refresh: bool = False) -> MarketMoversReport:
        """
        Get comprehensive market movers report
        
        Args:
            limit: Maximum number of movers in each category
            force_refresh: Bypass cache and fetch fresh data
            
        Returns:
            Complete report with gainers, losers, and most active
        """
        pass
    
    @abstractmethod
    def get_sector_performance(self, force_refresh: bool = False) -> Dict[SectorType, SectorMetrics]:
        """
        Get performance metrics for all market sectors
        
        Args:
            force_refresh: Bypass cache and fetch fresh data
            
        Returns:
            Dictionary mapping sectors to their performance metrics
        """
        pass
    
    @abstractmethod
    def get_sector_leaders(self, sector: SectorType, limit: int = 10) -> List[MarketQuote]:
        """
        Get top performing stocks in a specific sector
        
        Args:
            sector: Target sector for analysis
            limit: Maximum number of leaders to return
            
        Returns:
            List of top performing stocks in the sector
        """
        pass
    
    @abstractmethod
    def get_major_indices(self, force_refresh: bool = False) -> Dict[IndexType, IndexData]:
        """
        Get current data for major market indices
        
        Args:
            force_refresh: Bypass cache and fetch fresh data
            
        Returns:
            Dictionary mapping indices to their current data
        """
        pass
    
    @abstractmethod
    def get_index_performance(self, index: IndexType) -> Optional[IndexData]:
        """
        Get detailed performance data for specific index
        
        Args:
            index: Target index for analysis
            
        Returns:
            Detailed index performance data or None if unavailable
        """
        pass