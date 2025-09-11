"""
SQLite Repository Implementation

Core SQLite database manager for local development and production use.
Focuses on database connection management, migrations, and basic operations.
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from .interfaces import DatabaseManager

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
        self._apply_migrations()

    def _ensure_database_directory(self) -> None:
        """Create database directory if it doesn't exist"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        """Get a new database connection"""
        try:
            conn = sqlite3.connect(
                self.db_path,
                detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
                check_same_thread=False
            )
            # Enable foreign key constraints
            conn.execute("PRAGMA foreign_keys = ON")
            return conn
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def execute_migration(self, name: str, sql: str) -> None:
        """Execute a database migration"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Execute the migration SQL (may contain multiple statements)
            cursor.executescript(sql)
            conn.commit()
            
            logger.info(f"Successfully executed migration: {name}")
            
        except Exception as e:
            logger.error(f"Migration {name} failed: {e}")
            conn.rollback()
            raise
        finally:
            if 'conn' in locals():
                conn.close()

    def execute_migration_file(self, file_path: str) -> None:
        """Execute migration from SQL file"""
        try:
            with open(file_path, 'r') as f:
                sql_content = f.read()
            
            migration_name = Path(file_path).name
            self.execute_migration(migration_name, sql_content)
            
        except Exception as e:
            logger.error(f"Failed to execute migration file {file_path}: {e}")
            raise

    def _apply_migrations(self) -> None:
        """Apply all available migration files"""
        try:
            # Look for migration files in the migrations directory
            migrations_dir = Path(__file__).parent / "migrations"
            
            if not migrations_dir.exists():
                logger.warning(f"Migrations directory not found: {migrations_dir}")
                return
            
            # Get all .sql files and sort them
            migration_files = sorted(migrations_dir.glob("*.sql"))
            
            if not migration_files:
                logger.info("No migration files found")
                return
            
            # Apply each migration
            for migration_file in migration_files:
                logger.debug(f"Applying migration: {migration_file.name}")
                self.execute_migration_file(str(migration_file))
                
            logger.info(f"Applied {len(migration_files)} migrations successfully")
            
        except Exception as e:
            logger.error(f"Failed to apply migrations: {e}")
            raise

    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
            conn.close()
            return result is not None
        except Exception as e:
            logger.error(f"Database connection test failed: {e}")
            return False

    def get_table_info(self, table_name: str) -> List[Dict[str, Any]]:
        """Get information about a table's structure"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            
            columns = cursor.fetchall()
            table_info = []
            
            for col in columns:
                table_info.append({
                    'cid': col[0],
                    'name': col[1],
                    'type': col[2],
                    'notnull': bool(col[3]),
                    'default_value': col[4],
                    'primary_key': bool(col[5])
                })
            
            conn.close()
            return table_info
            
        except Exception as e:
            logger.error(f"Failed to get table info for {table_name}: {e}")
            return []

    def get_all_tables(self) -> List[str]:
        """Get list of all tables in the database"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
            
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()
            return tables
            
        except Exception as e:
            logger.error(f"Failed to get table list: {e}")
            return []

    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[tuple]:
        """Execute a SELECT query and return results"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
                
            results = cursor.fetchall()
            conn.close()
            return results
            
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise

    def execute_command(self, command: str, params: Optional[tuple] = None) -> int:
        """Execute an INSERT, UPDATE, or DELETE command"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            if params:
                cursor.execute(command, params)
            else:
                cursor.execute(command)
                
            conn.commit()
            affected_rows = cursor.rowcount
            conn.close()
            return affected_rows
            
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            conn.rollback()
            raise
        finally:
            if 'conn' in locals():
                conn.close()