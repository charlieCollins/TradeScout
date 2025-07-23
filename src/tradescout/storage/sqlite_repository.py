"""
SQLite Repository Implementation

Implements storage interfaces using SQLite database for local development
and production use.
"""

import sqlite3
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from decimal import Decimal
import json

from .interfaces import (
    QuoteRepository,
    ExtendedHoursRepository,
    DatabaseManager,
)
from ..data_models.domain_models_core import (
    Asset,
    MarketQuote,
    ExtendedHoursData,
    PriceData,
    AssetType,
    MarketStatus,
)

logger = logging.getLogger(__name__)


class SQLiteQuoteRepository(QuoteRepository):
    """SQLite implementation of QuoteRepository"""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_table_exists()

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with proper settings"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign keys
        return conn

    def _ensure_table_exists(self) -> None:
        """Create quotes table if it doesn't exist"""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS quotes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    price DECIMAL(18, 6) NOT NULL,
                    volume INTEGER NOT NULL,
                    open_price DECIMAL(18, 6),
                    high_price DECIMAL(18, 6),
                    low_price DECIMAL(18, 6),
                    previous_close DECIMAL(18, 6),
                    average_volume INTEGER,
                    price_change DECIMAL(18, 6),
                    price_change_percent DECIMAL(10, 4),
                    volume_ratio DECIMAL(10, 4),
                    session_type TEXT DEFAULT 'OPEN',
                    data_source TEXT DEFAULT 'unknown',
                    data_quality TEXT DEFAULT 'good',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(symbol, timestamp)
                )
            """
            )

            # Create index for faster queries
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_quotes_symbol_timestamp 
                ON quotes(symbol, timestamp DESC)
            """
            )

            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_quotes_timestamp 
                ON quotes(timestamp DESC)
            """
            )

    def save_quote(self, quote: MarketQuote) -> bool:
        """
        Save a market quote

        Args:
            quote: Market quote to save

        Returns:
            True if saved successfully
        """
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO quotes (
                        symbol, timestamp, price, volume, open_price, high_price, low_price,
                        previous_close, average_volume, price_change, price_change_percent,
                        volume_ratio, session_type, data_source, data_quality
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        quote.asset.symbol,
                        quote.price_data.timestamp,
                        str(quote.price_data.price),
                        quote.price_data.volume,
                        (
                            str(quote.price_data.open_price)
                            if quote.price_data.open_price
                            else None
                        ),
                        (
                            str(quote.price_data.high_price)
                            if quote.price_data.high_price
                            else None
                        ),
                        (
                            str(quote.price_data.low_price)
                            if quote.price_data.low_price
                            else None
                        ),
                        str(quote.previous_close) if quote.previous_close else None,
                        quote.average_volume,
                        str(quote.price_change) if quote.price_change else None,
                        (
                            str(quote.price_change_percent)
                            if quote.price_change_percent
                            else None
                        ),
                        str(quote.volume_ratio) if quote.volume_ratio else None,
                        quote.price_data.session_type.value,
                        quote.price_data.data_source,
                        quote.price_data.data_quality,
                    ),
                )
                return True

        except sqlite3.Error as e:
            logger.error(f"Error saving quote for {quote.asset.symbol}: {e}")
            return False

    def get_latest_quote(self, symbol: str) -> Optional[MarketQuote]:
        """
        Get the most recent quote for a symbol

        Args:
            symbol: Stock symbol

        Returns:
            Latest quote or None if not found
        """
        try:
            with self._get_connection() as conn:
                row = conn.execute(
                    """
                    SELECT * FROM quotes 
                    WHERE symbol = ? 
                    ORDER BY timestamp DESC 
                    LIMIT 1
                """,
                    (symbol,),
                ).fetchone()

                if not row:
                    return None

                return self._row_to_quote(row)

        except sqlite3.Error as e:
            logger.error(f"Error getting latest quote for {symbol}: {e}")
            return None

    def get_quotes_by_timeframe(
        self, symbol: str, start_time: datetime, end_time: datetime
    ) -> List[MarketQuote]:
        """
        Get quotes within a time range

        Args:
            symbol: Stock symbol
            start_time: Start of time range
            end_time: End of time range

        Returns:
            List of quotes in timeframe
        """
        try:
            with self._get_connection() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM quotes 
                    WHERE symbol = ? AND timestamp BETWEEN ? AND ?
                    ORDER BY timestamp ASC
                """,
                    (symbol, start_time, end_time),
                ).fetchall()

                return [self._row_to_quote(row) for row in rows]

        except sqlite3.Error as e:
            logger.error(f"Error getting quotes by timeframe for {symbol}: {e}")
            return []

    def get_historical_quotes(self, symbol: str, days_back: int) -> List[MarketQuote]:
        """
        Get historical quotes for analysis

        Args:
            symbol: Stock symbol
            days_back: Number of days to look back

        Returns:
            List of historical quotes
        """
        start_time = datetime.now() - timedelta(days=days_back)
        return self.get_quotes_by_timeframe(symbol, start_time, datetime.now())

    def bulk_save_quotes(self, quotes: List[MarketQuote]) -> int:
        """
        Save multiple quotes efficiently

        Args:
            quotes: List of quotes to save

        Returns:
            Number of quotes saved
        """
        if not quotes:
            return 0

        saved_count = 0
        try:
            with self._get_connection() as conn:
                for quote in quotes:
                    try:
                        conn.execute(
                            """
                            INSERT OR REPLACE INTO quotes (
                                symbol, timestamp, price, volume, open_price, high_price, low_price,
                                previous_close, average_volume, price_change, price_change_percent,
                                volume_ratio, session_type, data_source, data_quality
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                            (
                                quote.asset.symbol,
                                quote.price_data.timestamp,
                                str(quote.price_data.price),
                                quote.price_data.volume,
                                (
                                    str(quote.price_data.open_price)
                                    if quote.price_data.open_price
                                    else None
                                ),
                                (
                                    str(quote.price_data.high_price)
                                    if quote.price_data.high_price
                                    else None
                                ),
                                (
                                    str(quote.price_data.low_price)
                                    if quote.price_data.low_price
                                    else None
                                ),
                                (
                                    str(quote.previous_close)
                                    if quote.previous_close
                                    else None
                                ),
                                quote.average_volume,
                                str(quote.price_change) if quote.price_change else None,
                                (
                                    str(quote.price_change_percent)
                                    if quote.price_change_percent
                                    else None
                                ),
                                str(quote.volume_ratio) if quote.volume_ratio else None,
                                quote.price_data.session_type.value,
                                quote.price_data.data_source,
                                quote.price_data.data_quality,
                            ),
                        )
                        saved_count += 1
                    except sqlite3.Error as e:
                        logger.warning(
                            f"Failed to save quote for {quote.asset.symbol}: {e}"
                        )

                return saved_count

        except sqlite3.Error as e:
            logger.error(f"Error in bulk save quotes: {e}")
            return saved_count

    def delete_old_quotes(self, older_than_days: int) -> int:
        """
        Delete quotes older than specified days

        Args:
            older_than_days: Delete quotes older than this

        Returns:
            Number of quotes deleted
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=older_than_days)
            with self._get_connection() as conn:
                cursor = conn.execute(
                    """
                    DELETE FROM quotes WHERE timestamp < ?
                """,
                    (cutoff_date,),
                )
                return cursor.rowcount

        except sqlite3.Error as e:
            logger.error(f"Error deleting old quotes: {e}")
            return 0

    def _row_to_quote(self, row: sqlite3.Row) -> MarketQuote:
        """Convert database row to MarketQuote object"""
        # Create a minimal Asset object (in real implementation, this would come from asset repository)
        from ..data_models.factories import MarketFactory

        nasdaq = MarketFactory().create_nasdaq_market()  # Default market
        asset = Asset(
            symbol=row["symbol"],
            name=row["symbol"],  # Minimal name, could be enhanced
            asset_type=AssetType.COMMON_STOCK,  # Default type
            market=nasdaq,
            currency="USD",  # Default currency
        )

        # Create PriceData
        price_data = PriceData(
            asset=asset,
            timestamp=datetime.fromisoformat(row["timestamp"]),
            price=Decimal(row["price"]),
            volume=row["volume"],
            open_price=Decimal(row["open_price"]) if row["open_price"] else None,
            high_price=Decimal(row["high_price"]) if row["high_price"] else None,
            low_price=Decimal(row["low_price"]) if row["low_price"] else None,
            session_type=MarketStatus(row["session_type"]),
            data_source=row["data_source"],
            data_quality=row["data_quality"],
        )

        # Create MarketQuote
        quote = MarketQuote(
            asset=asset,
            price_data=price_data,
            previous_close=(
                Decimal(row["previous_close"]) if row["previous_close"] else None
            ),
            average_volume=row["average_volume"],
        )

        return quote


