"""Unit tests for AssetManager database manager."""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime

from database.managers.asset_manager import AssetManager
from models.asset import Asset, AssetType, AssetClass
from models.data_update_metadata import DataUpdateMetadataType


class TestAssetManager:
    """Test AssetManager database operations."""

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
        """Create AssetManager instance."""
        return AssetManager(mock_db_manager, mock_update_tracker)

    @pytest.fixture
    def sample_asset(self):
        """Create sample Asset for testing."""
        return Asset(
            id=1,
            symbol="AAPL",
            name="Apple Inc.",
            asset_type=AssetType.STOCK,
            asset_class=AssetClass.EQUITY,
            market_id=1,
            currency="USD",
            provider_id=1,
            created_at=datetime(2025, 9, 30, 12, 0, 0),
            updated_at=datetime(2025, 9, 30, 12, 0, 0),
            lot_size=1,
            tick_size=None,
            is_active=True,
            is_delisted=False,
            listing_date=None,
            delisting_date=None
        )

    # ============================================================================
    # METADATA TYPE & TTL TESTS
    # ============================================================================

    def test_get_data_update_metadata_type(self, manager):
        """Test that manager returns correct metadata type."""
        assert manager.get_data_update_metadata_type() == DataUpdateMetadataType.TICKERS

    def test_get_ttl_seconds(self, manager):
        """Test that manager returns TTL in seconds."""
        ttl = manager.get_ttl_seconds()
        assert ttl == 72 * 3600  # 72 hours = 3 days in seconds
        assert isinstance(ttl, int)

    # ============================================================================
    # GET ENTITY FROM DATABASE TESTS
    # ============================================================================

    def test_get_entity_from_database_success(self, manager, mock_db_manager):
        """Test successful retrieval of asset from database."""
        # Mock database response
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Simulate database row data
        mock_cursor.fetchone.return_value = (
            1,  # id
            "AAPL",  # symbol
            "Apple Inc.",  # name
            1,  # market_id
            "stock",  # asset_type
            "equity",  # asset_class
            "USD",  # currency
            1,  # lot_size
            None,  # tick_size
            True,  # is_active
            False,  # is_delisted
            None,  # listing_date
            None,  # delisting_date
            1,  # provider_id
            "2025-09-30T12:00:00",  # created_at
            "2025-09-30T12:00:00"  # updated_at
        )

        result = manager.get_entity_from_database("AAPL")

        assert result is not None
        assert isinstance(result, Asset)
        assert result.symbol == "AAPL"
        assert result.name == "Apple Inc."
        assert result.asset_type == AssetType.STOCK
        assert result.asset_class == AssetClass.EQUITY

    def test_get_entity_from_database_not_found(self, manager, mock_db_manager):
        """Test get_entity_from_database when asset not found."""
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
        manager = AssetManager(None, None)

        result = manager.get_entity_from_database("AAPL")

        assert result is None

    # ============================================================================
    # SET ENTITY TO DATABASE TESTS
    # ============================================================================

    def test_set_entity_to_database_success(self, manager, mock_db_manager, sample_asset):
        """Test successful storage of asset to database."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        result = manager.set_entity_to_database("AAPL", sample_asset)

        assert result is True
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

    def test_set_entity_to_database_none_entity(self, manager, mock_db_manager):
        """Test set_entity_to_database with None entity."""
        result = manager.set_entity_to_database("AAPL", None)

        assert result is False

    def test_set_entity_to_database_no_dependencies(self, sample_asset):
        """Test set_entity_to_database with no dependencies."""
        manager = AssetManager(None, None)

        result = manager.set_entity_to_database("AAPL", sample_asset)

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
            (100,),  # Total assets
            ("2025-09-30T12:00:00",)  # Last update
        ]
        mock_cursor.fetchall.return_value = [("stock", 90), ("etf", 10)]

        stats = manager.get_stats()

        assert stats is not None
        assert "metadata_type" in stats
        assert stats["metadata_type"] == "tickers"
        assert "ttl_hours" in stats
        assert stats["ttl_hours"] == 72
        assert "total_active_assets" in stats
        assert stats["total_active_assets"] == 100