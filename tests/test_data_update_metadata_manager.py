"""Unit tests for DataUpdateMetadataManager."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta

from database.managers.data_update_metadata_manager import DataUpdateMetadataManager
from models.data_update_metadata import DataUpdateMetadataType


class TestDataUpdateMetadataManager:
    """Test DataUpdateMetadataManager operations."""

    @pytest.fixture
    def mock_db_manager(self):
        """Create mock database manager."""
        db_manager = Mock()
        db_manager.get_connection = MagicMock()
        return db_manager

    @pytest.fixture
    def manager(self, mock_db_manager):
        """Create DataUpdateMetadataManager instance."""
        return DataUpdateMetadataManager(mock_db_manager)

    # ============================================================================
    # INITIALIZATION TESTS
    # ============================================================================

    def test_initialization(self, mock_db_manager):
        """Test manager initializes with database manager."""
        manager = DataUpdateMetadataManager(mock_db_manager)
        assert manager.db_manager == mock_db_manager

    # ============================================================================
    # RECORD UPDATE TESTS
    # ============================================================================

    def test_record_update_success(self, manager, mock_db_manager):
        """Test successful update recording."""
        # Setup mock connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Record update
        result = manager.record_update(
            DataUpdateMetadataType.TICKER_SNAPSHOTS,
            "fetch"
        )

        # Verify
        assert result is True
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

        # Verify SQL contains expected fields
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1]

        assert "INSERT OR REPLACE" in sql
        assert "data_update_metadata" in sql
        assert params[0] == "ticker_snapshots"  # operation_type
        assert params[1] == "fetch"  # operation_subtype
        assert params[4] == "completed"  # status

    def test_record_update_no_db_manager(self):
        """Test record_update handles missing database manager."""
        manager = DataUpdateMetadataManager(None)

        result = manager.record_update(
            DataUpdateMetadataType.TICKER_SNAPSHOTS,
            "fetch"
        )

        assert result is False

    def test_record_update_database_error(self, manager, mock_db_manager):
        """Test record_update handles database errors."""
        # Setup mock to raise error
        mock_db_manager.get_connection.side_effect = Exception("Database error")

        result = manager.record_update(
            DataUpdateMetadataType.TICKER_SNAPSHOTS,
            "fetch"
        )

        assert result is False

    def test_record_update_different_operation_types(self, manager, mock_db_manager):
        """Test record_update works for different operation types."""
        # Setup mock connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Test different operation types
        operation_types = [
            DataUpdateMetadataType.TICKER_SNAPSHOTS,
            DataUpdateMetadataType.MARKET_SNAPSHOTS,
            DataUpdateMetadataType.FUNDAMENTALS
        ]

        for op_type in operation_types:
            result = manager.record_update(op_type, "fetch")
            assert result is True

    # ============================================================================
    # STALENESS CHECK TESTS
    # ============================================================================

    def test_is_stale_no_metadata(self, manager, mock_db_manager):
        """Test is_stale returns True when no metadata exists."""
        # Setup mock to return no results
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        result = manager.is_stale(
            DataUpdateMetadataType.TICKER_SNAPSHOTS,
            ttl_seconds=900  # 15 minutes
        )

        assert result is True

    def test_is_stale_data_within_ttl(self, manager, mock_db_manager):
        """Test is_stale returns False when data is within TTL."""
        # Setup mock to return recent timestamp (5 minutes ago)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        recent_time = datetime.now() - timedelta(minutes=5)
        mock_cursor.fetchone.return_value = (recent_time.isoformat(),)

        result = manager.is_stale(
            DataUpdateMetadataType.TICKER_SNAPSHOTS,
            ttl_seconds=900  # 15 minutes TTL
        )

        assert result is False

    def test_is_stale_data_beyond_ttl(self, manager, mock_db_manager):
        """Test is_stale returns True when data is beyond TTL."""
        # Setup mock to return old timestamp (20 minutes ago)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        old_time = datetime.now() - timedelta(minutes=20)
        mock_cursor.fetchone.return_value = (old_time.isoformat(),)

        result = manager.is_stale(
            DataUpdateMetadataType.TICKER_SNAPSHOTS,
            ttl_seconds=900  # 15 minutes TTL
        )

        assert result is True

    def test_is_stale_just_within_ttl(self, manager, mock_db_manager):
        """Test is_stale returns False when data is just within TTL."""
        # Setup mock to return timestamp just within TTL (1 second before expiry)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        ttl_seconds = 900
        just_before_expiry = datetime.now() - timedelta(seconds=ttl_seconds - 1)
        mock_cursor.fetchone.return_value = (just_before_expiry.isoformat(),)

        result = manager.is_stale(
            DataUpdateMetadataType.TICKER_SNAPSHOTS,
            ttl_seconds=ttl_seconds
        )

        # Just before expiry should still be fresh
        assert result is False

    def test_is_stale_just_beyond_ttl(self, manager, mock_db_manager):
        """Test is_stale returns True when data is just beyond TTL."""
        # Setup mock to return timestamp just beyond TTL (1 second after expiry)
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        ttl_seconds = 900
        just_after_expiry = datetime.now() - timedelta(seconds=ttl_seconds + 1)
        mock_cursor.fetchone.return_value = (just_after_expiry.isoformat(),)

        result = manager.is_stale(
            DataUpdateMetadataType.TICKER_SNAPSHOTS,
            ttl_seconds=ttl_seconds
        )

        # Just after expiry should be stale
        assert result is True

    # ============================================================================
    # GET LAST UPDATE TIME TESTS
    # ============================================================================

    def test_get_last_update_time_success(self, manager, mock_db_manager):
        """Test successful retrieval of last update time."""
        # Setup mock connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        test_time = datetime(2025, 9, 30, 12, 0, 0)
        mock_cursor.fetchone.return_value = (test_time.isoformat(),)

        result = manager.get_last_update_time(DataUpdateMetadataType.TICKER_SNAPSHOTS)

        assert result == test_time
        mock_cursor.execute.assert_called_once()

        # Verify SQL query
        call_args = mock_cursor.execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1]

        assert "SELECT completed_at" in sql
        assert "data_update_metadata" in sql
        assert "ORDER BY completed_at DESC" in sql
        assert "LIMIT 1" in sql
        assert params[0] == "ticker_snapshots"

    def test_get_last_update_time_no_metadata(self, manager, mock_db_manager):
        """Test get_last_update_time returns None when no metadata exists."""
        # Setup mock to return no results
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        result = manager.get_last_update_time(DataUpdateMetadataType.TICKER_SNAPSHOTS)

        assert result is None

    def test_get_last_update_time_no_db_manager(self):
        """Test get_last_update_time handles missing database manager."""
        manager = DataUpdateMetadataManager(None)

        result = manager.get_last_update_time(DataUpdateMetadataType.TICKER_SNAPSHOTS)

        assert result is None

    def test_get_last_update_time_database_error(self, manager, mock_db_manager):
        """Test get_last_update_time handles database errors."""
        # Setup mock to raise error
        mock_db_manager.get_connection.side_effect = Exception("Database error")

        result = manager.get_last_update_time(DataUpdateMetadataType.TICKER_SNAPSHOTS)

        assert result is None

    # ============================================================================
    # GET UPDATE STATS TESTS
    # ============================================================================

    def test_get_update_stats_success(self, manager, mock_db_manager):
        """Test successful retrieval of update statistics."""
        # Setup mock connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock count query result
        test_time = datetime(2025, 9, 30, 12, 0, 0)
        mock_cursor.fetchone.side_effect = [
            (5,),  # Total updates count
            (test_time.isoformat(),)  # Last update time
        ]

        result = manager.get_update_stats(DataUpdateMetadataType.TICKER_SNAPSHOTS)

        assert result["operation_type"] == "ticker_snapshots"
        assert result["total_updates"] == 5
        assert result["last_update"] == test_time.isoformat()
        assert result["age_seconds"] is not None
        assert isinstance(result["age_seconds"], float)

    def test_get_update_stats_no_metadata(self, manager, mock_db_manager):
        """Test get_update_stats when no metadata exists."""
        # Setup mock connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock no updates
        mock_cursor.fetchone.side_effect = [
            (0,),  # No updates
            None   # No last update time
        ]

        result = manager.get_update_stats(DataUpdateMetadataType.TICKER_SNAPSHOTS)

        assert result["operation_type"] == "ticker_snapshots"
        assert result["total_updates"] == 0
        assert result["last_update"] is None
        assert result["age_seconds"] is None

    def test_get_update_stats_no_db_manager(self):
        """Test get_update_stats handles missing database manager."""
        manager = DataUpdateMetadataManager(None)

        result = manager.get_update_stats(DataUpdateMetadataType.TICKER_SNAPSHOTS)

        assert "error" in result
        assert result["error"] == "Database manager not available"

    def test_get_update_stats_database_error(self, manager, mock_db_manager):
        """Test get_update_stats handles database errors."""
        # Setup mock to raise error
        mock_db_manager.get_connection.side_effect = Exception("Database error")

        result = manager.get_update_stats(DataUpdateMetadataType.TICKER_SNAPSHOTS)

        assert "error" in result
        assert "Database error" in result["error"]