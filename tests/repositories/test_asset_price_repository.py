"""Unit tests for AssetPriceRepository - Critical for gap trading."""

import pytest
from datetime import date, datetime, timedelta
from decimal import Decimal
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool

import sys
sys.path.insert(0, '/home/ccollins/projects/TradeScout/src')

from repositories.asset_price_repository import AssetPriceRepository
from models.asset_price_sqlmodel import AssetPriceSQLModel
from models.asset_sqlmodel import AssetSQLModel
from models.provider_sqlmodel import ProviderSQLModel


class TestAssetPriceRepository:
    """Test AssetPriceRepository business operations.

    These tests use in-memory SQLite for fast, isolated testing.
    Critical for validating gap trading queries.
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
        """Create AssetPriceRepository instance."""
        return AssetPriceRepository(session)

    @pytest.fixture
    def provider(self, session):
        """Create test provider."""
        provider = ProviderSQLModel(
            id=1,
            name="polygon",
            display_name="Polygon.io",
            base_url="https://api.polygon.io",
            api_key_required=True,
            is_active=True,
            created_at=datetime.now()
        )
        session.add(provider)
        session.commit()
        session.refresh(provider)
        return provider

    @pytest.fixture
    def asset(self, session, provider):
        """Create test asset."""
        asset = AssetSQLModel(
            id=1,
            symbol="AAPL",
            name="Apple Inc.",
            asset_type="stock",
            asset_class="equity",
            market_id=1,
            currency="USD",
            lot_size=1,
            is_active=True,
            is_delisted=False,
            provider_id=provider.id,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        session.add(asset)
        session.commit()
        session.refresh(asset)
        return asset

    @pytest.fixture
    def sample_price(self, asset, provider):
        """Create sample price for testing."""
        return AssetPriceSQLModel(
            asset_id=asset.id,
            symbol=asset.symbol,
            provider_id=provider.id,
            trade_date=date.today(),
            prevday_close=Decimal("150.00"),
            day_open=Decimal("153.00"),  # 2% gap up
            day_high=Decimal("155.00"),
            day_low=Decimal("152.00"),
            day_close=Decimal("154.00"),
            day_volume=10000000,
            updated_at=datetime.now()
        )

    @pytest.fixture
    def sample_prices_with_gaps(self, session, asset, provider):
        """Create multiple prices with various gap sizes for gap screener testing."""
        today = date.today()
        prices = [
            # AAPL - 2% gap up (should be included for min_gap >= 2%)
            AssetPriceSQLModel(
                asset_id=asset.id,
                symbol="AAPL",
                provider_id=provider.id,
                trade_date=today,
                prevday_close=Decimal("150.00"),
                day_open=Decimal("153.00"),
                day_close=Decimal("154.00"),
                updated_at=datetime.now()
            ),
            # MSFT - 5% gap down (should be included for min_gap >= 2%)
            AssetPriceSQLModel(
                asset_id=asset.id + 1,
                symbol="MSFT",
                provider_id=provider.id,
                trade_date=today,
                prevday_close=Decimal("300.00"),
                day_open=Decimal("285.00"),
                day_close=Decimal("287.00"),
                updated_at=datetime.now()
            ),
            # GOOGL - 1% gap up (should NOT be included for min_gap >= 2%)
            AssetPriceSQLModel(
                asset_id=asset.id + 2,
                symbol="GOOGL",
                provider_id=provider.id,
                trade_date=today,
                prevday_close=Decimal("140.00"),
                day_open=Decimal("141.40"),
                day_close=Decimal("142.00"),
                updated_at=datetime.now()
            ),
            # TSLA - 3.5% gap up (should be included for min_gap >= 2%)
            AssetPriceSQLModel(
                asset_id=asset.id + 3,
                symbol="TSLA",
                provider_id=provider.id,
                trade_date=today,
                prevday_close=Decimal("200.00"),
                day_open=Decimal("207.00"),
                day_close=Decimal("208.00"),
                updated_at=datetime.now()
            ),
        ]

        session.add_all(prices)
        session.commit()
        return prices

    # ============================================================================
    # LATEST PRICE QUERIES (Critical for Gap Trading)
    # ============================================================================

    def test_get_latest_by_symbol_success(self, repository, session, sample_price):
        """Test get_latest_by_symbol returns most recent price."""
        # Save price
        session.add(sample_price)
        session.commit()

        # Retrieve
        result = repository.get_latest_by_symbol("AAPL")

        assert result is not None
        assert result.symbol == "AAPL"
        assert result.prevday_close == Decimal("150.00")
        assert result.day_open == Decimal("153.00")

    def test_get_latest_by_symbol_not_found(self, repository):
        """Test get_latest_by_symbol returns None for non-existent symbol."""
        result = repository.get_latest_by_symbol("INVALID")
        assert result is None

    def test_get_latest_by_symbol_case_insensitive(self, repository, session, sample_price):
        """Test get_latest_by_symbol handles lowercase symbols."""
        session.add(sample_price)
        session.commit()

        result = repository.get_latest_by_symbol("aapl")  # lowercase

        assert result is not None
        assert result.symbol == "AAPL"

    def test_get_latest_by_asset_id_success(self, repository, session, sample_price):
        """Test get_latest_by_asset_id returns most recent price."""
        session.add(sample_price)
        session.commit()

        result = repository.get_latest_by_asset_id(sample_price.asset_id)

        assert result is not None
        assert result.asset_id == sample_price.asset_id
        assert result.symbol == "AAPL"

    def test_get_latest_for_symbols_multiple(self, repository, session, asset, provider):
        """Test get_latest_for_symbols returns batch of latest prices."""
        prices = [
            AssetPriceSQLModel(
                asset_id=asset.id,
                symbol="AAPL",
                provider_id=provider.id,
                trade_date=date.today(),
                prevday_close=Decimal("150.00"),
                day_open=Decimal("153.00"),
                updated_at=datetime.now()
            ),
            AssetPriceSQLModel(
                asset_id=asset.id + 1,
                symbol="MSFT",
                provider_id=provider.id,
                trade_date=date.today(),
                prevday_close=Decimal("300.00"),
                day_open=Decimal("305.00"),
                updated_at=datetime.now()
            ),
        ]
        session.add_all(prices)
        session.commit()

        results = repository.get_latest_for_symbols(["AAPL", "MSFT"])

        assert len(results) == 2
        symbols = [p.symbol for p in results]
        assert "AAPL" in symbols
        assert "MSFT" in symbols

    # ============================================================================
    # HISTORICAL QUERIES
    # ============================================================================

    def test_get_by_trade_date_success(self, repository, session, sample_price):
        """Test get_by_trade_date returns price for specific date."""
        session.add(sample_price)
        session.commit()

        result = repository.get_by_trade_date("AAPL", date.today())

        assert result is not None
        assert result.symbol == "AAPL"
        assert result.trade_date == date.today()

    def test_find_by_date_range(self, repository, session, asset, provider):
        """Test find_by_date_range returns prices in date range."""
        today = date.today()
        yesterday = today - timedelta(days=1)
        two_days_ago = today - timedelta(days=2)

        prices = [
            AssetPriceSQLModel(
                asset_id=asset.id, symbol="AAPL", provider_id=provider.id,
                trade_date=two_days_ago, prevday_close=Decimal("148.00"),
                day_open=Decimal("149.00"), updated_at=datetime.now()
            ),
            AssetPriceSQLModel(
                asset_id=asset.id, symbol="AAPL", provider_id=provider.id,
                trade_date=yesterday, prevday_close=Decimal("149.00"),
                day_open=Decimal("150.00"), updated_at=datetime.now()
            ),
            AssetPriceSQLModel(
                asset_id=asset.id, symbol="AAPL", provider_id=provider.id,
                trade_date=today, prevday_close=Decimal("150.00"),
                day_open=Decimal("153.00"), updated_at=datetime.now()
            ),
        ]
        session.add_all(prices)
        session.commit()

        results = repository.find_by_date_range("AAPL", yesterday, today)

        assert len(results) == 2
        assert results[0].trade_date == today  # Descending order
        assert results[1].trade_date == yesterday

    def test_find_recent(self, repository, session, asset, provider):
        """Test find_recent returns recent prices."""
        today = date.today()
        old_date = today - timedelta(days=60)

        prices = [
            AssetPriceSQLModel(
                asset_id=asset.id, symbol="AAPL", provider_id=provider.id,
                trade_date=old_date, prevday_close=Decimal("140.00"),
                day_open=Decimal("141.00"), updated_at=datetime.now()
            ),
            AssetPriceSQLModel(
                asset_id=asset.id, symbol="AAPL", provider_id=provider.id,
                trade_date=today, prevday_close=Decimal("150.00"),
                day_open=Decimal("153.00"), updated_at=datetime.now()
            ),
        ]
        session.add_all(prices)
        session.commit()

        results = repository.find_recent("AAPL", days=30)

        # Should only return today's price (within 30 days)
        assert len(results) == 1
        assert results[0].trade_date == today

    # ============================================================================
    # GAP ANALYSIS QUERIES (MOST CRITICAL FOR GAP TRADING)
    # ============================================================================

    def test_find_with_gaps_default_threshold(self, repository, sample_prices_with_gaps):
        """Test find_with_gaps with default 2% threshold."""
        results = repository.find_with_gaps(min_gap_percent=2.0, trade_date=date.today())

        # Should find AAPL (2% up), MSFT (5% down), TSLA (3.5% up)
        # Should NOT find GOOGL (1% up)
        assert len(results) == 3
        symbols = [p.symbol for p in results]
        assert "AAPL" in symbols
        assert "MSFT" in symbols
        assert "TSLA" in symbols
        assert "GOOGL" not in symbols

    def test_find_with_gaps_higher_threshold(self, repository, sample_prices_with_gaps):
        """Test find_with_gaps with 3% threshold."""
        results = repository.find_with_gaps(min_gap_percent=3.0, trade_date=date.today())

        # Should find MSFT (5% down), TSLA (3.5% up)
        # Should NOT find AAPL (2% up), GOOGL (1% up)
        assert len(results) == 2
        symbols = [p.symbol for p in results]
        assert "MSFT" in symbols
        assert "TSLA" in symbols
        assert "AAPL" not in symbols

    def test_find_with_gaps_no_results(self, repository, sample_prices_with_gaps):
        """Test find_with_gaps with very high threshold returns empty."""
        results = repository.find_with_gaps(min_gap_percent=10.0, trade_date=date.today())

        assert len(results) == 0

    def test_find_with_gaps_missing_data(self, repository, session, asset, provider):
        """Test find_with_gaps filters out prices missing gap data."""
        today = date.today()

        # Price with no prevday_close (can't calculate gap)
        incomplete_price = AssetPriceSQLModel(
            asset_id=asset.id,
            symbol="INCOMPLETE",
            provider_id=provider.id,
            trade_date=today,
            prevday_close=None,  # Missing
            day_open=Decimal("150.00"),
            updated_at=datetime.now()
        )
        session.add(incomplete_price)
        session.commit()

        results = repository.find_with_gaps(min_gap_percent=2.0, trade_date=today)

        # Should not include INCOMPLETE (missing prevday_close)
        symbols = [p.symbol for p in results]
        assert "INCOMPLETE" not in symbols

    # ============================================================================
    # PERSISTENCE
    # ============================================================================

    def test_save_new_price(self, repository, sample_price):
        """Test save() persists new price."""
        result = repository.save(sample_price)

        assert result.id is not None
        assert result.symbol == "AAPL"

    def test_bulk_save(self, repository, session, asset, provider):
        """Test bulk_save() persists multiple prices."""
        prices = [
            AssetPriceSQLModel(
                asset_id=asset.id, symbol="AAPL", provider_id=provider.id,
                trade_date=date.today(), prevday_close=Decimal("150.00"),
                day_open=Decimal("153.00"), updated_at=datetime.now()
            ),
            AssetPriceSQLModel(
                asset_id=asset.id + 1, symbol="MSFT", provider_id=provider.id,
                trade_date=date.today(), prevday_close=Decimal("300.00"),
                day_open=Decimal("305.00"), updated_at=datetime.now()
            ),
        ]

        count = repository.bulk_save(prices)

        assert count == 2

    def test_delete(self, repository, session, sample_price):
        """Test delete() removes price."""
        session.add(sample_price)
        session.commit()
        symbol = sample_price.symbol

        repository.delete(sample_price)

        result = repository.get_latest_by_symbol(symbol)
        assert result is None

    # ============================================================================
    # STATISTICS
    # ============================================================================

    def test_count_by_symbol(self, repository, session, asset, provider):
        """Test count_by_symbol returns correct count."""
        prices = [
            AssetPriceSQLModel(
                asset_id=asset.id, symbol="AAPL", provider_id=provider.id,
                trade_date=date.today() - timedelta(days=1),
                prevday_close=Decimal("149.00"), day_open=Decimal("150.00"),
                updated_at=datetime.now()
            ),
            AssetPriceSQLModel(
                asset_id=asset.id, symbol="AAPL", provider_id=provider.id,
                trade_date=date.today(), prevday_close=Decimal("150.00"),
                day_open=Decimal("153.00"), updated_at=datetime.now()
            ),
        ]
        session.add_all(prices)
        session.commit()

        count = repository.count_by_symbol("AAPL")

        assert count == 2

    def test_count_by_date(self, repository, session, asset, provider):
        """Test count_by_date returns correct count."""
        today = date.today()
        prices = [
            AssetPriceSQLModel(
                asset_id=asset.id, symbol="AAPL", provider_id=provider.id,
                trade_date=today, prevday_close=Decimal("150.00"),
                day_open=Decimal("153.00"), updated_at=datetime.now()
            ),
            AssetPriceSQLModel(
                asset_id=asset.id + 1, symbol="MSFT", provider_id=provider.id,
                trade_date=today, prevday_close=Decimal("300.00"),
                day_open=Decimal("305.00"), updated_at=datetime.now()
            ),
        ]
        session.add_all(prices)
        session.commit()

        count = repository.count_by_date(today)

        assert count == 2

    def test_get_date_range(self, repository, session, asset, provider):
        """Test get_date_range returns earliest and latest dates."""
        today = date.today()
        week_ago = today - timedelta(days=7)

        prices = [
            AssetPriceSQLModel(
                asset_id=asset.id, symbol="AAPL", provider_id=provider.id,
                trade_date=week_ago, prevday_close=Decimal("145.00"),
                day_open=Decimal("146.00"), updated_at=datetime.now()
            ),
            AssetPriceSQLModel(
                asset_id=asset.id, symbol="AAPL", provider_id=provider.id,
                trade_date=today, prevday_close=Decimal("150.00"),
                day_open=Decimal("153.00"), updated_at=datetime.now()
            ),
        ]
        session.add_all(prices)
        session.commit()

        earliest, latest = repository.get_date_range("AAPL")

        assert earliest == week_ago
        assert latest == today

    def test_get_date_range_no_data(self, repository):
        """Test get_date_range returns None for symbol with no data."""
        earliest, latest = repository.get_date_range("INVALID")

        assert earliest is None
        assert latest is None

    # ============================================================================
    # COMPUTED PROPERTIES (Gap Calculations)
    # ============================================================================

    def test_gap_amount_calculation(self, sample_price):
        """Test gap_amount computed property."""
        gap = sample_price.gap_amount

        assert gap == Decimal("3.00")  # 153 - 150

    def test_gap_percent_calculation(self, sample_price):
        """Test gap_percent computed property."""
        gap_pct = sample_price.gap_percent

        assert gap_pct == 2.0  # (153-150)/150 * 100

    def test_gap_with_missing_data(self, asset, provider):
        """Test gap properties return None with missing data."""
        price = AssetPriceSQLModel(
            asset_id=asset.id,
            symbol="AAPL",
            provider_id=provider.id,
            trade_date=date.today(),
            prevday_close=None,  # Missing
            day_open=Decimal("153.00"),
            updated_at=datetime.now()
        )

        assert price.gap_amount is None
        assert price.gap_percent is None

    def test_current_price_prefers_min_close(self, asset, provider):
        """Test current_price property prefers min_close over day_close."""
        price = AssetPriceSQLModel(
            asset_id=asset.id,
            symbol="AAPL",
            provider_id=provider.id,
            trade_date=date.today(),
            day_close=Decimal("154.00"),
            min_close=Decimal("154.50"),  # More current
            updated_at=datetime.now()
        )

        assert price.current_price == Decimal("154.50")

    def test_current_price_falls_back_to_day_close(self, asset, provider):
        """Test current_price falls back to day_close if no min_close."""
        price = AssetPriceSQLModel(
            asset_id=asset.id,
            symbol="AAPL",
            provider_id=provider.id,
            trade_date=date.today(),
            day_close=Decimal("154.00"),
            min_close=None,
            updated_at=datetime.now()
        )

        assert price.current_price == Decimal("154.00")
