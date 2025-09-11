"""
Base Domain Models for TradeScout

Core models that are shared across all interfaces.
These represent fundamental market concepts.
"""

from dataclasses import dataclass, field
from datetime import time
from decimal import Decimal
from enum import Enum
from typing import List, Optional, Set


class MarketType(Enum):
    """Types of financial markets"""
    STOCK = "stock"
    OPTIONS = "options"
    FUTURES = "futures"
    FOREX = "forex"
    CRYPTO = "crypto"
    COMMODITY = "commodity"


class MarketStatus(Enum):
    """Current market session status"""
    CLOSED = "closed"
    PRE_MARKET = "pre_market"
    OPEN = "open"
    AFTER_HOURS = "after_hours"
    HOLIDAY = "holiday"


@dataclass
class Market:
    """Represents a financial market/exchange"""
    
    id: str  # e.g., "NYSE", "NASDAQ", "CME"
    name: str  # e.g., "New York Stock Exchange"
    market_type: MarketType
    timezone: str  # e.g., "America/New_York"
    currency: str  # e.g., "USD"
    
    # Trading hours (in market timezone)
    regular_open: time  # e.g., 09:30:00
    regular_close: time  # e.g., 16:00:00
    pre_market_start: Optional[time] = None  # e.g., 04:00:00
    after_hours_end: Optional[time] = None  # e.g., 20:00:00
    
    # Market characteristics
    min_tick_size: Decimal = Decimal("0.01")
    lot_size: int = 1
    trading_days: Set[int] = field(default_factory=lambda: {0, 1, 2, 3, 4})  # Mon-Fri


@dataclass(frozen=True)
class MarketSegment:
    """Market segments/sectors for classification"""
    
    id: str  # e.g., "technology", "healthcare", "sp500"
    name: str  # e.g., "Technology", "S&P 500"
    description: str
    segment_type: str  # "sector", "industry", "index", "size", "style"
    parent_segment: Optional["MarketSegment"] = None
    
    @property
    def full_hierarchy(self) -> List[str]:
        """Get full segment hierarchy"""
        hierarchy = [self.name]
        current = self.parent_segment
        while current:
            hierarchy.insert(0, current.name)
            current = current.parent_segment
        return hierarchy