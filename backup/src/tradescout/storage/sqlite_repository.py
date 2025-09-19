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
    try:
        return datetime.fromisoformat(val.decode())
    except ValueError:
        # Handle legacy format or other timestamp formats
        try:
            # Try space-separated format
            return datetime.strptime(val.decode(), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            # Return as string if can't parse
            return val.decode()


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
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
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

            logger.debug(f"Successfully executed migration: {name}")

        except Exception as e:
            logger.error(f"Migration {name} failed: {e}")
            conn.rollback()
            raise
        finally:
            if "conn" in locals():
                conn.close()

    def execute_migration_file(self, file_path: str) -> None:
        """Execute migration from SQL file"""
        try:
            with open(file_path, "r") as f:
                sql_content = f.read()

            migration_name = Path(file_path).name
            self.execute_migration(migration_name, sql_content)

        except Exception as e:
            logger.error(f"Failed to execute migration file {file_path}: {e}")
            raise

    def _ensure_schema_version_table(self) -> None:
        """Create schema_version table if it doesn't exist"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    migration_file TEXT NOT NULL
                )
            """
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to create schema_version table: {e}")
            raise

    def _get_current_schema_version(self) -> int:
        """Get the current schema version from database"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("SELECT MAX(version) FROM schema_version")
            result = cursor.fetchone()
            conn.close()

            return result[0] if result[0] is not None else 0
        except Exception:
            # Table doesn't exist or other error - assume version 0
            return 0

    def _record_migration(self, version: int, migration_file: str) -> None:
        """Record that a migration has been applied"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO schema_version (version, migration_file)
                VALUES (?, ?)
            """,
                (version, migration_file),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to record migration {version}: {e}")
            raise

    def _extract_version_from_filename(self, filename: str) -> int:
        """Extract version number from migration filename (e.g., '001_create_schema.sql' -> 1)"""
        try:
            # Extract numeric prefix before first underscore
            version_str = filename.split("_")[0]
            return int(version_str)
        except (IndexError, ValueError):
            logger.warning(f"Could not extract version from filename: {filename}")
            return 0

    def _apply_migrations(self) -> None:
        """Apply only new migration files based on current schema version"""
        try:
            # Ensure schema version table exists
            self._ensure_schema_version_table()

            # Get current version
            current_version = self._get_current_schema_version()

            # Look for migration files
            migrations_dir = Path(__file__).parent / "migrations"

            if not migrations_dir.exists():
                logger.warning(f"Migrations directory not found: {migrations_dir}")
                return

            # Get all .sql files and sort them
            migration_files = sorted(migrations_dir.glob("*.sql"))

            if not migration_files:
                logger.debug("No migration files found")
                return

            # Apply only new migrations
            applied_count = 0
            for migration_file in migration_files:
                file_version = self._extract_version_from_filename(migration_file.name)

                if file_version > current_version:
                    logger.debug(f"Applying migration: {migration_file.name}")
                    self.execute_migration_file(str(migration_file))
                    self._record_migration(file_version, migration_file.name)
                    applied_count += 1
                else:
                    logger.debug(
                        f"Skipping already applied migration: {migration_file.name}"
                    )

            if applied_count > 0:
                logger.debug(f"Applied {applied_count} new migrations")
            else:
                logger.debug("Database schema is up to date")

        except Exception as e:
            logger.error(f"Failed to apply migrations: {e}")
            raise

    def get_migration_status(self) -> Dict[str, Any]:
        """Get current migration status for debugging"""
        try:
            self._ensure_schema_version_table()
            current_version = self._get_current_schema_version()

            # Get applied migrations
            conn = self.get_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT version, migration_file, applied_at FROM schema_version ORDER BY version"
            )
            applied_migrations = cursor.fetchall()
            conn.close()

            # Get available migrations
            migrations_dir = Path(__file__).parent / "migrations"
            available_migrations = []
            if migrations_dir.exists():
                for file in sorted(migrations_dir.glob("*.sql")):
                    version = self._extract_version_from_filename(file.name)
                    available_migrations.append({"version": version, "file": file.name})

            return {
                "current_version": current_version,
                "applied_migrations": [
                    {"version": m[0], "file": m[1], "applied_at": m[2]}
                    for m in applied_migrations
                ],
                "available_migrations": available_migrations,
            }
        except Exception as e:
            logger.error(f"Failed to get migration status: {e}")
            return {"error": str(e)}

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
                table_info.append(
                    {
                        "cid": col[0],
                        "name": col[1],
                        "type": col[2],
                        "notnull": bool(col[3]),
                        "default_value": col[4],
                        "primary_key": bool(col[5]),
                    }
                )

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
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )

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
            if "conn" in locals():
                conn.close()

    def get_database_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            stats = {}

            # Get table row counts
            tables = self.get_all_tables()
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                stats[f"{table}_count"] = cursor.fetchone()[0]

            # Get database file size
            import os

            if os.path.exists(self.db_path):
                stats["file_size_bytes"] = os.path.getsize(self.db_path)
            else:
                stats["file_size_bytes"] = 0

            conn.close()
            return stats

        except Exception as e:
            logger.error(f"Failed to get database stats: {e}")
            return {}
