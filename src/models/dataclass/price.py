"""Price data models for TradeScout."""

from dataclasses import dataclass
from datetime import datetime, date
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class AssetPrice:
    """Unified asset pricing data from snapshot API.

    Represents a single snapshot of asset pricing data including:
    - Previous day session data (reference prices)
    - Current day regular session data
    - Last minute bar data (current real-time price)
    """

    # Primary identification
    id: int
    asset_id: int
    symbol: str

    # Provider tracking
    provider_id: int
    provider_updated_at: int  # Provider's 'updated' field (nanoseconds for Polygon)
    trade_date: date          # Date in market timezone

    # Metadata (required field)
    updated_at: datetime

    # Previous Day Data (prevDay.* from snapshot) - optional fields with defaults
    # This is THE reference price for change calculations
    prevday_open: Optional[Decimal] = None
    prevday_high: Optional[Decimal] = None
    prevday_low: Optional[Decimal] = None
    prevday_close: Optional[Decimal] = None  # THE reference price
    prevday_volume: Optional[int] = None
    prevday_vwap: Optional[Decimal] = None

    # Current Day Regular Session (day.* from snapshot) - optional fields with defaults
    day_open: Optional[Decimal] = None
    day_high: Optional[Decimal] = None
    day_low: Optional[Decimal] = None
    day_close: Optional[Decimal] = None  # Regular session close (4:00 PM)
    day_volume: Optional[int] = None
    day_vwap: Optional[Decimal] = None

    # Last Minute Bar Data (min.* from snapshot) - optional fields with defaults
    # This is the current real-time price
    min_timestamp: Optional[int] = None        # Timestamp (milliseconds)
    min_open: Optional[Decimal] = None
    min_high: Optional[Decimal] = None
    min_low: Optional[Decimal] = None
    min_close: Optional[Decimal] = None        # Last traded price (any session)
    min_volume: Optional[int] = None
    min_vwap: Optional[Decimal] = None
    min_accumulated_volume: Optional[int] = None
    min_num_trades: Optional[int] = None