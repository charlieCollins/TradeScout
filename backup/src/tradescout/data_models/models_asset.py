"""
Asset Domain Models for TradeScout

Models representing individual financial assets and their associated data.
These models are used by the AssetDataInterface operations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from .models_market import Market, MarketStatus


# ==================== ENUMS ====================


class AssetType(Enum):
    """Types of financial assets"""

    COMMON_STOCK = "common_stock"
    PREFERRED_STOCK = "preferred_stock"
    ETF = "etf"
    MUTUAL_FUND = "mutual_fund"
    OPTION = "option"


# ==================== DATACLASSES ====================


@dataclass
class Asset:
    """Core financial asset/instrument"""

    symbol: str  # Primary identifier (e.g., "AAPL", "SPY")
    name: str  # Full name (e.g., "Apple Inc.")
    asset_type: AssetType
    market: Market  # Which market/exchange it trades on

    # Asset characteristics
    currency: str  # Trading currency
    isin: Optional[str] = None  # International Securities ID
    cusip: Optional[str] = None  # US securities ID

    # Trading characteristics
    is_active: bool = True
    min_order_size: Decimal = Decimal("1")
    tick_size: Optional[Decimal] = None

    def __post_init__(self):
        """Validate and set defaults"""
        if not self.tick_size:
            self.tick_size = self.market.min_tick_size
        if not self.currency:
            self.currency = self.market.currency


@dataclass
class PriceData:
    """Price and volume data for an asset at a specific time"""

    asset: Asset
    timestamp: datetime
    volume: int

    # Current live data
    current_price: Optional[Decimal] = None  # Real-time current price

    # Complete OHLC data (for bar/candlestick data)
    open_price: Optional[Decimal] = None
    high_price: Optional[Decimal] = None
    low_price: Optional[Decimal] = None
    close_price: Optional[Decimal] = None

    # Reference data for gap analysis
    prev_session_close_price: Optional[Decimal] = None
    average_volume: Optional[int] = None

    # Market context
    session_type: MarketStatus = MarketStatus.OPEN

    # Calculated fields
    price_change: Optional[Decimal] = field(init=False, default=None)
    price_change_percent: Optional[Decimal] = field(init=False, default=None)
    volume_ratio: Optional[Decimal] = field(init=False, default=None)

    def __post_init__(self):
        """Calculate derived fields"""
        if (
            self.prev_session_close_price
            and self.prev_session_close_price > 0
            and self.current_price
        ):
            self.price_change = self.current_price - self.prev_session_close_price
            self.price_change_percent = (
                self.price_change / self.prev_session_close_price
            ) * 100

        if self.average_volume and self.average_volume > 0:
            self.volume_ratio = Decimal(self.volume) / Decimal(self.average_volume)
