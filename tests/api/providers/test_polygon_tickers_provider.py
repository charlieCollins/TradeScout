"""Unit tests for PolygonTickersProvider API provider."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from api.providers.polygon_tickers_provider import PolygonTickersProvider
from models.asset import Asset, AssetType, AssetClass


class TestPolygonTickersProvider:
    """Test PolygonTickersProvider API operations."""

    @pytest.fixture
    def provider(self):
        """Create PolygonTickersProvider instance with test API key."""
        return PolygonTickersProvider(api_key="test_api_key_12345")

    @pytest.fixture
    def sample_ticker_response(self):
        """Sample Polygon API response for ticker details."""
        return {
            "status": "OK",
            "results": {
                "ticker": "AAPL",
                "name": "Apple Inc.",
                "type": "CS",
                "currency_name": "USD",
                "active": True,
                "delisted_utc": None
            }
        }

    @pytest.fixture
    def sample_all_tickers_response(self):
        """Sample Polygon API response for all tickers (paginated)."""
        return {
            "status": "OK",
            "results": [
                {
                    "ticker": "AAPL",
                    "name": "Apple Inc.",
                    "type": "CS",
                    "currency_name": "USD",
                    "active": True
                },
                {
                    "ticker": "MSFT",
                    "name": "Microsoft Corporation",
                    "type": "CS",
                    "currency_name": "USD",
                    "active": True
                }
            ]
        }

    # ============================================================================
    # INITIALIZATION TESTS
    # ============================================================================

    def test_provider_initialization(self):
        """Test provider initializes with API key."""
        provider = PolygonTickersProvider(api_key="test_key")
        assert provider.api_key == "test_key"
        assert provider.base_url == "https://api.polygon.io"

    def test_provider_initialization_no_api_key(self):
        """Test provider raises error without API key."""
        with pytest.raises(ValueError, match="requires an API key"):
            PolygonTickersProvider(api_key="")

    def test_provider_info(self, provider):
        """Test provider info returns correct metadata."""
        info = provider.get_provider_info()
        assert info["name"] == "polygon_tickers"
        assert info["base_url"] == "https://api.polygon.io"
        assert "ticker_details" in info["endpoints"]
        assert "all_tickers" in info["endpoints"]

    def test_add_authentication(self, provider):
        """Test authentication adds API key to params."""
        params = {}
        authed_params = provider._add_authentication(params)
        assert "apikey" in authed_params
        assert authed_params["apikey"] == "test_api_key_12345"

    # ============================================================================
    # FETCH TICKER DETAILS TESTS
    # ============================================================================

    @patch.object(PolygonTickersProvider, "_make_request")
    def test_fetch_ticker_details_raw_success(self, mock_request, provider, sample_ticker_response):
        """Test fetching raw ticker details successfully."""
        mock_request.return_value = sample_ticker_response

        result = provider.fetch_ticker_details_raw("AAPL")

        assert result is not None
        assert result["ticker"] == "AAPL"
        assert result["name"] == "Apple Inc."
        mock_request.assert_called_once_with("/v3/reference/tickers/AAPL")

    @patch.object(PolygonTickersProvider, "_make_request")
    def test_fetch_ticker_details_raw_not_found(self, mock_request, provider):
        """Test fetching ticker details when ticker not found."""
        mock_request.return_value = {"status": "NOT_FOUND"}

        result = provider.fetch_ticker_details_raw("INVALID")

        assert result is None

    @patch.object(PolygonTickersProvider, "_make_request")
    def test_fetch_ticker_details_raw_no_results(self, mock_request, provider):
        """Test fetching ticker details when no results returned."""
        mock_request.return_value = {"status": "OK", "results": None}

        result = provider.fetch_ticker_details_raw("AAPL")

        assert result is None

    @patch.object(PolygonTickersProvider, "_make_request")
    def test_fetch_ticker_details_raw_api_error(self, mock_request, provider):
        """Test fetching ticker details handles API errors."""
        mock_request.side_effect = Exception("API Error")

        result = provider.fetch_ticker_details_raw("AAPL")

        assert result is None

    @patch.object(PolygonTickersProvider, "fetch_ticker_details_raw")
    def test_fetch_ticker_details_success(self, mock_raw, provider, sample_ticker_response):
        """Test fetching parsed ticker details successfully."""
        mock_raw.return_value = sample_ticker_response["results"]

        result = provider.fetch_ticker_details("AAPL")

        assert result is not None
        assert isinstance(result, Asset)
        assert result.symbol == "AAPL"
        assert result.name == "Apple Inc."
        assert result.asset_type == AssetType.STOCK
        assert result.asset_class == AssetClass.EQUITY

    @patch.object(PolygonTickersProvider, "fetch_ticker_details_raw")
    def test_fetch_ticker_details_no_data(self, mock_raw, provider):
        """Test fetching ticker details when no data returned."""
        mock_raw.return_value = None

        result = provider.fetch_ticker_details("AAPL")

        assert result is None

    # ============================================================================
    # FETCH ALL TICKERS TESTS
    # ============================================================================

    @patch.object(PolygonTickersProvider, "_make_request")
    def test_fetch_all_tickers_success(self, mock_request, provider, sample_all_tickers_response):
        """Test fetching all tickers successfully."""
        mock_request.return_value = sample_all_tickers_response

        result = provider.fetch_all_tickers()

        assert len(result) == 2
        assert all(isinstance(asset, Asset) for asset in result)
        assert result[0].symbol == "AAPL"
        assert result[1].symbol == "MSFT"

    @patch.object(PolygonTickersProvider, "_make_request")
    def test_fetch_all_tickers_with_pagination(self, mock_request, provider, sample_all_tickers_response):
        """Test fetching all tickers with pagination."""
        # First page has next_url
        first_response = {
            **sample_all_tickers_response,
            "next_url": "https://api.polygon.io/v3/reference/tickers?cursor=next"
        }
        # Second page has no next_url
        second_response = {
            "status": "OK",
            "results": [
                {
                    "ticker": "GOOGL",
                    "name": "Alphabet Inc.",
                    "type": "CS",
                    "currency_name": "USD",
                    "active": True
                }
            ]
        }

        mock_request.return_value = first_response
        # Mock _make_request_with_url for pagination
        with patch.object(provider, "_make_request_with_url", return_value=second_response):
            result = provider.fetch_all_tickers()

        assert len(result) == 3
        assert result[0].symbol == "AAPL"
        assert result[1].symbol == "MSFT"
        assert result[2].symbol == "GOOGL"

    @patch.object(PolygonTickersProvider, "_make_request")
    def test_fetch_all_tickers_empty_response(self, mock_request, provider):
        """Test fetching all tickers with empty results."""
        mock_request.return_value = {"status": "OK", "results": []}

        result = provider.fetch_all_tickers()

        assert len(result) == 0

    @patch.object(PolygonTickersProvider, "_make_request")
    def test_fetch_all_tickers_api_error(self, mock_request, provider):
        """Test fetching all tickers handles API errors."""
        mock_request.return_value = {"status": "ERROR"}

        result = provider.fetch_all_tickers()

        assert len(result) == 0

    @patch.object(PolygonTickersProvider, "_make_request")
    def test_fetch_all_tickers_with_params(self, mock_request, provider, sample_all_tickers_response):
        """Test fetching all tickers with custom parameters."""
        mock_request.return_value = sample_all_tickers_response

        result = provider.fetch_all_tickers(market="crypto", active=False, limit=500)

        mock_request.assert_called_once()
        call_args = mock_request.call_args
        assert call_args[0][0] == "/v3/reference/tickers"
        params = call_args[0][1]
        assert params["market"] == "crypto"
        assert params["active"] == "false"
        assert params["limit"] == 500

    # ============================================================================
    # TYPE MAPPING TESTS
    # ============================================================================

    def test_map_polygon_type_to_asset_type_stock(self, provider):
        """Test mapping Polygon stock types."""
        assert provider._map_polygon_type_to_asset_type("CS") == AssetType.STOCK
        assert provider._map_polygon_type_to_asset_type("ADRC") == AssetType.STOCK
        assert provider._map_polygon_type_to_asset_type("PFD") == AssetType.STOCK

    def test_map_polygon_type_to_asset_type_etf(self, provider):
        """Test mapping Polygon ETF types."""
        assert provider._map_polygon_type_to_asset_type("ETF") == AssetType.ETF
        assert provider._map_polygon_type_to_asset_type("ETS") == AssetType.ETF
        assert provider._map_polygon_type_to_asset_type("ETN") == AssetType.ETF

    def test_map_polygon_type_to_asset_type_reit(self, provider):
        """Test mapping Polygon REIT types."""
        assert provider._map_polygon_type_to_asset_type("REIT") == AssetType.REIT
        assert provider._map_polygon_type_to_asset_type("REITS") == AssetType.REIT



    def test_map_polygon_type_to_asset_type_unknown(self, provider):
        """Test mapping unknown Polygon types defaults to STOCK."""
        assert provider._map_polygon_type_to_asset_type("UNKNOWN") == AssetType.STOCK

    # ============================================================================
    # PARSE TICKER TESTS
    # ============================================================================

    def test_parse_ticker_to_asset_success(self, provider):
        """Test parsing ticker data to Asset object."""
        ticker_data = {
            "ticker": "AAPL",
            "name": "Apple Inc.",
            "type": "CS",
            "currency_name": "USD",
            "active": True,
            "delisted_utc": None
        }

        result = provider._parse_ticker_to_asset(ticker_data)

        assert result is not None
        assert isinstance(result, Asset)
        assert result.symbol == "AAPL"
        assert result.name == "Apple Inc."
        assert result.currency == "USD"
        assert result.is_active is True
        assert result.is_delisted is False

    def test_parse_ticker_to_asset_missing_ticker(self, provider):
        """Test parsing ticker data with missing ticker field."""
        ticker_data = {"name": "Apple Inc."}

        result = provider._parse_ticker_to_asset(ticker_data)

        assert result is None

    def test_parse_ticker_to_asset_with_delisting(self, provider):
        """Test parsing ticker data with delisting date."""
        ticker_data = {
            "ticker": "DEAD",
            "name": "Delisted Corp",
            "type": "CS",
            "delisted_utc": "2024-01-01T00:00:00Z"
        }

        result = provider._parse_ticker_to_asset(ticker_data)

        assert result is not None
        assert result.is_delisted is True

    def test_parse_ticker_to_asset_invalid_data(self, provider):
        """Test parsing invalid ticker data."""
        ticker_data = {"ticker": "AAPL", "invalid_field": None}
        # Should handle missing fields gracefully
        result = provider._parse_ticker_to_asset(ticker_data)

        assert result is not None
        assert result.symbol == "AAPL"

    # ============================================================================
    # HEALTH CHECK TESTS
    # ============================================================================

    @patch.object(PolygonTickersProvider, "_make_request")
    def test_health_check_success(self, mock_request, provider):
        """Test health check succeeds."""
        mock_request.return_value = {"status": "OK"}

        result = provider.health_check()

        assert result is True
        mock_request.assert_called_once_with("/v1/marketstatus/now")

    @patch.object(PolygonTickersProvider, "_make_request")
    def test_health_check_failure(self, mock_request, provider):
        """Test health check fails on API error."""
        mock_request.side_effect = Exception("API Error")

        result = provider.health_check()

        assert result is False
