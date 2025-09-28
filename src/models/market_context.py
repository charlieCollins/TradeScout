"""Market context models for TradeScout."""

from dataclasses import dataclass
from datetime import date, datetime, time
from enum import Enum
from typing import Optional, Dict, Any
from models.market import Market


class MarketSession(Enum):
    """Five distinct market states for trading days."""
    CLOSED_PRE = "closed_pre"      # 12:00 AM - 4:00 AM ET
    PREMARKET = "premarket"         # 4:00 AM - 9:30 AM ET
    REGULAR = "regular"             # 9:30 AM - 4:00 PM ET
    AFTERHOURS = "afterhours"       # 4:00 PM - 8:00 PM ET
    CLOSED_POST = "closed_post"     # 8:00 PM - 12:00 AM ET

    @property
    def is_open(self) -> bool:
        """Check if any trading is happening in this session."""
        return self in [MarketSession.PREMARKET, MarketSession.REGULAR, MarketSession.AFTERHOURS]

    @property
    def is_extended(self) -> bool:
        """Check if this is extended hours trading."""
        return self in [MarketSession.PREMARKET, MarketSession.AFTERHOURS]

    def to_screener_session(self) -> str:
        """Convert to screener-compatible session name."""
        if self in [MarketSession.CLOSED_PRE, MarketSession.CLOSED_POST]:
            return "closed"
        return self.value


class TradingDayType(Enum):
    """Type of trading day."""
    REGULAR_TRADING = "regular_trading"    # Normal trading day
    EARLY_CLOSE = "early_close"            # Early close (e.g., day before holiday)
    CLOSED_HOLIDAY = "closed_holiday"      # Market holiday
    CLOSED_WEEKEND = "closed_weekend"      # Weekend


@dataclass(frozen=True)
class MarketContext:
    """
    Current market context combining Market info with current status.

    This provides the 3 critical pieces of information:
    1. Is today a trading day?
    2. What was the previous trading day?
    3. What is the current market session?
    """

    # Reference to the actual market (reuse existing model)
    market: Market  # The market this context is for (has timezone, hours, etc.)

    # The 3 core properties we need
    is_trading_day: bool                       # Is today a trading day?
    previous_trading_date: date                # Most recent trading day
    current_session: MarketSession             # Current market state

    # Additional context
    day_type: TradingDayType                   # What kind of day is today?
    current_date: date                          # Today's date
    current_time: datetime                      # Current time in market timezone
    next_trading_date: Optional[date] = None   # Next trading day (if known)

    # API response data (for debugging/logging)
    raw_market_status: Optional[Dict[str, Any]] = None

    @property
    def session_name(self) -> str:
        """Get simplified session name for legacy compatibility."""
        return self.current_session.to_screener_session()

    @property
    def is_market_open(self) -> bool:
        """Check if any trading is currently happening."""
        return self.current_session.is_open

    @property
    def is_regular_hours(self) -> bool:
        """Check if regular trading hours are active."""
        return self.current_session == MarketSession.REGULAR

    @property
    def is_extended_hours(self) -> bool:
        """Check if extended hours trading is active."""
        return self.current_session.is_extended

    def get_session_times(self) -> Dict[str, Optional[datetime]]:
        """
        Get today's session times based on market's configured hours.
        Returns None values if not a trading day.
        """
        if not self.is_trading_day:
            return {
                'premarket_start': None,
                'regular_open': None,
                'regular_close': None,
                'afterhours_end': None
            }

        # Combine date with market's configured times
        return {
            'premarket_start': datetime.combine(
                self.current_date,
                self.market.premarket_start_time
            ) if self.market.premarket_start_time else None,
            'regular_open': datetime.combine(
                self.current_date,
                self.market.regular_open_time
            ),
            'regular_close': datetime.combine(
                self.current_date,
                self.market.regular_close_time
            ),
            'afterhours_end': datetime.combine(
                self.current_date,
                self.market.afterhours_end_time
            ) if self.market.afterhours_end_time else None
        }

    def __str__(self) -> str:
        """Human-readable representation."""
        return (f"MarketContext({self.market.code}: "
                f"trading_day={self.is_trading_day}, "
                f"session={self.current_session.value}, "
                f"prev_trading={self.previous_trading_date})")