"""Polygon API provider for aggregates/bars data."""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, date
from .base_provider import BaseAPIProvider

logger = logging.getLogger(__name__)


class PolygonAggregatesProvider(BaseAPIProvider):
    """API provider for Polygon aggregates endpoints.

    Handles ONLY aggregates API calls - no database operations, no caching.
    Used for getting historical bars, minute data, and extended hours volume.
    """

    def __init__(self, api_key: str):
        """Initialize Polygon aggregates provider.

        Args:
            api_key: Polygon API key
        """
        super().__init__(api_key, "https://api.polygon.io")

    # ============================================================================
    # AUTHENTICATION
    # ============================================================================

    def _add_authentication(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add Polygon API key to request parameters.

        Args:
            params: Request parameters

        Returns:
            Parameters with apikey added
        """
        params["apikey"] = self.api_key
        return params

    def _get_health_endpoint(self) -> str:
        """Get health check endpoint.

        Returns:
            Endpoint for health checking
        """
        return "/v1/marketstatus/now"

    # ============================================================================
    # AGGREGATES API CALLS
    # ============================================================================

    def _transform_bar(self, raw_bar: Dict[str, Any]) -> "PriceBar":
        """Transform raw Polygon bar data to PriceBar dataclass.

        Args:
            raw_bar: Raw bar dict from Polygon API

        Returns:
            PriceBar domain object
        """
        from models.dataclass.price_bar import PriceBar
        from datetime import datetime

        timestamp_ms = raw_bar.get("t", 0)
        timestamp = datetime.fromtimestamp(timestamp_ms / 1000) if timestamp_ms else datetime.now()

        return PriceBar(
            open=raw_bar.get("o", 0.0),
            high=raw_bar.get("h", 0.0),
            low=raw_bar.get("l", 0.0),
            close=raw_bar.get("c", 0.0),
            volume=raw_bar.get("v", 0),
            volume_weighted_price=raw_bar.get("vw"),
            timestamp=timestamp,
            timestamp_ms=timestamp_ms,
            num_transactions=raw_bar.get("n")
        )

    def fetch_minute_bars(
        self,
        symbol: str,
        from_datetime: datetime,
        to_datetime: datetime,
        adjusted: bool = True
    ) -> Optional[List["PriceBar"]]:
        """Fetch minute-level bars for a symbol within a time range.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            from_datetime: Start datetime (inclusive)
            to_datetime: End datetime (inclusive)
            adjusted: Whether to return adjusted prices (default: True)

        Returns:
            List of PriceBar objects, or None if error
        """
        try:
            # Convert datetimes to Unix timestamps in milliseconds (Polygon requirement)
            from_ts = int(from_datetime.timestamp() * 1000)
            to_ts = int(to_datetime.timestamp() * 1000)

            # Endpoint: /v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}
            endpoint = f"/v2/aggs/ticker/{symbol}/range/1/minute/{from_ts}/{to_ts}"

            params = {
                "adjusted": str(adjusted).lower(),  # "true" or "false"
                "sort": "asc",  # Chronological order
                "limit": 50000  # Max results (after-hours is ~240 minutes max)
            }

            raw_data = self._make_request(endpoint, params)

            if not raw_data:
                logger.warning(f"No data in aggregates response for {symbol}")
                return None

            # Check for results array
            if "results" not in raw_data:
                logger.debug(f"No results in aggregates response for {symbol}: {raw_data.get('status')}")
                return None

            # Transform raw bars to PriceBar objects
            raw_bars = raw_data["results"]
            bars = [self._transform_bar(raw_bar) for raw_bar in raw_bars]

            logger.debug(f"Fetched {len(bars)} minute bars for {symbol} ({from_datetime} to {to_datetime})")
            return bars

        except Exception as e:
            logger.error(f"Failed to fetch minute bars for {symbol}: {e}")
            return None

    def get_daily_aggregates(
        self,
        symbol: str,
        from_date: date,
        to_date: date,
        adjusted: bool = True
    ) -> Optional[List["PriceBar"]]:
        """Fetch daily aggregates for a symbol within a date range.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            from_date: Start date (inclusive)
            to_date: End date (inclusive)
            adjusted: Whether to return adjusted prices (default: True)

        Returns:
            List of PriceBar objects, or None if error
        """
        try:
            # Convert dates to timestamps
            from_dt = datetime.combine(from_date, datetime.min.time())
            to_dt = datetime.combine(to_date, datetime.max.time())

            from_ts = int(from_dt.timestamp() * 1000)
            to_ts = int(to_dt.timestamp() * 1000)

            # Endpoint: /v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}
            endpoint = f"/v2/aggs/ticker/{symbol}/range/1/day/{from_ts}/{to_ts}"

            params = {
                "adjusted": str(adjusted).lower(),  # "true" or "false"
                "sort": "asc",  # Chronological order
                "limit": 5000
            }

            raw_data = self._make_request(endpoint, params)

            if not raw_data:
                logger.warning(f"No data in daily aggregates response for {symbol}")
                return None

            # Check for results array
            if "results" not in raw_data:
                logger.debug(f"No results in daily aggregates response for {symbol}: {raw_data.get('status')}")
                return None

            # Transform raw bars to PriceBar objects
            raw_bars = raw_data["results"]
            bars = [self._transform_bar(raw_bar) for raw_bar in raw_bars]

            logger.debug(f"Fetched {len(bars)} daily bars for {symbol} ({from_date} to {to_date})")
            return bars

        except Exception as e:
            logger.error(f"Failed to fetch daily aggregates for {symbol}: {e}")
            return None

    def get_intraday_aggregates(
        self,
        symbol: str,
        date: str,
        timespan: str = 'minute',
        multiplier: int = 1,
        adjusted: bool = True
    ) -> Optional[List["PriceBar"]]:
        """Fetch intraday aggregates for a symbol on a specific date.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            date: Date string in YYYY-MM-DD format
            timespan: Timespan ('minute', 'hour')
            multiplier: Multiplier for timespan (1, 5, 15, etc.)
            adjusted: Whether to return adjusted prices (default: True)

        Returns:
            List of PriceBar objects, or None if error
        """
        try:
            # Parse date and create time range for regular trading hours (9:30 AM - 4:00 PM ET)
            trading_date = datetime.strptime(date, '%Y-%m-%d').date()

            from_dt = datetime.combine(trading_date, datetime.min.time()).replace(
                hour=9, minute=30, second=0
            )
            to_dt = datetime.combine(trading_date, datetime.min.time()).replace(
                hour=16, minute=0, second=0
            )

            from_ts = int(from_dt.timestamp() * 1000)
            to_ts = int(to_dt.timestamp() * 1000)

            # Endpoint: /v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}
            endpoint = f"/v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{from_ts}/{to_ts}"

            params = {
                "adjusted": str(adjusted).lower(),
                "sort": "asc",
                "limit": 50000
            }

            raw_data = self._make_request(endpoint, params)

            if not raw_data:
                logger.warning(f"No data in intraday aggregates response for {symbol}")
                return None

            if "results" not in raw_data:
                logger.debug(f"No results in intraday aggregates response for {symbol}: {raw_data.get('status')}")
                return None

            # Transform raw bars to PriceBar objects
            raw_bars = raw_data["results"]
            bars = [self._transform_bar(raw_bar) for raw_bar in raw_bars]

            logger.debug(f"Fetched {len(bars)} {timespan} bars for {symbol} on {date}")
            return bars

        except Exception as e:
            logger.error(f"Failed to fetch intraday aggregates for {symbol}: {e}")
            return None

    def calculate_extended_hours_volume(
        self,
        symbol: str,
        trading_date: date,
        session: str = "afterhours"
    ) -> Optional[int]:
        """Calculate total volume for an extended hours session.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            trading_date: Trading date (not datetime - just the date)
            session: Session type - "premarket" or "afterhours"

        Returns:
            Total volume for the session, or None if error

        Session Times (Eastern Time):
            - premarket: 4:00 AM - 9:30 AM
            - afterhours: 4:00 PM - 8:00 PM
        """
        try:
            # Define session time ranges (in ET/local time)
            if session == "premarket":
                start_hour, start_min = 4, 0
                end_hour, end_min = 9, 30
            elif session == "afterhours":
                start_hour, start_min = 16, 0
                end_hour, end_min = 20, 0
            else:
                raise ValueError(f"Invalid session: {session}. Must be 'premarket' or 'afterhours'")

            # Create datetime objects (assumes system timezone is ET or handles TZ correctly)
            from_dt = datetime.combine(trading_date, datetime.min.time()).replace(
                hour=start_hour, minute=start_min, second=0
            )
            to_dt = datetime.combine(trading_date, datetime.min.time()).replace(
                hour=end_hour, minute=end_min, second=0
            )

            logger.info(
                f"Calculating {session} volume for {symbol} on {trading_date} "
                f"({from_dt.strftime('%Y-%m-%d %H:%M:%S')} - {to_dt.strftime('%Y-%m-%d %H:%M:%S')} ET)"
            )

            # Fetch minute bars
            bars = self.fetch_minute_bars(symbol, from_dt, to_dt)

            if bars is None:
                return None

            # Sum up all volumes
            total_volume = sum(bar.volume for bar in bars)

            # Get time range of actual bars
            if bars:
                first_bar_ts = datetime.fromtimestamp(bars[0].timestamp_ms / 1000)
                last_bar_ts = datetime.fromtimestamp(bars[-1].timestamp_ms / 1000)
                logger.info(
                    f"{symbol} {session} volume: {total_volume:,} shares "
                    f"({len(bars)} bars from {first_bar_ts.strftime('%H:%M:%S')} to {last_bar_ts.strftime('%H:%M:%S')})"
                )
            else:
                logger.info(f"{symbol} {session} volume: {total_volume:,} shares (0 bars)")

            return total_volume

        except Exception as e:
            logger.error(f"Failed to calculate {session} volume for {symbol}: {e}")
            return None

    def fetch_grouped_daily_bars(self, target_date: date, adjusted: bool = True) -> Optional[Dict[str, "PriceBar"]]:
        """Fetch end-of-day bars for all stocks traded on a specific date.

        Uses Polygon's grouped bars endpoint to get all tickers in one API call.
        Returns all stocks that traded, not just US exchanges - caller should filter.

        Args:
            target_date: Trading date to fetch (e.g., date(2025, 10, 14))
            adjusted: Whether to return adjusted prices (default: True)

        Returns:
            Dict mapping symbol -> PriceBar for all stocks that traded, or None if error
        """
        try:
            # Format date as YYYY-MM-DD
            date_str = target_date.strftime('%Y-%m-%d')

            # Endpoint: /v2/aggs/grouped/locale/us/market/stocks/{date}
            endpoint = f"/v2/aggs/grouped/locale/us/market/stocks/{date_str}"

            params = {
                "adjusted": str(adjusted).lower(),
                "include_otc": "false"  # Exclude OTC stocks
            }

            raw_data = self._make_request(endpoint, params)

            if not raw_data:
                logger.warning(f"No data in grouped bars response for {date_str}")
                return None

            # Check for results array
            if "results" not in raw_data:
                logger.debug(f"No results in grouped bars response for {date_str}: {raw_data.get('status')}")
                return None

            # Transform raw bars to PriceBar objects, keyed by symbol
            raw_bars = raw_data["results"]
            bars_dict = {}

            for raw_bar in raw_bars:
                symbol = raw_bar.get("T")  # Polygon uses "T" for ticker symbol
                if not symbol:
                    continue

                bar = self._transform_bar(raw_bar)
                bars_dict[symbol] = bar

            logger.info(f"Fetched {len(bars_dict)} grouped daily bars for {date_str}")
            return bars_dict

        except Exception as e:
            logger.error(f"Failed to fetch grouped daily bars for {target_date}: {e}")
            return None
