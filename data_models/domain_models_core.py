"""
TradeScout Domain Models

Core domain entities that properly model the financial markets.
These represent the real-world concepts we're working with.
"""

from dataclasses import dataclass, field
from datetime import datetime, time
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Set
import uuid


class MarketType(Enum):
    """Types of financial markets"""
    STOCK = "stock"
    OPTIONS = "options"
    FUTURES = "futures"
    FOREX = "forex"
    CRYPTO = "crypto"
    COMMODITY = "commodity"


class MarketStatus(Enum):
    """Current market status"""
    CLOSED = "closed"
    PRE_MARKET = "pre_market"
    OPEN = "open"
    AFTER_HOURS = "after_hours"
    HOLIDAY = "holiday"


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
class Market:
    """Represents a financial market/exchange"""
    id: str                        # e.g., "NYSE", "NASDAQ", "CME"
    name: str                      # e.g., "New York Stock Exchange"
    market_type: MarketType
    timezone: str                  # e.g., "America/New_York"
    currency: str                  # e.g., "USD"
    
    # Trading hours (in market timezone)
    regular_open: time             # e.g., 09:30:00
    regular_close: time            # e.g., 16:00:00
    pre_market_start: Optional[time] = None    # e.g., 04:00:00
    after_hours_end: Optional[time] = None     # e.g., 20:00:00
    
    # Market characteristics
    min_tick_size: Decimal = Decimal('0.01')
    lot_size: int = 1
    trading_days: Set[int] = field(default_factory=lambda: {0, 1, 2, 3, 4})  # Mon-Fri
    
    def get_current_status(self) -> MarketStatus:
        """Determine current market status based on time"""
        # Implementation would check current time against trading hours
        pass
    
    def is_trading_day(self, date: datetime) -> bool:
        """Check if given date is a trading day"""
        return date.weekday() in self.trading_days


@dataclass(frozen=True)
class MarketSegment:
    """Market segments/sectors for classification"""
    id: str                        # e.g., "technology", "healthcare", "sp500"
    name: str                      # e.g., "Technology", "S&P 500"
    description: str
    segment_type: str              # "sector", "industry", "index", "size", "style"
    parent_segment: Optional['MarketSegment'] = None
    
    @property
    def full_hierarchy(self) -> List[str]:
        """Get full segment hierarchy"""
        hierarchy = [self.name]
        current = self.parent_segment
        while current:
            hierarchy.insert(0, current.name)
            current = current.parent_segment
        return hierarchy


