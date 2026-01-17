"""pandas_market_calendars adapter for market status and holidays.

Implements MarketStatusProvider protocol using local pandas_market_calendars library.
This eliminates API calls for market status/holiday queries - 100% local, unlimited.
"""

import logging
from typing import Optional, List
from datetime import datetime, date, time
from zoneinfo import ZoneInfo

import pandas_market_calendars as mcal

from models.dataclass.market_status import MarketStatusSnapshot
from models.dataclass.market_holiday import MarketHoliday, HolidayStatus
from api.providers.protocols.market_status_provider import MarketStatusProvider

logger = logging.getLogger(__name__)


class PandasMarketCalendarAdapter(MarketStatusProvider):
    """Adapter for pandas_market_calendars library.

    Implements MarketStatusProvider protocol using local market calendar data.
    No API calls required - all data is computed locally from calendar rules.

    Advantages:
    - Zero API calls (unlimited, no rate limits)
    - Fast (local computation)
    - Reliable (no network dependencies)
    - Accurate (based on official exchange calendars)
    """

    # Trading hours for US markets (Eastern Time)
    PREMARKET_START = time(4, 0)    # 4:00 AM ET
    MARKET_OPEN = time(9, 30)       # 9:30 AM ET
    MARKET_CLOSE = time(16, 0)      # 4:00 PM ET
    AFTERHOURS_END = time(20, 0)    # 8:00 PM ET

    def __init__(self, calendars: Optional[List[str]] = None):
        """Initialize pandas market calendar adapter.

        Args:
            calendars: List of calendar names to use (default: ['NYSE', 'NASDAQ'])
        """
        self.calendar_names = calendars or ['NYSE', 'NASDAQ']
        self.calendars = {}

        # Load calendars
        for name in self.calendar_names:
            try:
                self.calendars[name] = mcal.get_calendar(name)
                logger.debug(f"Loaded {name} calendar")
            except Exception as e:
                logger.warning(f"Could not load {name} calendar: {e}")

        # Use NYSE as primary calendar for market status
        self.primary_calendar = self.calendars.get('NYSE') or self.calendars.get('NASDAQ')

        if not self.primary_calendar:
            raise ValueError("No valid calendars loaded. Check calendar names.")

        # Get timezone
        self.tz = ZoneInfo('America/New_York')  # US markets use Eastern Time

    def fetch_market_status(self) -> Optional[MarketStatusSnapshot]:
        """Fetch current market status using local calendar data.

        Returns:
            MarketStatusSnapshot object, or None if error
        """
        try:
            now = datetime.now(self.tz)
            today = now.date()

            # Check if today is a trading day
            schedule = self.primary_calendar.schedule(start_date=today, end_date=today)
            is_trading_day = not schedule.empty

            # Determine market status
            if not is_trading_day:
                market_status = "closed"
                early_hours = False
                after_hours = False
            else:
                # Get market open/close times for today
                market_open_time = schedule.iloc[0]['market_open'].to_pydatetime()
                market_close_time = schedule.iloc[0]['market_close'].to_pydatetime()

                current_time = now.time()

                if current_time < self.PREMARKET_START:
                    market_status = "closed"
                    early_hours = False
                    after_hours = False
                elif current_time < self.MARKET_OPEN:
                    market_status = "extended-hours"
                    early_hours = True
                    after_hours = False
                elif current_time < self.MARKET_CLOSE:
                    market_status = "open"
                    early_hours = False
                    after_hours = False
                elif current_time < self.AFTERHOURS_END:
                    market_status = "extended-hours"
                    early_hours = False
                    after_hours = True
                else:
                    market_status = "closed"
                    early_hours = False
                    after_hours = False

            # Build exchange status map
            exchanges = {}
            for name, calendar in self.calendars.items():
                schedule = calendar.schedule(start_date=today, end_date=today)
                if schedule.empty:
                    exchanges[name.lower()] = "closed"
                else:
                    market_open_time = schedule.iloc[0]['market_open'].to_pydatetime()
                    market_close_time = schedule.iloc[0]['market_close'].to_pydatetime()

                    if market_open_time <= now <= market_close_time:
                        exchanges[name.lower()] = "open"
                    else:
                        exchanges[name.lower()] = "closed"

            # Create MarketStatusSnapshot
            market_status_snapshot = MarketStatusSnapshot(
                market=market_status,
                server_time=now,
                exchanges=exchanges,
                currencies={},  # pandas_market_calendars doesn't track currencies
                early_hours=early_hours,
                after_hours=after_hours
            )

            logger.debug(f"Market status: {market_status}, early_hours={early_hours}, after_hours={after_hours}")
            return market_status_snapshot

        except Exception as e:
            logger.error(f"Error fetching market status from pandas_market_calendars: {e}")
            return None

    def fetch_upcoming_holidays(self) -> Optional[List[MarketHoliday]]:
        """Fetch upcoming market holidays from local calendar data.

        Returns:
            List of MarketHoliday objects, or None if error
        """
        try:
            today = date.today()

            # Get holidays from primary calendar
            calendar_holidays = self.primary_calendar.holidays()

            # Filter for upcoming holidays (today onwards, next 12 months)
            from dateutil.relativedelta import relativedelta
            end_date = today + relativedelta(months=12)

            # calendar_holidays.holidays is an AbstractHolidayCalendar
            # We need to get the list of holiday dates
            holiday_dates = calendar_holidays.holidays

            # Filter holidays
            upcoming_holidays = []
            for holiday_date in holiday_dates:
                # Convert to date if it's a Timestamp
                if hasattr(holiday_date, 'date'):
                    holiday_date = holiday_date.date()
                elif isinstance(holiday_date, tuple):
                    # Sometimes holidays are returned as tuples (date, name)
                    holiday_date = holiday_date[0]
                    if hasattr(holiday_date, 'date'):
                        holiday_date = holiday_date.date()

                # Skip if not in range
                if holiday_date < today or holiday_date > end_date:
                    continue

                # Try to get holiday name from calendar rules
                holiday_name = self._get_holiday_name(holiday_date)

                # Check if it's an early close day
                # pandas_market_calendars has special schedules for early closes
                schedule = self.primary_calendar.schedule(
                    start_date=holiday_date,
                    end_date=holiday_date
                )

                if schedule.empty:
                    # Full closure
                    status = HolidayStatus.CLOSED
                else:
                    # Check if early close (market closes before 4 PM)
                    market_close = schedule.iloc[0]['market_close'].to_pydatetime()
                    if market_close.time() < self.MARKET_CLOSE:
                        status = HolidayStatus.EARLY_CLOSE
                    else:
                        # Not a holiday, just a regular trading day
                        # This can happen if the date is in the schedule but not a holiday
                        continue

                # Create MarketHoliday
                market_holiday = MarketHoliday(
                    date=holiday_date,
                    name=holiday_name,
                    status=status,
                    exchange="US"  # US markets
                )

                upcoming_holidays.append(market_holiday)

            # Sort by date
            upcoming_holidays.sort(key=lambda h: h.date)

            logger.debug(f"Found {len(upcoming_holidays)} upcoming holidays")
            return upcoming_holidays

        except Exception as e:
            logger.error(f"Error fetching holidays from pandas_market_calendars: {e}")
            return None

    def _get_holiday_name(self, holiday_date: date) -> str:
        """Get holiday name for a given date.

        Args:
            holiday_date: Date to check

        Returns:
            Holiday name or "Holiday" if not found
        """
        # pandas_market_calendars doesn't directly expose holiday names
        # We'll use common US market holidays
        holiday_map = {
            (1, 1): "New Year's Day",
            (7, 4): "Independence Day",
            (12, 25): "Christmas Day",
        }

        # Check for specific dates
        key = (holiday_date.month, holiday_date.day)
        if key in holiday_map:
            return holiday_map[key]

        # Check for special holidays (Thanksgiving, MLK, etc.)
        # These vary by year so we use heuristics
        if holiday_date.month == 11:  # November
            # Thanksgiving is 4th Thursday
            if holiday_date.weekday() == 3:  # Thursday
                return "Thanksgiving"

        if holiday_date.month == 1:  # January
            # MLK Day is 3rd Monday
            if holiday_date.weekday() == 0:  # Monday
                return "Martin Luther King Jr. Day"

        if holiday_date.month == 2:  # February
            # Presidents Day is 3rd Monday
            if holiday_date.weekday() == 0:  # Monday
                return "Presidents Day"

        # Default name
        return "Holiday"

    def get_provider_name(self) -> str:
        """Get provider name for logging/debugging.

        Returns:
            Provider identifier string
        """
        return "pandas_market_calendars"
