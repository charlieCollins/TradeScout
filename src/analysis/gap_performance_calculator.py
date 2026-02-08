"""Gap performance calculation logic.

Calculates actual intraday performance for gap candidates by:
1. Determining correct trading date (premarket vs afterhours)
2. Fetching daily and minute bars from data provider
3. Detecting gap fill events
4. Calculating performance metrics
"""

import logging
from datetime import datetime, date, timedelta
from typing import Optional, Tuple, List
from models.dataclass.gap_performance import GapCandidateResult

logger = logging.getLogger(__name__)


class GapCandidateResultCalculator:
    """Calculate gap performance metrics from market data."""

    def __init__(self, data_service):
        """Initialize performance calculator.

        Args:
            data_service: DataService instance for database access and API calls
        """
        self.data_service = data_service

    def get_performance_trading_date(self, gap_result: dict) -> date:
        """Determine which trading day to use for performance data.

        Args:
            gap_result: Gap result dict from database

        Returns:
            Trading date to use for performance data
        """
        trading_date = gap_result['trading_date']
        if isinstance(trading_date, str):
            trading_date = date.fromisoformat(trading_date)

        session_type = gap_result['session_type']

        if session_type == 'premarket':
            # Premarket: use same day's regular hours
            return trading_date

        elif session_type == 'afterhours':
            # Afterhours: use next trading day's regular hours
            return self.get_next_trading_day(trading_date)

        else:
            raise ValueError(f"Unknown session type: {session_type}")

    def get_next_trading_day(self, current_date: date) -> date:
        """Get next trading day after given date.

        Args:
            current_date: Starting date

        Returns:
            Next trading day
        """
        next_date = current_date + timedelta(days=1)

        # Skip weekends and holidays
        while self.is_non_trading_day(next_date):
            next_date += timedelta(days=1)

        return next_date

    def is_non_trading_day(self, check_date: date) -> bool:
        """Check if date is a non-trading day (weekend or holiday).

        Args:
            check_date: Date to check

        Returns:
            True if non-trading day
        """
        # Check weekend
        if check_date.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return True

        # Check market holidays - get_by_date returns MarketHolidaySQLModel or None
        holiday = self.data_service.market_holiday_repository.get_by_date(check_date.isoformat())
        return holiday is not None

    def is_trading_day_complete(self, trading_date: date) -> bool:
        """Check if trading day is complete and data is available.

        Args:
            trading_date: Trading date to check

        Returns:
            True if day is complete and data should be available
        """
        now = datetime.now()
        today = now.date()

        # If trading date is in the future, not complete
        if trading_date > today:
            return False

        # If trading date is in the past, complete
        if trading_date < today:
            return True

        # If trading date is today, check time
        # Data typically available ~5 PM ET (after 4 PM market close)
        # Being conservative: require 5:30 PM ET
        if now.hour < 17 or (now.hour == 17 and now.minute < 30):
            return False

        return True

    def calculate_performance(
        self,
        gap_result: dict,
        symbol: str,
        performance_date: date
    ) -> Optional[GapCandidateResult]:
        """Calculate performance metrics for a gap candidate.

        Args:
            gap_result: Gap result dict from database
            symbol: Stock symbol
            performance_date: Trading date to use for performance

        Returns:
            GapCandidateResult object or None if data unavailable
        """
        try:
            # Fetch daily bar for entry/exit and high/low
            daily_bar = self.data_service.get_daily_aggregates(
                symbol=symbol,
                from_date=performance_date,
                to_date=performance_date
            )

            if not daily_bar or len(daily_bar) == 0:
                logger.warning(f"No daily bar data for {symbol} on {performance_date}")
                return None

            bar = daily_bar[0]

            # Fetch minute bars for gap fill detection
            gap_filled, fill_timestamp = self.detect_gap_fill(
                symbol=symbol,
                trading_date=performance_date,
                reference_price=gap_result['reference_price']
            )

            # Create performance object (calculations happen in __post_init__)
            performance = GapCandidateResult(
                gap_result_id=gap_result['id'],
                entry_price=bar.open,
                exit_price=bar.close,
                max_intraday_price=bar.high,
                min_intraday_price=bar.low,
                gap_filled=gap_filled,
                gap_fill_timestamp=fill_timestamp
            )

            return performance

        except Exception as e:
            logger.error(f"Error calculating performance for {symbol}: {e}")
            return None

    def detect_gap_fill(
        self,
        symbol: str,
        trading_date: date,
        reference_price: float
    ) -> Tuple[bool, Optional[datetime]]:
        """Detect if gap was filled during the trading day.

        Gap is filled if any intraday bar touched the reference price.

        Args:
            symbol: Stock symbol
            trading_date: Trading date to check
            reference_price: Reference price from gap analysis

        Returns:
            Tuple of (gap_filled: bool, fill_timestamp: Optional[datetime])
        """
        try:
            # Fetch minute bars for trading day (9:30 AM - 4:00 PM)
            # Format: YYYY-MM-DD
            date_str = trading_date.strftime('%Y-%m-%d')

            minute_bars = self.data_service.get_intraday_aggregates(
                symbol=symbol,
                date=date_str,
                timespan='minute',
                multiplier=1
            )

            if not minute_bars or len(minute_bars) == 0:
                logger.warning(f"No minute bar data for {symbol} on {trading_date}")
                return False, None

            # Check each bar for gap fill
            for bar in minute_bars:
                # Gap is filled if reference price is within bar's range
                if bar.low <= reference_price <= bar.high:
                    # Convert timestamp to datetime
                    timestamp = datetime.fromtimestamp(bar.timestamp / 1000)
                    return True, timestamp

            return False, None

        except Exception as e:
            logger.error(f"Error detecting gap fill for {symbol}: {e}")
            return False, None