class SQLiteDatabaseManager(DatabaseManager):
    """SQLite implementation of DatabaseManager"""

    def __init__(self, db_path: str = "storage/tradescout.db"):
        self.db_path = db_path
        self._quotes_repo = None
        self._ensure_database_directory()

    def _ensure_database_directory(self) -> None:
        """Create database directory if it doesn't exist"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

    def initialize_database(self) -> bool:
        """Initialize database schema"""
        try:
            # Initialize all repository tables
            _ = self.quotes  # This will create the quotes table
            logger.info(f"Database initialized at {self.db_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            return False

    def migrate_schema(self, target_version: str) -> bool:
        """Migrate database schema to target version"""
        # Placeholder for future schema migrations
        logger.info(f"Schema migration to {target_version} - not yet implemented")
        return True

    def backup_database(self, backup_path: str) -> bool:
        """Create database backup"""
        try:
            import shutil

            backup_dir = Path(backup_path).parent
            backup_dir.mkdir(parents=True, exist_ok=True)

            shutil.copy2(self.db_path, backup_path)
            logger.info(f"Database backed up to {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to backup database: {e}")
            return False

    def restore_database(self, backup_path: str) -> bool:
        """Restore database from backup"""
        try:
            import shutil

            if not Path(backup_path).exists():
                logger.error(f"Backup file not found: {backup_path}")
                return False

            shutil.copy2(backup_path, self.db_path)
            logger.info(f"Database restored from {backup_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to restore database: {e}")
            return False

    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                stats = {}

                # Get table sizes
                cursor = conn.execute(
                    """
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name NOT LIKE 'sqlite_%'
                """
                )

                for (table_name,) in cursor.fetchall():
                    count_cursor = conn.execute(f"SELECT COUNT(*) FROM {table_name}")
                    stats[f"{table_name}_count"] = count_cursor.fetchone()[0]

                # Get database size
                stats["database_size_bytes"] = Path(self.db_path).stat().st_size
                stats["database_path"] = self.db_path

                return stats

        except Exception as e:
            logger.error(f"Error getting database stats: {e}")
            return {}

    def cleanup_old_data(self, retention_days: int = 90) -> int:
        """Clean up old data beyond retention period"""
        total_deleted = 0
        try:
            # Clean up old quotes
            total_deleted += self.quotes.delete_old_quotes(retention_days)
            logger.info(f"Cleaned up {total_deleted} old records")
            return total_deleted
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return total_deleted

    def execute_raw_query(
        self, query: str, params: Optional[List] = None
    ) -> List[Dict]:
        """Execute raw SQL query"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(query, params or [])
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error executing raw query: {e}")
            return []

    @property
    def quotes(self) -> QuoteRepository:
        """Get quotes repository"""
        if self._quotes_repo is None:
            self._quotes_repo = SQLiteQuoteRepository(self.db_path)
        return self._quotes_repo

    @property
    def extended_hours(self) -> ExtendedHoursRepository:
        """Get extended hours repository"""
        raise NotImplementedError("Extended hours repository not yet implemented")

    @property
    def news(self):
        """Get news repository"""
        raise NotImplementedError("News repository not yet implemented")

    @property
    def sentiment(self):
        """Get sentiment repository"""
        raise NotImplementedError("Sentiment repository not yet implemented")

    @property
    def technical(self):
        """Get technical repository"""
        raise NotImplementedError("Technical repository not yet implemented")

    @property
    def suggestions(self):
        """Get suggestions repository"""
        raise NotImplementedError("Suggestions repository not yet implemented")

    @property
    def trades(self):
        """Get trades repository"""
        raise NotImplementedError("Trades repository not yet implemented")

    @property
    def performance(self):
        """Get performance repository"""
        raise NotImplementedError("Performance repository not yet implemented")

    @property
    def events(self):
        """Get events repository"""
        raise NotImplementedError("Events repository not yet implemented")


