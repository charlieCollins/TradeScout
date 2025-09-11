"""
Asset Domain Models for TradeScout

Models representing individual financial assets and their associated data.
These models are used by the AssetDataInterface operations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional, Set

from .models_base import Market, MarketSegment, MarketStatus


class AssetType(Enum):
    """Types of financial assets"""
    COMMON_STOCK = "common_stock"
    PREFERRED_STOCK = "preferred_stock"
    ETF = "etf"
    MUTUAL_FUND = "mutual_fund"
    INDEX = "index"
    OPTION = "option"
    FUTURE = "future"
    CURRENCY_PAIR = "currency_pair"
    CRYPTOCURRENCY = "cryptocurrency"
    COMMODITY = "commodity"


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
    
    # Classification
    segments: Set[MarketSegment] = field(default_factory=set)
    
    # Trading characteristics
    is_active: bool = True
    min_order_size: Decimal = Decimal("1")
    tick_size: Optional[Decimal] = None
    
    # Corporate data (for stocks)
    shares_outstanding: Optional[int] = None
    market_cap: Optional[Decimal] = None
    
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
    price: Decimal  # Current/close price
    volume: int
    
    # OHLC data (for bar/candlestick data)
    open_price: Optional[Decimal] = None
    high_price: Optional[Decimal] = None
    low_price: Optional[Decimal] = None
    
    # Market context
    session_type: MarketStatus = MarketStatus.OPEN
    
    # Bid/Ask spread
    bid_price: Optional[Decimal] = None
    ask_price: Optional[Decimal] = None
    bid_size: Optional[int] = None
    ask_size: Optional[int] = None
    
    @property
    def is_complete_bar(self) -> bool:
        """Check if this is complete OHLC data"""
        return all([
            self.open_price is not None,
            self.high_price is not None,
            self.low_price is not None,
            self.price is not None,
        ])
    
    @property
    def spread(self) -> Optional[Decimal]:
        """Calculate bid-ask spread"""
        if self.bid_price and self.ask_price:
            return self.ask_price - self.bid_price
        return None


@dataclass
class MarketQuote:
    """Current market quote for an asset"""
    
    asset: Asset
    price_data: PriceData
    
    # Reference data for calculations
    previous_close: Optional[Decimal] = None
    average_volume: Optional[int] = None
    
    # Calculated fields
    price_change: Optional[Decimal] = field(init=False, default=None)
    price_change_percent: Optional[Decimal] = field(init=False, default=None)
    volume_ratio: Optional[Decimal] = field(init=False, default=None)
    
    def __post_init__(self):
        """Calculate derived fields"""
        if self.previous_close and self.previous_close > 0:
            self.price_change = self.price_data.price - self.previous_close
            self.price_change_percent = (self.price_change / self.previous_close) * 100
        
        if self.average_volume and self.average_volume > 0:
            self.volume_ratio = Decimal(self.price_data.volume) / Decimal(self.average_volume)


@dataclass
class Fundamentals:
    """Fundamental data for an asset"""
    
    asset: Asset
    
    # Company Information
    sector: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None
    employees: Optional[int] = None
    
    # Key Metrics
    market_cap: Optional[Decimal] = None
    enterprise_value: Optional[Decimal] = None
    shares_outstanding: Optional[int] = None
    float_shares: Optional[int] = None
    
    # Valuation Ratios
    price_to_earnings: Optional[Decimal] = None
    price_to_book: Optional[Decimal] = None
    price_to_sales: Optional[Decimal] = None
    peg_ratio: Optional[Decimal] = None
    
    # Profitability
    revenue_ttm: Optional[Decimal] = None
    net_income_ttm: Optional[Decimal] = None
    ebitda_ttm: Optional[Decimal] = None
    free_cash_flow_ttm: Optional[Decimal] = None
    
    # Margins
    gross_margin: Optional[Decimal] = None
    operating_margin: Optional[Decimal] = None
    net_margin: Optional[Decimal] = None
    
    # Returns
    return_on_equity: Optional[Decimal] = None
    return_on_assets: Optional[Decimal] = None
    
    # Financial Health
    current_ratio: Optional[Decimal] = None
    debt_to_equity: Optional[Decimal] = None
    
    # Dividends
    dividend_yield: Optional[Decimal] = None
    dividend_per_share: Optional[Decimal] = None
    
    # Growth
    revenue_growth_yoy: Optional[Decimal] = None
    earnings_growth_yoy: Optional[Decimal] = None
    
    # Metadata
    last_updated: datetime = field(default_factory=datetime.now)