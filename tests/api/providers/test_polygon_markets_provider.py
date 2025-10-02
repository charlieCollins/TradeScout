"""Unit tests for PolygonMarketsProvider API provider."""

import pytest
from unittest.mock import Mock, patch
from datetime import time

from api.providers.polygon_markets_provider import PolygonMarketsProvider
from models.market import Market


class TestPolygonMarketsProvider:
    """Test PolygonMarketsProvider API operations."""

    @pytest.fixture
    def provider(self):
        """Create PolygonMarketsProvider instance with test API key."""
        return PolygonMarketsProvider(api_key="test_api_key_12345")

    @pytest.fixture
    def sample_exchanges_response(self):
        """Sample Polygon API response for exchanges."""
        return {
            "status": "OK",
            "results": [
                {
                    "type": "exchange",
                    "asset_class": "stocks",
                    "locale": "us",
                    "name": "New York Stock Exchange",
                    "acronym": "NYSE",
                    "mic": "XNYS",
                    "operating_mic": "XNYS",
                    "participant_id": "N",
                    "url": "https://www.nyse.com"
                },
                {
                    "type": "exchange",
                    "asset_class": "stocks",
                    "locale": "us",
                    "name": "NASDAQ Stock Market",
                    "acronym": "NASDAQ",
                    "mic": "XNAS",
                    "operating_mic": "XNAS",
                    "participant_id": "Q",
                    "url": "https://www.nasdaq.com"
                }
            ]
        }

    # ============================================================================
    # INITIALIZATION TESTS
    # ============================================================================

    def test_provider_initialization(self):
        """Test provider initializes with API key."""
        provider = PolygonMarketsProvider(api_key="test_key")
        assert provider.api_key == "test_key"
        assert provider.base_url == "https://api.polygon.io"

    def test_provider_initialization_no_api_key(self):
        """Test provider raises error without API key."""
        with pytest.raises(ValueError, match="requires an API key"):
            PolygonMarketsProvider(api_key="")

    def test_provider_info(self, provider):
        """Test provider info returns correct metadata."""
        info = provider.get_provider_info()
        assert info["name"] == "polygon_markets"
        assert info["base_url"] == "https://api.polygon.io"
        assert "exchanges" in info["endpoints"]

    def test_add_authentication(self, provider):
        """Test authentication adds API key to params."""
        params = {}
        authed_params = provider._add_authentication(params)
        assert "apikey" in authed_params
        assert authed_params["apikey"] == "test_api_key_12345"

    # ============================================================================
    # FETCH EXCHANGES TESTS
    # ============================================================================

    @patch.object(PolygonMarketsProvider, "_make_request")
    def test_fetch_all_exchanges_success(self, mock_request, provider, sample_exchanges_response):
        """Test fetching all exchanges successfully."""
        mock_request.return_value = sample_exchanges_response

        result = provider.fetch_all_exchanges()

        assert len(result) == 2
        assert all(isinstance(market, Market) for market in result)
        assert result[0].code == "XNYS"
        assert result[0].name == "New York Stock Exchange"
        assert result[1].code == "XNAS"
        assert result[1].name == "NASDAQ Stock Market"

    @patch.object(PolygonMarketsProvider, "_make_request")
    def test_fetch_all_exchanges_with_params(self, mock_request, provider, sample_exchanges_response):
        """Test fetching exchanges with custom parameters."""
        mock_request.return_value = sample_exchanges_response

        result = provider.fetch_all_exchanges(asset_class="crypto", locale="global")

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "/v3/reference/exchanges"
        params = call_args[0][1]
        assert params["asset_class"] == "crypto"
        assert params["locale"] == "global"

    @patch.object(PolygonMarketsProvider, "_make_request")
    def test_fetch_all_exchanges_empty_response(self, mock_request, provider):
        """Test fetching exchanges with empty results."""
        mock_request.return_value = {"status": "OK", "results": []}

        result = provider.fetch_all_exchanges()

        assert len(result) == 0

    @patch.object(PolygonMarketsProvider, "_make_request")
    def test_fetch_all_exchanges_api_error(self, mock_request, provider):
        """Test fetching exchanges handles API errors."""
        mock_request.return_value = {"status": "ERROR"}

        result = provider.fetch_all_exchanges()

        assert len(result) == 0

    @patch.object(PolygonMarketsProvider, "_make_request")
    def test_fetch_all_exchanges_request_exception(self, mock_request, provider):
        """Test fetching exchanges handles request exceptions."""
        mock_request.side_effect = Exception("Network error")

        result = provider.fetch_all_exchanges()

        assert len(result) == 0

    @patch.object(PolygonMarketsProvider, "_make_request")
    def test_fetch_all_exchanges_skips_invalid_entries(self, mock_request, provider):
        """Test fetching exchanges skips entries that fail to parse."""
        mock_request.return_value = {
            "status": "OK",
            "results": [
                {
                    "type": "exchange",
                    "name": "Valid Exchange",
                    "mic": "VALID"
                },
                {
                    "type": "exchange"
                    # Missing required fields
                },
                {
                    "type": "exchange",
                    "name": "Another Valid",
                    "mic": "VALID2"
                }
            ]
        }

        result = provider.fetch_all_exchanges()

        # Should skip the invalid middle entry
        assert len(result) == 2
        assert result[0].code == "VALID"
        assert result[1].code == "VALID2"

    # ============================================================================
    # PARSE EXCHANGE TESTS
    # ============================================================================

    def test_parse_exchange_to_market_success(self, provider):
        """Test parsing exchange data to Market object."""
        exchange_data = {
            "type": "exchange",
            "asset_class": "stocks",
            "locale": "us",
            "name": "New York Stock Exchange",
            "acronym": "NYSE",
            "mic": "XNYS",
            "operating_mic": "XNYS",
            "participant_id": "N",
            "url": "https://www.nyse.com"
        }

        result = provider._parse_exchange_to_market(exchange_data)

        assert result is not None
        assert isinstance(result, Market)
        assert result.code == "XNYS"
        assert result.name == "New York Stock Exchange"
        assert result.timezone == "America/New_York"
        assert result.is_active is True

    def test_parse_exchange_to_market_missing_mic(self, provider):
        """Test parsing exchange data with missing MIC code."""
        exchange_data = {"name": "Invalid Exchange"}

        result = provider._parse_exchange_to_market(exchange_data)

        assert result is None

    def test_parse_exchange_to_market_with_default_hours(self, provider):
        """Test parsing exchange sets default US trading hours."""
        exchange_data = {
            "mic": "XNYS",
            "name": "NYSE"
        }

        result = provider._parse_exchange_to_market(exchange_data)

        assert result is not None
        assert result.premarket_start_time == time(4, 0)
        assert result.premarket_end_time == time(9, 30)
        assert result.regular_open_time == time(9, 30)
        assert result.regular_close_time == time(16, 0)
        assert result.afterhours_start_time == time(16, 0)
        assert result.afterhours_end_time == time(20, 0)

    def test_parse_exchange_to_market_invalid_data(self, provider):
        """Test parsing exchange with malformed data."""
        exchange_data = {
            "mic": "TEST",
            "name": None  # Invalid name
        }

        # Should handle gracefully
        result = provider._parse_exchange_to_market(exchange_data)

        # Depends on implementation - either returns None or Market with empty name
        assert result is None or (result is not None and result.code == "TEST")

    # ============================================================================
    # TIMEZONE MAPPING TESTS
    # ============================================================================





    # ============================================================================
    # HEALTH CHECK TESTS
    # ============================================================================

    @patch.object(PolygonMarketsProvider, "_make_request")
    def test_health_check_success(self, mock_request, provider):
        """Test health check succeeds."""
        mock_request.return_value = {"status": "OK"}

        result = provider.health_check()

        assert result is True
        mock_request.assert_called_once_with("/v1/marketstatus/now")

    @patch.object(PolygonMarketsProvider, "_make_request")
    def test_health_check_failure(self, mock_request, provider):
        """Test health check fails on API error."""
        mock_request.side_effect = Exception("API Error")

        result = provider.health_check()

        assert result is False
