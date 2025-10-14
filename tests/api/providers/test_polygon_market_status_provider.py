"""Unit tests for PolygonMarketStatusProvider API provider."""

import pytest
from unittest.mock import Mock, patch
from datetime import date, datetime

import sys
sys.path.insert(0, '/home/ccollins/projects/TradeScout/src')

from api.providers.polygon_market_status_provider import PolygonMarketStatusProvider
from models.dataclass.market_holiday import MarketHoliday, HolidayStatus
from models.dataclass.market_status import MarketStatusSnapshot


class TestPolygonMarketStatusProvider:
    """Test PolygonMarketStatusProvider API operations."""

    @pytest.fixture
    def provider(self):
        """Create PolygonMarketStatusProvider instance with test API key."""
        return PolygonMarketStatusProvider(api_key="test_api_key_12345")

    @pytest.fixture
    def sample_market_status_response(self):
        """Sample Polygon API response for market status."""
        return {
            "market": "open",
            "serverTime": "2024-01-15T14:30:00-05:00",
            "exchanges": {
                "nyse": "open",
                "nasdaq": "open",
                "otc": "closed"
            },
            "currencies": {
                "fx": "open",
                "crypto": "open"
            }
        }

    @pytest.fixture
    def sample_holidays_response(self):
        """Sample Polygon API response for upcoming holidays."""
        return [
            {
                "exchange": "NYSE",
                "name": "Presidents' Day",
                "status": "closed",
                "date": "2024-02-19",
                "open": None,
                "close": None
            },
            {
                "exchange": "NASDAQ",
                "name": "Presidents' Day",
                "status": "closed",
                "date": "2024-02-19",
                "open": None,
                "close": None
            },
            {
                "exchange": "NYSE",
                "name": "Good Friday",
                "status": "closed",
                "date": "2024-03-29",
                "open": None,
                "close": None
            },
            {
                "exchange": "NYSE",
                "name": "Christmas Eve",
                "status": "early-close",
                "date": "2024-12-24",
                "open": "09:30",
                "close": "13:00"
            }
        ]

    # ============================================================================
    # INITIALIZATION TESTS
    # ============================================================================

    def test_provider_initialization(self):
        """Test provider initializes with API key."""
        provider = PolygonMarketStatusProvider(api_key="test_key")
        assert provider.api_key == "test_key"
        assert provider.base_url == "https://api.polygon.io"

    def test_provider_initialization_no_api_key(self):
        """Test provider raises error without API key."""
        with pytest.raises(ValueError, match="requires an API key"):
            PolygonMarketStatusProvider(api_key="")

    def test_provider_info(self, provider):
        """Test provider info returns correct metadata."""
        info = provider.get_provider_info()
        assert info["name"] == "polygon_market_status"
        assert info["base_url"] == "https://api.polygon.io"
        assert "market_status" in info["endpoints"]
        assert "upcoming_holidays" in info["endpoints"]

    def test_add_authentication(self, provider):
        """Test authentication adds API key to params."""
        params = {}
        authed_params = provider._add_authentication(params)
        assert "apikey" in authed_params
        assert authed_params["apikey"] == "test_api_key_12345"

    # ============================================================================
    # FETCH MARKET STATUS TESTS
    # ============================================================================

    @patch.object(PolygonMarketStatusProvider, "_make_request")
    def test_fetch_market_status_success(self, mock_request, provider, sample_market_status_response):
        """Test fetching market status successfully."""
        mock_request.return_value = sample_market_status_response

        result = provider.fetch_market_status()

        assert result is not None
        assert isinstance(result, MarketStatusSnapshot)
        assert result.market == "open"
        assert result.exchanges["nyse"] == "open"
        assert result.exchanges["nasdaq"] == "open"
        assert result.exchanges["otc"] == "closed"
        assert isinstance(result.server_time, datetime)
        mock_request.assert_called_once_with("/v1/marketstatus/now")

    @patch.object(PolygonMarketStatusProvider, "_make_request")
    def test_fetch_market_status_api_error(self, mock_request, provider):
        """Test fetching market status handles API errors."""
        mock_request.side_effect = Exception("API Error")

        result = provider.fetch_market_status()

        assert result is None

    @patch.object(PolygonMarketStatusProvider, "_make_request")
    def test_fetch_market_status_dataclass_methods(self, mock_request, provider, sample_market_status_response):
        """Test MarketStatusSnapshot dataclass helper methods."""
        mock_request.return_value = sample_market_status_response

        result = provider.fetch_market_status()

        assert result.is_market_open() is True
        assert result.is_exchange_open("nyse") is True
        assert result.is_exchange_open("nasdaq") is True
        assert result.is_exchange_open("otc") is False

    @patch.object(PolygonMarketStatusProvider, "_make_request")
    def test_fetch_market_status_extended_hours(self, mock_request, provider):
        """Test detection of extended hours trading."""
        extended_hours_response = {
            "market": "extended-hours",
            "serverTime": "2024-01-15T07:00:00-05:00",
            "exchanges": {
                "nyse": "extended-hours",
                "nasdaq": "extended-hours"
            },
            "currencies": {
                "fx": "open",
                "crypto": "open"
            },
            "earlyHours": True,
            "afterHours": False
        }
        mock_request.return_value = extended_hours_response

        result = provider.fetch_market_status()

        assert result is not None
        assert result.market == "extended-hours"
        assert result.early_hours is True
        assert result.after_hours is False
        assert result.is_extended_hours() is True
        assert result.is_market_open() is False

    # ============================================================================
    # FETCH UPCOMING HOLIDAYS TESTS
    # ============================================================================

    @patch.object(PolygonMarketStatusProvider, "_make_request")
    def test_fetch_upcoming_holidays_success(self, mock_request, provider, sample_holidays_response):
        """Test fetching upcoming holidays successfully."""
        mock_request.return_value = sample_holidays_response

        result = provider.fetch_upcoming_holidays()

        assert result is not None
        assert len(result) == 3  # Deduplicated from 4 (two Presidents' Day entries)
        assert all(isinstance(holiday, MarketHoliday) for holiday in result)

        # Check deduplication worked
        dates = [h.date for h in result]
        assert len(dates) == len(set(dates))  # All dates unique

    @patch.object(PolygonMarketStatusProvider, "_make_request")
    def test_fetch_upcoming_holidays_deduplication(self, mock_request, provider, sample_holidays_response):
        """Test that holidays are deduplicated by date."""
        mock_request.return_value = sample_holidays_response

        result = provider.fetch_upcoming_holidays()

        # Presidents' Day appears twice (NYSE and NASDAQ) but should be one entry
        presidents_day = [h for h in result if h.name == "Presidents' Day"]
        assert len(presidents_day) == 1
        assert presidents_day[0].date == date(2024, 2, 19)

    @patch.object(PolygonMarketStatusProvider, "_make_request")
    def test_fetch_upcoming_holidays_preserves_status(self, mock_request, provider, sample_holidays_response):
        """Test that holiday status is correctly parsed."""
        mock_request.return_value = sample_holidays_response

        result = provider.fetch_upcoming_holidays()

        closed_holidays = [h for h in result if h.status == HolidayStatus.CLOSED]
        early_close_holidays = [h for h in result if h.status == HolidayStatus.EARLY_CLOSE]

        assert len(closed_holidays) == 2  # Presidents' Day and Good Friday
        assert len(early_close_holidays) == 1  # Christmas Eve

    @patch.object(PolygonMarketStatusProvider, "_make_request")
    def test_fetch_upcoming_holidays_empty_response(self, mock_request, provider):
        """Test fetching holidays with empty results."""
        mock_request.return_value = []

        result = provider.fetch_upcoming_holidays()

        assert result is not None
        assert len(result) == 0

    @patch.object(PolygonMarketStatusProvider, "_make_request")
    def test_fetch_upcoming_holidays_api_error(self, mock_request, provider):
        """Test fetching holidays handles API errors."""
        mock_request.side_effect = Exception("API Error")

        result = provider.fetch_upcoming_holidays()

        assert result is None

    @patch.object(PolygonMarketStatusProvider, "_make_request")
    def test_fetch_upcoming_holidays_handles_malformed_data(self, mock_request, provider):
        """Test fetching holidays handles malformed entries without crashing."""
        mock_request.return_value = [
            {"exchange": "NYSE", "name": "Valid", "status": "closed", "date": "2024-07-04"},
            {"exchange": "NYSE"}  # Missing fields
        ]

        result = provider.fetch_upcoming_holidays()

        # Should not crash, returns what it can parse
        assert result is not None

    # ============================================================================
    # HEALTH CHECK TESTS
    # ============================================================================

    @patch.object(PolygonMarketStatusProvider, "_make_request")
    def test_health_check_success(self, mock_request, provider):
        """Test health check succeeds."""
        mock_request.return_value = {"status": "OK"}

        result = provider.health_check()

        assert result is True
        mock_request.assert_called_once_with("/v1/marketstatus/now")

    @patch.object(PolygonMarketStatusProvider, "_make_request")
    def test_health_check_failure(self, mock_request, provider):
        """Test health check fails on API error."""
        mock_request.side_effect = Exception("API Error")

        result = provider.health_check()

        assert result is False
