"""Unit tests for FundamentalsManager database manager."""

import pytest
from unittest.mock import Mock, MagicMock
from datetime import datetime
from decimal import Decimal

from database.managers.fundamentals_manager import FundamentalsManager
from models.fundamentals import AssetFundamentals
from models.data_update_metadata import DataUpdateMetadataType


class TestFundamentalsManager:
    """Test FundamentalsManager database operations."""

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
        """Create FundamentalsManager instance."""
        return FundamentalsManager(
            mock_db_manager,
            mock_update_tracker,
            mock_metadata_manager
        )

    @pytest.fixture
    def sample_fundamentals(self):
        """Create sample AssetFundamentals for testing."""
        return AssetFundamentals(
            asset_id=1,
            company_name="Apple Inc.",
            sector="Technology",
            industry="Consumer Electronics",
            sic_code="3571",
            market_cap=300000000000,  # $3T in cents
            shares_outstanding=16000000000,
            avg_volume_30d=50000000,
            beta=Decimal("1.2"),
            pe_ratio=Decimal("30.5"),
            dividend_yield=Decimal("0.5"),
            provider_id=1,
            last_updated=datetime(2025, 9, 30, 12, 0, 0)
        )

    # ============================================================================
    # METADATA TYPE & TTL TESTS
    # ============================================================================

    def test_get_data_update_metadata_type(self, manager):
        """Test that manager returns correct metadata type."""
        assert manager.get_data_update_metadata_type() == DataUpdateMetadataType.FUNDAMENTALS

    def test_get_ttl_seconds(self, manager):
        """Test that manager returns TTL in seconds."""
        ttl = manager.get_ttl_seconds()
        assert ttl == 168 * 3600  # 168 hours = 1 week in seconds
        assert isinstance(ttl, int)

    # ============================================================================
    # GET ENTITY FROM DATABASE TESTS
    # ============================================================================

    def test_get_entity_from_database_success(self, manager, mock_db_manager):
        """Test successful retrieval of fundamentals from database."""
        # Mock database response
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Simulate database row data
        mock_cursor.fetchone.return_value = (
            1,  # asset_id
            "Apple Inc.",  # company_name
            "Technology",  # sector
            "Consumer Electronics",  # industry
            "3571",  # sic_code
            300000000000,  # market_cap
            16000000000,  # shares_outstanding
            50000000,  # avg_volume_30d
            1.2,  # beta
            30.5,  # pe_ratio
            0.5,  # dividend_yield
            1,  # provider_id
            "2025-09-30T12:00:00"  # last_updated
        )

        result = manager.get_entity_from_database("1")

        assert result is not None
        assert isinstance(result, AssetFundamentals)
        assert result.asset_id == 1
        assert result.company_name == "Apple Inc."
        assert result.sector == "Technology"
        assert result.market_cap == 300000000000

    def test_get_entity_from_database_not_found(self, manager, mock_db_manager):
        """Test get_entity_from_database when fundamentals not found."""
        # Mock database response - no results
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        result = manager.get_entity_from_database("999")

        assert result is None

    def test_get_entity_from_database_invalid_key(self, manager, mock_db_manager):
        """Test get_entity_from_database with invalid asset_id key."""
        result = manager.get_entity_from_database("invalid")

        assert result is None

    def test_get_entity_from_database_no_dependencies(self):
        """Test get_entity_from_database with no dependencies."""
        manager = FundamentalsManager(None, None, None)

        result = manager.get_entity_from_database("1")

        assert result is None

    # ============================================================================
    # GET FUNDAMENTALS BY SYMBOL TESTS
    # ============================================================================

    def test_get_fundamentals_by_symbol_success(self, manager, mock_db_manager):
        """Test successful retrieval of fundamentals by symbol."""
        # Mock database response
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Simulate database row data (joined with assets table)
        mock_cursor.fetchone.return_value = (
            1,  # asset_id
            "Apple Inc.",  # company_name
            "Technology",  # sector
            "Consumer Electronics",  # industry
            "3571",  # sic_code
            300000000000,  # market_cap
            16000000000,  # shares_outstanding
            50000000,  # avg_volume_30d
            1.2,  # beta
            30.5,  # pe_ratio
            0.5,  # dividend_yield
            1,  # provider_id
            "2025-09-30T12:00:00"  # last_updated
        )

        result = manager.get_fundamentals_by_symbol("AAPL")

        assert result is not None
        assert isinstance(result, AssetFundamentals)
        assert result.asset_id == 1
        assert result.company_name == "Apple Inc."
        # Verify uppercase conversion
        mock_cursor.execute.assert_called_once()
        call_args = mock_cursor.execute.call_args[0]
        assert call_args[1] == ("AAPL",)

    def test_get_fundamentals_by_symbol_not_found(self, manager, mock_db_manager):
        """Test get_fundamentals_by_symbol when symbol not found."""
        # Mock database response - no results
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = None

        result = manager.get_fundamentals_by_symbol("INVALID")

        assert result is None

    def test_get_fundamentals_by_symbol_no_dependencies(self):
        """Test get_fundamentals_by_symbol with no dependencies."""
        manager = FundamentalsManager(None, None, None)

        result = manager.get_fundamentals_by_symbol("AAPL")

        assert result is None

    # ============================================================================
    # SET ENTITY TO DATABASE TESTS
    # ============================================================================

    def test_set_entity_to_database_success(self, manager, mock_db_manager, sample_fundamentals):
        """Test successful storage of fundamentals to database."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        result = manager.set_entity_to_database("1", sample_fundamentals)

        assert result is True
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()

        # Verify the SQL values passed
        call_args = mock_cursor.execute.call_args[0]
        values = call_args[1]
        assert values[0] == 1  # asset_id
        assert values[1] == "Apple Inc."  # company_name
        assert values[5] == 300000000000  # market_cap

    def test_set_entity_to_database_none_entity(self, manager, mock_db_manager):
        """Test set_entity_to_database with None entity."""
        result = manager.set_entity_to_database("1", None)

        assert result is False

    def test_set_entity_to_database_no_dependencies(self, sample_fundamentals):
        """Test set_entity_to_database with no dependencies."""
        manager = FundamentalsManager(None, None, None)

        result = manager.set_entity_to_database("1", sample_fundamentals)

        assert result is False

    def test_set_entity_to_database_decimal_conversion(self, manager, mock_db_manager, sample_fundamentals):
        """Test that Decimal fields are converted to float for storage."""
        # Mock database connection
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_db_manager.get_connection.return_value.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        result = manager.set_entity_to_database("1", sample_fundamentals)

        assert result is True

        # Verify Decimal fields converted to float
        call_args = mock_cursor.execute.call_args[0]
        values = call_args[1]
        assert isinstance(values[8], float)  # beta
        assert isinstance(values[9], float)  # pe_ratio
        assert isinstance(values[10], float)  # dividend_yield

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

        # Mock stats queries (order matters for multiple fetchone calls)
        mock_cursor.fetchone.side_effect = [
            (100,),  # Total fundamentals
            ("2025-09-30T12:00:00",),  # Last update
            (95,)  # With market cap
        ]
        mock_cursor.fetchall.return_value = [
            ("Technology", 40),
            ("Healthcare", 20),
            ("Finance", 15)
        ]

        stats = manager.get_stats()

        assert stats is not None
        assert "metadata_type" in stats
        assert stats["metadata_type"] == "fundamentals"
        assert "ttl_hours" in stats
        assert stats["ttl_hours"] == 168
        assert "total_fundamentals" in stats
        assert stats["total_fundamentals"] == 100
        assert "with_market_cap" in stats
        assert stats["with_market_cap"] == 95
        assert "top_sectors" in stats
        assert stats["top_sectors"]["Technology"] == 40

    def test_get_stats_no_dependencies(self):
        """Test get_stats with no dependencies."""
        manager = FundamentalsManager(None, None, None)

        stats = manager.get_stats()

        assert stats is not None
        assert "error" in stats
        assert stats["error"] == "Dependencies not available"
