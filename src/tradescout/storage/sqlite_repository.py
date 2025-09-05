"""
SQLite Repository Implementation

Implements storage interfaces using SQLite database for local development
and production use.
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from .interfaces import (
    DatabaseManager,
    ExtendedHoursRepository,
)

logger = logging.getLogger(__name__)


def _adapt_datetime(dt):
    """Adapt datetime to ISO string for SQLite storage"""
    return dt.isoformat()


def _convert_datetime(val):
    """Convert ISO string from SQLite to datetime"""
    return datetime.fromisoformat(val.decode())


# Register adapters and converters for Python 3.12+ compatibility
sqlite3.register_adapter(datetime, _adapt_datetime)
sqlite3.register_converter("DATETIME", _convert_datetime)



class SQLiteDatabaseManager(DatabaseManager):
    """SQLite implementation of DatabaseManager"""

    def __init__(self, db_path: str = "storage/tradescout.db"):
        self.db_path = db_path
        self._ensure_database_directory()

    def _ensure_database_directory(self) -> None:
        """Create database directory if it doesn't exist"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

    def initialize_database(self) -> bool:
        """Initialize database schema"""
        try:
            # Database directory already created in __init__
            logger.debug(f"Database initialized at {self.db_path}")
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
            with sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
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
            # No data to clean up yet - placeholder for future implementation
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
            with sqlite3.connect(self.db_path, detect_types=sqlite3.PARSE_DECLTYPES) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(query, params or [])
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error executing raw query: {e}")
            return []


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
    print("🧪 Testing SQLite Repository...")

    # Create test database
    db_manager = create_sqlite_database_manager("test_tradescout.db")
    db_manager.initialize_database()

    # Get database stats
    print("📈 Database stats:")
    stats = db_manager.get_database_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")

    print("\n🎉 SQLite Repository test completed!")
