"""Market snapshot data models for TradeScout."""

from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True)
class TickerSnapshot:
    """Individual ticker snapshot from market data."""

    symbol: str

    # Previous day data
    prev_close: Optional[Decimal]
    prev_volume: Optional[int]

    # Current day data
    open_price: Optional[Decimal]
    high_price: Optional[Decimal]
    low_price: Optional[Decimal]
    close_price: Optional[Decimal]
    volume: Optional[int]
    vwap: Optional[Decimal]

    # Latest trade
    last_price: Optional[Decimal]
    last_timestamp: Optional[datetime]

    # Market status
    market_status: Optional[str]

    @property
    def change(self) -> Optional[Decimal]:
        """Calculate price change from previous close."""
        if self.last_price and self.prev_close:
            return self.last_price - self.prev_close
        return None

    @property
    def change_percent(self) -> Optional[Decimal]:
        """Calculate percentage change from previous close."""
        if self.change and self.prev_close and self.prev_close != 0:
            return (self.change / self.prev_close) * 100
        return None


@dataclass(frozen=True)
class MarketSnapshot:
    """Complete market snapshot with multiple tickers."""

    tickers: Dict[str, TickerSnapshot]
    timestamp: datetime
    market_status: str
    total_symbols: int

    @classmethod
    def from_polygon_data(cls, polygon_data: Dict) -> 'MarketSnapshot':
        """Create MarketSnapshot from Polygon API response."""
        tickers = {}

        for ticker_data in polygon_data.get('results', []):
            symbol = ticker_data.get('ticker', '')
            if not symbol:
                continue

            # Parse previous day data
            prev_day = ticker_data.get('prevDay', {})

            # Parse current day data
            day = ticker_data.get('day', {})

            # Parse last quote/trade
            last_quote = ticker_data.get('lastQuote', {})
            last_trade = ticker_data.get('lastTrade', {})

            snapshot = TickerSnapshot(
                symbol=symbol,
                prev_close=Decimal(str(prev_day.get('c'))) if prev_day.get('c') else None,
                prev_volume=prev_day.get('v'),
                open_price=Decimal(str(day.get('o'))) if day.get('o') else None,
                high_price=Decimal(str(day.get('h'))) if day.get('h') else None,
                low_price=Decimal(str(day.get('l'))) if day.get('l') else None,
                close_price=Decimal(str(day.get('c'))) if day.get('c') else None,
                volume=day.get('v'),
                vwap=Decimal(str(day.get('vw'))) if day.get('vw') else None,
                last_price=Decimal(str(last_trade.get('p'))) if last_trade.get('p') else None,
                last_timestamp=datetime.fromtimestamp(last_trade.get('t') / 1000) if last_trade.get('t') else None,
                market_status=ticker_data.get('market_status')
            )

            tickers[symbol] = snapshot

        return cls(
            tickers=tickers,
            timestamp=datetime.now(),
            market_status=polygon_data.get('status', 'unknown'),
            total_symbols=len(tickers)
        )


