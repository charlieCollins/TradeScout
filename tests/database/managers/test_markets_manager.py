"""Unit tests for MarketsManager database manager."""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime, time

from database.managers.markets_manager import MarketsManager
from models.market import Market
from models.data_update_metadata import DataUpdateMetadataType


class TestMarketsManager:
    """Test MarketsManager database operations."""

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
    def mock_metadata_manager(self):
        """Create mock metadata manager."""
        metadata_manager = Mock()
        metadata_manager.record_update = Mock()
        return metadata_manager

    @pytest.fixture
    def manager(self, mock_db_manager, mock_update_tracker, mock_metadata_manager):
        """Create MarketsManager instance."""
        return MarketsManager(
            mock_db_manager,
            mock_update_tracker,
            mock_metadata_manager
        )

    @pytest.fixture
    def sample_market(self):
        """Create sample Market for testing."""
        return Market(
            id=1,
            code="XNYS",
            name="New York Stock Exchange",
            country="US",
            timezone="America/New_York",
            currency="USD",
            premarket_start_time=time(4, 0),
            premarket_end_time=time(9, 30),
            regular_open_time=time(9, 30),
            regular_close_time=time(16, 0),
            afterhours_start_time=time(16, 0),
            afterhours_end_time=time(20, 0),
            is_active=True,
            created_at=datetime(2025, 9, 30, 12, 0, 0),
            updated_at=datetime(2025, 9, 30, 12, 0, 0)
        )

    # ============================================================================
    # METADATA TYPE & TTL TESTS
    # ============================================================================

    def test_get_data_update_metadata_type(self, manager):
        """Test that manager returns correct metadata type."""
        assert manager.get_data_update_metadata_type() == DataUpdateMetadataType.MARKETS

    def test_get_ttl_seconds(self, manager):
        """Test that manager returns TTL in seconds."""
        ttl = manager.get_ttl_seconds()
        assert ttl == 8760 * 3600  # 1 year in seconds
        assert isinstance(ttl, int)

    # ============================================================================
    # GET ENTITY FROM DATABASE TESTS
    # ============================================================================

    def test_get_entity_from_database_success(self, manager, mock_db_manager):
        """Test successful retrieval of market from database."""
        # Mock database response
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Simulate database row data
        mock_cursor.fetchone.return_value = (
            1,  # id
            "XNYS",  # code
            "New York Stock Exchange",  # name
            "US",  # country
            "America/New_York",  # timezone
            "USD",  # currency
            "04:00:00",  # premarket_start_time
            "09:30:00",  # premarket_end_time
            "09:30:00",  # regular_open_time
            "16:00:00",  # regular_close_time
            "16:00:00",  # afterhours_start_time
            "20:00:00",  # afterhours_end_time
            True,  # is_active
            "2025-09-30T12:00:00",  # created_at
            "2025-09-30T12:00:00"  # updated_at
        )

        result = manager.get_entity_from_database("XNYS")

        assert result is not None
        assert isinstance(result, Market)
        assert result.code == "XNYS"
        assert result.name == "New York Stock Exchange"
        assert result.country == "US"
        assert result.currency == "USD"

    def test_get_entity_from_database_case_insensitive(self, manager, mock_db_manager):
        """Test that market code lookup is case insensitive."""
        # Mock database response
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (
            1, "XNYS", "New York Stock Exchange", "US", "America/New_York", "USD",
            "04:00:00", "09:30:00", "09:30:00", "16:00:00", "16:00:00", "20:00:00",
            True, "2025-09-30T12:00:00", "2025-09-30T12:00:00"
        )

        result = manager.get_entity_from_database("xnys")

        assert result is not None
        # Verify uppercase conversion in query
        call_args = mock_cursor.execute.call_args[0]
        assert call_args[1] == ("XNYS",)

    def test_get_entity_from_database_not_found(self, manager, mock_db_manager):
        """Test get_entity_from_database when market not found."""
        # Mock database response - no results
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        result = manager.get_entity_from_database("INVALID")

        assert result is None

    def test_get_entity_from_database_no_dependencies(self):
        """Test get_entity_from_database with no dependencies."""
        manager = MarketsManager(None, None, None)

        result = manager.get_entity_from_database("XNYS")

        assert result is None

    # ============================================================================
    # SET ENTITY TO DATABASE TESTS
    # ============================================================================

    def test_set_entity_to_database_success(self, manager, mock_db_manager, sample_market):
        """Test successful storage of market to database."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        result = manager.set_entity_to_database("XNYS", sample_market)

        assert result is True
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

        # Verify the SQL values passed
        call_args = mock_cursor.execute.call_args[0]
        values = call_args[1]
        assert values[0] == "XNYS"  # code
        assert values[1] == "New York Stock Exchange"  # name

    def test_set_entity_to_database_none_entity(self, manager, mock_db_manager):
        """Test set_entity_to_database with None entity."""
        result = manager.set_entity_to_database("XNYS", None)

        assert result is False

    def test_set_entity_to_database_no_dependencies(self, sample_market):
        """Test set_entity_to_database with no dependencies."""
        manager = MarketsManager(None, None, None)

        result = manager.set_entity_to_database("XNYS", sample_market)

        assert result is False

    # ============================================================================
    # GET ALL MARKETS TESTS
    # ============================================================================

    def test_get_all_markets_success(self, manager, mock_db_manager):
        """Test successful retrieval of all markets."""
        # Mock database response
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Simulate two market rows
        mock_cursor.fetchall.return_value = [
            (1, "XNYS", "New York Stock Exchange", "US", "America/New_York", "USD",
             "04:00:00", "09:30:00", "09:30:00", "16:00:00", "16:00:00", "20:00:00",
             True, "2025-09-30T12:00:00", "2025-09-30T12:00:00"),
            (2, "XNAS", "NASDAQ", "US", "America/New_York", "USD",
             "04:00:00", "09:30:00", "09:30:00", "16:00:00", "16:00:00", "20:00:00",
             True, "2025-09-30T12:00:00", "2025-09-30T12:00:00")
        ]

        result = manager.get_all_markets()

        assert len(result) == 2
        assert result[0].code == "XNYS"
        assert result[1].code == "XNAS"

    def test_get_all_markets_active_only(self, manager, mock_db_manager):
        """Test that active_only parameter filters correctly."""
        # Mock database response
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        manager.get_all_markets(active_only=True)

        # Verify WHERE clause added for active markets
        call_args = mock_cursor.execute.call_args[0]
        query = call_args[0]
        assert "WHERE is_active = 1" in query

    def test_get_all_markets_no_dependencies(self):
        """Test get_all_markets with no dependencies."""
        manager = MarketsManager(None, None, None)

        result = manager.get_all_markets()

        assert result == []

    # ============================================================================
    # GET MARKET BY ID TESTS
    # ============================================================================

    def test_get_market_by_id_success(self, manager, mock_db_manager):
        """Test successful retrieval of market by ID."""
        # Mock database response
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (
            1, "XNYS", "New York Stock Exchange", "US", "America/New_York", "USD",
            "04:00:00", "09:30:00", "09:30:00", "16:00:00", "16:00:00", "20:00:00",
            True, "2025-09-30T12:00:00", "2025-09-30T12:00:00"
        )

        result = manager.get_market_by_id(1)

        assert result is not None
        assert result.id == 1
        assert result.code == "XNYS"

    def test_get_market_by_id_not_found(self, manager, mock_db_manager):
        """Test get_market_by_id when market not found."""
        # Mock database response - no results
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        result = manager.get_market_by_id(999)

        assert result is None

    # ============================================================================
    # GET MARKET ID BY CODE TESTS
    # ============================================================================

    def test_get_market_id_by_code_success(self, manager, mock_db_manager):
        """Test successful retrieval of market ID by code."""
        # Mock database response
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)

        result = manager.get_market_id_by_code("XNYS")

        assert result == 1

    def test_get_market_id_by_code_not_found(self, manager, mock_db_manager):
        """Test get_market_id_by_code when market not found."""
        # Mock database response - no results
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        result = manager.get_market_id_by_code("INVALID")

        assert result is None

    # ============================================================================
    # STATISTICS TESTS
    # ============================================================================

    def test_get_stats(self, manager, mock_db_manager):
        """Test get_stats returns manager statistics."""
        # Mock database responses
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock stats queries
        mock_cursor.fetchone.side_effect = [
            (4,),  # Total markets
            (4,),  # Active markets
            ("2025-09-30T12:00:00",)  # Last update
        ]
        mock_cursor.fetchall.return_value = [("US", 4)]

        stats = manager.get_stats()

        assert stats is not None
        assert "metadata_type" in stats
        assert stats["metadata_type"] == "markets"
        assert "ttl_hours" in stats
        assert stats["ttl_hours"] == 8760
        assert "total_markets" in stats
        assert stats["total_markets"] == 4
        assert "active_markets" in stats
        assert stats["active_markets"] == 4
        assert "by_country" in stats
        assert stats["by_country"]["US"] == 4

    def test_get_stats_no_dependencies(self):
        """Test get_stats with no dependencies."""
        manager = MarketsManager(None, None, None)

        stats = manager.get_stats()

        assert stats is not None
        assert "error" in stats
        assert stats["error"] == "Dependencies not available"
