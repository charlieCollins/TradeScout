"""
Tests for YFinance Adapter
"""

import pytest
from unittest.mock import Mock, patch
from decimal import Decimal
from datetime import datetime

from tradescout.data_sources.yfinance_adapter import YFinanceAdapter
from tradescout.data_models.domain_models_core import MarketStatus


@pytest.mark.unit
class TestYFinanceAdapter:
    """Test YFinance adapter functionality"""

    def test_adapter_initialization(self, mock_cache):
        """Test adapter initialization with cache"""
        adapter = YFinanceAdapter(cache=mock_cache)

        assert adapter.cache == mock_cache
        assert adapter.provider_name == "yfinance"
        assert adapter.rate_limit_per_minute == 60
        assert adapter.supports_extended_hours is True

    def test_adapter_initialization_default_cache(self):
        """Test adapter initialization with default cache"""
        adapter = YFinanceAdapter()

        assert adapter.cache is not None
        assert adapter.provider_name == "yfinance"

    @patch("tradescout.data_sources.yfinance_adapter.cached_api_call")
    def test_get_current_quote_success(
        self, mock_cached_call, sample_asset, sample_quote_data
    ):
        """Test successful current quote retrieval"""
        # Mock cached API call to return quote data
        mock_cached_call.return_value = sample_quote_data

        adapter = YFinanceAdapter()
        quote = adapter.get_current_quote(sample_asset)

        assert quote is not None
        assert quote.asset == sample_asset
        assert quote.price_data.price == Decimal("151.50")
        assert quote.price_data.volume == 50000000
        assert quote.price_change == Decimal("1.50")

    @patch("tradescout.data_sources.yfinance_adapter.cached_api_call")
    def test_get_current_quote_cache_miss_with_real_fetch(
        self, mock_cached_call, sample_asset, mock_yfinance_ticker
    ):
        """Test current quote with cache miss and real API fetch"""

        # Configure mock to simulate cache miss, then real API call
        def side_effect(*args, **kwargs):
            api_function = kwargs["api_function"]
            return api_function()  # Call the real fetch function

        mock_cached_call.side_effect = side_effect

        adapter = YFinanceAdapter()
        quote = adapter.get_current_quote(sample_asset)

        assert quote is not None
        assert quote.asset == sample_asset
        # Verify cached_api_call was called with correct parameters
        mock_cached_call.assert_called_once()
        call_kwargs = mock_cached_call.call_args[1]
        assert call_kwargs["provider"] == "yfinance"
        assert call_kwargs["endpoint"] == "get_current_quote"
        assert call_kwargs["params"]["symbol"] == sample_asset.symbol

    @patch("tradescout.data_sources.yfinance_adapter.cached_api_call")
    def test_get_current_quote_no_data(self, mock_cached_call, sample_asset):
        """Test current quote when no data is available"""
        mock_cached_call.return_value = None

        adapter = YFinanceAdapter()
        quote = adapter.get_current_quote(sample_asset)

        assert quote is None

    @patch("tradescout.data_sources.yfinance_adapter.cached_api_call")
    def test_get_extended_hours_data(self, mock_cached_call, sample_asset):
        """Test extended hours data retrieval"""
        # Mock extended hours data
        extended_data = {
            "session": MarketStatus.AFTER_HOURS,
            "volume": 5000000,
            "high": Decimal("152.50"),
            "low": Decimal("151.00"),
            "open": Decimal("151.50"),
            "close": Decimal("152.00"),
            "change": Decimal("0.50"),
            "timestamp": datetime.now(),
        }
        mock_cached_call.return_value = extended_data

        adapter = YFinanceAdapter()
        result = adapter.get_extended_hours_data(sample_asset, MarketStatus.AFTER_HOURS)

        assert result is not None
        assert result.asset == sample_asset
        assert result.session_type == MarketStatus.AFTER_HOURS
        assert result.price_data.volume == 5000000
        assert result.price_data.high_price == Decimal("152.50")

    @patch("tradescout.data_sources.yfinance_adapter.cached_api_call")
    def test_get_historical_quotes(self, mock_cached_call, sample_asset):
        """Test historical quotes retrieval"""
        # Mock historical data
        historical_data = [
            {
                "timestamp": datetime(2025, 7, 19, 16, 0),
                "open": Decimal("149.00"),
                "high": Decimal("151.00"),
                "low": Decimal("148.50"),
                "close": Decimal("150.50"),
                "volume": 45000000,
            },
            {
                "timestamp": datetime(2025, 7, 20, 16, 0),
                "open": Decimal("150.25"),
                "high": Decimal("152.00"),
                "low": Decimal("149.75"),
                "close": Decimal("151.50"),
                "volume": 50000000,
            },
        ]
        mock_cached_call.return_value = historical_data

        adapter = YFinanceAdapter()
        start_date = datetime(2025, 7, 19)
        end_date = datetime(2025, 7, 21)

        result = adapter.get_historical_quotes(sample_asset, start_date, end_date)

        assert len(result) == 2
        assert result[0].asset == sample_asset
        assert result[0].price == Decimal("150.50")  # price is the main/close price
        assert result[1].price == Decimal("151.50")

    def test_scan_volume_leaders(self, sample_asset):
        """Test volume leaders scanning"""
        adapter = YFinanceAdapter()

        # Mock get_current_quote to return quote with high volume ratio
        with patch.object(adapter, "get_current_quote") as mock_get_quote:
            from tradescout.data_models.domain_models_core import MarketQuote, PriceData

            # Create PriceData first
            price_data = PriceData(
                asset=sample_asset,
                timestamp=datetime.now(),
                price=Decimal("151.50"),
                volume=100000000,  # 2x average volume
                open_price=Decimal("150.25"),
                high_price=Decimal("152.00"),
                low_price=Decimal("149.00"),
            )

            # Create MarketQuote with proper structure
            mock_quote = MarketQuote(
                asset=sample_asset,
                price_data=price_data,
                previous_close=Decimal("150.00"),
                average_volume=50000000,
            )
            mock_get_quote.return_value = mock_quote

            result = adapter.scan_volume_leaders(
                [sample_asset], min_volume_ratio=Decimal("1.5")
            )

            assert len(result) == 1
            assert result[0] == mock_quote
            assert hasattr(result[0], "volume_ratio")
            assert result[0].volume_ratio == Decimal("2.0")

    @patch("tradescout.data_sources.yfinance_adapter.cached_api_call")
    def test_get_fundamental_data(self, mock_cached_call, sample_asset):
        """Test fundamental data retrieval"""
        # Mock fundamental data
        fundamental_data = {
            "symbol": "AAPL",
            "company_name": "Apple Inc.",
            "sector": "Technology",
            "industry": "Consumer Electronics",
            "market_cap": 2500000000000,
            "pe_ratio": 25.5,
            "beta": 1.2,
            "shares_outstanding": 16000000000,
            "52_week_high": 180.00,
            "52_week_low": 120.00,
            "timestamp": datetime.now().isoformat(),
        }
        mock_cached_call.return_value = fundamental_data

        adapter = YFinanceAdapter()
        result = adapter.get_fundamental_data(sample_asset)

        assert result["symbol"] == "AAPL"
        assert result["company_name"] == "Apple Inc."
        assert result["sector"] == "Technology"
        assert result["market_cap"] == 2500000000000

    def test_is_extended_hours_time(self):
        """Test extended hours time detection"""
        adapter = YFinanceAdapter()

        # Test during pre-market hours (6 AM)
        with patch(
            "tradescout.data_sources.yfinance_adapter.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value.hour = 6
            assert adapter._is_extended_hours_time() is True

        # Test during after-hours (5 PM)
        with patch(
            "tradescout.data_sources.yfinance_adapter.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value.hour = 17
            assert adapter._is_extended_hours_time() is True

        # Test during regular hours (11 AM)
        with patch(
            "tradescout.data_sources.yfinance_adapter.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value.hour = 11
            assert adapter._is_extended_hours_time() is False


@pytest.mark.integration
class TestYFinanceAdapterIntegration:
    """Integration tests for YFinance adapter (these may make real API calls)"""

    @pytest.mark.api
    def test_real_api_call(self, sample_asset):
        """Test real API call to YFinance (use sparingly)"""
        pytest.skip("Skipping real API test to avoid rate limits")

        adapter = YFinanceAdapter()
        quote = adapter.get_current_quote(sample_asset)

        # Basic validation that we got real data
        assert quote is not None
        assert quote.price > 0
        assert quote.volume > 0


def test_create_yfinance_adapter():
    """Test convenience function for creating adapter"""
    from tradescout.data_sources.yfinance_adapter import create_yfinance_adapter

    adapter = create_yfinance_adapter()

    assert isinstance(adapter, YFinanceAdapter)
    assert adapter.cache is not None
