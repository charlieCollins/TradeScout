"""FedData Repository - Business-focused data access for Federal Reserve economic data.

This repository provides domain-specific operations for FedData.
It wraps the DAO layer (FedDataSQLModel) with business queries.
"""

import logging
from typing import List, Optional, Dict
from sqlmodel import Session, select
from models.sqlmodel.fed_data_sqlmodel import FedDataSQLModel

logger = logging.getLogger(__name__)


class FedDataRepository:
    """Repository for FedData business operations.

    This layer provides business-focused data access for Federal Reserve economic data.
    It wraps the DAO layer (SQLModel) with domain operations.

    Responsibilities:
    - Business queries (latest by type, recent observations, etc.)
    - Domain operations (filtering by data type)
    - Persistence (save, bulk_save, upsert)

    Does NOT:
    - Handle caching (that's CacheService)
    - Make API calls (that's the economic data provider)
    - Manage TTL (that's CacheService)
    """

    def __init__(self, session: Session):
        """Initialize repository with database session.

        Args:
            session: SQLModel session for database operations
        """
        self.session = session

    # ============================================================================
    # BUSINESS QUERIES
    # ============================================================================

    def get_by_id(self, fed_data_id: int) -> Optional[FedDataSQLModel]:
        """Get FED data by database ID.

        Args:
            fed_data_id: FedData database ID

        Returns:
            FedData if found, None otherwise
        """
        return self.session.get(FedDataSQLModel, fed_data_id)

    def get_latest_by_type(self, data_type: str) -> Optional[FedDataSQLModel]:
        """Get most recent observation for a specific data type.

        Args:
            data_type: Data type ('inflation', 'inflation_expectations', 'treasury_yields')

        Returns:
            Most recent FedData for this type, or None
        """
        statement = select(FedDataSQLModel).where(
            FedDataSQLModel.data_type == data_type
        ).order_by(FedDataSQLModel.observation_date.desc()).limit(1)  # type: ignore

        return self.session.exec(statement).first()

    def get_all_latest(self) -> Dict[str, Optional[FedDataSQLModel]]:
        """Get latest observation for each data type.

        Business query: Get current state of all FED data types.

        Returns:
            Dictionary mapping data_type -> latest FedData
        """
        data_types = ['inflation', 'inflation_expectations', 'treasury_yields']

        result = {}
        for data_type in data_types:
            result[data_type] = self.get_latest_by_type(data_type)

        return result

    def get_recent_by_type(
        self,
        data_type: str,
        limit: int = 10
    ) -> List[FedDataSQLModel]:
        """Get recent observations for a specific data type.

        Args:
            data_type: Data type to query
            limit: Number of recent observations (default: 10)

        Returns:
            List of recent FedData, ordered by date DESC
        """
        statement = select(FedDataSQLModel).where(
            FedDataSQLModel.data_type == data_type
        ).order_by(FedDataSQLModel.observation_date.desc()).limit(limit)  # type: ignore

        return list(self.session.exec(statement).all())

    def find_by_type(self, data_type: str) -> List[FedDataSQLModel]:
        """Get all observations for a specific data type.

        Args:
            data_type: Data type to query

        Returns:
            List of all FedData for this type, ordered by date DESC
        """
        statement = select(FedDataSQLModel).where(
            FedDataSQLModel.data_type == data_type
        ).order_by(FedDataSQLModel.observation_date.desc())  # type: ignore

        return list(self.session.exec(statement).all())

    # ============================================================================
    # PERSISTENCE OPERATIONS
    # ============================================================================

    def save(self, fed_data: FedDataSQLModel) -> FedDataSQLModel:
        """Persist FedData to database.

        Handles both INSERT (new) and UPDATE (existing) operations.

        Args:
            fed_data: FedData to persist

        Returns:
            Persisted FedData with updated fields
        """
        self.session.add(fed_data)
        self.session.commit()
        self.session.refresh(fed_data)
        logger.debug(f"Saved fed_data: {fed_data.data_type} on {fed_data.observation_date}")
        return fed_data

    def bulk_save(self, fed_data_list: List[FedDataSQLModel]) -> int:
        """Bulk persist multiple FedData records.

        Optimized for inserting/updating many records at once.

        Args:
            fed_data_list: List of FedData to persist

        Returns:
            Number of records saved
        """
        self.session.add_all(fed_data_list)
        self.session.commit()
        count = len(fed_data_list)
        logger.debug(f"Bulk saved {count} fed_data records")
        return count

    def bulk_upsert(self, fed_data_list: List[FedDataSQLModel]) -> int:
        """Bulk upsert multiple FedData records.

        Queries for existing records by unique constraint (data_type, observation_date)
        and updates them, or inserts new records if they don't exist.

        Args:
            fed_data_list: List of FedData to upsert

        Returns:
            Number of records upserted
        """
        from datetime import datetime

        for fed_data in fed_data_list:
            # Query for existing record by unique constraint
            statement = select(FedDataSQLModel).where(
                FedDataSQLModel.data_type == fed_data.data_type,
                FedDataSQLModel.observation_date == fed_data.observation_date
            )
            existing = self.session.exec(statement).first()

            if existing:
                # Update existing record
                existing.value = fed_data.value
                existing.details = fed_data.details
                existing.updated_at = datetime.utcnow()
                self.session.add(existing)
            else:
                # Insert new record
                self.session.add(fed_data)

        self.session.commit()
        count = len(fed_data_list)
        logger.debug(f"Bulk upserted {count} fed_data records")
        return count

    def delete(self, fed_data: FedDataSQLModel) -> None:
        """Delete FedData from database.

        Args:
            fed_data: FedData to delete
        """
        self.session.delete(fed_data)
        self.session.commit()
        logger.debug(f"Deleted fed_data: {fed_data.data_type} on {fed_data.observation_date}")

    # ============================================================================
    # STATISTICS
    # ============================================================================

    def count_all(self) -> int:
        """Count total number of FedData records.

        Returns:
            Total count
        """
        from sqlmodel import func
        statement = select(func.count(FedDataSQLModel.id))
        return self.session.exec(statement).one() or 0

    def count_by_type(self, data_type: str) -> int:
        """Count observations for a specific data type.

        Args:
            data_type: Data type to count

        Returns:
            Count of observations
        """
        from sqlmodel import func
        statement = select(func.count(FedDataSQLModel.id)).where(
            FedDataSQLModel.data_type == data_type
        )
        return self.session.exec(statement).one() or 0

    def get_stats(self) -> dict:
        """Get FED data repository statistics.

        Returns aggregated statistics about FED data in the database.

        Returns:
            Dictionary with keys:
            - total_observations: Total count
            - by_type: Dict of data_type -> count
            - latest_dates: Dict of data_type -> latest observation_date
        """
        from sqlmodel import func

        # Count total
        total_observations = self.count_all()

        # Count by type
        data_types = ['inflation', 'inflation_expectations', 'treasury_yields']
        by_type = {dt: self.count_by_type(dt) for dt in data_types}

        # Get latest dates
        latest_dates = {}
        for data_type in data_types:
            statement = select(func.max(FedDataSQLModel.observation_date)).where(
                FedDataSQLModel.data_type == data_type
            )
            latest_date = self.session.exec(statement).first()
            latest_dates[data_type] = latest_date

        return {
            "total_observations": total_observations,
            "by_type": by_type,
            "latest_dates": latest_dates
        }
