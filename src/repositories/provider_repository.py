"""Provider Repository - Business-focused data access for Providers.

This repository provides domain-specific operations for Provider data.
It wraps the DAO layer (ProviderSQLModel) with business queries.
"""

import logging
from typing import List, Optional
from sqlmodel import Session, select
from models.sqlmodel.provider_sqlmodel import ProviderSQLModel

logger = logging.getLogger(__name__)


class ProviderRepository:
    """Repository for Provider business operations.

    This layer provides business-focused data access for Providers.
    Simple reference data - mostly basic CRUD.
    """

    def __init__(self, session: Session):
        """Initialize repository with database session."""
        self.session = session

    # ============================================================================
    # BASIC QUERIES
    # ============================================================================

    def get_by_name(self, name: str) -> Optional[ProviderSQLModel]:
        """Get provider by name.

        Args:
            name: Provider name (e.g., 'polygon', 'yfinance')

        Returns:
            Provider if found, None otherwise
        """
        statement = select(ProviderSQLModel).where(
            ProviderSQLModel.name == name.lower()
        )
        return self.session.exec(statement).first()

    def get_by_id(self, provider_id: int) -> Optional[ProviderSQLModel]:
        """Get provider by ID."""
        return self.session.get(ProviderSQLModel, provider_id)

    def find_all_active(self) -> List[ProviderSQLModel]:
        """Get all active providers."""
        statement = select(ProviderSQLModel).where(
            ProviderSQLModel.is_active == True
        ).order_by(ProviderSQLModel.name)
        return list(self.session.exec(statement).all())

    def find_all(self) -> List[ProviderSQLModel]:
        """Get all providers (including inactive)."""
        statement = select(ProviderSQLModel).order_by(ProviderSQLModel.name)
        return list(self.session.exec(statement).all())

    def get_active_provider(self) -> Optional[ProviderSQLModel]:
        """Get the active provider (typically 'polygon').

        Returns the first active provider, or None if no active providers exist.
        In practice, there should always be one active provider.

        Returns:
            Active provider if found, None otherwise
        """
        statement = select(ProviderSQLModel).where(
            ProviderSQLModel.is_active == True
        ).order_by(ProviderSQLModel.name).limit(1)
        return self.session.exec(statement).first()

    # ============================================================================
    # PERSISTENCE
    # ============================================================================

    def save(self, provider: ProviderSQLModel) -> ProviderSQLModel:
        """Persist provider to database."""
        self.session.add(provider)
        self.session.commit()
        self.session.refresh(provider)
        logger.debug(f"Saved provider: {provider.name}")
        return provider

    def delete(self, provider: ProviderSQLModel) -> None:
        """Delete provider from database."""
        self.session.delete(provider)
        self.session.commit()
        logger.debug(f"Deleted provider: {provider.name}")

    # ============================================================================
    # STATISTICS
    # ============================================================================

    def count_all(self) -> int:
        """Count total number of providers (including inactive).

        Returns:
            Total provider count
        """
        statement = select(ProviderSQLModel)
        return len(list(self.session.exec(statement).all()))

    def count_active(self) -> int:
        """Count active providers."""
        statement = select(ProviderSQLModel).where(ProviderSQLModel.is_active == True)
        return len(list(self.session.exec(statement).all()))
