"""
Market Domain Models for TradeScout

Models representing market-wide data and analysis.
These models are used by the MarketDataInterface operations.
"""

from dataclasses import dataclass, field
from datetime import datetime, time
from decimal import Decimal
from enum import Enum
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .models_asset import Asset


# ==================== ENUMS ====================


class MarketType(Enum):
    """Types of financial markets"""

    STOCK = "stock"
    OPTIONS = "options"
    FUTURES = "futures"
    FOREX = "forex"
    CRYPTO = "crypto"


class MarketStatus(Enum):
    """Current market session status"""

    CLOSED = "closed"
    PRE_MARKET = "pre_market"
    OPEN = "open"
    AFTER_HOURS = "after_hours"


# ==================== DATACLASSES ====================


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


@dataclass(frozen=True)
class MarketSegment:
    """Market segments/sectors for classification"""

    id: str  # e.g., "technology", "healthcare", "sp500"
    name: str  # e.g., "Technology", "S&P 500"
    description: str
    segment_type: str  # "sector", "industry", "index", "size", "style"
    parent_segment: Optional["MarketSegment"] = None


@dataclass
class MarketMover:
    """Individual stock that's a significant market mover"""

    asset: "Asset"
    current_price: Decimal
    price_change: Decimal
    price_change_percent: Decimal
    volume: int
    rank: int = 0  # 1 = biggest gainer/loser
    market_cap: Optional[Decimal] = None
    timestamp: Optional[datetime] = None  # Minute bar timestamp

    # Extended session data (if applicable)
    session_type: MarketStatus = MarketStatus.OPEN
