"""Unit tests for ProviderManager database manager."""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime

from database.managers.provider_manager import ProviderManager, POLYGON_PROVIDER
from models.provider import Provider
from models.data_update_metadata import DataUpdateMetadataType


class TestProviderManager:
    """Test ProviderManager database operations."""

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
        """Create ProviderManager instance."""
        return ProviderManager(mock_db_manager, mock_update_tracker)

    # ============================================================================
    # METADATA TYPE & TTL TESTS
    # ============================================================================

    def test_get_data_update_metadata_type(self, manager):
        """Test that manager returns correct metadata type."""
        assert manager.get_data_update_metadata_type() == DataUpdateMetadataType.PROVIDERS

    def test_get_ttl_seconds(self, manager):
        """Test that manager returns TTL in seconds."""
        ttl = manager.get_ttl_seconds()
        assert ttl == 365 * 24 * 3600  # 1 year in seconds
        assert isinstance(ttl, int)

    # ============================================================================
    # GET ENTITY FROM DATABASE TESTS (HARDCODED POLYGON)
    # ============================================================================

    def test_get_entity_from_database_polygon(self, manager):
        """Test retrieval of hardcoded Polygon provider."""
        result = manager.get_entity_from_database("polygon")

        assert result is not None
        assert isinstance(result, Provider)
        assert result.name == "polygon"
        assert result.display_name == "Polygon.io"
        assert result.base_url == "https://api.polygon.io"
        assert result.is_active is True

    def test_get_entity_from_database_case_insensitive(self, manager):
        """Test that provider lookup is case insensitive."""
        result = manager.get_entity_from_database("POLYGON")

        assert result is not None
        assert result.name == "polygon"

    def test_get_entity_from_database_not_found(self, manager):
        """Test get_entity_from_database for unknown provider returns None."""
        result = manager.get_entity_from_database("unknown_provider")

        assert result is None

    # ============================================================================
    # PROVIDER-SPECIFIC OPERATION TESTS (HARDCODED)
    # ============================================================================

    def test_get_all_providers(self, manager):
        """Test get_all_providers returns hardcoded Polygon."""
        result = manager.get_all_providers()

        assert len(result) == 1
        assert result[0].name == "polygon"
        assert isinstance(result[0], Provider)

    def test_get_active_provider(self, manager):
        """Test get_active_provider returns Polygon."""
        result = manager.get_active_provider()

        assert result is not None
        assert result.name == "polygon"
        assert result.is_active is True

    def test_get_provider_by_id(self, manager):
        """Test get_provider_by_id returns Polygon for ID 1."""
        result = manager.get_provider_by_id(1)

        assert result is not None
        assert result.name == "polygon"
        assert result.id == 1

    def test_get_provider_by_id_not_found(self, manager):
        """Test get_provider_by_id returns None for unknown ID."""
        result = manager.get_provider_by_id(999)

        assert result is None

    # ============================================================================
    # STATISTICS TESTS
    # ============================================================================

    def test_get_stats(self, manager):
        """Test get_stats returns manager statistics."""
        stats = manager.get_stats()

        assert stats is not None
        assert "metadata_type" in stats
        assert stats["metadata_type"] == "providers"
        assert "ttl_hours" in stats
        assert stats["total_providers"] == 1
        assert stats["active_provider"] == "polygon"
        assert "polygon" in stats["providers"]
        assert "hardcoded" in stats["storage"]
