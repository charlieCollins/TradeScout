"""Unit tests for price models."""

import pytest
from datetime import datetime, date
from decimal import Decimal

from models.price import AssetPrice


class TestAssetPrice:
    """Test AssetPrice model."""

    def test_create_asset_price(self):
        """Test basic AssetPrice creation."""
        price = AssetPrice(
            id=1,
            asset_id=100,
            symbol="AAPL",
            provider_id=1,
            provider_updated_at=1727546400000000000,
            trade_date=date(2025, 9, 28),
            updated_at=datetime(2025, 9, 28, 16, 0, 0),

            # Previous day data
            prevday_open=Decimal("149.00"),
            prevday_high=Decimal("151.00"),
            prevday_low=Decimal("148.50"),
            prevday_close=Decimal("150.00"),
            prevday_volume=1000000,
            prevday_vwap=Decimal("149.75"),

            # Current day data
            day_open=Decimal("150.50"),
            day_high=Decimal("152.00"),
            day_low=Decimal("149.50"),
            day_close=Decimal("151.50"),
            day_volume=800000,
            day_vwap=Decimal("151.25"),

            # Minute data
            min_timestamp=1727546400000000000,
            min_open=Decimal("151.40"),
            min_high=Decimal("151.60"),
            min_low=Decimal("151.30"),
            min_close=Decimal("151.50"),
            min_volume=1000,
            min_vwap=Decimal("151.45"),
            min_accumulated_volume=800000,
            min_num_trades=50
        )

        assert price.symbol == "AAPL"
        assert price.asset_id == 100
        assert price.prevday_close == Decimal("150.00")
        assert price.day_close == Decimal("151.50")

    def test_asset_price_with_minimal_data(self):
        """Test AssetPrice with only required fields."""
        price = AssetPrice(
            id=0,
            asset_id=100,
            symbol="AAPL",
            provider_id=1,
            provider_updated_at=0,
            trade_date=date(2025, 9, 28),
            updated_at=datetime(2025, 9, 28, 16, 0, 0),

            # Only previous day close (minimal required data)
            prevday_open=None,
            prevday_high=None,
            prevday_low=None,
            prevday_close=Decimal("150.00"),
            prevday_volume=None,
            prevday_vwap=None,

            # No current day data
            day_open=None,
            day_high=None,
            day_low=None,
            day_close=None,
            day_volume=None,
            day_vwap=None,

            # No minute data
            min_timestamp=None,
            min_open=None,
            min_high=None,
            min_low=None,
            min_close=None,
            min_volume=None,
            min_vwap=None,
            min_accumulated_volume=None,
            min_num_trades=None
        )

        # Should be able to create with minimal data
        assert price.symbol == "AAPL"
        assert price.prevday_close == Decimal("150.00")
        assert price.day_close is None

    def test_asset_price_change_calculation(self):
        """Test change calculations."""
        price = AssetPrice(
            id=1,
            asset_id=100,
            symbol="AAPL",
            provider_id=1,
            provider_updated_at=1727546400000000000,
            trade_date=date(2025, 9, 28),
            updated_at=datetime(2025, 9, 28, 16, 0, 0),

            prevday_open=None,
            prevday_high=None,
            prevday_low=None,
            prevday_close=Decimal("150.00"),
            prevday_volume=None,
            prevday_vwap=None,

            day_open=None,
            day_high=None,
            day_low=None,
            day_close=Decimal("151.50"),  # Current close
            day_volume=None,
            day_vwap=None,

            min_timestamp=None,
            min_open=None,
            min_high=None,
            min_low=None,
            min_close=None,
            min_volume=None,
            min_vwap=None,
            min_accumulated_volume=None,
            min_num_trades=None
        )

        # Test manual change calculation (model doesn't have change property)
        change = price.day_close - price.prevday_close
        assert change == Decimal("1.50")

    def test_asset_price_handles_missing_provider_timestamp(self):
        """Test AssetPrice handles missing provider timestamp (stale/inactive symbols)."""
        price = AssetPrice(
            id=1,
            asset_id=100,
            symbol="STALE",
            provider_id=1,
            provider_updated_at=0,  # No recent update
            trade_date=date(2025, 9, 28),
            updated_at=datetime(2025, 9, 28, 16, 0, 0),

            prevday_open=None,
            prevday_high=None,
            prevday_low=None,
            prevday_close=Decimal("10.00"),
            prevday_volume=None,
            prevday_vwap=None,

            # No current day data for stale symbol
            day_open=None,
            day_high=None,
            day_low=None,
            day_close=None,
            day_volume=None,
            day_vwap=None,

            min_timestamp=None,
            min_open=None,
            min_high=None,
            min_low=None,
            min_close=None,
            min_volume=None,
            min_vwap=None,
            min_accumulated_volume=None,
            min_num_trades=None
        )

        # Should handle stale symbols gracefully
        assert price.symbol == "STALE"
        assert price.provider_updated_at == 0
        assert price.prevday_close == Decimal("10.00")
        assert price.day_close is None