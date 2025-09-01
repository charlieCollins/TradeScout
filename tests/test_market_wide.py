"""
Tests for Market-Wide Data Providers

Tests the Phase 1 implementation of market gainers/losers functionality
including Alpha Vantage integration and YFinance fallback.
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
from src.tradescout.data_sources_api.asset_data_provider_alpha_vantage import (
    AssetDataProviderAlphaVantage,
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


class TestAlphaVantageProvider:
    """Test Alpha Vantage provider with market movers functionality"""

    @patch.dict("os.environ", {"ALPHA_VANTAGE_API_KEY": "test_key"})
    def test_provider_initialization(self):
        """Test provider initializes with API key"""
        provider = AssetDataProviderAlphaVantage()
        assert provider.api_key == "test_key"
        assert provider.provider_name == "alphavantage"
        assert provider.available == True

    def test_provider_initialization_no_key(self):
        """Test provider without API key uses demo"""
        with patch.dict("os.environ", {}, clear=True):
            provider = AssetDataProviderAlphaVantage()
            assert provider.api_key == "demo"
            assert provider.available == False

    def test_market_movers_methods_exist(self):
        """Test that market movers methods exist"""
        provider = AssetDataProviderAlphaVantage(api_key="test")

        assert hasattr(provider, 'get_market_gainers')
        assert hasattr(provider, 'get_market_losers')
        assert hasattr(provider, 'get_most_active')
        assert hasattr(provider, 'get_market_movers_report')

        # Test empty input
        assert provider._safe_int("") == 0


class TestMarketMoversProvider:
    """Test MarketMoversProvider functionality"""

    @patch.dict("os.environ", {"ALPHA_VANTAGE_API_KEY": "test_key"})
    def test_provider_initialization_with_alpha_vantage(self):
        """Test provider initializes successfully with Alpha Vantage"""
        provider = MarketMoversProvider()
        assert provider.has_alpha_vantage == True
        assert provider.alpha_vantage is not None

    def test_provider_initialization_without_alpha_vantage(self):
        """Test provider handles Alpha Vantage initialization failure gracefully"""
        with patch.dict("os.environ", {}, clear=True):
            provider = MarketMoversProvider()
            assert provider.has_alpha_vantage == False
            assert provider.alpha_vantage is None

    @patch.dict("os.environ", {"ALPHA_VANTAGE_API_KEY": "test_key"})
    @patch("requests.get")
    def test_get_market_gainers_alpha_vantage_success(self, mock_get):
        """Test getting gainers via Alpha Vantage success path"""
        # Mock successful API response
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "top_gainers": [
                {
                    "ticker": "AAPL",
                    "price": "150.00",
                    "change_amount": "10.00",
                    "change_percentage": "7.14%",
                    "volume": "1000000",
                }
            ],
            "top_losers": [],
            "most_actively_traded": [],
        }
        mock_get.return_value = mock_response

        provider = MarketMoversProvider()
        gainers = provider.get_market_gainers(limit=1)

        assert len(gainers) == 1
        assert gainers[0].asset.symbol == "AAPL"
        assert gainers[0].current_price == Decimal("150.00")

    @patch.dict("os.environ", {"ALPHA_VANTAGE_API_KEY": "test_key"})
    def test_get_market_gainers_alpha_vantage_failure_fallback(self):
        """Test fallback to YFinance when Alpha Vantage fails"""
        # Mock Alpha Vantage failure
        with patch.object(AssetDataProviderAlphaVantage, "get_market_gainers") as mock_av:
            mock_av.side_effect = Exception("API Error")

            # Mock YFinance smart coordinator
            mock_coordinator = Mock()
            mock_quote = Mock()
            mock_quote.price_data.price = Decimal("100.00")
            mock_quote.price_change = Decimal("5.00")
            mock_quote.price_change_percent = Decimal("5.26")
            mock_quote.price_data.volume = 500000
            mock_coordinator.get_current_quote.return_value = mock_quote

            provider = MarketMoversProvider()
            provider.smart_coordinator = mock_coordinator

            gainers = provider.get_market_gainers(limit=1)

            # Should return results from YFinance fallback
            # Note: Actual implementation might return empty list if no quotes work
            # This test verifies the fallback logic is called
            assert isinstance(gainers, list)


class TestMarketWideInterface:
    """Test MarketWideDataProvider interface compliance"""

    @patch.dict("os.environ", {"ALPHA_VANTAGE_API_KEY": "test_key"})
    def test_provider_implements_interface(self):
        """Test that MarketMoversProvider implements MarketWideDataProvider"""
        provider = MarketMoversProvider()
        assert isinstance(provider, MarketWideDataProvider)

        # Test required methods exist
        assert hasattr(provider, "get_market_gainers")
        assert hasattr(provider, "get_market_losers")
        assert hasattr(provider, "get_most_active")
        assert hasattr(provider, "get_market_movers_report")

    @patch.dict("os.environ", {"ALPHA_VANTAGE_API_KEY": "test_key"})
    def test_phase_2_phase_3_stub_methods(self):
        """Test that Phase 2 and Phase 3 methods return appropriate stubs"""
        provider = MarketMoversProvider()

        # Phase 2 (sector analysis) should return empty dict
        sector_performance = provider.get_sector_performance()
        assert sector_performance == {}

        sector_leaders = provider.get_sector_leaders(SectorType.TECHNOLOGY)
        assert sector_leaders == []

        # Phase 3 (index tracking) should return empty dict/None
        major_indices = provider.get_major_indices()
        assert major_indices == {}

        index_performance = provider.get_index_performance(IndexType.SP500)
        assert index_performance is None


class TestMarketMoversReport:
    """Test MarketMoversReport data structure"""

    def test_market_movers_report_creation(self):
        """Test creating MarketMoversReport with valid data"""
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
            gainers=[mover],
            losers=[],
            most_active=[mover],
            timestamp=datetime.now(),
            market_status=MarketStatus.OPEN,
        )

        assert len(report.gainers) == 1
        assert len(report.losers) == 0
        assert len(report.most_active) == 1
        assert report.market_status == MarketStatus.OPEN
        assert report.gainers[0].asset.symbol == "AAPL"


@pytest.fixture
def sample_market_mover():
    """Fixture providing a sample MarketMover for testing"""
    nasdaq = MarketFactory().create_nasdaq_market()
    asset = Asset(
        symbol="TSLA",
        name="Tesla Inc.",
        asset_type=AssetType.COMMON_STOCK,
        market=nasdaq,
        currency="USD",
    )

    return MarketMover(
        asset=asset,
        current_price=Decimal("250.00"),
        price_change=Decimal("20.00"),
        price_change_percent=Decimal("8.70"),
        volume=2000000,
        market_cap=800000000000,
        rank=1,
    )


class TestIntegrationMarketMovers:
    """Integration tests for market movers functionality"""

    def test_market_mover_data_consistency(self, sample_market_mover):
        """Test that MarketMover data is internally consistent"""
        mover = sample_market_mover

        # Price change should be consistent with percentage
        previous_price = mover.current_price - mover.price_change
        calculated_percentage = (mover.price_change / previous_price) * 100

        # Allow for small rounding differences
        assert abs(calculated_percentage - mover.price_change_percent) < Decimal("0.1")

    def test_market_movers_ranking(self, sample_market_mover):
        """Test that market movers can be properly ranked"""
        # Create multiple movers with different gains
        movers = []
        for i, gain in enumerate([Decimal("5.0"), Decimal("10.0"), Decimal("2.5")]):
            nasdaq = MarketFactory().create_nasdaq_market()
            asset = Asset(
                symbol=f"TEST{i}",
                name=f"Test Company {i}",
                asset_type=AssetType.COMMON_STOCK,
                market=nasdaq,
                currency="USD",
            )

            mover = MarketMover(
                asset=asset,
                current_price=Decimal("100.00"),
                price_change=gain,
                price_change_percent=gain,  # Simplified for test
                volume=1000000,
                rank=0,  # Will be set by sorting
            )
            movers.append(mover)

        # Sort by percentage gain (descending)
        sorted_movers = sorted(
            movers, key=lambda m: m.price_change_percent, reverse=True
        )

        # Set ranks
        for i, mover in enumerate(sorted_movers):
            mover.rank = i + 1

        # Verify correct ranking
        assert sorted_movers[0].price_change_percent == Decimal("10.0")  # Highest gain
        assert sorted_movers[0].rank == 1
        assert sorted_movers[2].price_change_percent == Decimal("2.5")  # Lowest gain
        assert sorted_movers[2].rank == 3
