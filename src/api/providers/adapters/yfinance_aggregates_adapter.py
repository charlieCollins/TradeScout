"""Yahoo Finance adapter for aggregates/bars data.

Implements AggregatesProvider protocol using yfinance library.
Provides free access to daily and limited intraday historical data.
"""

import logging
from typing import Optional, List, Dict
from datetime import datetime, date, timedelta

import yfinance as yf

from models.dataclass.price_bar import PriceBar
from api.providers.protocols.aggregates_provider import AggregatesProvider

logger = logging.getLogger(__name__)


class YFinanceAggregatesAdapter(AggregatesProvider):
    """Adapter for Yahoo Finance historical bars data.

    Implements AggregatesProvider protocol using yfinance library.

    Capabilities:
    - Daily bars: Full history available
    - Minute bars: Last 30 days only (yfinance limitation)
    - Grouped daily bars: Not practical for full market (returns None)
    - Extended hours volume: Supported via prepost=True

    Limitations:
    - No VWAP data
    - Minute bars limited to last 30 days
    - No transaction count data
    - Grouped daily bars for entire market is too slow
    """

    def get_daily_aggregates(
        self,
        symbol: str,
        from_date: date,
        to_date: date,
        adjusted: bool = True
    ) -> Optional[List[PriceBar]]:
        """Fetch daily bars for a symbol using yfinance.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            from_date: Start date (inclusive)
            to_date: End date (inclusive)
            adjusted: Whether to return adjusted prices

        Returns:
            List of PriceBar objects, or None if error
        """
        try:
            logger.debug(f"Fetching daily bars for {symbol} from {from_date} to {to_date}")

            # yfinance end date is exclusive, add 1 day
            end_date = to_date + timedelta(days=1)

            df = yf.download(
                symbol,
                start=from_date.isoformat(),
                end=end_date.isoformat(),
                interval="1d",
                auto_adjust=adjusted,
                progress=False
            )

            if df is None or df.empty:
                logger.warning(f"No daily data returned for {symbol}")
                return []

            return self._transform_dataframe(df, symbol)

        except Exception as e:
            logger.error(f"Error fetching daily bars for {symbol}: {e}")
            return None

    def fetch_minute_bars(
        self,
        symbol: str,
        from_datetime: datetime,
        to_datetime: datetime,
        adjusted: bool = True
    ) -> Optional[List[PriceBar]]:
        """Fetch minute-level bars using yfinance.

        Note: yfinance only provides intraday data for the last 30 days.

        Args:
            symbol: Stock symbol
            from_datetime: Start datetime
            to_datetime: End datetime
            adjusted: Whether to return adjusted prices

        Returns:
            List of PriceBar objects, or None if error
        """
        try:
            cutoff = datetime.now() - timedelta(days=30)
            if from_datetime < cutoff:
                logger.warning(
                    f"yfinance only provides minute bars for last 30 days. "
                    f"Requested from {from_datetime.date()}, adjusting to {cutoff.date()}"
                )
                from_datetime = cutoff

            logger.debug(f"Fetching minute bars for {symbol}")

            end_date = to_datetime + timedelta(days=1)

            df = yf.download(
                symbol,
                start=from_datetime.strftime('%Y-%m-%d'),
                end=end_date.strftime('%Y-%m-%d'),
                interval="1m",
                auto_adjust=adjusted,
                prepost=True,
                progress=False
            )

            if df is None or df.empty:
                logger.warning(f"No minute data returned for {symbol}")
                return []

            bars = self._transform_dataframe(df, symbol)

            # Filter to exact datetime range
            filtered = [
                b for b in bars
                if from_datetime <= b.timestamp <= to_datetime
            ]
            return filtered

        except Exception as e:
            logger.error(f"Error fetching minute bars for {symbol}: {e}")
            return None

    def fetch_grouped_daily_bars(
        self,
        target_date: date,
        adjusted: bool = True
    ) -> Optional[Dict[str, PriceBar]]:
        """Fetch end-of-day bars for all stocks on a date.

        Not practical with yfinance for full market (thousands of symbols).
        Returns None to signal that callers should use an alternative approach.

        Args:
            target_date: Trading date
            adjusted: Whether to return adjusted prices

        Returns:
            None (not supported for full market via yfinance)
        """
        logger.warning(
            "fetch_grouped_daily_bars not supported by yfinance adapter "
            "(would require downloading all symbols individually). "
            "Use backfill_market_data with individual symbols instead."
        )
        return None

    def calculate_extended_hours_volume(
        self,
        symbol: str,
        trading_date: date,
        session: str = "afterhours"
    ) -> Optional[int]:
        """Calculate extended hours volume using yfinance prepost data.

        Args:
            symbol: Stock symbol
            trading_date: Trading date
            session: "premarket" or "afterhours"

        Returns:
            Total volume for the session, or None if error
        """
        try:
            end_date = trading_date + timedelta(days=1)

            df = yf.download(
                symbol,
                start=trading_date.isoformat(),
                end=end_date.isoformat(),
                interval="1m",
                prepost=True,
                progress=False
            )

            if df is None or df.empty:
                return None

            # Filter by session time
            if session == "premarket":
                # Premarket: 4:00 AM - 9:30 AM ET
                mask = df.index.hour < 9
                mask |= (df.index.hour == 9) & (df.index.minute < 30)
                mask &= df.index.hour >= 4
            elif session == "afterhours":
                # Afterhours: 4:00 PM - 8:00 PM ET
                mask = df.index.hour >= 16
                mask &= df.index.hour < 20
            else:
                logger.warning(f"Unknown session type: {session}")
                return None

            session_df = df[mask]

            if session_df.empty:
                return 0

            # Handle multi-level columns from yfinance
            if isinstance(session_df.columns, pd.MultiIndex):
                volume = int(session_df[("Volume", symbol)].sum())
            else:
                volume = int(session_df["Volume"].sum())

            return volume

        except Exception as e:
            logger.error(f"Error calculating extended hours volume for {symbol}: {e}")
            return None

    def _transform_dataframe(self, df, symbol: str) -> List[PriceBar]:
        """Transform yfinance DataFrame to list of PriceBar objects.

        Args:
            df: yfinance DataFrame with OHLCV data
            symbol: Stock symbol (needed for multi-level column access)

        Returns:
            List of PriceBar objects
        """
        import pandas as pd

        bars = []
        for idx, row in df.iterrows():
            try:
                # Handle multi-level columns (yfinance returns these for single tickers too)
                if isinstance(df.columns, pd.MultiIndex):
                    open_price = float(row[("Open", symbol)])
                    high_price = float(row[("High", symbol)])
                    low_price = float(row[("Low", symbol)])
                    close_price = float(row[("Close", symbol)])
                    volume = int(row[("Volume", symbol)])
                else:
                    open_price = float(row["Open"])
                    high_price = float(row["High"])
                    low_price = float(row["Low"])
                    close_price = float(row["Close"])
                    volume = int(row["Volume"])

                # Convert timestamp
                if isinstance(idx, pd.Timestamp):
                    ts = idx.to_pydatetime()
                else:
                    ts = datetime.fromisoformat(str(idx))

                timestamp_ms = int(ts.timestamp() * 1000)

                bar = PriceBar(
                    open=open_price,
                    high=high_price,
                    low=low_price,
                    close=close_price,
                    volume=volume,
                    timestamp=ts,
                    timestamp_ms=timestamp_ms,
                    volume_weighted_price=None,
                    num_transactions=None
                )
                bars.append(bar)

            except Exception as e:
                logger.warning(f"Failed to transform bar for {symbol} at {idx}: {e}")
                continue

        return bars

    def get_provider_name(self) -> str:
        return "yfinance"
