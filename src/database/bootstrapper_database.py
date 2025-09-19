"""Bootstrap database initialization for TradeScout."""

import logging
from .database_manager import DatabaseManager

logger = logging.getLogger(__name__)


class DatabaseBootstrapper:
    """Bootstrap database creation and initialization."""

    def __init__(self, db_path: str = "tradescout.db"):
        """Initialize with database path."""
        self.db_path = db_path
        self.db_manager = DatabaseManager(db_path)

    def bootstrap_database(self) -> bool:
        """Complete database bootstrap process."""
        logger.info(f"Starting database bootstrap: {self.db_path}")

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

            logger.info("Database bootstrap completed successfully")
            return True

        except Exception as e:
            logger.error(f"Database bootstrap failed: {e}")
            return False

    def _verify_default_data(self) -> bool:
        """Verify that default data was inserted correctly."""
        try:
            # Check markets
            markets = self.db_manager.execute_query("SELECT COUNT(*) as count FROM markets")
            if markets[0]['count'] < 2:
                logger.error("Default markets not found")
                return False

            # Check universes
            universes = self.db_manager.execute_query("SELECT COUNT(*) as count FROM universes")
            if universes[0]['count'] < 1:
                logger.error("Default universe not found")
                return False


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
                "markets", "assets", "asset_fundamentals", "asset_prices",
                "universes", "universe_memberships", "sentiment_types", "sentiment_events",
                "data_versions", "data_sources", "data_lineage",
                "system_config", "system_metrics", "schema_versions"
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