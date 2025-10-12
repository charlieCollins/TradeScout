"""Market context models for TradeScout."""

from dataclasses import dataclass
from datetime import date, datetime, time
from enum import Enum
from typing import Optional, Dict, Any, List
from models.market import Market
from utils.config_loader import get_config_loader, get_field_for_context, validate_required_fields


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

    def get_current_price_field(self, available_data: Dict[str, Any]) -> Optional[Any]:
        """
        Get the appropriate current price based on session context.

        Args:
            available_data: Dict with keys like 'min_close', 'day_close', 'prevday_close'

        Returns:
            The appropriate price value based on context, or None if no data available
        """
        return get_field_for_context(
            "current_price",
            self.current_session.value,
            available_data
        )

    def get_reference_price_field(self, available_data: Dict[str, Any]) -> Optional[Any]:
        """
        Get the appropriate reference price for change calculations.

        Args:
            available_data: Dict with keys like 'min_close', 'day_close', 'prevday_close'

        Returns:
            The appropriate reference price based on context, or None if no data available
        """
        return get_field_for_context(
            "reference_price",
            self.current_session.value,
            available_data
        )

    def get_volume_field(self, available_data: Dict[str, Any]) -> Optional[Any]:
        """
        Get the appropriate volume field based on session context.

        Args:
            available_data: Dict with keys like 'min_volume', 'day_volume', 'prevday_volume'

        Returns:
            The appropriate volume value based on context, or None if no data available
        """
        return get_field_for_context(
            "volume",
            self.current_session.value,
            available_data
        )

    def get_field_mapping_for_session(self, field_type: str) -> List[str]:
        """
        Get the prioritized list of fields to check for a given field type.

        Args:
            field_type: Type like 'current_price', 'reference_price', 'volume'

        Returns:
            List of field names in priority order
        """
        loader = get_config_loader()
        rules = loader.load_market_context_rules()
        mappings = rules.get("field_mappings", {}).get(field_type, {})
        return mappings.get(self.current_session.value, [])


    def validate_data_for_calculation(
        self,
        operation: str,
        available_data: Dict[str, Any]
    ) -> bool:
        """
        Check if required fields are available for an operation.

        Args:
            operation: Operation like 'change_calculation', 'volume_analysis'
            available_data: Dict of available data fields

        Returns:
            True if all required fields are non-NULL
        """
        return validate_required_fields(
            operation,
            self.current_session.value,
            available_data
        )

    def __str__(self) -> str:
        """Human-readable representation."""
        return (f"MarketContext({self.market.code}: "
                f"trading_day={self.is_trading_day}, "
                f"session={self.current_session.value}, "
                f"prev_trading={self.previous_trading_date})")

    def to_dict(self) -> Dict[str, Any]:
        """Serialize MarketContext to dictionary for JSON storage.

        Returns:
            Dictionary representation of MarketContext
        """
        return {
            'market': self.market.to_dict() if hasattr(self.market, 'to_dict') else {
                'id': self.market.id,
                'code': self.market.code,
                'name': self.market.name,
                'country': self.market.country,
                'timezone': self.market.timezone,
                'currency': self.market.currency,
                'premarket_start_time': str(self.market.premarket_start_time) if self.market.premarket_start_time else None,
                'premarket_end_time': str(self.market.premarket_end_time) if self.market.premarket_end_time else None,
                'regular_open_time': str(self.market.regular_open_time),
                'regular_close_time': str(self.market.regular_close_time),
                'afterhours_start_time': str(self.market.afterhours_start_time) if self.market.afterhours_start_time else None,
                'afterhours_end_time': str(self.market.afterhours_end_time) if self.market.afterhours_end_time else None,
                'is_active': self.market.is_active
            },
            'is_trading_day': self.is_trading_day,
            'previous_trading_date': self.previous_trading_date.isoformat(),
            'current_session': self.current_session.value,
            'day_type': self.day_type.value,
            'current_date': self.current_date.isoformat(),
            'current_time': self.current_time.isoformat(),
            'next_trading_date': self.next_trading_date.isoformat() if self.next_trading_date else None,
            'raw_market_status': self.raw_market_status
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MarketContext':
        """Deserialize MarketContext from dictionary.

        Args:
            data: Dictionary representation of MarketContext

        Returns:
            MarketContext instance
        """
        from models.market import Market
        from datetime import datetime, date, time as dt_time

        # Reconstruct Market object
        market_data = data['market']
        market = Market(
            id=market_data['id'],
            code=market_data['code'],
            name=market_data['name'],
            country=market_data.get('country', 'US'),
            timezone=market_data.get('timezone', 'America/New_York'),
            currency=market_data.get('currency', 'USD'),
            premarket_start_time=dt_time.fromisoformat(market_data['premarket_start_time']) if market_data.get('premarket_start_time') else None,
            premarket_end_time=dt_time.fromisoformat(market_data['premarket_end_time']) if market_data.get('premarket_end_time') else None,
            regular_open_time=dt_time.fromisoformat(market_data['regular_open_time']),
            regular_close_time=dt_time.fromisoformat(market_data['regular_close_time']),
            afterhours_start_time=dt_time.fromisoformat(market_data['afterhours_start_time']) if market_data.get('afterhours_start_time') else None,
            afterhours_end_time=dt_time.fromisoformat(market_data['afterhours_end_time']) if market_data.get('afterhours_end_time') else None,
            is_active=market_data.get('is_active', True)
        )

        # Parse dates and times
        previous_trading_date = date.fromisoformat(data['previous_trading_date'])
        current_date = date.fromisoformat(data['current_date'])
        current_time = datetime.fromisoformat(data['current_time'])
        next_trading_date = date.fromisoformat(data['next_trading_date']) if data.get('next_trading_date') else None

        # Parse enums
        current_session = MarketSession(data['current_session'])
        day_type = TradingDayType(data['day_type'])

        return cls(
            market=market,
            is_trading_day=data['is_trading_day'],
            previous_trading_date=previous_trading_date,
            current_session=current_session,
            day_type=day_type,
            current_date=current_date,
            current_time=current_time,
            next_trading_date=next_trading_date,
            raw_market_status=data.get('raw_market_status')
        )