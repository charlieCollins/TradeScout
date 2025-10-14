"""Database initialization for TradeScout using SQLModel."""

import logging
import sqlite3
from pathlib import Path
from sqlmodel import SQLModel, create_engine

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
        from models.sqlmodel.gap_candidate_sqlmodel import GapCandidateSQLModel
        from models.sqlmodel.gap_candidate_result_sqlmodel import GapCandidateResultSQLModel
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

            info = {
                "database_path": self.db_path,
                "tables": {},
                "status": "healthy"
            }

            # Count records in each table
            tables = [
                "asset_fundamentals", "asset_prices", "assets", "data_update_metadata",
                "markets", "providers", "sentiment_events",
                "sentiment_types", "universe_memberships", "universes", "fed_data",
                "gap_candidate", "gap_candidate_result", "gap_result_news",
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