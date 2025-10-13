"""Unit tests for UniverseRepository - Universe membership management."""

import pytest
from datetime import datetime
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

import sys
sys.path.insert(0, '/home/ccollins/projects/TradeScout/src')

from repositories.universe_repository import UniverseRepository
from models.universe_sqlmodel import UniverseSQLModel, UniverseMembershipSQLModel
from models.asset_sqlmodel import AssetSQLModel
from models.provider_sqlmodel import ProviderSQLModel


class TestUniverseRepository:
    """Test UniverseRepository business operations.

    These tests use in-memory SQLite for fast, isolated testing.
    Critical for validating universe membership management for gap trading.
    """

    @pytest.fixture
    def engine(self):
        """Create in-memory SQLite engine for testing."""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        SQLModel.metadata.create_all(engine)
        return engine

    @pytest.fixture
    def session(self, engine):
        """Create database session for testing."""
        with Session(engine) as session:
            yield session

    @pytest.fixture
    def repository(self, session):
        """Create UniverseRepository instance."""
        return UniverseRepository(session)

    @pytest.fixture
    def provider(self, session):
        """Create test provider."""
        provider = ProviderSQLModel(
            id=1,
            name="polygon",
            display_name="Polygon.io",
            is_active=True,
            created_at=datetime.now()
        )
        session.add(provider)
        session.commit()
        session.refresh(provider)
        return provider

    @pytest.fixture
    def assets(self, session, provider):
        """Create test assets."""
        assets = [
            AssetSQLModel(
                id=1, symbol="AAPL", name="Apple Inc.",
                asset_type="stock", asset_class="equity",
                market_id=1, currency="USD", lot_size=1,
                is_active=True, is_delisted=False,
                provider_id=provider.id,
                created_at=datetime.now(), updated_at=datetime.now()
            ),
            AssetSQLModel(
                id=2, symbol="MSFT", name="Microsoft Corp.",
                asset_type="stock", asset_class="equity",
                market_id=1, currency="USD", lot_size=1,
                is_active=True, is_delisted=False,
                provider_id=provider.id,
                created_at=datetime.now(), updated_at=datetime.now()
            ),
            AssetSQLModel(
                id=3, symbol="GOOGL", name="Alphabet Inc.",
                asset_type="stock", asset_class="equity",
                market_id=1, currency="USD", lot_size=1,
                is_active=True, is_delisted=False,
                provider_id=provider.id,
                created_at=datetime.now(), updated_at=datetime.now()
            ),
        ]
        session.add_all(assets)
        session.commit()
        return assets

    @pytest.fixture
    def universes(self, session):
        """Create test universes."""
        universes = [
            UniverseSQLModel(
                id=1,
                name="gap_trading_universe",
                description="Assets for gap trading strategy",
                min_market_cap=300_000_000,
                min_volume=1_000_000,
                is_active=True,
                created_at=datetime.now(),
                updated_at=datetime.now()
            ),
            UniverseSQLModel(
                id=2,
                name="tech_universe",
                description="Technology sector stocks",
                min_market_cap=1_000_000_000,
                is_active=False,
                created_at=datetime.now(),
                updated_at=datetime.now()
            ),
            UniverseSQLModel(
                id=3,
                name="large_cap_universe",
                description="Large cap stocks",
                min_market_cap=10_000_000_000,
                is_active=False,
                created_at=datetime.now(),
                updated_at=datetime.now()
            ),
        ]
        session.add_all(universes)
        session.commit()
        return universes

    @pytest.fixture
    def memberships(self, session, universes, assets):
        """Create test universe memberships."""
        memberships = [
            # gap_trading_universe has AAPL and MSFT
            UniverseMembershipSQLModel(
                universe_id=1, asset_id=1, created_at=datetime.now()
            ),
            UniverseMembershipSQLModel(
                universe_id=1, asset_id=2, created_at=datetime.now()
            ),
            # tech_universe has all 3 stocks
            UniverseMembershipSQLModel(
                universe_id=2, asset_id=1, created_at=datetime.now()
            ),
            UniverseMembershipSQLModel(
                universe_id=2, asset_id=2, created_at=datetime.now()
            ),
            UniverseMembershipSQLModel(
                universe_id=2, asset_id=3, created_at=datetime.now()
            ),
        ]
        session.add_all(memberships)
        session.commit()
        return memberships

    # ============================================================================
    # BASIC QUERIES - Universe
    # ============================================================================

    def test_get_by_name_success(self, repository, universes):
        """Test get_by_name returns correct universe."""
        result = repository.get_by_name("gap_trading_universe")

        assert result is not None
        assert result.name == "gap_trading_universe"
        assert result.description == "Assets for gap trading strategy"

    def test_get_by_name_not_found(self, repository):
        """Test get_by_name returns None for non-existent universe."""
        result = repository.get_by_name("nonexistent_universe")
        assert result is None

    def test_get_by_id_success(self, repository, universes):
        """Test get_by_id returns correct universe."""
        result = repository.get_by_id(1)

        assert result is not None
        assert result.name == "gap_trading_universe"

    def test_find_all(self, repository, universes):
        """Test find_all returns all universes."""
        results = repository.find_all()

        assert len(results) == 3
        names = [u.name for u in results]
        assert "gap_trading_universe" in names
        assert "tech_universe" in names
        assert "large_cap_universe" in names

    def test_find_all_active(self, repository, universes):
        """Test find_all_active returns only active universes."""
        results = repository.find_all_active()

        # Only gap_trading_universe is active
        assert len(results) == 1
        assert results[0].name == "gap_trading_universe"

    def test_get_active_universe(self, repository, universes):
        """Test get_active_universe returns the active universe."""
        result = repository.get_active_universe()

        assert result is not None
        assert result.name == "gap_trading_universe"
        assert result.is_active is True

    def test_get_active_universe_none_active(self, repository, session):
        """Test get_active_universe returns None when no universe is active."""
        # Deactivate all universes
        universes = repository.find_all()
        for u in universes:
            u.is_active = False
        session.commit()

        result = repository.get_active_universe()
        assert result is None

    # ============================================================================
    # ACTIVE UNIVERSE MANAGEMENT (BUSINESS CRITICAL)
    # ============================================================================

    def test_set_active_universe_success(self, repository, universes):
        """Test set_active_universe activates specified universe."""
        result = repository.set_active_universe("tech_universe")

        assert result is True

        # Verify tech_universe is now active
        active = repository.get_active_universe()
        assert active.name == "tech_universe"

        # Verify gap_trading_universe is now inactive
        gap_universe = repository.get_by_name("gap_trading_universe")
        assert gap_universe.is_active is False

    def test_set_active_universe_deactivates_others(self, repository, universes):
        """Test set_active_universe deactivates all other universes."""
        repository.set_active_universe("large_cap_universe")

        # All universes should be inactive except large_cap_universe
        all_universes = repository.find_all()
        active_count = sum(1 for u in all_universes if u.is_active)
        assert active_count == 1

        active = repository.get_active_universe()
        assert active.name == "large_cap_universe"

    def test_set_active_universe_not_found(self, repository, universes):
        """Test set_active_universe returns False for non-existent universe."""
        result = repository.set_active_universe("nonexistent_universe")

        assert result is False

        # NOTE: Current implementation deactivates all universes first,
        # then fails to find target. No rollback happens, so no universe is active.
        # This is a known limitation - could be improved with rollback on failure.
        active = repository.get_active_universe()
        assert active is None  # No universe is active after failed attempt

    # ============================================================================
    # PERSISTENCE - Universe
    # ============================================================================

    def test_save_new_universe(self, repository):
        """Test save() persists new universe."""
        new_universe = UniverseSQLModel(
            name="momentum_universe",
            description="Momentum strategy stocks",
            min_market_cap=500_000_000,
            is_active=False,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

        result = repository.save(new_universe)

        assert result.id is not None
        assert result.name == "momentum_universe"

    def test_delete_universe(self, repository, session, universes, memberships):
        """Test delete() removes universe and memberships."""
        universe = repository.get_by_name("gap_trading_universe")

        # Should have 2 memberships before deletion
        count_before = repository.count_memberships(universe.id)
        assert count_before == 2

        memberships_deleted = repository.delete(universe)

        # Should have deleted 2 memberships
        assert memberships_deleted == 2

        # Universe should be gone
        result = repository.get_by_name("gap_trading_universe")
        assert result is None

    # ============================================================================
    # MEMBERSHIP QUERIES
    # ============================================================================

    def test_get_memberships(self, repository, universes, memberships):
        """Test get_memberships returns memberships for universe."""
        results = repository.get_memberships(universe_id=1)

        # gap_trading_universe has 2 memberships
        assert len(results) == 2
        asset_ids = [m.asset_id for m in results]
        assert 1 in asset_ids  # AAPL
        assert 2 in asset_ids  # MSFT

    def test_get_memberships_with_limit(self, repository, universes, memberships):
        """Test get_memberships respects limit parameter."""
        results = repository.get_memberships(universe_id=2, limit=2)

        # tech_universe has 3 memberships, but limited to 2
        assert len(results) == 2

    def test_get_memberships_by_universe_name(self, repository, universes, memberships):
        """Test get_memberships_by_universe_name returns memberships."""
        results = repository.get_memberships_by_universe_name("tech_universe")

        # tech_universe has 3 memberships
        assert len(results) == 3

    def test_get_memberships_by_universe_name_not_found(self, repository):
        """Test get_memberships_by_universe_name returns empty for non-existent."""
        results = repository.get_memberships_by_universe_name("nonexistent")
        assert len(results) == 0

    def test_get_active_universe_asset_ids(self, repository, universes, memberships, assets):
        """Test get_active_universe_asset_ids returns asset IDs."""
        results = repository.get_active_universe_asset_ids()

        # gap_trading_universe (active) has AAPL and MSFT
        assert len(results) == 2
        assert 1 in results  # AAPL
        assert 2 in results  # MSFT

    def test_get_active_universe_symbols(self, repository, universes, memberships, assets):
        """Test get_active_universe_symbols returns symbols (critical for gap trading)."""
        results = repository.get_active_universe_symbols()

        # gap_trading_universe (active) has AAPL and MSFT
        assert len(results) == 2
        assert "AAPL" in results
        assert "MSFT" in results
        # Should be sorted alphabetically
        assert results == sorted(results)

    def test_get_active_universe_symbols_filters_inactive_assets(self, repository, session, universes, memberships, assets):
        """Test get_active_universe_symbols excludes inactive assets."""
        # Mark MSFT as inactive
        msft = session.get(AssetSQLModel, 2)
        msft.is_active = False
        session.commit()

        results = repository.get_active_universe_symbols()

        # Should only return AAPL (active)
        assert len(results) == 1
        assert "AAPL" in results
        assert "MSFT" not in results

    def test_is_symbol_in_universe_true(self, repository, universes, memberships, assets):
        """Test is_symbol_in_universe returns True for member."""
        result = repository.is_symbol_in_universe("AAPL", "gap_trading_universe")
        assert result is True

    def test_is_symbol_in_universe_false(self, repository, universes, memberships, assets):
        """Test is_symbol_in_universe returns False for non-member."""
        result = repository.is_symbol_in_universe("GOOGL", "gap_trading_universe")
        assert result is False

    def test_is_symbol_in_universe_case_insensitive(self, repository, universes, memberships, assets):
        """Test is_symbol_in_universe handles lowercase symbols."""
        result = repository.is_symbol_in_universe("aapl", "gap_trading_universe")
        assert result is True

    def test_is_symbol_in_universe_not_found_universe(self, repository, assets):
        """Test is_symbol_in_universe returns False for non-existent universe."""
        result = repository.is_symbol_in_universe("AAPL", "nonexistent_universe")
        assert result is False

    # ============================================================================
    # MEMBERSHIP MANAGEMENT (BUSINESS CRITICAL)
    # ============================================================================

    def test_add_memberships_new(self, repository, universes, assets):
        """Test add_memberships adds new memberships."""
        count = repository.add_memberships(universe_id=3, asset_ids=[1, 2, 3])

        assert count == 3

        # Verify memberships were added
        memberships = repository.get_memberships(universe_id=3)
        assert len(memberships) == 3

    def test_add_memberships_duplicate(self, repository, universes, memberships, assets):
        """Test add_memberships skips existing memberships."""
        # Try to add AAPL again to gap_trading_universe (already exists)
        count = repository.add_memberships(universe_id=1, asset_ids=[1])

        # Should skip duplicate
        assert count == 0

        # Should still have only 2 memberships
        all_memberships = repository.get_memberships(universe_id=1)
        assert len(all_memberships) == 2

    def test_add_memberships_mixed(self, repository, universes, memberships, assets):
        """Test add_memberships handles mix of new and existing."""
        # gap_trading_universe already has AAPL (1) and MSFT (2)
        # Try to add MSFT (duplicate) and GOOGL (new)
        count = repository.add_memberships(universe_id=1, asset_ids=[2, 3])

        # Should only add GOOGL
        assert count == 1

        # Should now have 3 memberships
        all_memberships = repository.get_memberships(universe_id=1)
        assert len(all_memberships) == 3

    def test_clear_memberships(self, repository, universes, memberships):
        """Test clear_memberships removes all memberships."""
        # gap_trading_universe has 2 memberships
        count_before = repository.count_memberships(universe_id=1)
        assert count_before == 2

        count = repository.clear_memberships(universe_id=1)

        assert count == 2

        # Should now have 0 memberships
        count_after = repository.count_memberships(universe_id=1)
        assert count_after == 0

    def test_clear_memberships_empty_universe(self, repository, universes):
        """Test clear_memberships works on universe with no memberships."""
        # large_cap_universe has no memberships
        count = repository.clear_memberships(universe_id=3)

        assert count == 0

    # ============================================================================
    # STATISTICS
    # ============================================================================

    def test_count_all(self, repository, universes):
        """Test count_all returns correct count."""
        count = repository.count_all()

        assert count == 3

    def test_count_memberships(self, repository, universes, memberships):
        """Test count_memberships returns correct count."""
        count = repository.count_memberships(universe_id=2)

        # tech_universe has 3 memberships
        assert count == 3

    def test_count_memberships_empty(self, repository, universes):
        """Test count_memberships returns 0 for empty universe."""
        count = repository.count_memberships(universe_id=3)

        assert count == 0

    # ============================================================================
    # BUSINESS WORKFLOWS
    # ============================================================================

    def test_workflow_switch_active_universe(self, repository, universes, memberships, assets):
        """Test complete workflow: switch active universe and get symbols."""
        # Start with gap_trading_universe active
        symbols_before = repository.get_active_universe_symbols()
        assert symbols_before == ["AAPL", "MSFT"]

        # Switch to tech_universe
        repository.set_active_universe("tech_universe")

        # Get new symbols
        symbols_after = repository.get_active_universe_symbols()
        assert symbols_after == ["AAPL", "GOOGL", "MSFT"]

    def test_workflow_rebuild_universe(self, repository, universes, memberships, assets):
        """Test complete workflow: clear and rebuild universe."""
        universe_id = 1  # gap_trading_universe

        # Clear existing memberships
        cleared = repository.clear_memberships(universe_id)
        assert cleared == 2

        # Add all assets
        added = repository.add_memberships(universe_id, [1, 2, 3])
        assert added == 3

        # Verify new membership count
        count = repository.count_memberships(universe_id)
        assert count == 3
