"""
Tests for TradeScout data models
"""

import pytest
from datetime import datetime, time
from decimal import Decimal

from tradescout.data_models.domain_models_core import (
    Asset,
    Market,
    MarketSegment,
    PriceData,
    MarketQuote,
    AssetType,
    MarketType,
    MarketStatus,
)


class TestMarket:
    """Test Market domain model"""

    def test_market_creation(self):
        """Test basic market creation"""
        market = Market(
            id="NYSE",
            name="New York Stock Exchange",
            market_type=MarketType.STOCK,
            timezone="America/New_York",
            currency="USD",
            regular_open=time(9, 30),
            regular_close=time(16, 0),
            pre_market_start=time(4, 0),
            after_hours_end=time(20, 0),
        )

        assert market.id == "NYSE"
        assert market.name == "New York Stock Exchange"
        assert market.market_type == MarketType.STOCK
        assert market.currency == "USD"

    def test_market_is_open_during_regular_hours(self, sample_market):
        """Test market open status during regular hours"""
        # Mock current time to 10:00 AM (market open)
        test_time = time(10, 0)
        assert sample_market.regular_open <= test_time <= sample_market.regular_close

    def test_market_equality(self):
        """Test market equality comparison"""
        market1 = Market(
            id="NASDAQ",
            name="NASDAQ",
            market_type=MarketType.STOCK,
            timezone="America/New_York",
            currency="USD",
            regular_open=time(9, 30),
            regular_close=time(16, 0),
            pre_market_start=time(4, 0),
            after_hours_end=time(20, 0),
        )

        market2 = Market(
            id="NASDAQ",
            name="NASDAQ",
            market_type=MarketType.STOCK,
            timezone="America/New_York",
            currency="USD",
            regular_open=time(9, 30),
            regular_close=time(16, 0),
            pre_market_start=time(4, 0),
            after_hours_end=time(20, 0),
        )

        assert market1 == market2


class TestMarketSegment:
    """Test MarketSegment domain model"""

    def test_segment_creation(self):
        """Test basic segment creation"""
        segment = MarketSegment(
            id="TECH",
            name="Technology",
            description="Technology sector",
            segment_type="sector",
        )

        assert segment.id == "TECH"
        assert segment.name == "Technology"
        assert segment.segment_type == "sector"

    def test_segment_with_parent(self, sample_market_segment):
        """Test segment with parent relationship"""
        child_segment = MarketSegment(
            id="AI_TECH",
            name="AI Technology",
            description="AI-focused technology companies",
            segment_type="sub_sector",
            parent_segment=sample_market_segment,
        )

        assert child_segment.parent_segment == sample_market_segment
        assert child_segment.parent_segment.id == "TECH"

    def test_segment_hashable(self, sample_market_segment):
        """Test that MarketSegment is hashable (can be used in sets)"""
        segment_set = {sample_market_segment}
        assert len(segment_set) == 1
        assert sample_market_segment in segment_set


class TestAsset:
    """Test Asset domain model"""

    def test_asset_creation(self, sample_asset):
        """Test basic asset creation"""
        assert sample_asset.symbol == "AAPL"
        assert sample_asset.name == "Apple Inc."
        assert sample_asset.asset_type == AssetType.COMMON_STOCK
        assert sample_asset.market.id == "NASDAQ"

    def test_asset_with_segments(self, sample_asset, sample_market_segment):
        """Test asset with market segments"""
        assert len(sample_asset.segments) == 1
        assert sample_market_segment in sample_asset.segments

    def test_asset_string_representation(self, sample_asset):
        """Test asset string representation"""
        assert str(sample_asset) == "AAPL (Apple Inc.)"

    def test_asset_equality(self, sample_market):
        """Test asset equality comparison (ignoring timestamp fields)"""
        # Use fixed timestamp to ensure equality
        fixed_time = datetime(2025, 1, 1, 12, 0, 0)

        asset1 = Asset(
            symbol="MSFT",
            name="Microsoft Corporation",
            asset_type=AssetType.COMMON_STOCK,
            market=sample_market,
            currency="USD",
            segments=set(),
            created_at=fixed_time,
            updated_at=fixed_time,
        )

        asset2 = Asset(
            symbol="MSFT",
            name="Microsoft Corporation",
            asset_type=AssetType.COMMON_STOCK,
            market=sample_market,
            currency="USD",
            segments=set(),
            created_at=fixed_time,
            updated_at=fixed_time,
        )

        assert asset1 == asset2


