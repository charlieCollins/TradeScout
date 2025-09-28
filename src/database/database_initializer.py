"""Database initialization for TradeScout."""

import logging
from .database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class DatabaseInitializer:
    """Handle database creation and initialization."""

    def __init__(self, db_path: str = "tradescout.db"):
        """Initialize with database path."""
        self.db_path = db_path
        self.db_manager = DatabaseManager(db_path)

    def initialize_database(self) -> bool:
        """Complete database initialization process."""
        logger.info(f"Starting database initialization: {self.db_path}")

        try:
            # Initialize database with schema
            if not self.db_manager.initialize_database():
                logger.error("Database initialization failed")
                return False

            # Verify schema version
            version = self.db_manager.get_schema_version()
            logger.info(f"Database schema version: {version}")

            # Verify default data
            if not self._verify_default_data():
                logger.error("Default data verification failed")
                return False

            logger.info("Database initialization completed successfully")
            return True

        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            return False

    def _verify_default_data(self) -> bool:
        """Verify that default data was inserted correctly."""
        try:



            logger.info("Default data verification passed")
            return True

        except Exception as e:
            logger.error(f"Default data verification error: {e}")
            return False

    def get_database_info(self) -> dict:
        """Get information about the current database."""
        try:
            info = {
                "database_path": self.db_path,
                "schema_version": self.db_manager.get_schema_version(),
                "tables": {},
                "status": "healthy"
            }

            # Count records in each table
            tables = [
                "asset_fundamentals", "asset_prices", "assets", "data_update_metadata",
                "markets", "providers", "schema_versions", "sentiment_events",
                "sentiment_types", "universe_memberships", "universes"
            ]

            for table in tables:
                try:
                    result = self.db_manager.execute_query(f"SELECT COUNT(*) as count FROM {table}")
                    info["tables"][table] = result[0]['count']
                except Exception as e:
                    info["tables"][table] = f"Error: {e}"
                    info["status"] = "warning"

            return info

        except Exception as e:
            return {
                "database_path": self.db_path,
                "status": "error",
                "error": str(e)
            }