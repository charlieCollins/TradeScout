"""Unit tests for UniverseManager database manager."""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime

from database.managers.universe_manager import UniverseManager
from models.universe import Universe, UniverseMembership
from models.data_update_metadata import DataUpdateMetadataType


class TestUniverseManager:
    """Test UniverseManager database operations."""

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
        """Create UniverseManager instance."""
        return UniverseManager(mock_db_manager, mock_update_tracker)

    @pytest.fixture
    def sample_universe(self):
        """Create sample Universe for testing."""
        return Universe(
            id=1,
            name="default_universe",
            description="Default trading universe",
            is_active=True,
            min_market_cap=1000000000,  # 1B
            min_volume=100000,
            max_assets=500,
            last_updated=datetime(2025, 9, 30, 12, 0, 0),
            created_at=datetime(2025, 9, 1, 10, 0, 0),
            updated_at=datetime(2025, 9, 30, 12, 0, 0)
        )

    # ============================================================================
    # METADATA TYPE & TTL TESTS
    # ============================================================================

    def test_get_data_update_metadata_type(self, manager):
        """Test that manager returns correct metadata type."""
        assert manager.get_data_update_metadata_type() == DataUpdateMetadataType.UNIVERSES

    def test_get_ttl_seconds(self, manager):
        """Test that manager returns TTL in seconds."""
        ttl = manager.get_ttl_seconds()
        assert ttl == 24 * 3600  # 24 hours = 1 day in seconds
        assert isinstance(ttl, int)

    # ============================================================================
    # GET ENTITY FROM DATABASE TESTS
    # ============================================================================

    def test_get_entity_from_database_success(self, manager, mock_db_manager):
        """Test successful retrieval of universe from database."""
        # Mock database response
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Simulate database row data
        mock_cursor.fetchone.return_value = (
            1,  # id
            "default_universe",  # name
            "Default trading universe",  # description
            True,  # is_active
            1000000000,  # min_market_cap
            100000,  # min_volume
            500,  # max_assets
            "2025-09-30T12:00:00",  # last_updated
            "2025-09-01T10:00:00",  # created_at
            "2025-09-30T12:00:00"  # updated_at
        )

        result = manager.get_entity_from_database("default_universe")

        assert result is not None
        assert isinstance(result, Universe)
        assert result.name == "default_universe"
        assert result.description == "Default trading universe"
        assert result.is_active is True

    def test_get_entity_from_database_not_found(self, manager, mock_db_manager):
        """Test get_entity_from_database when universe not found."""
        # Mock database response - no results
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        result = manager.get_entity_from_database("nonexistent")

        assert result is None

    def test_get_entity_from_database_no_dependencies(self):
        """Test get_entity_from_database with no dependencies."""
        manager = UniverseManager(None, None)

        result = manager.get_entity_from_database("default_universe")

        assert result is None

    # ============================================================================
    # SET ENTITY TO DATABASE TESTS
    # ============================================================================

    def test_set_entity_to_database_success(self, manager, mock_db_manager, sample_universe):
        """Test successful storage of universe to database."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        result = manager.set_entity_to_database("default_universe", sample_universe)

        assert result is True
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    def test_set_entity_to_database_none_entity(self, manager, mock_db_manager):
        """Test set_entity_to_database with None entity."""
        result = manager.set_entity_to_database("default_universe", None)

        assert result is False

    def test_set_entity_to_database_no_dependencies(self, sample_universe):
        """Test set_entity_to_database with no dependencies."""
        manager = UniverseManager(None, None)

        result = manager.set_entity_to_database("default_universe", sample_universe)

        assert result is False

    # ============================================================================
    # UNIVERSE-SPECIFIC OPERATION TESTS
    # ============================================================================

    def test_get_all_universes(self, manager, mock_db_manager):
        """Test get_all_universes returns all universes."""
        # Mock database response
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock multiple universe rows
        mock_cursor.fetchall.return_value = [
            (1, "default_universe", "Default", True, 1000000000, 100000, 500,
             "2025-09-30T12:00:00", "2025-09-01T10:00:00", "2025-09-30T12:00:00"),
            (2, "momentum", "Momentum", False, 500000000, 50000, 200,
             "2025-09-30T12:00:00", "2025-09-01T10:00:00", "2025-09-30T12:00:00")
        ]

        result = manager.get_all_universes()

        assert len(result) == 2
        assert all(isinstance(u, Universe) for u in result)
        assert result[0].name == "default_universe"
        assert result[1].name == "momentum"

    def test_get_active_universe(self, manager, mock_db_manager):
        """Test get_active_universe returns active universe."""
        # Mock database response
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = (
            1, "default_universe", "Default", True, 1000000000, 100000, 500,
            "2025-09-30T12:00:00", "2025-09-01T10:00:00", "2025-09-30T12:00:00"
        )

        result = manager.get_active_universe()

        assert result is not None
        assert result.is_active is True
        assert result.name == "default_universe"

    def test_get_active_universe_none(self, manager, mock_db_manager):
        """Test get_active_universe when no active universe."""
        # Mock database response - no active universe
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        result = manager.get_active_universe()

        assert result is None

    def test_set_active_universe_success(self, manager, mock_db_manager):
        """Test set_active_universe successfully sets active universe."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.rowcount = 1  # Simulate successful update

        result = manager.set_active_universe("momentum")

        assert result is True
        # Should execute 2 queries: deactivate all, then activate one
        assert mock_cursor.execute.call_count == 2
        mock_conn.commit.assert_called_once()

    def test_set_active_universe_not_found(self, manager, mock_db_manager):
        """Test set_active_universe when universe not found."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.rowcount = 0  # Simulate no rows updated

        result = manager.set_active_universe("nonexistent")

        assert result is False

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
            (3,),  # Total universes
            ("default_universe",),  # Active universe
            (450,)  # Total memberships
        ]

        stats = manager.get_stats()

        assert stats is not None
        assert "metadata_type" in stats
        assert stats["metadata_type"] == "universes"
        assert "ttl_hours" in stats
        assert stats["ttl_hours"] == 24
        assert "total_universes" in stats
        assert stats["total_universes"] == 3
        assert stats["active_universe"] == "default_universe"
        assert stats["total_active_memberships"] == 450
