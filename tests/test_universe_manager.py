"""
Tests for Universe Manager

Tests universe management functionality including:
- Universe creation and management
- Asset-universe membership operations
- Universe statistics and queries
- Asset activation/deactivation in universes
- Database integrity
"""

import pytest
import sqlite3
import tempfile
from datetime import datetime, date

from src.tradescout.storage.sqlite_repository import SQLiteDatabaseManager
from src.tradescout.storage.universe_manager import UniverseManager


class TestUniverseManager:
    """Test suite for UniverseManager"""

    @pytest.fixture
    def temp_db(self):
        """Create temporary database for testing"""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp_file:
            db_path = tmp_file.name
        
        db_manager = SQLiteDatabaseManager(db_path)
        yield db_manager
        
        # Cleanup
        import os
        os.unlink(db_path)

    @pytest.fixture
    def universe_manager(self, temp_db):
        """Create UniverseManager instance for testing"""
        return UniverseManager(temp_db)

    @pytest.fixture
    def sample_assets(self, universe_manager):
        """Create sample assets in database for testing"""
        conn = universe_manager._get_connection()
        cursor = conn.cursor()
        
        # Create sample assets
        assets = [
            ("AAPL", "Apple Inc.", "common_stock", "NASDAQ", "USD"),
            ("MSFT", "Microsoft Corporation", "common_stock", "NASDAQ", "USD"),
            ("TSLA", "Tesla Inc.", "common_stock", "NASDAQ", "USD"),
            ("SPY", "SPDR S&P 500 ETF", "etf", "NYSE", "USD")
        ]
        
        for symbol, name, asset_type, market_id, currency in assets:
            cursor.execute("""
                INSERT INTO assets (symbol, name, asset_type, market_id, currency, is_active)
                VALUES (?, ?, ?, ?, ?, 1)
            """, (symbol, name, asset_type, market_id, currency))
        
        conn.commit()
        conn.close()
        return [asset[0] for asset in assets]  # Return symbols

    def test_database_initialization(self, temp_db):
        """Test that database initializes properly"""
        # Test that universes table exists
        conn = temp_db.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='universes'")
        assert cursor.fetchone() is not None
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='universe_memberships'")
        assert cursor.fetchone() is not None
        
        # Check default universe exists
        cursor.execute("SELECT * FROM universes WHERE name = 'default_universe'")
        default_universe = cursor.fetchone()
        assert default_universe is not None
        
        conn.close()

    def test_universe_creation(self, universe_manager):
        """Test creating universes"""
        # Create universe
        universe_id = universe_manager.create_universe("test_universe", "Test universe for unit tests")
        assert universe_id is not None
        assert universe_id > 0
        
        # Verify universe was stored
        universe = universe_manager.get_universe("test_universe")
        assert universe is not None
        assert universe['name'] == "test_universe"
        assert universe['description'] == "Test universe for unit tests"

    def test_universe_duplicate_prevention(self, universe_manager):
        """Test that duplicate universes are handled correctly"""
        # Create universe first time
        universe_id_1 = universe_manager.create_universe("duplicate_test", "First description")
        
        # Try to create same universe again should fail due to unique constraint
        with pytest.raises(Exception):
            universe_manager.create_universe("duplicate_test", "Second description")

    def test_get_universe_nonexistent(self, universe_manager):
        """Test getting universe that doesn't exist"""
        result = universe_manager.get_universe("NONEXISTENT")
        assert result is None

    def test_add_asset_to_universe(self, universe_manager, sample_assets):
        """Test adding assets to universe"""
        # Create universe
        universe_manager.create_universe("liquid_universe", "High volume liquid stocks")
        
        # Add asset to universe
        success = universe_manager.add_to_universe("AAPL", "liquid_universe", "High volume tech stock")
        assert success is True
        
        # Verify membership
        assets = universe_manager.get_universe_assets("liquid_universe")
        assert "AAPL" in assets

    def test_add_nonexistent_asset_to_universe(self, universe_manager):
        """Test adding non-existent asset to universe fails gracefully"""
        universe_manager.create_universe("test_universe", "Test universe")
        
        success = universe_manager.add_to_universe("NONEXISTENT", "test_universe")
        assert success is False

    def test_add_asset_to_nonexistent_universe(self, universe_manager, sample_assets):
        """Test adding asset to non-existent universe fails gracefully"""
        success = universe_manager.add_to_universe("AAPL", "nonexistent_universe")
        assert success is False

    def test_remove_asset_from_universe(self, universe_manager, sample_assets):
        """Test removing assets from universe"""
        # Create universe and add asset
        universe_manager.create_universe("test_universe", "Test universe")
        universe_manager.add_to_universe("AAPL", "test_universe")
        
        # Verify asset is in universe
        assets = universe_manager.get_universe_assets("test_universe")
        assert "AAPL" in assets
        
        # Remove asset from universe
        success = universe_manager.remove_from_universe("AAPL", "test_universe", "Testing removal")
        assert success is True
        
        # Verify asset is no longer in universe
        assets = universe_manager.get_universe_assets("test_universe")
        assert "AAPL" not in assets

    def test_get_universe_assets(self, universe_manager, sample_assets):
        """Test getting all assets in a universe"""
        # Create universe and add multiple assets
        universe_manager.create_universe("tech_universe", "Technology stocks")
        
        tech_stocks = ["AAPL", "MSFT", "TSLA"]
        for symbol in tech_stocks:
            universe_manager.add_to_universe(symbol, "tech_universe")
        
        # Get universe assets
        universe_assets = universe_manager.get_universe_assets("tech_universe")
        
        assert len(universe_assets) == 3
        for symbol in tech_stocks:
            assert symbol in universe_assets

    def test_get_universe_assets_empty(self, universe_manager):
        """Test getting assets from empty universe"""
        universe_manager.create_universe("empty_universe", "Empty universe")
        
        universe_assets = universe_manager.get_universe_assets("empty_universe")
        assert len(universe_assets) == 0

    def test_get_asset_universes(self, universe_manager, sample_assets):
        """Test getting all universes that contain an asset"""
        # Create multiple universes and add AAPL to both
        universe_manager.create_universe("tech_universe", "Tech stocks")
        universe_manager.create_universe("large_cap_universe", "Large cap stocks")
        
        universe_manager.add_to_universe("AAPL", "tech_universe")
        universe_manager.add_to_universe("AAPL", "large_cap_universe")
        
        # Get universes containing AAPL
        universes = universe_manager.get_asset_universes("AAPL")
        
        assert len(universes) == 2
        assert "tech_universe" in universes
        assert "large_cap_universe" in universes

    def test_deactivate_asset(self, universe_manager, sample_assets):
        """Test deactivating an asset (removes from all universes)"""
        # Create universes and add AAPL to both
        universe_manager.create_universe("universe1", "Universe 1")
        universe_manager.create_universe("universe2", "Universe 2")
        
        universe_manager.add_to_universe("AAPL", "universe1")
        universe_manager.add_to_universe("AAPL", "universe2")
        
        # Verify AAPL is in both universes
        assert "AAPL" in universe_manager.get_universe_assets("universe1")
        assert "AAPL" in universe_manager.get_universe_assets("universe2")
        
        # Deactivate AAPL
        success = universe_manager.deactivate_asset("AAPL")
        assert success is True
        
        # Verify AAPL is removed from both universes
        assert "AAPL" not in universe_manager.get_universe_assets("universe1")
        assert "AAPL" not in universe_manager.get_universe_assets("universe2")

    def test_get_all_active_assets(self, universe_manager, sample_assets):
        """Test getting all active assets across universes"""
        # Create universe and add assets
        universe_manager.create_universe("active_universe", "Active assets")
        
        for symbol in sample_assets[:3]:  # Add first 3 assets
            universe_manager.add_to_universe(symbol, "active_universe")
        
        # Get all active assets
        active_assets = universe_manager.get_all_active_assets()
        
        assert len(active_assets) >= 3
        for symbol in sample_assets[:3]:
            assert symbol in active_assets

    def test_universe_statistics(self, universe_manager, sample_assets):
        """Test getting universe statistics"""
        # Create universe and add assets
        universe_manager.create_universe("stats_universe", "Universe for statistics")
        
        # Add some assets
        for symbol in sample_assets[:2]:
            universe_manager.add_to_universe(symbol, "stats_universe")
        
        # Remove one asset
        universe_manager.remove_from_universe(sample_assets[0], "stats_universe")
        
        # Get statistics
        stats = universe_manager.get_universe_statistics("stats_universe")
        
        assert stats['total_assets'] == 2  # 2 total memberships
        assert stats['active_assets'] == 1  # 1 still active
        assert stats['first_asset_added'] is not None
        assert stats['last_asset_added'] is not None

    def test_database_integrity_foreign_keys(self, universe_manager, sample_assets):
        """Test database foreign key constraints"""
        # Create universe and add asset
        universe_manager.create_universe("integrity_test", "Test universe")
        universe_manager.add_to_universe("AAPL", "integrity_test")
        
        # Verify the relationships exist
        conn = universe_manager._get_connection()
        cursor = conn.cursor()
        
        # Check that asset and universe exist in membership table
        cursor.execute("""
            SELECT um.*, a.symbol, u.name
            FROM universe_memberships um
            JOIN assets a ON um.asset_id = a.id
            JOIN universes u ON um.universe_id = u.id
            WHERE a.symbol = ? AND u.name = ?
        """, ("AAPL", "integrity_test"))
        
        row = cursor.fetchone()
        assert row is not None
        assert row['symbol'] == "AAPL"
        assert row['name'] == "integrity_test"
        
        conn.close()

    def test_multiple_universe_operations(self, universe_manager, sample_assets):
        """Test complex operations across multiple universes"""
        # Create multiple universes
        universes = [
            ("large_cap", "Large cap stocks"),
            ("tech_sector", "Technology sector"),
            ("growth_stocks", "High growth stocks")
        ]
        
        for name, desc in universes:
            universe_manager.create_universe(name, desc)
        
        # Add assets to multiple universes
        universe_manager.add_to_universe("AAPL", "large_cap")
        universe_manager.add_to_universe("AAPL", "tech_sector")
        universe_manager.add_to_universe("AAPL", "growth_stocks")
        
        universe_manager.add_to_universe("MSFT", "large_cap")
        universe_manager.add_to_universe("MSFT", "tech_sector")
        
        universe_manager.add_to_universe("TSLA", "growth_stocks")
        
        # Verify memberships
        assert len(universe_manager.get_asset_universes("AAPL")) == 3
        assert len(universe_manager.get_asset_universes("MSFT")) == 2
        assert len(universe_manager.get_asset_universes("TSLA")) == 1
        
        # Test universe asset counts
        assert len(universe_manager.get_universe_assets("large_cap")) == 2
        assert len(universe_manager.get_universe_assets("tech_sector")) == 2
        assert len(universe_manager.get_universe_assets("growth_stocks")) == 2
        
        # Remove AAPL from tech sector
        universe_manager.remove_from_universe("AAPL", "tech_sector")
        
        # Verify removal
        assert len(universe_manager.get_asset_universes("AAPL")) == 2
        assert len(universe_manager.get_universe_assets("tech_sector")) == 1