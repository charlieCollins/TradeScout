"""
Tests for SQLite Repository Implementation
"""

import pytest
import tempfile
import os
from datetime import datetime, timedelta
from decimal import Decimal

from src.tradescout.storage.sqlite_repository import (
    SQLiteQuoteRepository,
    SQLiteDatabaseManager,
    create_sqlite_database_manager,
)
from src.tradescout.data_models.domain_models_core import (
    Asset,
    MarketQuote,
    PriceData,
    AssetType,
    MarketStatus,
)
from src.tradescout.data_models.factories import MarketFactory


@pytest.fixture
def temp_db_path():
    """Create a temporary database file path"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as temp_file:
        temp_path = temp_file.name
    yield temp_path
    # Cleanup
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def quote_repository(temp_db_path):
    """Create a SQLite quote repository with temporary database"""
    return SQLiteQuoteRepository(temp_db_path)


@pytest.fixture
def db_manager(temp_db_path):
    """Create a SQLite database manager with temporary database"""
    manager = SQLiteDatabaseManager(temp_db_path)
    manager.initialize_database()
    return manager


@pytest.fixture
def sample_asset():
    """Create a sample asset for testing"""
    nasdaq = MarketFactory().create_nasdaq_market()
    return Asset(
        symbol="AAPL",
        name="Apple Inc.",
        asset_type=AssetType.COMMON_STOCK,
        market=nasdaq,
        currency="USD",
    )


@pytest.fixture
def sample_quote(sample_asset):
    """Create a sample quote for testing"""
    price_data = PriceData(
        asset=sample_asset,
        timestamp=datetime.now(),
        price=Decimal("150.50"),
        volume=1000000,
        open_price=Decimal("149.00"),
        high_price=Decimal("151.00"),
        low_price=Decimal("148.50"),
        session_type=MarketStatus.OPEN,
        data_source="test",
        data_quality="good",
    )

    return MarketQuote(
        asset=sample_asset,
        price_data=price_data,
        previous_close=Decimal("148.00"),
        average_volume=1500000,
    )


class TestSQLiteQuoteRepository:
    """Test SQLite Quote Repository"""

    def test_table_creation(self, quote_repository):
        """Test that database tables are created properly"""
        # Repository should be initialized without errors
        assert quote_repository.db_path is not None

    def test_save_quote_success(self, quote_repository, sample_quote):
        """Test successful quote saving"""
        result = quote_repository.save_quote(sample_quote)
        assert result is True

    def test_save_quote_duplicate_handling(self, quote_repository, sample_quote):
        """Test that duplicate quotes are handled properly (REPLACE)"""
        # Save quote first time
        result1 = quote_repository.save_quote(sample_quote)
        assert result1 is True

        # Save same quote again (should replace)
        result2 = quote_repository.save_quote(sample_quote)
        assert result2 is True

    def test_get_latest_quote_success(self, quote_repository, sample_quote):
        """Test successful quote retrieval"""
        # Save quote first
        quote_repository.save_quote(sample_quote)

        # Retrieve it
        retrieved_quote = quote_repository.get_latest_quote(sample_quote.asset.symbol)

        assert retrieved_quote is not None
        assert retrieved_quote.asset.symbol == sample_quote.asset.symbol
        assert retrieved_quote.price_data.price == sample_quote.price_data.price
        assert retrieved_quote.price_data.volume == sample_quote.price_data.volume

    def test_get_latest_quote_not_found(self, quote_repository):
        """Test quote retrieval when symbol doesn't exist"""
        result = quote_repository.get_latest_quote("NONEXISTENT")
        assert result is None

    def test_get_quotes_by_timeframe(self, quote_repository, sample_asset):
        """Test retrieval of quotes within a timeframe"""
        now = datetime.now()

        # Create quotes at different times
        for i in range(3):
            timestamp = now - timedelta(hours=i)
            price_data = PriceData(
                asset=sample_asset,
                timestamp=timestamp,
                price=Decimal(f"150.{i}0"),
                volume=1000000,
                session_type=MarketStatus.OPEN,
                data_source="test",
            )
            quote = MarketQuote(
                asset=sample_asset,
                price_data=price_data,
                previous_close=Decimal("148.00"),
                average_volume=1500000,
            )
            quote_repository.save_quote(quote)

        # Retrieve quotes from the last 2 hours
        start_time = now - timedelta(hours=2)
        end_time = now + timedelta(minutes=10)  # Small buffer for timing

        quotes = quote_repository.get_quotes_by_timeframe(
            sample_asset.symbol, start_time, end_time
        )

        assert len(quotes) >= 2  # Should get at least 2 quotes
        assert all(q.asset.symbol == sample_asset.symbol for q in quotes)

    def test_get_historical_quotes(self, quote_repository, sample_asset):
        """Test retrieval of historical quotes"""
        now = datetime.now()

        # Create quotes over several days
        for i in range(5):
            timestamp = now - timedelta(days=i)
            price_data = PriceData(
                asset=sample_asset,
                timestamp=timestamp,
                price=Decimal(f"150.{i}0"),
                volume=1000000,
                session_type=MarketStatus.OPEN,
                data_source="test",
            )
            quote = MarketQuote(
                asset=sample_asset,
                price_data=price_data,
                previous_close=Decimal("148.00"),
                average_volume=1500000,
            )
            quote_repository.save_quote(quote)

        # Get quotes from last 3 days
        quotes = quote_repository.get_historical_quotes(sample_asset.symbol, 3)

        assert len(quotes) >= 3  # Should get at least 3 quotes
        assert all(q.asset.symbol == sample_asset.symbol for q in quotes)

    def test_bulk_save_quotes(self, quote_repository, sample_asset):
        """Test bulk saving of multiple quotes"""
        quotes = []
        for i in range(5):
            timestamp = datetime.now() - timedelta(minutes=i)
            price_data = PriceData(
                asset=sample_asset,
                timestamp=timestamp,
                price=Decimal(f"150.{i}0"),
                volume=1000000,
                session_type=MarketStatus.OPEN,
                data_source="test",
            )
            quote = MarketQuote(
                asset=sample_asset,
                price_data=price_data,
                previous_close=Decimal("148.00"),
                average_volume=1500000,
            )
            quotes.append(quote)

        # Bulk save
        saved_count = quote_repository.bulk_save_quotes(quotes)
        assert saved_count == 5

        # Verify they were saved
        latest_quote = quote_repository.get_latest_quote(sample_asset.symbol)
        assert latest_quote is not None

    def test_bulk_save_empty_list(self, quote_repository):
        """Test bulk save with empty list"""
        result = quote_repository.bulk_save_quotes([])
        assert result == 0

    def test_delete_old_quotes(self, quote_repository, sample_asset):
        """Test deletion of old quotes"""
        now = datetime.now()

        # Create old and new quotes
        old_timestamp = now - timedelta(days=10)
        new_timestamp = now - timedelta(hours=1)

        for timestamp, price in [(old_timestamp, "149.00"), (new_timestamp, "151.00")]:
            price_data = PriceData(
                asset=sample_asset,
                timestamp=timestamp,
                price=Decimal(price),
                volume=1000000,
                session_type=MarketStatus.OPEN,
                data_source="test",
            )
            quote = MarketQuote(
                asset=sample_asset,
                price_data=price_data,
                previous_close=Decimal("148.00"),
                average_volume=1500000,
            )
            quote_repository.save_quote(quote)

        # Delete quotes older than 5 days
        deleted_count = quote_repository.delete_old_quotes(5)
        assert deleted_count >= 1  # Should delete at least the old quote

        # Verify new quote still exists
        latest_quote = quote_repository.get_latest_quote(sample_asset.symbol)
        assert latest_quote is not None
        assert latest_quote.price_data.price == Decimal("151.00")


