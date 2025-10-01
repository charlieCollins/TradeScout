"""Integration tests for DataService orchestration layer."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from decimal import Decimal
from datetime import datetime

from services.data_service import DataService
from models.snapshot import TickerSnapshot, MarketSnapshot, MinuteBar
from database.managers.ticker_snapshot_manager import TickerSnapshotManager
from database.managers.market_snapshot_manager import MarketSnapshotManager
from api.provider.polygon_snapshot_provider import PolygonSnapshotProvider


class TestDataServiceIntegration:
    """Test DataService orchestration between managers and providers."""

    @pytest.fixture
    def mock_db_manager(self):
        """Create mock database manager."""
        db_manager = Mock()
        db_manager.get_connection = MagicMock()
        return db_manager

    @pytest.fixture
    def mock_update_tracker(self):
        """Create mock update tracker."""
        tracker = Mock()
        tracker.is_data_stale = Mock(return_value=False)
        return tracker

    @pytest.fixture
    def data_service(self, mock_db_manager, mock_update_tracker):
        """Create DataService instance with mocked dependencies."""
        return DataService(
            db_manager=mock_db_manager,
            update_tracker=mock_update_tracker,
            polygon_api_key="test_api_key_12345"
        )

    @pytest.fixture
    def sample_ticker_snapshot(self):
        """Create sample TickerSnapshot for testing."""
        min_bar = MinuteBar(
            timestamp=1695920400000,
            open=Decimal("151.50"),
            high=Decimal("151.50"),
            low=Decimal("151.50"),
            close=Decimal("151.50"),
            volume=100000,
            vwap=Decimal("151.50"),
            accumulated_volume=50000,
            num_trades=100
        )

        return TickerSnapshot(
            symbol="AAPL",
            prev_close=Decimal("150.00"),
            prev_volume=1000000,
            open_price=Decimal("151.00"),
            high_price=Decimal("152.00"),
            low_price=Decimal("149.50"),
            close_price=Decimal("151.50"),
            volume=800000,
            vwap=Decimal("151.25"),
            last_price=Decimal("151.50"),
            last_timestamp=datetime(2025, 9, 28, 16, 0, 0),
            min_bar=min_bar,
            market_status="closed",
            updated_ns=1695920400000000000
        )

    # ============================================================================
    # INITIALIZATION TESTS
    # ============================================================================

    def test_data_service_initialization(self, data_service):
        """Test DataService initializes all components."""
        assert data_service.ticker_snapshot_manager is not None
        assert isinstance(data_service.ticker_snapshot_manager, TickerSnapshotManager)

        assert data_service.polygon_snapshot_provider is not None
        assert isinstance(data_service.polygon_snapshot_provider, PolygonSnapshotProvider)

    # ============================================================================
    # GET TICKER SNAPSHOT - CACHE HIT TESTS
    # ============================================================================

    def test_get_ticker_snapshot_cache_hit(self, data_service, sample_ticker_snapshot, mock_db_manager, mock_update_tracker):
        """Test get_ticker_snapshot returns cached data when fresh."""
        # Setup: Mock metadata manager to indicate data is fresh
        data_service.metadata_manager.is_stale = Mock(return_value=False)

        # Mock database connection and cursor
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Simulate database row for cached ticker
        mock_cursor.fetchone.return_value = (
            "AAPL", "2025-09-28T16:00:00",
            150.00, 150.00, 150.00, 150.00, 1000000, None,
            151.00, 152.00, 149.50, 151.50, 800000, 151.25,
            1695920400000, 151.50, 151.50, 151.50, 151.50, 100000, 151.50
        )

        result = data_service.get_ticker_snapshot("AAPL")

        # Verify it returns model object, not dict
        assert result is not None
        assert isinstance(result, TickerSnapshot)
        assert result.symbol == "AAPL"
        assert result.prev_close == Decimal("150.00")

        # Verify no API call was made (cache hit)
        # This is implicit - if API was called, it would fail without mocking

    # ============================================================================
    # GET TICKER SNAPSHOT - CACHE MISS TESTS
    # ============================================================================

    @patch('api.provider.base_provider.requests.request')
    def test_get_ticker_snapshot_cache_miss(self, mock_request, data_service, mock_db_manager, mock_update_tracker):
        """Test get_ticker_snapshot fetches from API when cache is stale."""
        # Setup: cache is stale
        mock_update_tracker.is_data_stale.return_value = True

        # Mock database connections for get and set operations
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # First call: get_entity_from_database (not used when stale)
        # Second/Third calls: set_entity_to_database (asset_id, provider_id lookups)
        mock_cursor.fetchone.side_effect = [
            (123,),  # asset_id
            (1,),    # provider_id
        ]

        # Mock API response
        polygon_response = {
            "status": "OK",
            "ticker": {
                "ticker": "AAPL",
                "todaysChangePerc": 1.5,
                "todaysChange": 2.25,
                "updated": 1695920400000000000,
                "day": {"o": 151.00, "h": 152.00, "l": 149.50, "c": 151.50, "v": 800000, "vw": 151.25},
                "min": {"av": 50000, "t": 1695920400000, "n": 100, "o": 151.50, "h": 151.50, "l": 151.50, "c": 151.50, "v": 100000, "vw": 151.50},
                "prevDay": {"o": 150.00, "h": 150.00, "l": 150.00, "c": 150.00, "v": 1000000, "vw": 150.00}
            }
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = polygon_response
        mock_request.return_value = mock_response

        result = data_service.get_ticker_snapshot("AAPL")

        # Verify it returns model object from API
        assert result is not None
        assert isinstance(result, TickerSnapshot)
        assert result.symbol == "AAPL"

        # Verify API was called
        mock_request.assert_called()

        # Verify database insert was attempted
        insert_calls = [call for call in mock_cursor.execute.call_args_list
                       if "INSERT OR REPLACE" in str(call)]
        assert len(insert_calls) > 0

    # ============================================================================
    # GET TICKER SNAPSHOT - FORCE REFRESH TESTS
    # ============================================================================

    @patch('api.provider.base_provider.requests.request')
    def test_get_ticker_snapshot_force_refresh(self, mock_request, data_service, mock_db_manager, mock_update_tracker):
        """Test get_ticker_snapshot with force_refresh bypasses cache."""
        # Setup: cache would normally be fresh
        mock_update_tracker.is_data_stale.return_value = False

        # Mock database connections
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock asset_id and provider_id lookups
        mock_cursor.fetchone.side_effect = [
            (123,),  # asset_id
            (1,),    # provider_id
        ]

        # Mock API response
        polygon_response = {
            "status": "OK",
            "ticker": {
                "ticker": "AAPL",
                "todaysChangePerc": 1.5,
                "todaysChange": 2.25,
                "updated": 1695920400000000000,
                "day": {"o": 151.00, "h": 152.00, "l": 149.50, "c": 151.50, "v": 800000, "vw": 151.25},
                "min": {"av": 50000, "t": 1695920400000, "n": 100, "o": 151.50, "h": 151.50, "l": 151.50, "c": 151.50, "v": 100000, "vw": 151.50},
                "prevDay": {"o": 150.00, "h": 150.00, "l": 150.00, "c": 150.00, "v": 1000000, "vw": 150.00}
            }
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = polygon_response
        mock_request.return_value = mock_response

        result = data_service.get_ticker_snapshot("AAPL", force_refresh=True)

        # Verify it returns model object
        assert result is not None
        assert isinstance(result, TickerSnapshot)

        # Verify API was called despite fresh cache
        mock_request.assert_called()

        # Verify TTL check was NOT called (force refresh bypasses)
        mock_update_tracker.is_data_stale.assert_not_called()

    # ============================================================================
    # GET TICKER SNAPSHOT - ERROR HANDLING TESTS
    # ============================================================================

    @patch('api.provider.base_provider.requests.request')
    def test_get_ticker_snapshot_api_error(self, mock_request, data_service, mock_update_tracker):
        """Test get_ticker_snapshot handles API errors gracefully."""
        # Setup: cache is stale, must fetch
        mock_update_tracker.is_data_stale.return_value = True

        # Mock API error
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"error": "Not found"}
        mock_request.return_value = mock_response

        result = data_service.get_ticker_snapshot("NONEXISTENT")

        # Should return None on error, not raise
        assert result is None

    # ============================================================================
    # PROVIDER HEALTH & INFO TESTS
    # ============================================================================

    @patch('api.provider.base_provider.requests.request')
    def test_check_api_health_success(self, mock_request, data_service):
        """Test API health check returns True when healthy."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "OK"}
        mock_request.return_value = mock_response

        result = data_service.check_api_health()

        assert result is True

    @patch('api.provider.base_provider.requests.request')
    def test_check_api_health_failure(self, mock_request, data_service):
        """Test API health check returns False when unhealthy."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "Unauthorized"}
        mock_request.return_value = mock_response

        result = data_service.check_api_health()

        assert result is False

    def test_get_provider_info(self, data_service):
        """Test get_provider_info returns provider information."""
        info = data_service.get_provider_info()

        assert "polygon_snapshot" in info
        assert info["polygon_snapshot"]["name"] == "polygon"

    # ============================================================================
    # MANAGER STATISTICS TESTS
    # ============================================================================

    def test_get_ticker_snapshot_stats(self, data_service, mock_db_manager):
        """Test get_ticker_snapshot_stats returns statistics."""
        # Mock database queries for stats
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.side_effect = [
            (1000,),  # total_records
            (500,),   # unique_symbols
            ("2025-09-28T16:00:00",)  # last_update
        ]

        stats = data_service.get_ticker_snapshot_stats()

        assert stats is not None
        assert "metadata_type" in stats
        assert stats["metadata_type"] == "ticker_snapshots"
    # ============================================================================
    # MARKET SNAPSHOT INTEGRATION TESTS
    # ============================================================================

    def test_data_service_has_market_snapshot_manager(self, data_service):
        """Test DataService initializes market snapshot manager."""
        assert data_service.market_snapshot_manager is not None
        assert isinstance(data_service.market_snapshot_manager, MarketSnapshotManager)

    @patch('api.provider.base_provider.requests.request')
    def test_refresh_market_data_success(self, mock_request, data_service):
        """Test refresh_market_data fetches bulk data successfully."""
        # Mock bulk API response
        polygon_response = {
            "status": "OK",
            "results": [
                {
                    "ticker": "AAPL",
                    "todaysChangePerc": 1.5,
                    "todaysChange": 2.25,
                    "updated": 1695920400000000000,
                    "day": {"o": 151.00, "h": 152.00, "l": 149.50, "c": 151.50, "v": 800000, "vw": 151.25},
                    "min": {"av": 50000, "t": 1695920400000, "n": 100, "o": 151.50, "h": 151.50, "l": 151.50, "c": 151.50, "v": 100000, "vw": 151.50},
                    "prevDay": {"o": 150.00, "h": 150.00, "l": 150.00, "c": 150.00, "v": 1000000, "vw": 150.00}
                },
                {
                    "ticker": "MSFT",
                    "todaysChangePerc": 0.8,
                    "todaysChange": 2.50,
                    "updated": 1695920400000000000,
                    "day": {"o": 310.00, "h": 315.00, "l": 308.00, "c": 312.50, "v": 500000, "vw": 311.25},
                    "min": {"av": 25000, "t": 1695920400000, "n": 50, "o": 312.50, "h": 312.50, "l": 312.50, "c": 312.50, "v": 50000, "vw": 312.50},
                    "prevDay": {"o": 310.00, "h": 310.00, "l": 310.00, "c": 310.00, "v": 600000, "vw": 310.00}
                }
            ]
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = polygon_response
        mock_request.return_value = mock_response

        result = data_service.refresh_market_data()

        # Verify it returns MarketSnapshot model object
        assert result is not None
        assert isinstance(result, MarketSnapshot)
        assert len(result.tickers) == 2
        assert "AAPL" in result.tickers
        assert "MSFT" in result.tickers
        assert isinstance(result.tickers["AAPL"], TickerSnapshot)

    @patch('api.provider.base_provider.requests.request')
    def test_refresh_market_data_with_symbols_list(self, mock_request, data_service):
        """Test refresh_market_data with specific symbols list."""
        polygon_response = {
            "status": "OK",
            "results": [
                {
                    "ticker": "AAPL",
                    "todaysChangePerc": 1.5,
                    "updated": 1695920400000000000,
                    "day": {"o": 151.00, "h": 152.00, "l": 149.50, "c": 151.50, "v": 800000, "vw": 151.25},
                    "min": {"av": 50000, "t": 1695920400000, "n": 100, "o": 151.50, "h": 151.50, "l": 151.50, "c": 151.50, "v": 100000, "vw": 151.50},
                    "prevDay": {"o": 150.00, "h": 150.00, "l": 150.00, "c": 150.00, "v": 1000000, "vw": 150.00}
                }
            ]
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = polygon_response
        mock_request.return_value = mock_response

        result = data_service.refresh_market_data(symbols=["AAPL", "MSFT"])

        assert result is not None
        assert isinstance(result, MarketSnapshot)
        # Verify API was called with symbols parameter
        call_args = mock_request.call_args
        assert "params" in call_args.kwargs
        assert "tickers" in call_args.kwargs["params"]

    @patch('api.provider.base_provider.requests.request')
    def test_refresh_market_data_force_refresh(self, mock_request, data_service):
        """Test refresh_market_data with force_refresh parameter."""
        polygon_response = {
            "status": "OK",
            "results": [
                {
                    "ticker": "AAPL",
                    "updated": 1695920400000000000,
                    "day": {"o": 151.00, "h": 152.00, "l": 149.50, "c": 151.50, "v": 800000, "vw": 151.25},
                    "min": {"av": 50000, "t": 1695920400000, "n": 100, "o": 151.50, "h": 151.50, "l": 151.50, "c": 151.50, "v": 100000, "vw": 151.50},
                    "prevDay": {"o": 150.00, "h": 150.00, "l": 150.00, "c": 150.00, "v": 1000000, "vw": 150.00}
                }
            ]
        }

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = polygon_response
        mock_request.return_value = mock_response

        result = data_service.refresh_market_data(force_refresh=True)

        assert result is not None
        assert isinstance(result, MarketSnapshot)
        # Verify API was called
        mock_request.assert_called()

    def test_get_market_snapshot_stats(self, data_service):
        """Test get_market_snapshot_stats returns statistics."""
        stats = data_service.get_market_snapshot_stats()

        assert stats is not None
        assert "metadata_type" in stats
        assert stats["metadata_type"] == "market_snapshots"
        assert "ttl_minutes" in stats
        assert stats["ttl_minutes"] == 15

    # ============================================================================
    # ASSET OPERATIONS TESTS
    # ============================================================================

    def test_data_service_has_asset_manager(self, data_service):
        """Test that DataService initializes with AssetManager."""
        assert data_service.asset_manager is not None
        from database.managers import AssetManager
        assert isinstance(data_service.asset_manager, AssetManager)

    def test_get_asset_from_database(self, data_service):
        """Test get_asset retrieves from database."""
        # Mock the asset manager's get method
        from models.asset import Asset, AssetType, AssetClass
        from datetime import datetime

        sample_asset = Asset(
            id=1,
            symbol="AAPL",
            name="Apple Inc.",
            asset_type=AssetType.STOCK,
            asset_class=AssetClass.EQUITY,
            market_id=1,
            currency="USD",
            provider_id=1,
            created_at=datetime(2025, 9, 30, 12, 0, 0),
            updated_at=datetime(2025, 9, 30, 12, 0, 0)
        )

        # Mock get_or_fetch to return sample asset
        data_service.asset_manager.get_or_fetch = Mock(return_value=sample_asset)

        result = data_service.get_asset("AAPL")

        assert result is not None
        assert isinstance(result, Asset)
        assert result.symbol == "AAPL"
        assert result.name == "Apple Inc."

    def test_get_asset_not_found(self, data_service):
        """Test get_asset when asset not found."""
        data_service.asset_manager.get_or_fetch = Mock(return_value=None)

        result = data_service.get_asset("INVALID")

        assert result is None

    def test_get_asset_stats(self, data_service):
        """Test get_asset_stats returns statistics."""
        stats = data_service.get_asset_stats()

        assert stats is not None
        assert "metadata_type" in stats
        assert stats["metadata_type"] == "tickers"
        assert "ttl_hours" in stats
        assert stats["ttl_hours"] == 72