@dataclass
class Asset:
    """Core financial asset/instrument"""
    symbol: str                    # Primary identifier (e.g., "AAPL", "SPY")
    name: str                      # Full name (e.g., "Apple Inc.")
    asset_type: AssetType
    market: Market                 # Which market/exchange it trades on
    
    # Asset characteristics
    currency: str                  # Trading currency (usually same as market.currency)
    isin: Optional[str] = None     # International Securities ID
    cusip: Optional[str] = None    # US securities ID
    
    # Classification
    segments: Set[MarketSegment] = field(default_factory=set)
    
    # Trading characteristics
    is_active: bool = True
    min_order_size: Decimal = Decimal('1')
    tick_size: Optional[Decimal] = None  # Override market default if needed
    
    # Corporate data (for stocks)
    shares_outstanding: Optional[int] = None
    market_cap: Optional[Decimal] = None
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Validate asset data"""
        if not self.tick_size:
            self.tick_size = self.market.min_tick_size
        if not self.currency:
            self.currency = self.market.currency
    
    @property
    def qualified_symbol(self) -> str:
        """Get fully qualified symbol with market"""
        return f"{self.symbol}:{self.market.id}"
    
    @property
    def primary_segment(self) -> Optional[MarketSegment]:
        """Get primary market segment (sector)"""
        sector_segments = [s for s in self.segments if s.segment_type == "sector"]
        return sector_segments[0] if sector_segments else None
    
    def is_in_segment(self, segment_id: str) -> bool:
        """Check if asset belongs to a market segment"""
        return any(s.id == segment_id for s in self.segments)


@dataclass
class PriceData:
    """Price and volume data for an asset at a specific time"""
    asset: Asset
    timestamp: datetime
    price: Decimal
    volume: int
    
    # OHLC data (for bar/candlestick data)
    open_price: Optional[Decimal] = None
    high_price: Optional[Decimal] = None
    low_price: Optional[Decimal] = None
    
    # Market context
    session_type: MarketStatus = MarketStatus.OPEN
    bid_price: Optional[Decimal] = None
    ask_price: Optional[Decimal] = None
    bid_size: Optional[int] = None
    ask_size: Optional[int] = None
    
    # Data source metadata
    data_source: str = "unknown"
    data_quality: str = "good"  # "good", "stale", "estimated"
    
    @property
    def is_complete_bar(self) -> bool:
        """Check if this is complete OHLC data"""
        return all([
            self.open_price is not None,
            self.high_price is not None,
            self.low_price is not None,
            self.price is not None  # close price
        ])
    
    @property
    def spread(self) -> Optional[Decimal]:
        """Calculate bid-ask spread"""
        if self.bid_price and self.ask_price:
            return self.ask_price - self.bid_price
        return None


@dataclass
class MarketQuote:
    """Current market quote - uses Asset and extends with market data"""
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
    
    @property
    def is_gap_up(self) -> bool:
        """Check if price gapped up significantly"""
        return self.price_change_percent is not None and self.price_change_percent > 1.0
    
    @property
    def is_gap_down(self) -> bool:
        """Check if price gapped down significantly"""
        return self.price_change_percent is not None and self.price_change_percent < -1.0
    
    @property
    def has_volume_surge(self) -> bool:
        """Check if volume is significantly above average"""
        return self.volume_ratio is not None and self.volume_ratio > 2.0


@dataclass
class ExtendedHoursData:
    """Extended hours trading data for an asset"""
    asset: Asset
    session_type: MarketStatus      # PRE_MARKET or AFTER_HOURS
    price_data: PriceData
    
    # Reference for gap calculation
    regular_session_close: Decimal
    
    # Calculated gap metrics
    gap_amount: Decimal = field(init=False)
    gap_percent: Decimal = field(init=False)
    
    def __post_init__(self):
        """Calculate gap metrics"""
        self.gap_amount = self.price_data.price - self.regular_session_close
        if self.regular_session_close > 0:
            self.gap_percent = (self.gap_amount / self.regular_session_close) * 100
        else:
            self.gap_percent = Decimal(0)
    
    @property
    def is_significant_gap(self) -> bool:
        """Check if gap is significant (>1%)"""
        return abs(self.gap_percent) > 1.0


@dataclass
class NewsItem:
    """News article that may affect one or more assets"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=datetime.now)
    
    # Content
    headline: str = ""
    summary: str = ""
    content: str = ""
    source: str = ""
    url: Optional[str] = None
    
    # Asset relevance
    related_assets: Set[Asset] = field(default_factory=set)
    primary_asset: Optional[Asset] = None  # Main asset if story is focused on one
    
    # Market segments affected
    affected_segments: Set[MarketSegment] = field(default_factory=set)
    
    # Analysis
    sentiment_score: Optional[Decimal] = None  # -1.0 to 1.0
    sentiment_label: str = "neutral"           # "bullish", "bearish", "neutral"
    impact_score: Optional[Decimal] = None     # 0.0 to 1.0
    keywords: List[str] = field(default_factory=list)
    
    # Metadata
    language: str = "en"
    category: str = "general"  # "earnings", "merger", "regulatory", etc.
    
    def affects_asset(self, asset: Asset) -> bool:
        """Check if this news affects a specific asset"""
        return asset in self.related_assets
    
    def affects_segment(self, segment: MarketSegment) -> bool:
        """Check if this news affects a market segment"""
        return segment in self.affected_segments
    
    @property
    def is_bullish(self) -> bool:
        """Check if news sentiment is bullish"""
        return self.sentiment_score is not None and self.sentiment_score > 0.1
    
    @property
    def is_bearish(self) -> bool:
        """Check if news sentiment is bearish"""
        return self.sentiment_score is not None and self.sentiment_score < -0.1


@dataclass
class SocialSentiment:
    """Social media sentiment for an asset"""
    asset: Asset
    timestamp: datetime
    source_platform: str          # "reddit", "twitter", "stocktwits"
    total_mentions: int
    sentiment_score: Decimal       # -1.0 to 1.0
    bullish_mentions: int
    bearish_mentions: int
    neutral_mentions: int
    
    # Optional fields with defaults
    timeframe_hours: int = 24      # Period this sentiment covers
    
    # Engagement metrics
    total_upvotes: Optional[int] = None
    total_comments: Optional[int] = None
    trending_score: Optional[Decimal] = None
    
    # Content analysis
    top_keywords: List[str] = field(default_factory=list)
    top_hashtags: List[str] = field(default_factory=list)
    
    @property
    def bullish_ratio(self) -> Decimal:
        """Ratio of bullish to total mentions"""
        if self.total_mentions == 0:
            return Decimal(0)
        return Decimal(self.bullish_mentions) / Decimal(self.total_mentions)
    
    @property
    def sentiment_strength(self) -> str:
        """Categorize sentiment strength"""
        abs_score = abs(self.sentiment_score)
        if abs_score > 0.6:
            return "strong"
        elif abs_score > 0.3:
            return "moderate"
        else:
            return "weak"


