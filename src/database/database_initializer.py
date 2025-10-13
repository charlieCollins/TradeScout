"""Database initialization for TradeScout using SQLModel."""

import logging
import sqlite3
from pathlib import Path
from sqlmodel import SQLModel, create_engine, Session

logger = logging.getLogger(__name__)


class DatabaseInitializer:
    """Handle database creation and initialization using SQLModel."""

    def __init__(self, db_path: str = "data/tradescout.db"):
        """Initialize with database path."""
        self.db_path = db_path
        self.database_url = f"sqlite:///{db_path}"

    def initialize_database(self) -> bool:
        """Complete database initialization process using SQLModel.

        Uses SQLModel's metadata.create_all() to create all tables
        defined by our SQLModel classes.
        """
        logger.info(f"Starting database initialization: {self.db_path}")

        try:
            # Ensure parent directory exists
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

            # Create engine
            engine = create_engine(
                self.database_url,
                echo=False,
                connect_args={"check_same_thread": False}
            )

            # Import all SQLModel classes to register them with metadata
            self._import_all_models()

            # Create all tables
            SQLModel.metadata.create_all(engine)

            logger.info("Database schema created successfully using SQLModel")

            # Insert initial schema version record
            with Session(engine) as session:
                # Check if schema_versions table exists and has records
                result = session.exec(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='schema_versions'"
                ).first()

                if result and result > 0:
                    # Check if we have any version records
                    version_count = session.exec("SELECT COUNT(*) FROM schema_versions").first()
                    if version_count == 0:
                        # Insert initial version
                        session.exec("""
                            INSERT INTO schema_versions (version, description, applied_at)
                            VALUES ('001', 'Initial SQLModel schema', datetime('now'))
                        """)
                        session.commit()
                        logger.info("Inserted initial schema version record")

            logger.info("Database initialization completed successfully")
            return True

        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            return False

    def _import_all_models(self):
        """Import all SQLModel classes to register them with metadata."""
        # Import all SQLModel classes so they register with SQLModel.metadata
        from models.sqlmodel.asset_sqlmodel import AssetSQLModel
        from models.sqlmodel.asset_price_sqlmodel import AssetPriceSQLModel
        from models.sqlmodel.fundamentals_sqlmodel import FundamentalsSQLModel
        from models.sqlmodel.market_sqlmodel import MarketSQLModel
        from models.sqlmodel.provider_sqlmodel import ProviderSQLModel
        from models.sqlmodel.universe_sqlmodel import UniverseSQLModel, UniverseMembershipSQLModel
        from models.sqlmodel.fed_data_sqlmodel import FedDataSQLModel
        from models.sqlmodel.gap_result_sqlmodel import GapResultSQLModel
        from models.sqlmodel.gap_performance_tracking_sqlmodel import GapPerformanceTrackingSQLModel
        from models.sqlmodel.gap_result_news_sqlmodel import GapResultNewsSQLModel
        from models.sqlmodel.market_holiday_sqlmodel import MarketHolidaySQLModel
        from models.sqlmodel.sentiment_event_sqlmodel import SentimentEventSQLModel
        from models.sqlmodel.sentiment_type_sqlmodel import SentimentTypeSQLModel
        from models.sqlmodel.data_update_metadata_sqlmodel import DataUpdateMetadataSQLModel

    def get_database_info(self) -> dict:
        """Get information about the current database."""
        try:
            # Use raw sqlite3 for info queries
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get schema version
            try:
                cursor.execute(
                    "SELECT version FROM schema_versions ORDER BY applied_at DESC LIMIT 1"
                )
                result = cursor.fetchone()
                schema_version = result[0] if result else "unknown"
            except Exception:
                schema_version = "unknown"

            info = {
                "database_path": self.db_path,
                "schema_version": schema_version,
                "tables": {},
                "status": "healthy"
            }

            # Count records in each table
            tables = [
                "asset_fundamentals", "asset_prices", "assets", "data_update_metadata",
                "markets", "providers", "schema_versions", "sentiment_events",
                "sentiment_types", "universe_memberships", "universes", "fed_data",
                "gap_results", "gap_performance_tracking", "gap_result_news",
                "market_holidays"
            ]

            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
                    result = cursor.fetchone()
                    info["tables"][table] = result[0] if result else 0
                except Exception as e:
                    info["tables"][table] = f"Error: {e}"
                    info["status"] = "warning"

            conn.close()
            return info

        except Exception as e:
            return {
                "database_path": self.db_path,
                "status": "error",
                "error": str(e)
            }