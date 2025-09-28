"""Market context service for determining trading status."""

import logging
from datetime import datetime, date, timedelta, time as dt_time
from typing import Optional
import pytz

from models.market import Market
from models.market_context import (
    MarketContext, MarketSession, TradingDayType
)
from config.ttl_config import MARKET_CONTEXT_TTL_MINUTES

logger = logging.getLogger(__name__)


class MarketContextService:
    """
    Service to determine market context using Polygon APIs.

    Combines existing Market model with current status to provide:
    1. Is today a trading day?
    2. What was the previous trading day?
    3. What is the current market session?
    """

    def __init__(self, data_provider, db_manager):
        """
        Initialize service with data provider and database.

        Args:
            data_provider: Data provider instance (Polygon or Emulation)
            db_manager: Database manager to fetch Market info
        """
        self.data_provider = data_provider
        self.db_manager = db_manager

        # Cache management - cache per market code
        self._context_cache: dict[str, MarketContext] = {}
        self._cache_timestamp: dict[str, datetime] = {}
        self._cache_duration_seconds = MARKET_CONTEXT_TTL_MINUTES * 60  # Convert minutes to seconds

    def get_context(self, market_code: str = "XNYS",
                   force_refresh: bool = False) -> MarketContext:
        """
        Get current market context for a specific market.

        Args:
            market_code: Market code (e.g., 'XNYS', 'XNAS')
            force_refresh: Force API call even if cache is valid

        Returns:
            MarketContext with all required information
        """
        if force_refresh or self._should_refresh_cache(market_code):
            logger.info(f"Fetching fresh market context for {market_code}")
            self._context_cache[market_code] = self._fetch_context(market_code)
            self._cache_timestamp[market_code] = datetime.now()
        else:
            logger.debug(f"Using cached market context for {market_code}")

        return self._context_cache.get(market_code)

    def _fetch_context(self, market_code: str) -> MarketContext:
        """Fetch fresh market context from APIs and database."""
        try:
            # 1. Get Market model from database
            market = self._get_market(market_code)
            if not market:
                logger.warning(f"Market {market_code} not found in database, using fallback")
                return self._create_fallback_context(market_code)

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

            return MarketContext(
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

        except Exception as e:
            logger.error(f"Failed to fetch market context: {e}")
            # Return safe defaults on error
            return self._create_fallback_context(market_code)

    def _get_market(self, market_code: str) -> Optional[Market]:
        """Fetch Market from database."""
        if not self.db_manager:
            logger.warning("No database manager provided")
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, code, name, country, timezone, currency,
                           premarket_start_time, premarket_end_time,
                           regular_open_time, regular_close_time,
                           afterhours_start_time, afterhours_end_time,
                           is_active, created_at, updated_at
                    FROM markets
                    WHERE code = ? AND is_active = TRUE
                """, (market_code,))

                row = cursor.fetchone()
                if row:
                    # Convert time strings to time objects
                    def parse_time(time_str: Optional[str]) -> Optional[dt_time]:
                        if time_str:
                            try:
                                return datetime.strptime(time_str, '%H:%M:%S').time()
                            except ValueError:
                                return None
                        return None

                    return Market(
                        id=row[0],
                        code=row[1],
                        name=row[2],
                        country=row[3],
                        timezone=row[4],
                        currency=row[5],
                        premarket_start_time=parse_time(row[6]),
                        premarket_end_time=parse_time(row[7]),
                        regular_open_time=parse_time(row[8]) or dt_time(9, 30),
                        regular_close_time=parse_time(row[9]) or dt_time(16, 0),
                        afterhours_start_time=parse_time(row[10]),
                        afterhours_end_time=parse_time(row[11]),
                        is_active=bool(row[12]),
                        created_at=datetime.fromisoformat(row[13]) if row[13] else datetime.now(),
                        updated_at=datetime.fromisoformat(row[14]) if row[14] else datetime.now()
                    )

        except Exception as e:
            logger.error(f"Failed to fetch market {market_code}: {e}")

        return None

    def _determine_day_type(self, market_status: dict, today: date) -> TradingDayType:
        """Determine what type of day today is."""
        # Parse market status to determine day type
        market = market_status.get('market', '').lower()

        # Check if it's a weekend
        if today.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return TradingDayType.CLOSED_WEEKEND

        # Check market status
        if market in ['open', 'extended-hours']:
            # Could be regular or early close
            # For now, assume regular - could check closing time later
            return TradingDayType.REGULAR_TRADING

        # If closed on a weekday, likely a holiday
        if market == 'closed' and today.weekday() < 5:
            return TradingDayType.CLOSED_HOLIDAY

        return TradingDayType.REGULAR_TRADING

    def _find_previous_trading_day(self, today: date, market_status: dict) -> date:
        """Find the most recent trading day before today."""
        # Simple logic for now - skip weekends and go back max 10 days
        check_date = today - timedelta(days=1)
        max_days_back = 10  # Safety limit

        for _ in range(max_days_back):
            # Skip weekends
            while check_date.weekday() >= 5:
                check_date -= timedelta(days=1)

            # For now, assume weekdays are trading days
            # TODO: Check against holiday calendar
            return check_date

        # Fallback
        return today - timedelta(days=1)

    def _determine_session(self, market: Market, market_status: dict,
                          is_trading_day: bool,
                          current_time: datetime) -> MarketSession:
        """
        Determine session using Market's configured hours.
        """
        if not is_trading_day:
            return MarketSession.CLOSED_POST

        # Use market's actual trading hours to determine session
        current_time_only = current_time.time()

        # Check premarket
        if (market.premarket_start_time and
            market.premarket_start_time <= current_time_only < market.regular_open_time):
            return MarketSession.PREMARKET

        # Check regular hours
        elif market.regular_open_time <= current_time_only < market.regular_close_time:
            return MarketSession.REGULAR

        # Check afterhours
        elif (market.afterhours_end_time and
              market.regular_close_time <= current_time_only < market.afterhours_end_time):
            return MarketSession.AFTERHOURS

        # Check if before premarket
        elif (market.premarket_start_time and
              current_time_only < market.premarket_start_time):
            return MarketSession.CLOSED_PRE

        # Everything else is closed post
        else:
            return MarketSession.CLOSED_POST

    def _find_next_trading_day(self, today: date, market_status: dict) -> Optional[date]:
        """Find the next trading day after today."""
        check_date = today + timedelta(days=1)
        max_days_forward = 10

        for _ in range(max_days_forward):
            # Skip weekends
            while check_date.weekday() >= 5:
                check_date += timedelta(days=1)

            # For now, assume weekdays are trading days
            # TODO: Check against holiday calendar
            return check_date

        return None

    def _should_refresh_cache(self, market_code: str) -> bool:
        """Check if cache should be refreshed for a specific market."""
        if market_code not in self._context_cache or market_code not in self._cache_timestamp:
            return True

        elapsed = (datetime.now() - self._cache_timestamp[market_code]).total_seconds()
        return elapsed > self._cache_duration_seconds

    def _create_fallback_context(self, market_code: str) -> MarketContext:
        """Create fallback context when API fails or market not found."""
        # Create basic market for fallback
        fallback_market = Market(
            id=0,
            code=market_code,
            name=f"Fallback Market {market_code}",
            country="US",
            timezone="America/New_York",
            currency="USD",
            premarket_start_time=dt_time(4, 0),
            premarket_end_time=dt_time(9, 30),
            regular_open_time=dt_time(9, 30),
            regular_close_time=dt_time(16, 0),
            afterhours_start_time=dt_time(16, 0),
            afterhours_end_time=dt_time(20, 0),
            is_active=True,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        # Safe defaults for when we can't reach the API
        tz = pytz.timezone(fallback_market.timezone)
        current_time = datetime.now(tz)
        today = current_time.date()

        # Assume it's a trading day if weekday
        is_trading_day = today.weekday() < 5

        # Simple previous trading day logic
        prev_date = today - timedelta(days=1)
        while prev_date.weekday() >= 5:
            prev_date -= timedelta(days=1)

        # Simple session determination
        hour = current_time.hour
        if not is_trading_day:
            session = MarketSession.CLOSED_POST
        elif hour < 4:
            session = MarketSession.CLOSED_PRE
        elif hour < 9.5:
            session = MarketSession.PREMARKET
        elif hour < 16:
            session = MarketSession.REGULAR
        elif hour < 20:
            session = MarketSession.AFTERHOURS
        else:
            session = MarketSession.CLOSED_POST

        return MarketContext(
            market=fallback_market,
            day_type=TradingDayType.REGULAR_TRADING if is_trading_day
                     else TradingDayType.CLOSED_WEEKEND,
            is_trading_day=is_trading_day,
            previous_trading_date=prev_date,
            current_session=session,
            current_date=today,
            current_time=current_time
        )