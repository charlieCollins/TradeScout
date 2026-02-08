"""Yahoo Finance adapter for snapshot data.

Implements SnapshotProvider protocol using yfinance library.
Provides free, unlimited access to market data (unofficial API).
"""

import logging
from typing import Optional, List
from datetime import datetime
from decimal import Decimal

import yfinance as yf
import pandas as pd

from models.dataclass.snapshot import MarketSnapshot, TickerSnapshot, MinuteBar
from api.providers.protocols.snapshot_provider import SnapshotProvider

logger = logging.getLogger(__name__)


class YFinanceSnapshotAdapter(SnapshotProvider):
    """Adapter for Yahoo Finance snapshot data.

    Implements SnapshotProvider protocol using yfinance library.
    Transforms Yahoo's data to TradeScout's domain models.

    Advantages:
    - Free, unlimited access (no API key required)
    - Supports bulk downloads of multiple tickers
    - Includes real-time quotes during market hours
    - Provides previous day data

    Risks:
    - Unofficial API - could break anytime
    - Rate limiting if too aggressive
    - Data may have slight delays
    """

    def __init__(self, symbol_provider: Optional[callable] = None):
        """Initialize Yahoo Finance snapshot adapter.

        Args:
            symbol_provider: Optional callable that returns list of symbols to fetch.
                           If not provided, fetch_bulk_market_snapshot will raise.
        """
        self._symbol_provider = symbol_provider
        self._batch_size = 100  # Process symbols in batches to avoid timeouts

    def set_symbol_provider(self, symbol_provider: callable) -> None:
        """Set the symbol provider for bulk snapshots.

        Args:
            symbol_provider: Callable that returns list of symbols
        """
        self._symbol_provider = symbol_provider

    def fetch_bulk_market_snapshot(self) -> Optional[MarketSnapshot]:
        """Fetch snapshots for all tracked tickers.

        Uses the symbol_provider to get the list of symbols, then fetches
        data for all of them using yfinance bulk download.

        Returns:
            MarketSnapshot containing all ticker snapshots, or None if error
        """
        if not self._symbol_provider:
            logger.error(
                "No symbol_provider configured. Call set_symbol_provider() first "
                "or use fetch_multiple_ticker_snapshots() with explicit symbols."
            )
            return None

        try:
            # Get symbols from provider
            symbols = self._symbol_provider()
            if not symbols:
                logger.warning("Symbol provider returned empty list")
                return None

            logger.info(f"Fetching bulk snapshot for {len(symbols)} symbols via yfinance")
            return self.fetch_multiple_ticker_snapshots(symbols)

        except Exception as e:
            logger.error(f"Error in fetch_bulk_market_snapshot: {e}")
            return None

    def fetch_single_ticker_snapshot(self, symbol: str) -> Optional[TickerSnapshot]:
        """Fetch snapshot for a single ticker.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')

        Returns:
            TickerSnapshot or None if error
        """
        try:
            ticker = yf.Ticker(symbol)

            # Get current quote info
            info = ticker.info

            if not info or 'regularMarketPrice' not in info:
                logger.warning(f"No data returned for {symbol}")
                return None

            snapshot = self._transform_yfinance_info(symbol, info)
            logger.debug(f"Successfully fetched snapshot for {symbol} from yfinance")
            return snapshot

        except Exception as e:
            logger.error(f"Error fetching snapshot for {symbol} from yfinance: {e}")
            return None

    def fetch_multiple_ticker_snapshots(self, symbols: List[str]) -> Optional[MarketSnapshot]:
        """Fetch snapshots for multiple tickers efficiently.

        Uses yfinance bulk download with multithreading for performance.

        Args:
            symbols: List of stock symbols (e.g., ['AAPL', 'MSFT', 'GOOGL'])

        Returns:
            MarketSnapshot containing requested ticker snapshots, or None if error
        """
        if not symbols:
            logger.warning("Empty symbol list provided")
            return None

        try:
            all_tickers = {}
            failed_symbols = []

            # Process in batches to avoid timeouts
            for i in range(0, len(symbols), self._batch_size):
                batch = symbols[i:i + self._batch_size]
                batch_num = (i // self._batch_size) + 1
                total_batches = (len(symbols) + self._batch_size - 1) // self._batch_size

                logger.debug(f"Processing batch {batch_num}/{total_batches} ({len(batch)} symbols)")

                try:
                    batch_tickers = self._fetch_batch(batch)
                    all_tickers.update(batch_tickers)
                except Exception as e:
                    logger.warning(f"Batch {batch_num} failed: {e}")
                    failed_symbols.extend(batch)

            if failed_symbols:
                logger.warning(f"Failed to fetch {len(failed_symbols)} symbols: {failed_symbols[:10]}...")

            if not all_tickers:
                logger.error("No snapshots retrieved")
                return None

            # Create MarketSnapshot
            market_snapshot = MarketSnapshot(
                tickers=all_tickers,
                timestamp=datetime.now(),
                market_status="unknown",  # yfinance doesn't provide market status
                total_symbols=len(all_tickers)
            )

            logger.info(f"Successfully fetched {len(all_tickers)} snapshots from yfinance")
            return market_snapshot

        except Exception as e:
            logger.error(f"Error fetching multiple snapshots from yfinance: {e}")
            return None

    def _fetch_batch(self, symbols: List[str]) -> dict:
        """Fetch a batch of symbols using yfinance download.

        Args:
            symbols: List of symbols to fetch

        Returns:
            Dict mapping symbol to TickerSnapshot
        """
        tickers = {}

        # Download current day + previous day data
        # period="2d" gets us today and yesterday for prev_close calculation
        data = yf.download(
            symbols,
            period="2d",
            interval="1d",
            group_by="ticker",
            threads=True,
            progress=False,
            auto_adjust=False  # Keep raw prices
        )

        if data.empty:
            logger.warning("yfinance download returned empty dataframe")
            return tickers

        # Handle single vs multiple ticker response
        if len(symbols) == 1:
            # Single ticker - data has simple columns
            symbol = symbols[0]
            snapshot = self._transform_single_ticker_df(symbol, data)
            if snapshot:
                tickers[symbol] = snapshot
        else:
            # Multiple tickers - data is multi-indexed
            for symbol in symbols:
                try:
                    if symbol in data.columns.get_level_values(0):
                        ticker_data = data[symbol]
                        snapshot = self._transform_single_ticker_df(symbol, ticker_data)
                        if snapshot:
                            tickers[symbol] = snapshot
                except Exception as e:
                    logger.debug(f"Failed to process {symbol}: {e}")
                    continue

        return tickers

    def _transform_single_ticker_df(
        self,
        symbol: str,
        df: pd.DataFrame
    ) -> Optional[TickerSnapshot]:
        """Transform yfinance DataFrame to TickerSnapshot.

        Args:
            symbol: Stock symbol
            df: DataFrame with OHLCV data (2 days)

        Returns:
            TickerSnapshot or None if transformation fails
        """
        try:
            if df.empty or len(df) < 1:
                return None

            # Get the most recent row (today or last trading day)
            current = df.iloc[-1]

            # Get previous day if available
            prev = df.iloc[-2] if len(df) >= 2 else None

            # Current day data
            open_price = self._safe_decimal(current.get('Open'))
            high_price = self._safe_decimal(current.get('High'))
            low_price = self._safe_decimal(current.get('Low'))
            close_price = self._safe_decimal(current.get('Close'))
            volume = self._safe_int(current.get('Volume'))

            # Previous day data
            prev_open = self._safe_decimal(prev.get('Open')) if prev is not None else None
            prev_high = self._safe_decimal(prev.get('High')) if prev is not None else None
            prev_low = self._safe_decimal(prev.get('Low')) if prev is not None else None
            prev_close = self._safe_decimal(prev.get('Close')) if prev is not None else None
            prev_volume = self._safe_int(prev.get('Volume')) if prev is not None else None

            # Create timestamp for tracking
            now = datetime.now()
            # Convert to nanoseconds since epoch (standard provider timestamp format)
            updated_ns = int(now.timestamp() * 1_000_000_000)

            # Create TickerSnapshot
            snapshot = TickerSnapshot(
                symbol=symbol,
                prev_open=prev_open,
                prev_high=prev_high,
                prev_low=prev_low,
                prev_close=prev_close,
                prev_volume=prev_volume,
                prev_vwap=None,  # yfinance doesn't provide VWAP
                open_price=open_price,
                high_price=high_price,
                low_price=low_price,
                close_price=close_price,
                volume=volume,
                vwap=None,  # yfinance doesn't provide VWAP
                last_price=close_price,  # Use close as last price
                last_timestamp=now,
                min_bar=None,  # Would need intraday data for this
                updated_ns=updated_ns,
                market_status=None
            )

            return snapshot

        except Exception as e:
            logger.debug(f"Error transforming yfinance data for {symbol}: {e}")
            return None

    def _transform_yfinance_info(self, symbol: str, info: dict) -> Optional[TickerSnapshot]:
        """Transform yfinance ticker.info to TickerSnapshot.

        This method uses the real-time info dict which has more current data
        but is slower (one API call per ticker).

        Args:
            symbol: Stock symbol
            info: yfinance ticker.info dictionary

        Returns:
            TickerSnapshot or None if transformation fails
        """
        try:
            # Current market data
            current_price = self._safe_decimal(info.get('regularMarketPrice'))
            open_price = self._safe_decimal(info.get('regularMarketOpen'))
            high_price = self._safe_decimal(info.get('regularMarketDayHigh'))
            low_price = self._safe_decimal(info.get('regularMarketDayLow'))
            volume = self._safe_int(info.get('regularMarketVolume'))

            # Previous day data
            prev_close = self._safe_decimal(info.get('regularMarketPreviousClose'))

            # Create timestamp for tracking
            now = datetime.now()
            # Convert to nanoseconds since epoch (standard provider timestamp format)
            updated_ns = int(now.timestamp() * 1_000_000_000)

            # Create TickerSnapshot
            snapshot = TickerSnapshot(
                symbol=symbol,
                prev_open=None,  # Not available in info
                prev_high=None,
                prev_low=None,
                prev_close=prev_close,
                prev_volume=None,
                prev_vwap=None,
                open_price=open_price,
                high_price=high_price,
                low_price=low_price,
                close_price=current_price,
                volume=volume,
                vwap=None,
                last_price=current_price,
                last_timestamp=now,
                min_bar=None,
                updated_ns=updated_ns,
                market_status=None
            )

            return snapshot

        except Exception as e:
            logger.error(f"Error transforming yfinance info for {symbol}: {e}")
            return None

    def _safe_decimal(self, value) -> Optional[Decimal]:
        """Safely convert value to Decimal.

        Args:
            value: Value to convert

        Returns:
            Decimal or None if conversion fails
        """
        if value is None or pd.isna(value):
            return None
        try:
            return Decimal(str(value))
        except (ValueError, TypeError):
            return None

    def _safe_int(self, value) -> Optional[int]:
        """Safely convert value to int.

        Args:
            value: Value to convert

        Returns:
            int or None if conversion fails
        """
        if value is None or pd.isna(value):
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    def get_provider_name(self) -> str:
        """Get provider name for logging/debugging.

        Returns:
            Provider identifier string
        """
        return "yfinance"
