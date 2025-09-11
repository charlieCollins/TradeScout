"""
Market Domain Models for TradeScout

Models representing market-wide data and analysis.
These models are used by the MarketDataInterface operations.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from .models_asset import Asset
from .models_base import MarketStatus


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
    # ETF Proxies for indices
    SPY = "SPDR S&P 500 ETF"
    QQQ = "Invesco QQQ"
    IWM = "iShares Russell 2000 ETF"
    DIA = "SPDR Dow Jones ETF"


@dataclass
class MarketMover:
    """Individual stock that's a significant market mover"""
    
    asset: Asset
    current_price: Decimal
    price_change: Decimal
    price_change_percent: Decimal
    volume: int
    rank: int = 0  # 1 = biggest gainer/loser
    market_cap: Optional[Decimal] = None
    
    # Extended session data (if applicable)
    session_type: MarketStatus = MarketStatus.OPEN
    
    @property
    def is_significant_move(self) -> bool:
        """Check if price movement is significant (>5%)"""
        return abs(self.price_change_percent) > 5.0


@dataclass
class MarketSnapshot:
    """Complete market snapshot at a point in time"""
    
    timestamp: datetime
    market_status: MarketStatus
    
    # Market movers
    top_gainers: List[MarketMover]
    top_losers: List[MarketMover]
    most_active: List[MarketMover]
    
    # Index performance
    index_performance: dict[IndexType, "IndexData"]
    
    # Sector performance
    sector_performance: dict[SectorType, "SectorMetrics"]
    
    # Market breadth
    advances: int = 0
    declines: int = 0
    unchanged: int = 0
    new_highs: int = 0
    new_lows: int = 0
    
    # Volume metrics
    total_volume: int = 0
    average_volume: int = 0
    
    @property
    def advance_decline_ratio(self) -> Optional[Decimal]:
        """Calculate advance/decline ratio"""
        if self.declines > 0:
            return Decimal(self.advances) / Decimal(self.declines)
        return None
    
    @property
    def market_breadth_score(self) -> str:
        """Assess overall market breadth"""
        if self.advance_decline_ratio:
            if self.advance_decline_ratio > 2:
                return "very_bullish"
            elif self.advance_decline_ratio > 1.5:
                return "bullish"
            elif self.advance_decline_ratio > 0.66:
                return "neutral"
            elif self.advance_decline_ratio > 0.5:
                return "bearish"
            else:
                return "very_bearish"
        return "unknown"


@dataclass
class SectorMetrics:
    """Performance metrics for a market sector"""
    
    sector: SectorType
    avg_price_change_percent: Decimal
    total_volume: int
    advancing_stocks: int
    declining_stocks: int
    
    # Top movers within sector
    top_gainers: List[MarketMover]
    top_losers: List[MarketMover]
    
    # Sector statistics
    total_market_cap: Optional[Decimal] = None
    constituent_count: int = 0
    
    @property
    def is_sector_strong(self) -> bool:
        """Check if sector is showing strength"""
        return (
            self.avg_price_change_percent > 1.0 and
            self.advancing_stocks > self.declining_stocks * 1.5
        )


@dataclass
class IndexData:
    """Market index performance data"""
    
    index: IndexType
    current_value: Decimal
    previous_close: Decimal
    price_change: Decimal
    price_change_percent: Decimal
    
    # Intraday data
    high: Optional[Decimal] = None
    low: Optional[Decimal] = None
    volume: Optional[int] = None  # For ETF proxies
    
    # 52-week range
    week_52_high: Optional[Decimal] = None
    week_52_low: Optional[Decimal] = None
    
    @property
    def is_at_high(self) -> bool:
        """Check if index is near 52-week high"""
        if self.week_52_high:
            return self.current_value >= self.week_52_high * Decimal("0.98")
        return False
    
    @property
    def is_at_low(self) -> bool:
        """Check if index is near 52-week low"""
        if self.week_52_low:
            return self.current_value <= self.week_52_low * Decimal("1.02")
        return False