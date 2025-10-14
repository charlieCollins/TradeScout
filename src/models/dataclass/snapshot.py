"""Market snapshot data models for TradeScout."""

from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class MinuteBar:
    """Last minute bar data from market."""

    timestamp: Optional[int]  # milliseconds
    open: Optional[Decimal]
    high: Optional[Decimal]
    low: Optional[Decimal]
    close: Optional[Decimal]
    volume: Optional[int]
    vwap: Optional[Decimal]
    accumulated_volume: Optional[int]
    num_trades: Optional[int]


@dataclass(frozen=True)
class TickerSnapshot:
    """Individual ticker snapshot from market data."""

    symbol: str

    # Previous day data
    prev_open: Optional[Decimal]
    prev_high: Optional[Decimal]
    prev_low: Optional[Decimal]
    prev_close: Optional[Decimal]
    prev_volume: Optional[int]
    prev_vwap: Optional[Decimal]

    # Current day data (regular session)
    open_price: Optional[Decimal]
    high_price: Optional[Decimal]
    low_price: Optional[Decimal]
    close_price: Optional[Decimal]
    volume: Optional[int]
    vwap: Optional[Decimal]

    # Latest trade (deprecated - use min_bar instead)
    last_price: Optional[Decimal]
    last_timestamp: Optional[datetime]

    # Minute bar data (includes premarket/afterhours)
    min_bar: Optional[MinuteBar]

    # Polygon's internal update timestamp (nanoseconds)
    updated_ns: Optional[int]

    # Market status
    market_status: Optional[str]


@dataclass(frozen=True)
class MarketSnapshot:
    """Complete market snapshot with multiple tickers."""

    tickers: Dict[str, TickerSnapshot]
    timestamp: datetime
    market_status: str
    total_symbols: int

    @classmethod
    def from_polygon_data(cls, polygon_data: Dict) -> "MarketSnapshot":
        """Create MarketSnapshot from Polygon API response."""
        tickers = {}

        # Bulk snapshot API returns 'tickers', single ticker returns 'results'
        ticker_list = polygon_data.get("tickers") or polygon_data.get("results", [])

        for ticker_data in ticker_list:
            symbol = ticker_data.get("ticker", "")
            if not symbol:
                continue

            # Parse previous day data
            prev_day = ticker_data.get("prevDay", {})

            # Parse current day data (regular session)
            day = ticker_data.get("day", {})

            # Parse minute bar data (includes extended hours)
            min_data = ticker_data.get("min", {})
            min_bar = None
            if min_data and min_data.get("c") is not None:
                min_bar = MinuteBar(
                    timestamp=min_data.get("t"),
                    open=(
                        Decimal(str(min_data.get("o")))
                        if min_data.get("o") is not None
                        else None
                    ),
                    high=(
                        Decimal(str(min_data.get("h")))
                        if min_data.get("h") is not None
                        else None
                    ),
                    low=(
                        Decimal(str(min_data.get("l")))
                        if min_data.get("l") is not None
                        else None
                    ),
                    close=(
                        Decimal(str(min_data.get("c")))
                        if min_data.get("c") is not None
                        else None
                    ),
                    volume=min_data.get("v"),
                    vwap=(
                        Decimal(str(min_data.get("vw")))
                        if min_data.get("vw") is not None
                        else None
                    ),
                    accumulated_volume=min_data.get("av"),
                    num_trades=min_data.get("n"),
                )

            # Parse last quote/trade (deprecated - use min_bar instead)
            last_quote = ticker_data.get("lastQuote", {})
            last_trade = ticker_data.get("lastTrade", {})

            snapshot = TickerSnapshot(
                symbol=symbol,
                prev_open=(
                    Decimal(str(prev_day.get("o")))
                    if prev_day.get("o") is not None
                    else None
                ),
                prev_high=(
                    Decimal(str(prev_day.get("h")))
                    if prev_day.get("h") is not None
                    else None
                ),
                prev_low=(
                    Decimal(str(prev_day.get("l")))
                    if prev_day.get("l") is not None
                    else None
                ),
                prev_close=(
                    Decimal(str(prev_day.get("c")))
                    if prev_day.get("c") is not None
                    else None
                ),
                prev_volume=prev_day.get("v"),
                prev_vwap=(
                    Decimal(str(prev_day.get("vw")))
                    if prev_day.get("vw") is not None
                    else None
                ),
                open_price=(
                    Decimal(str(day.get("o"))) if day.get("o") is not None else None
                ),
                high_price=(
                    Decimal(str(day.get("h"))) if day.get("h") is not None else None
                ),
                low_price=(
                    Decimal(str(day.get("l"))) if day.get("l") is not None else None
                ),
                close_price=(
                    Decimal(str(day.get("c"))) if day.get("c") is not None else None
                ),
                volume=day.get("v"),
                vwap=Decimal(str(day.get("vw"))) if day.get("vw") is not None else None,
                last_price=(
                    Decimal(str(last_trade.get("p")))
                    if last_trade.get("p") is not None
                    else None
                ),
                last_timestamp=(
                    datetime.fromtimestamp(last_trade.get("t") / 1000)
                    if last_trade.get("t")
                    else None
                ),
                min_bar=min_bar,
                updated_ns=ticker_data.get("updated"),
                market_status=ticker_data.get("market_status"),
            )

            tickers[symbol] = snapshot

        return cls(
            tickers=tickers,
            timestamp=datetime.now(),
            market_status=polygon_data.get("status", "unknown"),
            total_symbols=len(tickers),
        )
