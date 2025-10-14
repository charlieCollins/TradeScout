"""PriceBar domain model - represents OHLCV price data."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class PriceBar:
    """Domain model representing a price bar (OHLCV candle).

    This is the clean interface between API providers and business logic.
    Providers transform their API responses into this standard format.

    Used for historical price data at various timeframes (minute, hour, day).
    """

    # OHLC prices
    open: float
    high: float
    low: float
    close: float

    # Volume
    volume: int  # Number of shares traded

    # Timing
    timestamp: datetime  # Bar start time
    timestamp_ms: int  # Unix timestamp in milliseconds (from API)

    # Optional fields
    volume_weighted_price: Optional[float] = None  # VWAP
    num_transactions: Optional[int] = None  # Number of trades in this bar

    @property
    def range(self) -> float:
        """Calculate price range (high - low)."""
        return self.high - self.low

    @property
    def body(self) -> float:
        """Calculate candle body size (close - open)."""
        return self.close - self.open

    @property
    def is_bullish(self) -> bool:
        """Check if bar closed higher than open."""
        return self.close > self.open

    @property
    def is_bearish(self) -> bool:
        """Check if bar closed lower than open."""
        return self.close < self.open

    def percent_change(self) -> float:
        """Calculate percent change from open to close.

        Returns:
            Percent change (e.g., 2.5 for 2.5% gain)
        """
        if self.open == 0:
            return 0.0
        return ((self.close - self.open) / self.open) * 100
