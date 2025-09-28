"""Unit tests for asset and market models."""

import pytest
from datetime import datetime

from models.asset import Asset, AssetType, AssetClass
from models.market import Market


class TestAsset:
    """Test Asset model."""

    def test_create_asset(self):
        """Test basic Asset creation."""
        asset = Asset(
            id=1,
            symbol="AAPL",
            name="Apple Inc.",
            market_id=1,
            asset_type=AssetType.STOCK,
            asset_class=AssetClass.EQUITY,
            currency="USD",
            provider_id=1,
            created_at=datetime(2025, 1, 1, 12, 0, 0),
            updated_at=datetime(2025, 1, 1, 12, 0, 0),
            lot_size=1,
            tick_size=None,
            is_active=True,
            is_delisted=False,
            listing_date=None,
            delisting_date=None
        )

        assert asset.symbol == "AAPL"
        assert asset.name == "Apple Inc."
        assert asset.asset_type == AssetType.STOCK
        assert asset.asset_class == AssetClass.EQUITY
        assert asset.is_active is True
        assert asset.is_delisted is False

    def test_asset_types_enum(self):
        """Test AssetType enum values."""
        assert AssetType.STOCK.value == "stock"
        assert AssetType.ETF.value == "etf"
        assert AssetType.REIT.value == "reit"

    def test_asset_class_enum(self):
        """Test AssetClass enum values."""
        assert AssetClass.EQUITY.value == "equity"
        assert AssetClass.FIXED_INCOME.value == "fixed_income"
        assert AssetClass.COMMODITY.value == "commodity"

    def test_asset_with_optional_fields(self):
        """Test Asset creation with optional fields populated."""
        listing_date = datetime(2020, 1, 1)

        asset = Asset(
            id=2,
            symbol="NEWCO",
            name="New Company Inc.",
            market_id=1,
            asset_type=AssetType.STOCK,
            asset_class=AssetClass.EQUITY,
            currency="USD",
            provider_id=1,
            created_at=datetime(2025, 1, 1, 12, 0, 0),
            updated_at=datetime(2025, 1, 1, 12, 0, 0),
            lot_size=100,
            tick_size=0.01,
            is_active=True,
            is_delisted=False,
            listing_date=listing_date,
            delisting_date=None
        )

        assert asset.lot_size == 100
        assert asset.tick_size == 0.01
        assert asset.listing_date == listing_date

    def test_delisted_asset(self):
        """Test creating a delisted asset."""
        delisting_date = datetime(2024, 12, 31)

        asset = Asset(
            id=3,
            symbol="DELISTED",
            name="Delisted Company Inc.",
            market_id=1,
            asset_type=AssetType.STOCK,
            asset_class=AssetClass.EQUITY,
            currency="USD",
            provider_id=1,
            created_at=datetime(2025, 1, 1, 12, 0, 0),
            updated_at=datetime(2025, 1, 1, 12, 0, 0),
            lot_size=1,
            tick_size=None,
            is_active=False,
            is_delisted=True,
            listing_date=None,
            delisting_date=delisting_date
        )

        assert asset.is_active is False
        assert asset.is_delisted is True
        assert asset.delisting_date == delisting_date


class TestMarket:
    """Test Market model."""

    def test_create_market(self):
        """Test basic Market creation."""
        market = Market(
            id=1,
            code="XNYS",
            name="New York Stock Exchange",
            country="US",
            timezone="America/New_York",
            currency="USD",
            created_at=datetime(2025, 1, 1, 12, 0, 0),
            updated_at=datetime(2025, 1, 1, 12, 0, 0),
            premarket_start_time="04:00:00",
            premarket_end_time="09:30:00",
            regular_open_time="09:30:00",
            regular_close_time="16:00:00",
            afterhours_start_time="16:00:00",
            afterhours_end_time="20:00:00",
            is_active=True
        )

        assert market.code == "XNYS"
        assert market.name == "New York Stock Exchange"
        assert market.country == "US"
        assert market.timezone == "America/New_York"
        assert market.currency == "USD"
        assert market.is_active is True

    def test_market_trading_hours(self):
        """Test market trading hours."""
        market = Market(
            id=1,
            code="XNAS",
            name="NASDAQ",
            country="US",
            timezone="America/New_York",
            currency="USD",
            created_at=datetime(2025, 1, 1, 12, 0, 0),
            updated_at=datetime(2025, 1, 1, 12, 0, 0),
            premarket_start_time="04:00:00",
            premarket_end_time="09:30:00",
            regular_open_time="09:30:00",
            regular_close_time="16:00:00",
            afterhours_start_time="16:00:00",
            afterhours_end_time="20:00:00",
            is_active=True
        )

        # Test that time fields are stored as expected
        assert market.premarket_start_time == "04:00:00"
        assert market.premarket_end_time == "09:30:00"
        assert market.regular_open_time == "09:30:00"
        assert market.regular_close_time == "16:00:00"
        assert market.afterhours_start_time == "16:00:00"
        assert market.afterhours_end_time == "20:00:00"

    def test_market_minimal_creation(self):
        """Test Market creation with minimal required fields."""
        market = Market(
            id=2,
            code="TEST",
            name="Test Exchange",
            country="US",
            timezone="UTC",
            currency="USD",
            created_at=datetime(2025, 1, 1, 12, 0, 0),
            updated_at=datetime(2025, 1, 1, 12, 0, 0),
            premarket_start_time=None,
            premarket_end_time=None,
            regular_open_time=None,
            regular_close_time=None,
            afterhours_start_time=None,
            afterhours_end_time=None,
            is_active=True
        )

        assert market.code == "TEST"
        assert market.premarket_start_time is None
        assert market.regular_open_time is None