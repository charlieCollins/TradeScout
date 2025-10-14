"""Integration tests for DataServiceV2 - Orchestration layer testing.

These tests verify that DataServiceV2 correctly orchestrates:
- Repositories (business queries)
- CacheService (cache-aside pattern)
- API Providers (Polygon API - mocked)

Unlike unit tests, these test the full integration between layers.
"""

import pytest
from datetime import datetime, date
from decimal import Decimal
from unittest.mock import Mock, MagicMock, patch
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

import sys
sys.path.insert(0, '/home/ccollins/projects/TradeScout/src')

from services.data_service_v2 import DataServiceV2
from models.asset_sqlmodel import AssetSQLModel
from models.market_sqlmodel import MarketSQLModel
from models.fundamentals_sqlmodel import FundamentalsSQLModel
from models.provider_sqlmodel import ProviderSQLModel
from models.universe_sqlmodel import UniverseSQLModel, UniverseMembershipSQLModel
from models.asset_price_sqlmodel import AssetPriceSQLModel


class TestDataServiceV2Integration:
    """Integration tests for DataServiceV2.

    These tests use in-memory SQLite and mock API providers.
    They test the full orchestration layer without external dependencies.
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
    def mock_db_manager(self):
        """Mock the old DatabaseManager (used for metadata tracking)."""
        mock_db = Mock()
        mock_db.get_connection = MagicMock()
        return mock_db

    @pytest.fixture
    def mock_metadata_manager(self):
        """Mock metadata manager for TTL tracking."""
        mock_manager = Mock()
        mock_manager.is_data_stale = Mock(return_value=False)
        mock_manager.update_last_update_time = Mock()
        return mock_manager

    @pytest.fixture
    def data_service(self, session, mock_metadata_manager):
        """Create DataServiceV2 instance with mocked dependencies."""
        # Patch DatabaseManager and DataUpdateMetadataManager to avoid file I/O
        with patch('services.data_service_v2.DatabaseManager') as mock_db, \
             patch('services.data_service_v2.DataUpdateMetadataManager') as mock_meta:

            mock_meta.return_value = mock_metadata_manager

            service = DataServiceV2.__new__(DataServiceV2)
            service.metadata_manager = mock_metadata_manager

            # Initialize repositories manually
            from repositories.asset_repository import AssetRepository
            from repositories.market_repository import MarketRepository
            from repositories.fundamentals_repository import FundamentalsRepository
            from repositories.provider_repository import ProviderRepository
            from repositories.universe_repository import UniverseRepository
            from repositories.asset_price_repository import AssetPriceRepository

            service.asset_repository = AssetRepository(session)
            service.market_repository = MarketRepository(session)
            service.fundamentals_repository = FundamentalsRepository(session)
            service.provider_repository = ProviderRepository(session)
            service.universe_repository = UniverseRepository(session)
            service.asset_price_repository = AssetPriceRepository(session)

            # Mock the API provider
            service.polygon_provider = Mock()

            # Initialize cache services manually (simplified without full cache logic)
            from services.cache_service import CacheService, CacheConfig
            from models.data_update_metadata import DataUpdateMetadataType

            service.asset_cache = CacheService[AssetSQLModel](
                repository=service.asset_repository,
                metadata_manager=mock_metadata_manager,
                metadata_type=DataUpdateMetadataType.TICKERS,
                ttl_seconds=CacheConfig.get_ttl(DataUpdateMetadataType.TICKERS)
            )

            service.market_cache = CacheService[MarketSQLModel](
                repository=service.market_repository,
                metadata_manager=mock_metadata_manager,
                metadata_type=DataUpdateMetadataType.MARKETS,
                ttl_seconds=CacheConfig.get_ttl(DataUpdateMetadataType.MARKETS)
            )

            service.fundamentals_cache = CacheService[FundamentalsSQLModel](
                repository=service.fundamentals_repository,
                metadata_manager=mock_metadata_manager,
                metadata_type=DataUpdateMetadataType.FUNDAMENTALS,
                ttl_seconds=CacheConfig.get_ttl(DataUpdateMetadataType.FUNDAMENTALS)
            )

            yield service

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
    def market(self, session):
        """Create test market."""
        market = MarketSQLModel(
            id=1,
            code="XNYS",
            name="New York Stock Exchange",
            country="US",
            is_active=True,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        session.add(market)
        session.commit()
        session.refresh(market)
        return market

    @pytest.fixture
    def assets(self, session, provider, market):
        """Create test assets."""
        assets = [
            AssetSQLModel(
                id=1, symbol="AAPL", name="Apple Inc.",
                asset_type="stock", asset_class="equity",
                market_id=market.id, currency="USD", lot_size=1,
                is_active=True, is_delisted=False,
                provider_id=provider.id,
                created_at=datetime.now(), updated_at=datetime.now()
            ),
            AssetSQLModel(
                id=2, symbol="MSFT", name="Microsoft Corp.",
                asset_type="stock", asset_class="equity",
                market_id=market.id, currency="USD", lot_size=1,
                is_active=True, is_delisted=False,
                provider_id=provider.id,
                created_at=datetime.now(), updated_at=datetime.now()
            ),
        ]
        session.add_all(assets)
        session.commit()
        return assets

    @pytest.fixture
    def fundamentals(self, session, provider, assets):
        """Create test fundamentals."""
        fundamentals = [
            FundamentalsSQLModel(
                asset_id=1,
                company_name="Apple Inc.",
                sector="Technology",
                market_cap=300_000_000_000_000,  # $3T
                avg_volume_30d=50_000_000,
                provider_id=provider.id
            ),
            FundamentalsSQLModel(
                asset_id=2,
                company_name="Microsoft Corp.",
                sector="Technology",
                market_cap=250_000_000_000_000,  # $2.5T
                avg_volume_30d=30_000_000,
                provider_id=provider.id
            ),
        ]
        session.add_all(fundamentals)
        session.commit()
        return fundamentals

    @pytest.fixture
    def prices(self, session, provider, assets):
        """Create test prices with gaps."""
        today = date.today()
        prices = [
            # AAPL with 2% gap up
            AssetPriceSQLModel(
                asset_id=1,
                symbol="AAPL",
                provider_id=provider.id,
                trade_date=today,
                prevday_close=Decimal("150.00"),
                day_open=Decimal("153.00"),
                day_close=Decimal("154.00"),
                updated_at=datetime.now()
            ),
            # MSFT with 3% gap down
            AssetPriceSQLModel(
                asset_id=2,
                symbol="MSFT",
                provider_id=provider.id,
                trade_date=today,
                prevday_close=Decimal("300.00"),
                day_open=Decimal("291.00"),
                day_close=Decimal("292.00"),
                updated_at=datetime.now()
            ),
        ]
        session.add_all(prices)
        session.commit()
        return prices

    @pytest.fixture
    def universe(self, session, assets):
        """Create test universe with memberships."""
        universe = UniverseSQLModel(
            id=1,
            name="test_universe",
            description="Test universe",
            is_active=True,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        session.add(universe)
        session.commit()

        # Add memberships
        memberships = [
            UniverseMembershipSQLModel(universe_id=1, asset_id=1, created_at=datetime.now()),
            UniverseMembershipSQLModel(universe_id=1, asset_id=2, created_at=datetime.now()),
        ]
        session.add_all(memberships)
        session.commit()

        return universe

    # ============================================================================
    # MARKET OPERATIONS (Simple - no API)
    # ============================================================================

    def test_get_market(self, data_service, market):
        """Test get_market returns market from repository."""
        result = data_service.get_market("XNYS")

        assert result is not None
        assert result.code == "XNYS"
        assert result.name == "New York Stock Exchange"

    def test_get_all_markets(self, data_service, market):
        """Test get_all_markets returns all active markets."""
        results = data_service.get_all_markets()

        assert len(results) >= 1
        assert any(m.code == "XNYS" for m in results)

    # ============================================================================
    # FUNDAMENTALS OPERATIONS
    # ============================================================================

    def test_get_fundamentals(self, data_service, fundamentals):
        """Test get_fundamentals returns fundamentals from repository."""
        result = data_service.get_fundamentals(asset_id=1)

        assert result is not None
        assert result.company_name == "Apple Inc."
        assert result.sector == "Technology"

    def test_find_gap_trading_candidates(self, data_service, fundamentals):
        """Test find_gap_trading_candidates filters by market cap."""
        results = data_service.find_gap_trading_candidates()

        # Both stocks exceed $300M threshold
        assert len(results) == 2
        companies = [f.company_name for f in results]
        assert "Apple Inc." in companies
        assert "Microsoft Corp." in companies

    def test_find_by_market_cap(self, data_service, fundamentals):
        """Test find_by_market_cap filters correctly."""
        # Find stocks with at least $2T market cap
        results = data_service.find_by_market_cap(min_cap=2_000_000_000_000)

        # Should find AAPL ($3T) and MSFT ($2.5T)
        assert len(results) == 2

    def test_find_by_sector(self, data_service, fundamentals):
        """Test find_by_sector filters by sector."""
        results = data_service.find_by_sector("Technology")

        assert len(results) == 2
        assert all(f.sector == "Technology" for f in results)

    # ============================================================================
    # UNIVERSE OPERATIONS (Internal-only)
    # ============================================================================

    def test_get_universe(self, data_service, universe):
        """Test get_universe returns universe by name."""
        result = data_service.get_universe("test_universe")

        assert result is not None
        assert result.name == "test_universe"

    def test_get_active_universe(self, data_service, universe):
        """Test get_active_universe returns active universe."""
        result = data_service.get_active_universe()

        assert result is not None
        assert result.name == "test_universe"
        assert result.is_active is True

    def test_get_active_universe_symbols(self, data_service, universe, assets):
        """Test get_active_universe_symbols returns symbols (critical for gap trading)."""
        results = data_service.get_active_universe_symbols()

        assert len(results) == 2
        assert "AAPL" in results
        assert "MSFT" in results

    def test_set_active_universe(self, data_service, session, universe):
        """Test set_active_universe switches active universe."""
        # Create second universe
        universe2 = UniverseSQLModel(
            id=2,
            name="other_universe",
            description="Other universe",
            is_active=False,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        session.add(universe2)
        session.commit()

        # Switch active universe
        result = data_service.set_active_universe("other_universe")

        assert result is True

        # Verify switch
        active = data_service.get_active_universe()
        assert active.name == "other_universe"

    # ============================================================================
    # ASSET PRICE OPERATIONS (Gap Trading)
    # ============================================================================

    def test_get_latest_price(self, data_service, prices):
        """Test get_latest_price returns most recent price."""
        result = data_service.get_latest_price("AAPL")

        assert result is not None
        assert result.symbol == "AAPL"
        assert result.prevday_close == Decimal("150.00")
        assert result.day_open == Decimal("153.00")

    def test_get_latest_prices_batch(self, data_service, prices):
        """Test get_latest_prices returns batch of prices."""
        results = data_service.get_latest_prices(["AAPL", "MSFT"])

        assert len(results) == 2
        symbols = [p.symbol for p in results]
        assert "AAPL" in symbols
        assert "MSFT" in symbols

    def test_find_prices_with_gaps(self, data_service, prices):
        """Test find_prices_with_gaps filters by gap percentage."""
        # Find prices with at least 2% gap
        results = data_service.find_prices_with_gaps(min_gap_percent=2.0)

        # Should find AAPL (2% up) and MSFT (3% down)
        assert len(results) == 2
        symbols = [p.symbol for p in results]
        assert "AAPL" in symbols
        assert "MSFT" in symbols

    def test_find_prices_with_gaps_higher_threshold(self, data_service, prices):
        """Test find_prices_with_gaps with higher threshold."""
        # Find prices with at least 2.5% gap
        results = data_service.find_prices_with_gaps(min_gap_percent=2.5)

        # Should only find MSFT (3% down), not AAPL (2% up)
        assert len(results) == 1
        assert results[0].symbol == "MSFT"

    # ============================================================================
    # INTEGRATION WORKFLOWS (Critical Business Scenarios)
    # ============================================================================

    def test_gap_trading_workflow(self, data_service, universe, assets, fundamentals, prices):
        """Test complete gap trading workflow: universe → fundamentals → prices."""
        # Step 1: Get active universe symbols
        symbols = data_service.get_active_universe_symbols()
        assert len(symbols) == 2

        # Step 2: Find gap trading candidates (market cap filter)
        candidates = data_service.find_gap_trading_candidates()
        assert len(candidates) == 2

        # Step 3: Find prices with gaps
        gaps = data_service.find_prices_with_gaps(min_gap_percent=2.0)
        assert len(gaps) == 2

        # Step 4: Verify gap calculations
        aapl_gap = next(g for g in gaps if g.symbol == "AAPL")
        assert aapl_gap.gap_percent == pytest.approx(2.0, rel=0.01)

        msft_gap = next(g for g in gaps if g.symbol == "MSFT")
        assert msft_gap.gap_percent == pytest.approx(-3.0, rel=0.01)

    def test_universe_rebuild_workflow(self, data_service, session, universe, assets, fundamentals):
        """Test universe rebuild workflow: clear → filter → add."""
        # Step 1: Clear existing memberships
        cleared = data_service.clear_universe_memberships("test_universe")
        assert cleared == 2

        # Step 2: Find assets meeting criteria (e.g., market cap > $2T)
        candidates = data_service.find_by_market_cap(min_cap=2_000_000_000_000)
        asset_ids = [c.asset_id for c in candidates]

        # Step 3: Add memberships
        added = data_service.add_universe_memberships("test_universe", asset_ids)
        assert added == 2

        # Step 4: Verify new memberships
        symbols = data_service.get_active_universe_symbols()
        assert len(symbols) == 2

    def test_sector_analysis_workflow(self, data_service, fundamentals):
        """Test sector analysis workflow: sectors → filter → stats."""
        # Step 1: Get all sectors
        sectors = data_service.get_all_sectors()
        assert "Technology" in sectors

        # Step 2: Find stocks in Technology sector
        tech_stocks = data_service.find_by_sector("Technology")
        assert len(tech_stocks) == 2

        # Step 3: Verify ordered by market cap (descending)
        assert tech_stocks[0].company_name == "Apple Inc."  # $3T
        assert tech_stocks[1].company_name == "Microsoft Corp."  # $2.5T

    # ============================================================================
    # ERROR HANDLING
    # ============================================================================

    def test_get_market_not_found(self, data_service):
        """Test get_market returns None for non-existent market."""
        result = data_service.get_market("INVALID")
        assert result is None

    def test_get_fundamentals_not_found(self, data_service):
        """Test get_fundamentals returns None for non-existent asset."""
        result = data_service.get_fundamentals(asset_id=999)
        assert result is None

    def test_get_latest_price_not_found(self, data_service):
        """Test get_latest_price returns None for non-existent symbol."""
        result = data_service.get_latest_price("INVALID")
        assert result is None

    def test_get_universe_not_found(self, data_service):
        """Test get_universe returns None for non-existent universe."""
        result = data_service.get_universe("nonexistent_universe")
        assert result is None

    def test_set_active_universe_not_found(self, data_service, universe):
        """Test set_active_universe returns False for non-existent universe."""
        result = data_service.set_active_universe("nonexistent_universe")
        assert result is False
