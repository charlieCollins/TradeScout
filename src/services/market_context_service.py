"""Market context service for determining trading status."""

import logging
from datetime import datetime, date, timedelta, time as dt_time
from typing import Optional, List, Dict, Any
import pytz

from models.dataclass.market import Market
from models.dataclass.market_context import (
    MarketContext, MarketSession, TradingDayType
)

logger = logging.getLogger(__name__)


class MarketContextService:
    """
    Service to determine market context using Polygon APIs.

    Combines existing Market model with current status to provide:
    1. Is today a trading day?
    2. What was the previous trading day?
    3. What is the current market session?
    """

    def __init__(self, data_provider):
        """
        Initialize service with data provider.

        Args:
            data_provider: Data provider instance (Polygon or Emulation)
        """
        self.data_provider = data_provider

    def get_context(self, market_code: str = "XNYS") -> MarketContext:
        """
        Get current market context for a specific market.

        Computes market context on-demand from markets table, holidays cache,
        and current Polygon API status. No derived caching - the data records
        (markets, market_holidays) are the cache.

        Args:
            market_code: Market code (e.g., 'XNYS', 'XNAS')

        Returns:
            MarketContext with all required information
        """
        return self._compute_context(market_code)

    def get_historical_context(self, date: date, market_code: str = "XNYS") -> MarketContext:
        """
        Get market context for a specific historical date.

        Creates a MarketContext for a past date without making live API calls.
        Used for backtesting and historical analysis.

        Args:
            date: The reference date to create context for
            market_code: Market code (e.g., 'XNYS', 'XNAS')

        Returns:
            MarketContext configured for the historical date
        """
        return self._compute_historical_context(market_code, date)

    def _compute_context(self, market_code: str) -> MarketContext:
        """Compute market context from data sources (markets table, holidays, API status)."""
        try:
            # 1. Get Market model from database
            market = self._get_market(market_code)
            if not market:
                raise RuntimeError(f"Market {market_code} not found in database")

            # 2. Get current time in market timezone
            tz = pytz.timezone(market.timezone)
            current_time = datetime.now(tz)
            today = current_time.date()

            # 3. Get current market status from API
            market_status = self.data_provider.get_market_status()

            # 4. Determine day type and trading status
            day_type = self._determine_day_type(market_status, today)
            is_trading_day = day_type in [
                TradingDayType.REGULAR_TRADING,
                TradingDayType.EARLY_CLOSE
            ]

            # 5. Get previous trading day
            previous_trading_date = self._find_previous_trading_day(
                today, market_status
            )

            # 6. Determine current session based on market's hours
            current_session = self._determine_session(
                market, market_status, is_trading_day, current_time
            )

            # 7. Get next trading day (optional)
            next_trading_date = self._find_next_trading_day(
                today, market_status
            )

            context = MarketContext(
                market=market,  # Use existing Market model
                is_trading_day=is_trading_day,
                previous_trading_date=previous_trading_date,
                current_session=current_session,
                day_type=day_type,
                current_date=today,
                current_time=current_time,
                next_trading_date=next_trading_date,
                raw_market_status=market_status
            )

            return context

        except Exception as e:
            logger.error(f"Failed to fetch market context: {e}")
            # Re-raise the exception - no fallbacks
            raise

    def _compute_historical_context(self, market_code: str, reference_date: date) -> MarketContext:
        """Compute market context for a specific historical date.

        Args:
            market_code: Market code (e.g., 'XNYS', 'XNAS')
            reference_date: The date to create context for

        Returns:
            MarketContext configured for the historical date
        """
        try:
            # 1. Get Market model from database
            market = self._get_market(market_code)
            if not market:
                raise RuntimeError(f"Market {market_code} not found in database")

            # 2. Get reference time in market timezone (use end of day for historical)
            tz = pytz.timezone(market.timezone)
            reference_time = datetime.combine(reference_date, dt_time(23, 59, 59))
            reference_time = tz.localize(reference_time)

            # 3. For historical dates, we don't have live market status
            # Create a mock market status (not used for historical context)
            market_status = None

            # 4. Determine day type for the reference date
            day_type = self._determine_day_type_for_date(reference_date)
            is_trading_day = day_type in [
                TradingDayType.REGULAR_TRADING,
                TradingDayType.EARLY_CLOSE
            ]

            # 5. Get previous trading day from the reference date
            previous_trading_date = self._find_previous_trading_day_from_date(reference_date)

            # 6. For historical dates, session is always "closed" (we're looking at past data)
            # The entire day is in the past, so treat it as closed
            current_session = MarketSession.CLOSED_POST

            # 7. Get next trading day from the reference date
            next_trading_date = self._find_next_trading_day_from_date(reference_date)

            context = MarketContext(
                market=market,
                is_trading_day=is_trading_day,
                previous_trading_date=previous_trading_date,
                current_session=current_session,
                day_type=day_type,
                current_date=reference_date,
                current_time=reference_time,
                next_trading_date=next_trading_date,
                raw_market_status=market_status
            )

            logger.info(f"Historical Market Context for {reference_date}: {context}")
            return context

        except Exception as e:
            logger.error(f"Failed to create historical market context for {reference_date}: {e}")
            raise

    def _get_market(self, market_code: str) -> Optional[Market]:
        """Fetch Market using data provider."""
        return self.data_provider.get_market_by_code(market_code)

    def _determine_day_type(self, market_status: "MarketStatusSnapshot", today: date) -> TradingDayType:
        """Determine what type of day today is using Polygon holiday API."""
        return self._determine_day_type_for_date(today)

    def _determine_day_type_for_date(self, check_date: date) -> TradingDayType:
        """Determine what type of day a specific date is using Polygon holiday API.

        This version doesn't require market_status, useful for historical dates.

        Args:
            check_date: The date to check

        Returns:
            TradingDayType for this date
        """
        # Check if it's a weekend
        if check_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return TradingDayType.CLOSED_WEEKEND

        # Check against Polygon's official holiday calendar (cached)
        holidays = self.data_provider.get_market_holidays()
        date_str = check_date.strftime('%Y-%m-%d')

        for holiday in holidays:
            if holiday.date == date_str:
                if holiday.status == 'early-close':
                    return TradingDayType.EARLY_CLOSE
                elif holiday.status == 'closed':
                    return TradingDayType.CLOSED_HOLIDAY

        # If not a weekend or holiday, it's a regular trading day
        return TradingDayType.REGULAR_TRADING

    def _find_previous_trading_day(self, today: date, market_status: "MarketStatusSnapshot") -> date:
        """Find the most recent trading day before today using Polygon holiday API."""
        return self._find_previous_trading_day_from_date(today)

    def _find_previous_trading_day_from_date(self, from_date: date) -> date:
        """Find the most recent trading day before a given date.

        This version doesn't require market_status, useful for historical dates.

        Args:
            from_date: The date to search backwards from

        Returns:
            The previous trading day
        """
        holidays = self.data_provider.get_market_holidays()
        holiday_dates = {h.date for h in holidays if h.status == 'closed'}

        check_date = from_date - timedelta(days=1)
        max_days_back = 30  # Safety limit (handle long holiday periods)

        for _ in range(max_days_back):
            # Skip weekends
            if check_date.weekday() < 5:  # Monday=0, Friday=4
                # Check if it's a holiday
                check_date_str = check_date.strftime('%Y-%m-%d')
                if check_date_str not in holiday_dates:
                    return check_date

            check_date -= timedelta(days=1)

        # Fallback - shouldn't happen unless there's a very long holiday period
        return from_date - timedelta(days=1)

    def _determine_session(self, market: Market, market_status: "MarketStatusSnapshot",
                          is_trading_day: bool,
                          current_time: datetime) -> MarketSession:
        """
        Determine session using Polygon API market status.
        Raises exception if API data is not available.
        """
        # Require API market status - no fallbacks
        if not market_status or not market_status.market:
            raise RuntimeError("Market status API data is required but not available")

        api_market = market_status.market.lower()
        early_hours = market_status.early_hours
        after_hours = market_status.after_hours

        # Use API status to determine session
        if api_market == 'open':
            return MarketSession.REGULAR
        elif api_market == 'extended-hours':
            if early_hours:
                return MarketSession.PREMARKET
            elif after_hours:
                return MarketSession.AFTERHOURS
            else:
                # API says extended hours but didn't specify which - this is an API error
                raise RuntimeError(f"Polygon API returned extended-hours without earlyHours or afterHours flags: {market_status}")
        elif api_market == 'closed':
            # Market is closed - the API has determined this
            # We'll return CLOSED_POST as the general closed state
            # The distinction between CLOSED_PRE and CLOSED_POST is less important
            # when the API already tells us the market is closed
            return MarketSession.CLOSED_POST
        else:
            raise RuntimeError(f"Unknown market status from Polygon API: {api_market}")

    # TODO not sure this will actually get the next market day, it's just adding 1 day after skipping weekdays, need to validate
    def _find_next_trading_day(self, today: date, market_status: "MarketStatusSnapshot") -> Optional[date]:
        """Find the next trading day after today using Polygon holiday API."""
        return self._find_next_trading_day_from_date(today)

    def _find_next_trading_day_from_date(self, from_date: date) -> Optional[date]:
        """Find the next trading day after a given date.

        This version doesn't require market_status, useful for historical dates.

        Args:
            from_date: The date to search forward from

        Returns:
            The next trading day, or None if not found within 30 days
        """
        holidays = self.data_provider.get_market_holidays()
        holiday_dates = {h.date for h in holidays if h.status == 'closed'}

        check_date = from_date + timedelta(days=1)
        max_days_forward = 30  # Safety limit (handle long holiday periods)

        for _ in range(max_days_forward):
            # Skip weekends
            if check_date.weekday() < 5:  # Monday=0, Friday=4
                # Check if it's a holiday
                check_date_str = check_date.strftime('%Y-%m-%d')
                if check_date_str not in holiday_dates:
                    return check_date

            check_date += timedelta(days=1)

        return None


