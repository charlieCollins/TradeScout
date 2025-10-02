"""Unit tests for MarketSnapshotManager database manager."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
from decimal import Decimal

from database.managers.market_snapshot_manager import MarketSnapshotManager
from models.snapshot import MarketSnapshot, TickerSnapshot, MinuteBar
from models.data_update_metadata import DataUpdateMetadataType


class TestMarketSnapshotManager:
    """Test MarketSnapshotManager database operations."""

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
        """Create MarketSnapshotManager instance."""
        return MarketSnapshotManager(mock_db_manager, mock_update_tracker)

    @pytest.fixture
    def sample_market_snapshot(self):
        """Create sample MarketSnapshot for testing."""
        # Create sample ticker snapshots
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

        ticker1 = TickerSnapshot(
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

        ticker2 = TickerSnapshot(
            symbol="MSFT",
            prev_close=Decimal("310.00"),
            prev_volume=600000,
            open_price=Decimal("310.00"),
            high_price=Decimal("315.00"),
            low_price=Decimal("308.00"),
            close_price=Decimal("312.50"),
            volume=500000,
            vwap=Decimal("311.25"),
            last_price=Decimal("312.50"),
            last_timestamp=datetime(2025, 9, 28, 16, 0, 0),
            min_bar=min_bar,
            market_status="closed",
            updated_ns=1695920400000000000
        )

        return MarketSnapshot(
            tickers={"AAPL": ticker1, "MSFT": ticker2},
            timestamp=datetime(2025, 9, 28, 16, 0, 0),
            market_status="closed",
            total_symbols=2
        )

    # ============================================================================
    # METADATA TYPE & TTL TESTS
    # ============================================================================

    def test_get_data_update_metadata_type(self, manager):
        """Test that manager returns correct metadata type."""
        assert manager.get_data_update_metadata_type() == DataUpdateMetadataType.MARKET_SNAPSHOTS

    def test_get_ttl_seconds(self, manager):
        """Test that manager returns TTL in seconds."""
        ttl = manager.get_ttl_seconds()
        assert ttl == 15 * 60  # 15 minutes in seconds
        assert isinstance(ttl, int)

    # ============================================================================
    # GET ENTITY FROM DATABASE TESTS
    # ============================================================================

    def test_get_entity_from_database_returns_none(self, manager):
        """Test that get_entity_from_database always returns None.

        MarketSnapshot is not stored as an entity, so this should always
        return None to indicate a fetch is needed.
        """
        result = manager.get_entity_from_database("all")
        assert result is None

    # ============================================================================
    # SET ENTITY TO DATABASE TESTS
    # ============================================================================

    def test_set_entity_to_database_success(self, manager, sample_market_snapshot):
        """Test successful metadata update for market snapshot."""
        result = manager.set_entity_to_database("all", sample_market_snapshot)

        # Should return True to indicate metadata tracking successful
        assert result is True

    def test_set_entity_to_database_none_entity(self, manager):
        """Test set fails with None entity."""
        result = manager.set_entity_to_database("all", None)
        assert result is False

    def test_set_entity_to_database_no_dependencies(self, manager, sample_market_snapshot):
        """Test set fails when dependencies are missing."""
        manager.db_manager = None
        result = manager.set_entity_to_database("all", sample_market_snapshot)
        assert result is False

    # ============================================================================
    # GET OR FETCH TESTS
    # ============================================================================

    def test_get_or_fetch_when_data_fresh(self, manager, sample_market_snapshot):
        """Test get_or_fetch skips fetch when data is fresh (within TTL)."""
        # Mock metadata_manager to indicate data is fresh
        manager.metadata_manager = Mock()
        manager.metadata_manager.is_stale.return_value = False

        fetch_fn = Mock(return_value=sample_market_snapshot)

        result = manager.get_or_fetch("all", fetch_fn)

        # Should NOT fetch because data is fresh - returns None to avoid API waste
        assert result is None
        fetch_fn.assert_not_called()

    def test_get_or_fetch_when_data_stale(self, manager, sample_market_snapshot):
        """Test get_or_fetch calls fetch_fn when data is stale."""
        # Mock metadata_manager to indicate data is stale
        manager.metadata_manager = Mock()
        manager.metadata_manager.is_stale.return_value = True

        fetch_fn = Mock(return_value=sample_market_snapshot)

        result = manager.get_or_fetch("all", fetch_fn)

        # Should fetch because data is stale
        assert result == sample_market_snapshot
        fetch_fn.assert_called_once()

    def test_get_or_fetch_with_force_refresh(self, manager, sample_market_snapshot):
        """Test get_or_fetch with force_refresh bypasses TTL."""
        # Mock metadata_manager to indicate data is fresh
        manager.metadata_manager = Mock()
        manager.metadata_manager.is_stale.return_value = False

        fetch_fn = Mock(return_value=sample_market_snapshot)

        result = manager.get_or_fetch("all", fetch_fn, force_refresh=True)

        assert result == sample_market_snapshot
        fetch_fn.assert_called_once()
        # Verify TTL check was NOT called when force_refresh=True
        manager.metadata_manager.is_stale.assert_not_called()

    def test_get_or_fetch_fetch_returns_none(self, manager):
        """Test get_or_fetch when API fetch returns None."""
        # Mock metadata_manager to indicate data is stale (should fetch)
        manager.metadata_manager = Mock()
        manager.metadata_manager.is_stale.return_value = True

        fetch_fn = Mock(return_value=None)

        result = manager.get_or_fetch("all", fetch_fn)

        assert result is None
        fetch_fn.assert_called_once()

    # ============================================================================
    # STATISTICS TESTS
    # ============================================================================

    def test_get_stats(self, manager):
        """Test get_stats returns manager statistics."""
        stats = manager.get_stats()

        assert stats is not None
        assert "metadata_type" in stats
        assert stats["metadata_type"] == "market_snapshots"
        assert "ttl_minutes" in stats
        assert stats["ttl_minutes"] == 15
        assert "storage" in stats

    # ============================================================================
    # HELPER METHOD TESTS
    # ============================================================================

    def test_should_store_individual_tickers_true(self, manager, sample_market_snapshot):
        """Test should_store_individual_tickers returns True for valid snapshot."""
        result = manager.should_store_individual_tickers(sample_market_snapshot)
        assert result is True

    def test_should_store_individual_tickers_none_snapshot(self, manager):
        """Test should_store_individual_tickers returns False for None."""
        result = manager.should_store_individual_tickers(None)
        assert result is False

    def test_should_store_individual_tickers_empty_snapshot(self, manager):
        """Test should_store_individual_tickers returns False for empty snapshot."""
        empty_snapshot = MarketSnapshot(
            tickers={},
            timestamp=datetime.now(),
            market_status="closed",
            total_symbols=0
        )
        result = manager.should_store_individual_tickers(empty_snapshot)
        assert result is False