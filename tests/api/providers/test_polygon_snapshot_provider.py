"""Unit tests for PolygonSnapshotProvider API provider."""

import pytest
from unittest.mock import Mock, patch
from decimal import Decimal

from api.providers.polygon_snapshot_provider import PolygonSnapshotProvider
from models.snapshot import TickerSnapshot, MarketSnapshot


class TestPolygonSnapshotProvider:
    """Test PolygonSnapshotProvider API operations."""

    @pytest.fixture
    def provider(self):
        """Create PolygonSnapshotProvider instance with test API key."""
        return PolygonSnapshotProvider(api_key="test_api_key_12345")

    @pytest.fixture
    def sample_polygon_ticker_response(self):
        """Sample Polygon API response for single ticker snapshot."""
        return {
            "status": "OK",
            "ticker": {
                "ticker": "AAPL",
                "todaysChangePerc": 1.5,
                "todaysChange": 2.25,
                "updated": 1695920400000000000,
                "day": {
                    "o": 151.00,
                    "h": 152.00,
                    "l": 149.50,
                    "c": 151.50,
                    "v": 800000,
                    "vw": 151.25
                },
                "min": {
                    "av": 50000,
                    "t": 1695920400000,
                    "n": 100,
                    "o": 151.50,
                    "h": 151.50,
                    "l": 151.50,
                    "c": 151.50,
                    "v": 100000,
                    "vw": 151.50
                },
                "prevDay": {
                    "o": 150.00,
                    "h": 150.00,
                    "l": 150.00,
                    "c": 150.00,
                    "v": 1000000,
                    "vw": 150.00
                }
            }
        }

    @pytest.fixture
    def sample_polygon_bulk_response(self):
        """Sample Polygon API response for bulk market snapshot."""
        return {
            "status": "OK",
            "results": [
                {
                    "ticker": "AAPL",
                    "todaysChangePerc": 1.5,
                    "todaysChange": 2.25,
                    "updated": 1695920400000000000,
                    "day": {"o": 151.00, "h": 152.00, "l": 149.50, "c": 151.50, "v": 800000, "vw": 151.25},
                    "min": {"t": 1695920400000, "o": 151.50, "h": 151.50, "l": 151.50, "c": 151.50, "v": 100000, "vw": 151.50},
                    "prevDay": {"o": 150.00, "h": 150.00, "l": 150.00, "c": 150.00, "v": 1000000, "vw": 150.00}
                },
                {
                    "ticker": "MSFT",
                    "todaysChangePerc": 0.8,
                    "todaysChange": 2.50,
                    "updated": 1695920400000000000,
                    "day": {"o": 310.00, "h": 315.00, "l": 308.00, "c": 312.50, "v": 500000, "vw": 311.25},
                    "min": {"t": 1695920400000, "o": 312.50, "h": 312.50, "l": 312.50, "c": 312.50, "v": 50000, "vw": 312.50},
                    "prevDay": {"o": 310.00, "h": 310.00, "l": 310.00, "c": 310.00, "v": 600000, "vw": 310.00}
                }
            ]
        }

    # ============================================================================
    # INITIALIZATION TESTS
    # ============================================================================

    def test_provider_initialization(self):
        """Test provider initializes with API key."""
        provider = PolygonSnapshotProvider(api_key="test_key")
        assert provider.api_key == "test_key"
        assert provider.base_url == "https://api.polygon.io"

    def test_provider_initialization_no_api_key(self):
        """Test provider raises error without API key."""
        with pytest.raises(ValueError, match="requires an API key"):
            PolygonSnapshotProvider(api_key="")

    def test_provider_name(self, provider):
        """Test provider name is correct."""
        assert provider.get_provider_info()["name"] == "polygon"

    def test_provider_info(self, provider):
        """Test provider info contains expected fields."""
        info = provider.get_provider_info()
        assert info["name"] == "polygon"
        assert info["base_url"] == "https://api.polygon.io"
        assert "endpoints" in info
        assert "single_ticker" in info["endpoints"]
        assert "bulk_snapshot" in info["endpoints"]

    # ============================================================================
    # AUTHENTICATION TESTS
    # ============================================================================

    def test_add_authentication(self, provider):
        """Test authentication adds API key to params."""
        params = {"limit": 100}
        authenticated_params = provider._add_authentication(params)

        assert "apikey" in authenticated_params
        assert authenticated_params["apikey"] == "test_api_key_12345"
        assert authenticated_params["limit"] == 100

    # ============================================================================
    # FETCH SINGLE TICKER TESTS
    # ============================================================================

    @patch('api.providers.base_provider.requests.request')
    def test_fetch_single_ticker_success(self, mock_request, provider, sample_polygon_ticker_response):
        """Test successful single ticker snapshot fetch."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_polygon_ticker_response
        mock_request.return_value = mock_response

        result = provider.fetch_single_ticker_snapshot("AAPL")

        assert result is not None
        assert isinstance(result, TickerSnapshot)
        assert result.symbol == "AAPL"
        assert result.prev_close == Decimal("150.00")
        assert result.close_price == Decimal("151.50")

    @patch('api.providers.base_provider.requests.request')
    def test_fetch_single_ticker_not_found(self, mock_request, provider):
        """Test fetch when ticker not found."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "OK"}  # No ticker field
        mock_request.return_value = mock_response

        result = provider.fetch_single_ticker_snapshot("NONEXISTENT")

        assert result is None

    @patch('api.providers.base_provider.requests.request')
    def test_fetch_single_ticker_api_error(self, mock_request, provider):
        """Test fetch handles API errors gracefully."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"error": "Not found"}
        mock_request.return_value = mock_response

        result = provider.fetch_single_ticker_snapshot("AAPL")

        # Should return None on error, not raise
        assert result is None

    @patch('api.providers.base_provider.requests.request')
    def test_fetch_single_ticker_rate_limit(self, mock_request, provider, sample_polygon_ticker_response):
        """Test fetch handles rate limiting with retry."""
        # First response: rate limit
        rate_limit_response = Mock()
        rate_limit_response.status_code = 429

        # Second response: success
        success_response = Mock()
        success_response.status_code = 200
        success_response.json.return_value = sample_polygon_ticker_response

        mock_request.side_effect = [rate_limit_response, success_response]

        with patch('time.sleep') as mock_sleep:
            result = provider.fetch_single_ticker_snapshot("AAPL")

            assert result is not None
            assert isinstance(result, TickerSnapshot)
            mock_sleep.assert_called_once()  # Verify it waited

    # ============================================================================
    # FETCH BULK MARKET SNAPSHOT TESTS
    # ============================================================================

    @patch('api.providers.base_provider.requests.request')
    def test_fetch_bulk_snapshot_success(self, mock_request, provider, sample_polygon_bulk_response):
        """Test successful bulk market snapshot fetch."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = sample_polygon_bulk_response
        mock_request.return_value = mock_response

        result = provider.fetch_bulk_market_snapshot()

        assert result is not None
        assert isinstance(result, MarketSnapshot)
        assert len(result.tickers) == 2
        assert "AAPL" in result.tickers
        assert "MSFT" in result.tickers

    @patch('api.providers.base_provider.requests.request')
    def test_fetch_bulk_snapshot_empty_response(self, mock_request, provider):
        """Test bulk fetch with empty response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = None
        mock_request.return_value = mock_response

        result = provider.fetch_bulk_market_snapshot()

        assert result is None

    # ============================================================================
    # HEALTH CHECK TESTS
    # ============================================================================

    @patch('api.providers.base_provider.requests.request')
    def test_health_check_success(self, mock_request, provider):
        """Test health check passes with valid API."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "OK"}
        mock_request.return_value = mock_response

        result = provider.health_check()

        assert result is True

    @patch('api.providers.base_provider.requests.request')
    def test_health_check_failure(self, mock_request, provider):
        """Test health check fails with invalid API."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "Unauthorized"}
        mock_request.return_value = mock_response

        result = provider.health_check()

        assert result is False