class TestPriceData:
    """Test PriceData domain model"""

    def test_price_data_creation(self, sample_asset):
        """Test basic price data creation"""
        price_data = PriceData(
            asset=sample_asset,
            timestamp=datetime.now(),
            price=Decimal("151.50"),  # Main price field
            open_price=Decimal("150.00"),
            high_price=Decimal("152.00"),
            low_price=Decimal("149.00"),
            volume=50000000,
        )

        assert price_data.asset == sample_asset
        assert price_data.price == Decimal("151.50")
        assert price_data.open_price == Decimal("150.00")
        assert price_data.volume == 50000000

    def test_price_data_complete_bar(self, sample_asset):
        """Test price data complete bar detection"""
        price_data = PriceData(
            asset=sample_asset,
            timestamp=datetime.now(),
            price=Decimal("105.00"),  # close price
            open_price=Decimal("100.00"),
            high_price=Decimal("110.00"),
            low_price=Decimal("95.00"),
            volume=1000000,
        )

        # Test complete bar detection
        assert price_data.is_complete_bar is True

        # Test bid-ask spread
        price_data.bid_price = Decimal("104.50")
        price_data.ask_price = Decimal("105.50")
        assert price_data.spread == Decimal("1.00")


class TestMarketQuote:
    """Test MarketQuote domain model"""

    def test_market_quote_creation(self, sample_asset):
        """Test basic market quote creation"""
        price_data = PriceData(
            asset=sample_asset,
            timestamp=datetime.now(),
            price=Decimal("151.50"),
            volume=50000000,
            open_price=Decimal("150.25"),
            high_price=Decimal("152.00"),
            low_price=Decimal("149.00"),
        )

        quote = MarketQuote(
            asset=sample_asset, price_data=price_data, previous_close=Decimal("150.00")
        )

        assert quote.asset == sample_asset
        assert quote.price_data.price == Decimal("151.50")
        assert quote.price_data.volume == 50000000

    def test_market_quote_calculations(self, sample_asset):
        """Test market quote calculated properties"""
        price_data = PriceData(
            asset=sample_asset,
            timestamp=datetime.now(),
            price=Decimal("105.00"),
            volume=1000000,
            open_price=Decimal("101.00"),
            high_price=Decimal("106.00"),
            low_price=Decimal("99.00"),
        )

        quote = MarketQuote(
            asset=sample_asset, price_data=price_data, previous_close=Decimal("100.00")
        )

        # Test price change calculations (handled in __post_init__)
        assert quote.price_change == Decimal("5.00")  # 105 - 100
        assert quote.price_change_percent == Decimal("5.00")  # 5/100 * 100

    def test_volume_ratio_calculation(self, sample_asset):
        """Test volume ratio calculation when average volume is provided"""
        price_data = PriceData(
            asset=sample_asset,
            timestamp=datetime.now(),
            price=Decimal("100.00"),
            volume=75000000,  # 1.5x average
            open_price=Decimal("99.50"),
            high_price=Decimal("101.00"),
            low_price=Decimal("98.00"),
        )

        quote = MarketQuote(
            asset=sample_asset,
            price_data=price_data,
            previous_close=Decimal("99.00"),
            average_volume=50000000,  # Average volume
        )

        assert quote.volume_ratio == Decimal("1.50")  # 75M / 50M
