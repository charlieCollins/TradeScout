"""SQLModel version of AssetPrice - Repository/DAO pattern implementation.

This file contains the SQLModel version for the new architecture.
AssetPrice stores market snapshot data (price, volume, VWAP) for gap trading analysis.

The data comes from market snapshot providers (yfinance, etc.) and is stored for:
1. Gap analysis (comparing prev_close to current prices)
2. Historical tracking
3. Performance validation
"""

from datetime import datetime, date
from typing import Optional
from decimal import Decimal
from sqlmodel import Field, SQLModel


class AssetPriceSQLModel(SQLModel, table=True):
    """SQLModel representation of AssetPrice - market snapshot storage.

    This model maps to the existing 'asset_prices' table in the database.
    It stores snapshot data including previous day, current day, and minute bar data.

    Key Use Cases:
    - Gap analysis: Compare prev_close to current prices
    - Extended hours tracking: min_* fields include premarket/afterhours
    - Historical data: Track price movements over time
    """

    __tablename__ = "asset_prices"

    # ============================================================================
    # PRIMARY IDENTIFICATION
    # ============================================================================

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        description="Auto-incrementing primary key"
    )

    asset_id: int = Field(
        foreign_key="assets.id",
        index=True,
        description="Asset this price data belongs to"
    )

    symbol: str = Field(
        index=True,
        max_length=20,
        description="Stock symbol (redundant but useful for queries)"
    )

    # ============================================================================
    # PROVIDER TRACKING
    # ============================================================================

    provider_id: int = Field(
        foreign_key="providers.id",
        description="Data provider (yfinance, nasdaq_trader, etc.)"
    )

    provider_updated_at: Optional[int] = Field(
        default=None,
        description="Provider's update timestamp (nanoseconds/milliseconds)"
    )

    trade_date: date = Field(
        index=True,
        description="Trading date (derived from provider_updated_at)"
    )

    # ============================================================================
    # PREVIOUS DAY DATA (previous day OHLCV)
    # ============================================================================

    prevday_open: Optional[Decimal] = Field(
        default=None,
        max_digits=12,
        decimal_places=4,
        description="Previous day open price"
    )

    prevday_high: Optional[Decimal] = Field(
        default=None,
        max_digits=12,
        decimal_places=4,
        description="Previous day high price"
    )

    prevday_low: Optional[Decimal] = Field(
        default=None,
        max_digits=12,
        decimal_places=4,
        description="Previous day low price"
    )

    prevday_close: Optional[Decimal] = Field(
        default=None,
        max_digits=12,
        decimal_places=4,
        description="Previous day close price - THE reference for gap analysis"
    )

    prevday_volume: Optional[int] = Field(
        default=None,
        description="Previous day volume"
    )

    prevday_vwap: Optional[Decimal] = Field(
        default=None,
        max_digits=12,
        decimal_places=4,
        description="Previous day volume-weighted average price"
    )

    # ============================================================================
    # CURRENT DAY REGULAR SESSION (regular hours OHLCV)
    # ============================================================================

    day_open: Optional[Decimal] = Field(
        default=None,
        max_digits=12,
        decimal_places=4,
        description="Current day open price (9:30 AM)"
    )

    day_high: Optional[Decimal] = Field(
        default=None,
        max_digits=12,
        decimal_places=4,
        description="Current day high price (regular session)"
    )

    day_low: Optional[Decimal] = Field(
        default=None,
        max_digits=12,
        decimal_places=4,
        description="Current day low price (regular session)"
    )

    day_close: Optional[Decimal] = Field(
        default=None,
        max_digits=12,
        decimal_places=4,
        description="Current day close price (4:00 PM)"
    )

    day_volume: Optional[int] = Field(
        default=None,
        description="Current day volume (regular session)"
    )

    day_vwap: Optional[Decimal] = Field(
        default=None,
        max_digits=12,
        decimal_places=4,
        description="Current day volume-weighted average price"
    )

    # ============================================================================
    # LAST MINUTE BAR DATA (latest minute bar)
    # Includes premarket and afterhours data
    # ============================================================================

    min_timestamp: Optional[int] = Field(
        default=None,
        description="Minute bar timestamp (milliseconds)"
    )

    min_open: Optional[Decimal] = Field(
        default=None,
        max_digits=12,
        decimal_places=4,
        description="Minute bar open price"
    )

    min_high: Optional[Decimal] = Field(
        default=None,
        max_digits=12,
        decimal_places=4,
        description="Minute bar high price"
    )

    min_low: Optional[Decimal] = Field(
        default=None,
        max_digits=12,
        decimal_places=4,
        description="Minute bar low price"
    )

    min_close: Optional[Decimal] = Field(
        default=None,
        max_digits=12,
        decimal_places=4,
        description="Minute bar close (last traded price - any session)"
    )

    min_volume: Optional[int] = Field(
        default=None,
        description="Minute bar volume"
    )

    min_vwap: Optional[Decimal] = Field(
        default=None,
        max_digits=12,
        decimal_places=4,
        description="Minute bar volume-weighted average price"
    )

    min_accumulated_volume: Optional[int] = Field(
        default=None,
        description="Minute bar accumulated volume"
    )

    min_num_trades: Optional[int] = Field(
        default=None,
        description="Minute bar number of trades"
    )

    # ============================================================================
    # METADATA
    # ============================================================================

    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        index=True,
        description="Record update timestamp (UTC)"
    )

    # ============================================================================
    # COMPUTED PROPERTIES
    # ============================================================================

    @property
    def has_prevday_data(self) -> bool:
        """Check if previous day data is available."""
        return self.prevday_close is not None

    @property
    def has_current_day_data(self) -> bool:
        """Check if current day data is available."""
        return self.day_open is not None

    @property
    def has_minute_bar_data(self) -> bool:
        """Check if minute bar data is available."""
        return self.min_close is not None

    @property
    def gap_amount(self) -> Optional[Decimal]:
        """Calculate gap amount (day_open - prevday_close).

        Returns:
            Gap in dollars, or None if data not available
        """
        if self.prevday_close is None or self.day_open is None:
            return None
        return self.day_open - self.prevday_close

    @property
    def gap_percent(self) -> Optional[float]:
        """Calculate gap percentage ((day_open - prevday_close) / prevday_close * 100).

        Returns:
            Gap percentage, or None if data not available
        """
        if self.prevday_close is None or self.day_open is None:
            return None
        if self.prevday_close == 0:
            return None
        return float((self.day_open - self.prevday_close) / self.prevday_close * 100)

    @property
    def current_price(self) -> Optional[Decimal]:
        """Get most current price (prefers min_close, falls back to day_close).

        Returns:
            Most recent price, or None if no data
        """
        return self.min_close or self.day_close

    # ============================================================================
    # MODEL CONFIGURATION
    # ============================================================================

    class Config:
        """SQLModel configuration."""
        json_schema_extra = {
            "example": {
                "id": 1,
                "asset_id": 42,
                "symbol": "AAPL",
                "provider_id": 1,
                "trade_date": "2025-10-12",
                "prevday_close": "175.50",
                "day_open": "178.00",
                "day_high": "180.25",
                "day_low": "177.50",
                "day_close": "179.75",
                "day_volume": 52000000,
                "min_close": "179.80"
            }
        }
