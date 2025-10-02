"""Database manager for TradeScout SQLite operations."""

import sqlite3
import os
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manage SQLite database connections and operations."""

    def __init__(self, db_path: str = "data/tradescout.db"):
        """Initialize database manager with path."""
        self.db_path = db_path
        self.schema_dir = Path(__file__).parent / "schema"
        self.migrations_dir = Path(__file__).parent / "migrations"

    def get_connection(self) -> sqlite3.Connection:
        """Get a database connection with proper settings."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")  # Enable foreign key constraints
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        return conn

    def initialize_database(self) -> bool:
        """Initialize database with schema if it doesn't exist."""
        try:
            # Check if database exists and has tables
            if self._database_exists() and self._schema_is_complete():
                logger.info(f"Database {self.db_path} already exists with complete schema")
                return True

            logger.info(f"Initializing new database: {self.db_path}")

            # Run initial schema
            self._run_schema_file("001_initial_schema.sql")

            # Insert default data
            self._insert_default_data()

            logger.info("Database initialization complete")
            return True

        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            return False

    def _database_exists(self) -> bool:
        """Check if database exists and has our tables."""
        if not os.path.exists(self.db_path):
            return False

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_versions'"
                )
                return cursor.fetchone() is not None
        except Exception:
            return False

    def _schema_is_complete(self) -> bool:
        """Check if all expected tables exist in the database."""
        expected_tables = [
            'providers', 'markets', 'assets', 'asset_fundamentals', 'asset_prices',
            'universes', 'universe_memberships', 'sentiment_types', 'sentiment_events',
            'schema_versions', 'data_update_metadata'
        ]

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
                existing_tables = {row[0] for row in cursor.fetchall()}

                # Check if all expected tables exist
                for table in expected_tables:
                    if table not in existing_tables:
                        logger.debug(f"Missing table: {table}")
                        return False

                return True
        except Exception as e:
            logger.error(f"Error checking schema completeness: {e}")
            return False

    def _run_schema_file(self, filename: str) -> None:
        """Run a SQL schema file."""
        schema_file = self.schema_dir / filename
        if not schema_file.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_file}")

        logger.info(f"Running schema file: {filename}")

        with open(schema_file, 'r') as f:
            sql_content = f.read()

        with self.get_connection() as conn:
            # Execute the entire file as a script
            conn.executescript(sql_content)
            conn.commit()

    def _insert_default_data(self) -> None:
        """Insert default data after schema creation."""
        with self.get_connection() as conn:
            cursor = conn.cursor()



            conn.commit()

        logger.info("Default data inserted successfully")

    def get_schema_version(self) -> Optional[str]:
        """Get current database schema version."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT version FROM schema_versions ORDER BY applied_at DESC LIMIT 1"
                )
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting schema version: {e}")
            return None

    def execute_query(self, query: str, params: tuple = ()) -> List[sqlite3.Row]:
        """Execute a SELECT query and return results."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            return cursor.fetchall()

    def execute_update(self, query: str, params: tuple = ()) -> int:
        """Execute an INSERT/UPDATE/DELETE query and return affected rows."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount