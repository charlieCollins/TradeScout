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

    def fetch_minute_bars(
        self,
        symbol: str,
        from_datetime: datetime,
        to_datetime: datetime,
        adjusted: bool = True
    ) -> Optional[List[Dict[str, Any]]]:
        """Fetch minute-level bars for a symbol within a time range.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            from_datetime: Start datetime (inclusive)
            to_datetime: End datetime (inclusive)
            adjusted: Whether to return adjusted prices (default: True)

        Returns:
            List of bar dictionaries with fields: o, h, l, c, v, vw, t, n
            Or None if error

        Example response bar:
            {
                "o": 178.35,     # Open
                "h": 178.44,     # High
                "l": 178.34,     # Low
                "c": 178.39,     # Close
                "v": 52438,      # Volume
                "vw": 178.3817,  # Volume weighted average
                "t": 1696611600000,  # Timestamp (milliseconds)
                "n": 445         # Number of transactions
            }
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

            results = raw_data["results"]
            logger.debug(f"Fetched {len(results)} minute bars for {symbol} ({from_datetime} to {to_datetime})")

            return results

        except Exception as e:
            logger.error(f"Failed to fetch minute bars for {symbol}: {e}")
            return None

    def get_daily_aggregates(
        self,
        symbol: str,
        from_date: date,
        to_date: date,
        adjusted: bool = True
    ) -> Optional[List[Dict[str, Any]]]:
        """Fetch daily aggregates for a symbol within a date range.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            from_date: Start date (inclusive)
            to_date: End date (inclusive)
            adjusted: Whether to return adjusted prices (default: True)

        Returns:
            List of daily bar dictionaries with fields: o, h, l, c, v, vw, t, n
            Or None if error

        Example response bar:
            {
                "o": 178.35,     # Open
                "h": 180.50,     # High
                "l": 177.25,     # Low
                "c": 179.80,     # Close
                "v": 52438000,   # Volume
                "vw": 179.1234,  # Volume weighted average
                "t": 1696611600000,  # Timestamp (milliseconds)
                "n": 445000      # Number of transactions
            }
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

            results = raw_data["results"]

            # Convert timestamps to more usable format
            for bar in results:
                bar['open'] = bar.get('o')
                bar['high'] = bar.get('h')
                bar['low'] = bar.get('l')
                bar['close'] = bar.get('c')
                bar['volume'] = bar.get('v')
                bar['timestamp'] = bar.get('t')

            logger.debug(f"Fetched {len(results)} daily bars for {symbol} ({from_date} to {to_date})")
            return results

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
    ) -> Optional[List[Dict[str, Any]]]:
        """Fetch intraday aggregates for a symbol on a specific date.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            date: Date string in YYYY-MM-DD format
            timespan: Timespan ('minute', 'hour')
            multiplier: Multiplier for timespan (1, 5, 15, etc.)
            adjusted: Whether to return adjusted prices (default: True)

        Returns:
            List of intraday bar dictionaries or None if error
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

            results = raw_data["results"]

            # Convert timestamps to more usable format
            for bar in results:
                bar['open'] = bar.get('o')
                bar['high'] = bar.get('h')
                bar['low'] = bar.get('l')
                bar['close'] = bar.get('c')
                bar['volume'] = bar.get('v')
                bar['timestamp'] = bar.get('t')

            logger.debug(f"Fetched {len(results)} {timespan} bars for {symbol} on {date}")
            return results

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
            total_volume = sum(bar.get("v", 0) for bar in bars)

            # Get time range of actual bars
            if bars:
                first_bar_ts = datetime.fromtimestamp(bars[0]['t'] / 1000)
                last_bar_ts = datetime.fromtimestamp(bars[-1]['t'] / 1000)
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
