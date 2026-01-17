"""Alpaca API adapter for snapshot data.

Implements SnapshotProvider protocol using Alpaca's market data API.
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime
from decimal import Decimal

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockLatestQuoteRequest, StockSnapshotRequest
from alpaca.data.models import Snapshot as AlpacaSnapshot

from models.dataclass.snapshot import MarketSnapshot, TickerSnapshot, MinuteBar
from api.providers.protocols.snapshot_provider import SnapshotProvider

logger = logging.getLogger(__name__)


class AlpacaSnapshotAdapter(SnapshotProvider):
    """Adapter for Alpaca snapshot data API.

    Implements SnapshotProvider protocol using alpaca-py library.
    Transforms Alpaca's snapshot data to TradeScout's domain models.
    """

    def __init__(self, api_key: str, secret_key: str):
        """Initialize Alpaca snapshot adapter.

        Args:
            api_key: Alpaca API key
            secret_key: Alpaca secret key

        Raises:
            ValueError: If API key or secret key is empty
        """
        if not api_key or not api_key.strip():
            raise ValueError("Alpaca API key is required")
        if not secret_key or not secret_key.strip():
            raise ValueError("Alpaca secret key is required")

        self.api_key = api_key
        self.secret_key = secret_key
        self.client = StockHistoricalDataClient(api_key, secret_key)

    def fetch_bulk_market_snapshot(self) -> Optional[MarketSnapshot]:
        """Fetch snapshots for ALL tickers in one call.

        Note: Alpaca's snapshot API doesn't support bulk "all tickers" like Polygon.
        This method will raise NotImplementedError. Use fetch_single_ticker_snapshot
        for individual symbols, or provide a list of symbols.

        Returns:
            MarketSnapshot containing ticker snapshots, or None if error

        Raises:
            NotImplementedError: Alpaca doesn't support bulk "all tickers" snapshot
        """
        logger.warning(
            "Alpaca does not support bulk 'all tickers' snapshot. "
            "Use fetch_single_ticker_snapshot() or provide a symbol list."
        )
        raise NotImplementedError(
            "Alpaca snapshot API requires explicit symbol list. "
            "Cannot fetch all market tickers in one call."
        )

    def fetch_single_ticker_snapshot(self, symbol: str) -> Optional[TickerSnapshot]:
        """Fetch snapshot for a single ticker.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')

        Returns:
            TickerSnapshot or None if error
        """
        try:
            # Fetch snapshot from Alpaca
            request = StockSnapshotRequest(symbol_or_symbols=symbol)
            snapshots = self.client.get_stock_snapshot(request)

            if not snapshots or symbol not in snapshots:
                logger.warning(f"No snapshot data returned for {symbol}")
                return None

            alpaca_snapshot = snapshots[symbol]

            # Transform to our TickerSnapshot model
            ticker_snapshot = self._transform_alpaca_snapshot(symbol, alpaca_snapshot)

            logger.debug(f"Successfully fetched snapshot for {symbol} from Alpaca")
            return ticker_snapshot

        except Exception as e:
            logger.error(f"Error fetching snapshot for {symbol} from Alpaca: {e}")
            return None

    def fetch_multiple_ticker_snapshots(self, symbols: list[str]) -> Optional[MarketSnapshot]:
        """Fetch snapshots for multiple tickers.

        This is a custom method that allows fetching snapshots for a specific list
        of symbols. More efficient than calling fetch_single_ticker_snapshot repeatedly.

        Args:
            symbols: List of stock symbols (e.g., ['AAPL', 'MSFT', 'GOOGL'])

        Returns:
            MarketSnapshot containing requested ticker snapshots, or None if error
        """
        try:
            # Fetch snapshots from Alpaca (supports multiple symbols)
            request = StockSnapshotRequest(symbol_or_symbols=symbols)
            alpaca_snapshots = self.client.get_stock_snapshot(request)

            if not alpaca_snapshots:
                logger.warning(f"No snapshot data returned for symbols: {symbols}")
                return None

            # Transform each Alpaca snapshot to our model
            tickers = {}
            for symbol, alpaca_snapshot in alpaca_snapshots.items():
                ticker_snapshot = self._transform_alpaca_snapshot(symbol, alpaca_snapshot)
                if ticker_snapshot:
                    tickers[symbol] = ticker_snapshot

            # Create MarketSnapshot
            market_snapshot = MarketSnapshot(
                tickers=tickers,
                timestamp=datetime.now(),
                market_status="open",  # Alpaca doesn't provide market status in snapshot
                total_symbols=len(tickers)
            )

            logger.debug(f"Successfully fetched {len(tickers)} snapshots from Alpaca")
            return market_snapshot

        except Exception as e:
            logger.error(f"Error fetching multiple snapshots from Alpaca: {e}")
            return None

    def _transform_alpaca_snapshot(
        self,
        symbol: str,
        alpaca_snapshot: AlpacaSnapshot
    ) -> Optional[TickerSnapshot]:
        """Transform Alpaca snapshot to TradeScout TickerSnapshot.

        Args:
            symbol: Stock symbol
            alpaca_snapshot: Alpaca Snapshot object

        Returns:
            TickerSnapshot or None if transformation fails
        """
        try:
            # Alpaca snapshot structure:
            # - latest_trade: most recent trade
            # - latest_quote: most recent quote (bid/ask)
            # - minute_bar: most recent minute bar
            # - daily_bar: current day's bar
            # - previous_daily_bar: previous day's bar

            # Previous day data
            prev_bar = alpaca_snapshot.previous_daily_bar
            prev_open = Decimal(str(prev_bar.open)) if prev_bar and prev_bar.open else None
            prev_high = Decimal(str(prev_bar.high)) if prev_bar and prev_bar.high else None
            prev_low = Decimal(str(prev_bar.low)) if prev_bar and prev_bar.low else None
            prev_close = Decimal(str(prev_bar.close)) if prev_bar and prev_bar.close else None
            prev_volume = int(prev_bar.volume) if prev_bar and prev_bar.volume else None
            prev_vwap = Decimal(str(prev_bar.vwap)) if prev_bar and prev_bar.vwap else None

            # Current day data (regular session)
            day_bar = alpaca_snapshot.daily_bar
            open_price = Decimal(str(day_bar.open)) if day_bar and day_bar.open else None
            high_price = Decimal(str(day_bar.high)) if day_bar and day_bar.high else None
            low_price = Decimal(str(day_bar.low)) if day_bar and day_bar.low else None
            close_price = Decimal(str(day_bar.close)) if day_bar and day_bar.close else None
            volume = int(day_bar.volume) if day_bar and day_bar.volume else None
            vwap = Decimal(str(day_bar.vwap)) if day_bar and day_bar.vwap else None

            # Latest trade
            latest_trade = alpaca_snapshot.latest_trade
            last_price = Decimal(str(latest_trade.price)) if latest_trade and latest_trade.price else None
            last_timestamp = latest_trade.timestamp if latest_trade else None

            # Minute bar (includes extended hours)
            min_bar_data = alpaca_snapshot.minute_bar
            min_bar = None
            if min_bar_data:
                min_bar = MinuteBar(
                    timestamp=int(min_bar_data.timestamp.timestamp() * 1000) if min_bar_data.timestamp else None,
                    open=Decimal(str(min_bar_data.open)) if min_bar_data.open else None,
                    high=Decimal(str(min_bar_data.high)) if min_bar_data.high else None,
                    low=Decimal(str(min_bar_data.low)) if min_bar_data.low else None,
                    close=Decimal(str(min_bar_data.close)) if min_bar_data.close else None,
                    volume=int(min_bar_data.volume) if min_bar_data.volume else None,
                    vwap=Decimal(str(min_bar_data.vwap)) if min_bar_data.vwap else None,
                    accumulated_volume=None,  # Alpaca doesn't provide accumulated volume
                    num_trades=int(min_bar_data.trade_count) if min_bar_data.trade_count else None
                )

            # Create TickerSnapshot
            ticker_snapshot = TickerSnapshot(
                symbol=symbol,
                prev_open=prev_open,
                prev_high=prev_high,
                prev_low=prev_low,
                prev_close=prev_close,
                prev_volume=prev_volume,
                prev_vwap=prev_vwap,
                open_price=open_price,
                high_price=high_price,
                low_price=low_price,
                close_price=close_price,
                volume=volume,
                vwap=vwap,
                last_price=last_price,
                last_timestamp=last_timestamp,
                min_bar=min_bar,
                updated_ns=None,  # Alpaca doesn't provide this
                market_status=None  # Alpaca doesn't provide market status in snapshot
            )

            return ticker_snapshot

        except Exception as e:
            logger.error(f"Error transforming Alpaca snapshot for {symbol}: {e}")
            return None

    def get_provider_name(self) -> str:
        """Get provider name for logging/debugging.

        Returns:
            Provider identifier string
        """
        return "alpaca"