class TestSQLiteDatabaseManager:
    """Test SQLite Database Manager"""

    def test_initialization(self, db_manager):
        """Test database manager initialization"""
        assert db_manager.db_path is not None
        assert os.path.exists(db_manager.db_path)

    def test_quotes_repository_access(self, db_manager):
        """Test access to quotes repository"""
        quotes_repo = db_manager.quotes
        assert quotes_repo is not None
        assert hasattr(quotes_repo, "save_quote")
        assert hasattr(quotes_repo, "get_latest_quote")

    def test_database_stats(self, db_manager, sample_quote):
        """Test database statistics retrieval"""
        # Save a quote first
        db_manager.quotes.save_quote(sample_quote)

        # Get stats
        stats = db_manager.get_database_stats()
        assert isinstance(stats, dict)
        assert "quotes_count" in stats
        assert "database_size_bytes" in stats
        assert "database_path" in stats
        assert stats["quotes_count"] >= 1

    def test_cleanup_old_data(self, db_manager, sample_asset):
        """Test cleanup of old data"""
        now = datetime.now()

        # Create old quote
        old_timestamp = now - timedelta(days=100)
        price_data = PriceData(
            asset=sample_asset,
            timestamp=old_timestamp,
            price=Decimal("149.00"),
            volume=1000000,
            session_type=MarketStatus.OPEN,
            data_source="test",
        )
        old_quote = MarketQuote(
            asset=sample_asset,
            price_data=price_data,
            previous_close=Decimal("148.00"),
            average_volume=1500000,
        )
        db_manager.quotes.save_quote(old_quote)

        # Cleanup data older than 90 days
        deleted_count = db_manager.cleanup_old_data(90)
        assert deleted_count >= 1

    def test_backup_and_restore(self, db_manager, sample_quote, temp_db_path):
        """Test database backup and restore functionality"""
        # Save some data
        db_manager.quotes.save_quote(sample_quote)

        # Create backup
        backup_path = temp_db_path + ".backup"
        backup_success = db_manager.backup_database(backup_path)
        assert backup_success is True
        assert os.path.exists(backup_path)

        # Create new database manager and restore
        new_db_path = temp_db_path + ".restored"
        new_manager = SQLiteDatabaseManager(new_db_path)
        new_manager.initialize_database()

        restore_success = new_manager.restore_database(backup_path)
        assert restore_success is True

        # Verify data was restored
        restored_quote = new_manager.quotes.get_latest_quote(sample_quote.asset.symbol)
        assert restored_quote is not None
        assert restored_quote.asset.symbol == sample_quote.asset.symbol

        # Cleanup
        for path in [backup_path, new_db_path]:
            if os.path.exists(path):
                os.unlink(path)

    def test_not_implemented_repositories(self, db_manager):
        """Test that not-yet-implemented repositories raise NotImplementedError"""
        with pytest.raises(NotImplementedError):
            _ = db_manager.extended_hours

        with pytest.raises(NotImplementedError):
            _ = db_manager.news

        with pytest.raises(NotImplementedError):
            _ = db_manager.sentiment


def test_create_sqlite_database_manager():
    """Test the convenience function for creating database manager"""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as temp_file:
        temp_path = temp_file.name

    try:
        manager = create_sqlite_database_manager(temp_path)
        assert isinstance(manager, SQLiteDatabaseManager)
        assert manager.db_path == temp_path

        # Test initialization
        success = manager.initialize_database()
        assert success is True
        assert os.path.exists(temp_path)

    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
