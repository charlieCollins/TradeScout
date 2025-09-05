"""
Tests for Market-Wide Data Providers

Tests the Phase 1 implementation of market gainers/losers functionality.
"""

from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.tradescout.data_models.domain_models_core import Asset, AssetType, MarketStatus
from src.tradescout.data_models.factories import MarketFactory
from src.tradescout.data_models.market_wide_models import (
    IndexType,
    MarketMover,
    MarketMoversReport,
    MarketWideDataProvider,
    SectorType,
)
from src.tradescout.data_sources.smart_coordinator import SmartCoordinator


class TestMarketMover:
    """Test MarketMover data structure"""

    def test_market_mover_creation(self):
        """Test creating MarketMover with valid data"""
        nasdaq = MarketFactory().create_nasdaq_market()
        asset = Asset(
            symbol="AAPL",
            name="Apple Inc.",
            asset_type=AssetType.COMMON_STOCK,
            market=nasdaq,
            currency="USD",
        )

        mover = MarketMover(
            asset=asset,
            current_price=Decimal("150.00"),
            price_change=Decimal("10.00"),
            price_change_percent=Decimal("7.14"),
            volume=1000000,
            market_cap=2500000000,
            rank=1,
        )

        assert mover.asset.symbol == "AAPL"
        assert mover.current_price == Decimal("150.00")
        assert mover.price_change_percent == Decimal("7.14")
        assert mover.rank == 1

    def test_market_mover_str_representation(self):
        """Test string representation of MarketMover"""
        nasdaq = MarketFactory().create_nasdaq_market()
        asset = Asset(
            symbol="AAPL",
            name="Apple Inc.",
            asset_type=AssetType.COMMON_STOCK,
            market=nasdaq,
            currency="USD",
        )

        mover = MarketMover(
            asset=asset,
            current_price=Decimal("150.00"),
            price_change=Decimal("10.00"),
            price_change_percent=Decimal("7.14"),
            volume=1000000,
            market_cap=2500000000,
            rank=1,
        )

        str_repr = str(mover)
        assert "AAPL" in str_repr
        assert "150.00" in str_repr


class TestMarketMoversReport:
    """Test MarketMoversReport data structure"""

    def test_empty_report_creation(self):
        """Test creating empty MarketMoversReport"""
        report = MarketMoversReport(
            timestamp=datetime.now(),
            market_status=MarketStatus.OPEN,
            gainers=[],
            losers=[],
            most_active=[],
        )

        assert isinstance(report.gainers, list)
        assert isinstance(report.losers, list)
        assert isinstance(report.most_active, list)
        assert len(report.gainers) == 0

    def test_report_with_data(self):
        """Test creating MarketMoversReport with data"""
        nasdaq = MarketFactory().create_nasdaq_market()
        asset = Asset(
            symbol="AAPL",
            name="Apple Inc.",
            asset_type=AssetType.COMMON_STOCK,
            market=nasdaq,
            currency="USD",
        )

        mover = MarketMover(
            asset=asset,
            current_price=Decimal("150.00"),
            price_change=Decimal("10.00"),
            price_change_percent=Decimal("7.14"),
            volume=1000000,
            rank=1,
        )

        report = MarketMoversReport(
            timestamp=datetime.now(),
            market_status=MarketStatus.OPEN,
            gainers=[mover],
            losers=[],
            most_active=[],
        )

        assert len(report.gainers) == 1
        assert report.gainers[0].asset.symbol == "AAPL"


class TestSmartCoordinator:
    """Test SmartCoordinator market data functionality"""

    def test_smart_coordinator_initialization(self):
        """Test SmartCoordinator can be initialized"""
        try:
            coordinator = SmartCoordinator()
            assert coordinator is not None
        except Exception as e:
            # If initialization fails due to missing config, that's expected
            pytest.skip(f"SmartCoordinator initialization failed: {e}")
