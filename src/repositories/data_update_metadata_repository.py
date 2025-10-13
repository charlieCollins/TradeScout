"""DataUpdateMetadata Repository - Business-focused data access for operation tracking.

This repository provides domain-specific operations for DataUpdateMetadata.
It wraps the DAO layer (DataUpdateMetadataSQLModel) with business queries.
"""

import logging
from typing import Optional
from sqlmodel import Session, select
from models.sqlmodel.data_update_metadata_sqlmodel import DataUpdateMetadataSQLModel

logger = logging.getLogger(__name__)


class DataUpdateMetadataRepository:
    """Repository for DataUpdateMetadata business operations.

    This layer provides business-focused data access for operation tracking metadata.
    It wraps the DAO layer (SQLModel) with domain operations.

    Responsibilities:
    - Business queries (latest by operation, recent operations, etc.)
    - Persistence (save, upsert)
    - Operation tracking queries
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

    def get_by_id(
        self, metadata_id: int
    ) -> Optional[DataUpdateMetadataSQLModel]:
        """Get metadata by database ID.

        Args:
            metadata_id: Metadata database ID

        Returns:
            DataUpdateMetadata if found, None otherwise
        """
        return self.session.get(DataUpdateMetadataSQLModel, metadata_id)

    def get_latest_by_operation(
        self,
        operation_type: str,
        operation_subtype: Optional[str] = None
    ) -> Optional[DataUpdateMetadataSQLModel]:
        """Get most recent metadata for a specific operation.

        Business query: Used to check when data was last updated.

        Args:
            operation_type: Operation type (e.g., 'market_snapshots')
            operation_subtype: Optional subtype (e.g., 'fetch')

        Returns:
            Most recent metadata for this operation, or None
        """
        statement = select(DataUpdateMetadataSQLModel).where(
            DataUpdateMetadataSQLModel.operation_type == operation_type
        )

        if operation_subtype:
            statement = statement.where(
                DataUpdateMetadataSQLModel.operation_subtype == operation_subtype
            )

        statement = statement.order_by(
            DataUpdateMetadataSQLModel.completed_at.desc()  # type: ignore
        ).limit(1)

        return self.session.exec(statement).first()

    def find_by_operation_type(
        self,
        operation_type: str,
        limit: int = 10
    ) -> list[DataUpdateMetadataSQLModel]:
        """Get recent operations for a specific type.

        Args:
            operation_type: Operation type to query
            limit: Number of recent operations (default: 10)

        Returns:
            List of recent metadata, ordered by completed_at DESC
        """
        statement = select(DataUpdateMetadataSQLModel).where(
            DataUpdateMetadataSQLModel.operation_type == operation_type
        ).order_by(
            DataUpdateMetadataSQLModel.completed_at.desc()  # type: ignore
        ).limit(limit)

        return list(self.session.exec(statement).all())

    def find_by_status(
        self,
        status: str,
        limit: int = 10
    ) -> list[DataUpdateMetadataSQLModel]:
        """Get operations by status.

        Args:
            status: Status to filter by ('running', 'completed', 'failed', 'partial')
            limit: Number of operations (default: 10)

        Returns:
            List of metadata matching status
        """
        statement = select(DataUpdateMetadataSQLModel).where(
            DataUpdateMetadataSQLModel.status == status
        ).order_by(
            DataUpdateMetadataSQLModel.started_at.desc()  # type: ignore
        ).limit(limit)

        return list(self.session.exec(statement).all())

    # ============================================================================
    # PERSISTENCE OPERATIONS
    # ============================================================================

    def save(
        self, metadata: DataUpdateMetadataSQLModel
    ) -> DataUpdateMetadataSQLModel:
        """Persist metadata to database.

        Handles both INSERT (new) and UPDATE (existing) operations.

        Args:
            metadata: Metadata to persist

        Returns:
            Persisted metadata with updated fields
        """
        self.session.add(metadata)
        self.session.commit()
        self.session.refresh(metadata)
        logger.debug(
            f"Saved metadata: {metadata.operation_type}.{metadata.operation_subtype}"
        )
        return metadata

    def delete(self, metadata: DataUpdateMetadataSQLModel) -> None:
        """Delete metadata from database.

        Args:
            metadata: Metadata to delete
        """
        self.session.delete(metadata)
        self.session.commit()
        logger.debug(
            f"Deleted metadata: {metadata.operation_type}.{metadata.operation_subtype}"
        )

    # ============================================================================
    # STATISTICS
    # ============================================================================

    def count_all(self) -> int:
        """Count total number of metadata records.

        Returns:
            Total count
        """
        from sqlmodel import func

        statement = select(func.count(DataUpdateMetadataSQLModel.id))
        return self.session.exec(statement).one()

    def count_by_status(self, status: str) -> int:
        """Count operations by status.

        Args:
            status: Status to count

        Returns:
            Count of operations with this status
        """
        statement = select(DataUpdateMetadataSQLModel).where(
            DataUpdateMetadataSQLModel.status == status
        )
        return len(list(self.session.exec(statement).all()))
