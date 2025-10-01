"""Unit tests for TickerSnapshotManager database manager."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from decimal import Decimal

from database.managers.ticker_snapshot_manager import TickerSnapshotManager
from models.snapshot import TickerSnapshot, MinuteBar
from models.data_update_metadata import DataUpdateMetadataType


class TestTickerSnapshotManager:
    """Test TickerSnapshotManager database operations."""

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
    def manager(self, mock_db_manager, mock_update_tracker):
        """Create TickerSnapshotManager instance."""
        return TickerSnapshotManager(mock_db_manager, mock_update_tracker)

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
    # METADATA TYPE & TTL TESTS
    # ============================================================================

    def test_get_data_update_metadata_type(self, manager):
        """Test that manager returns correct metadata type."""
        assert manager.get_data_update_metadata_type() == DataUpdateMetadataType.TICKER_SNAPSHOTS

    def test_get_ttl_seconds(self, manager):
        """Test that manager returns TTL in seconds."""
        ttl = manager.get_ttl_seconds()
        assert ttl == 15 * 60  # 15 minutes in seconds
        assert isinstance(ttl, int)

    # ============================================================================
    # GET ENTITY FROM DATABASE TESTS
    # ============================================================================

    def test_get_entity_from_database_success(self, manager, mock_db_manager):
        """Test successful retrieval of ticker snapshot from database."""
        # Mock database response
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Simulate database row data
        mock_cursor.fetchone.return_value = (
            "AAPL",                      # symbol
            "2025-09-28T16:00:00",       # updated_at
            150.00, 150.00, 150.00, 150.00, 1000000, None,  # prevday data
            151.00, 152.00, 149.50, 151.50, 800000, 151.25,  # day data
            1695920400000, 151.50, 151.50, 151.50, 151.50, 100000, 151.50  # min data
        )

        result = manager.get_entity_from_database("AAPL")

        assert result is not None
        assert isinstance(result, TickerSnapshot)
        assert result.symbol == "AAPL"
        assert result.prev_close == Decimal("150.00")

    def test_get_entity_from_database_not_found(self, manager, mock_db_manager):
        """Test retrieval when ticker not found in database."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        result = manager.get_entity_from_database("NONEXISTENT")

        assert result is None

    def test_get_entity_from_database_no_dependencies(self, manager):
        """Test that None is returned when dependencies are missing."""
        manager.db_manager = None
        result = manager.get_entity_from_database("AAPL")
        assert result is None

    # ============================================================================
    # SET ENTITY TO DATABASE TESTS
    # ============================================================================

    def test_set_entity_to_database_success(self, manager, mock_db_manager, sample_ticker_snapshot):
        """Test successful storage of ticker snapshot to database."""
        # Mock database connections for asset_id and provider_id lookups
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock asset_id lookup (first call)
        # Mock provider_id lookup (second call)
        # Mock insert (third call)
        mock_cursor.fetchone.side_effect = [
            (123,),  # asset_id
            (1,),    # provider_id
        ]

        result = manager.set_entity_to_database("AAPL", sample_ticker_snapshot)

        assert result is True
        # Verify insert was called
        assert mock_cursor.execute.call_count >= 3

    def test_set_entity_to_database_no_asset_id(self, manager, mock_db_manager, sample_ticker_snapshot):
        """Test storage fails when asset_id not found."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock asset_id lookup returns None
        mock_cursor.fetchone.return_value = None

        result = manager.set_entity_to_database("AAPL", sample_ticker_snapshot)

        assert result is False

    def test_set_entity_to_database_none_entity(self, manager):
        """Test storage fails with None entity."""
        result = manager.set_entity_to_database("AAPL", None)
        assert result is False

    def test_set_entity_to_database_no_dependencies(self, manager, sample_ticker_snapshot):
        """Test storage fails when dependencies are missing."""
        manager.db_manager = None
        result = manager.set_entity_to_database("AAPL", sample_ticker_snapshot)
        assert result is False

    # ============================================================================
    # GET OR FETCH TESTS
    # ============================================================================

    def test_get_or_fetch_with_fresh_cache(self, manager, mock_update_tracker, sample_ticker_snapshot):
        """Test get_or_fetch returns cached data when TTL is fresh."""
        # Setup: cache is fresh
        mock_update_tracker.is_data_stale.return_value = False

        # Mock get_entity_from_database to return data
        with patch.object(manager, 'get_entity_from_database', return_value=sample_ticker_snapshot):
            fetch_fn = Mock()  # Should NOT be called

            result = manager.get_or_fetch("AAPL", fetch_fn)

            assert result == sample_ticker_snapshot
            fetch_fn.assert_not_called()

    def test_get_or_fetch_with_stale_cache(self, manager, mock_update_tracker, sample_ticker_snapshot):
        """Test get_or_fetch calls API when TTL is stale."""
        # Setup: cache is stale
        mock_update_tracker.is_data_stale.return_value = True

        # Mock fetch function
        fetch_fn = Mock(return_value=sample_ticker_snapshot)

        # Mock set_entity_to_database
        with patch.object(manager, 'set_entity_to_database', return_value=True):
            result = manager.get_or_fetch("AAPL", fetch_fn)

            assert result == sample_ticker_snapshot
            fetch_fn.assert_called_once()

    def test_get_or_fetch_with_force_refresh(self, manager, mock_update_tracker, sample_ticker_snapshot):
        """Test get_or_fetch bypasses cache when force_refresh=True."""
        # Setup: cache is fresh but force_refresh=True should bypass
        mock_update_tracker.is_data_stale.return_value = False

        # Mock fetch function
        fetch_fn = Mock(return_value=sample_ticker_snapshot)

        # Mock set_entity_to_database
        with patch.object(manager, 'set_entity_to_database', return_value=True):
            result = manager.get_or_fetch("AAPL", fetch_fn, force_refresh=True)

            assert result == sample_ticker_snapshot
            fetch_fn.assert_called_once()
            # Verify TTL check was NOT called
            mock_update_tracker.is_data_stale.assert_not_called()

    def test_get_or_fetch_fetch_returns_none(self, manager, mock_update_tracker):
        """Test get_or_fetch when API fetch returns None."""
        mock_update_tracker.is_data_stale.return_value = True

        fetch_fn = Mock(return_value=None)

        result = manager.get_or_fetch("AAPL", fetch_fn)

        assert result is None
        fetch_fn.assert_called_once()

    # ============================================================================
    # STATISTICS TESTS
    # ============================================================================

    def test_get_stats(self, manager, mock_db_manager):
        """Test get_stats returns manager statistics."""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock count queries
        mock_cursor.fetchone.side_effect = [
            (1000,),  # total_records
            (500,),   # unique_symbols
            ("2025-09-28T16:00:00",)  # last_update
        ]

        stats = manager.get_stats()

        assert stats is not None
        assert "metadata_type" in stats
        assert stats["metadata_type"] == "ticker_snapshots"
        assert "total_records" in stats
        assert stats["total_records"] == 1000