# Convenience function for creating database manager
def create_sqlite_database_manager(
    db_path: str = "storage/tradescout.db",
) -> SQLiteDatabaseManager:
    """
    Create a SQLite database manager with default settings

    Args:
        db_path: Path to SQLite database file

    Returns:
        Configured SQLiteDatabaseManager
    """
    return SQLiteDatabaseManager(db_path)


if __name__ == "__main__":
    # Simple test of the repository
    from ..data_sources.yfinance_adapter import YFinanceAdapter
    from ..data_models.domain_models_core import Asset, AssetType
    from ..data_models.factories import MarketFactory

    print("🧪 Testing SQLite Repository...")

    # Create test database
    db_manager = create_sqlite_database_manager("test_tradescout.db")
    db_manager.initialize_database()

    # Create test asset and adapter
    nasdaq = MarketFactory().create_nasdaq_market()
    test_asset = Asset(
        symbol="AAPL",
        name="Apple Inc.",
        asset_type=AssetType.COMMON_STOCK,
        market=nasdaq,
        currency="USD",
    )

    adapter = YFinanceAdapter()

    # Get live quote and save it
    print("📊 Getting live quote...")
    quote = adapter.get_current_quote(test_asset)

    if quote:
        print(f"💾 Saving quote for {quote.asset.symbol}: ${quote.price_data.price}")
        success = db_manager.quotes.save_quote(quote)
        print(f"✅ Save successful: {success}")

        # Retrieve it back
        print("🔍 Retrieving saved quote...")
        saved_quote = db_manager.quotes.get_latest_quote(test_asset.symbol)
        if saved_quote:
            print(f"✅ Retrieved: ${saved_quote.price_data.price}")

        # Get database stats
        print("📈 Database stats:")
        stats = db_manager.get_database_stats()
        for key, value in stats.items():
            print(f"   {key}: {value}")

    print("\n🎉 SQLite Repository test completed!")
