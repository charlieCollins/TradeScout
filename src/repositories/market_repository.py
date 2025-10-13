"""Market Repository - Business-focused data access for Markets.

This repository provides domain-specific operations for Market data.
It wraps the DAO layer (MarketSQLModel) with business queries.
"""

import logging
from typing import List, Optional
from sqlmodel import Session, select
from models.sqlmodel.market_sqlmodel import MarketSQLModel

logger = logging.getLogger(__name__)


class MarketRepository:
    """Repository for Market business operations.

    This layer provides business-focused data access for Markets.
    It wraps the DAO layer (SQLModel) with domain operations.

    Responsibilities:
    - Business queries (get_by_code, find_us_markets, etc.)
    - Domain operations (filtering, timezone operations)
    - Persistence (save, bulk_save)

    Does NOT:
    - Handle caching (that's CacheService)
    - Make API calls (that's providers)
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

    def get_by_code(self, code: str) -> Optional[MarketSQLModel]:
        """Get active market by code.

        Business rule: Only return active markets.

        Args:
            code: Market code (e.g., 'XNYS', 'NASDAQ')

        Returns:
            Market if found and active, None otherwise
        """
        statement = select(MarketSQLModel).where(
            MarketSQLModel.code == code.upper(),
            MarketSQLModel.is_active == True
        )
        return self.session.exec(statement).first()

    def get_by_id(self, market_id: int) -> Optional[MarketSQLModel]:
        """Get market by database ID.

        Args:
            market_id: Market database ID

        Returns:
            Market if found, None otherwise
        """
        return self.session.get(MarketSQLModel, market_id)

    def find_all_active(self) -> List[MarketSQLModel]:
        """Get all active markets.

        Business rule: Only return active markets.

        Returns:
            List of active markets, ordered by name
        """
        statement = select(MarketSQLModel).where(
            MarketSQLModel.is_active == True
        ).order_by(MarketSQLModel.name)

        return list(self.session.exec(statement).all())

    def find_by_country(self, country: str) -> List[MarketSQLModel]:
        """Get all active markets for a specific country.

        Business query: Filter by country and active status.

        Args:
            country: Country code (e.g., 'US', 'GB')

        Returns:
            List of active markets in the country
        """
        statement = select(MarketSQLModel).where(
            MarketSQLModel.country == country.upper(),
            MarketSQLModel.is_active == True
        ).order_by(MarketSQLModel.name)

        return list(self.session.exec(statement).all())

    def find_us_markets(self) -> List[MarketSQLModel]:
        """Get all active US markets.

        Business query: Common use case - get US markets.

        Returns:
            List of active US markets
        """
        return self.find_by_country("US")

    def find_with_extended_hours(self) -> List[MarketSQLModel]:
        """Get all markets that support extended hours trading.

        Business query: Find markets with pre-market or after-hours sessions.

        Returns:
            List of markets supporting extended hours
        """
        # Note: SQLModel doesn't support property filters directly
        # So we filter in Python after fetching
        all_markets = self.find_all_active()
        return [m for m in all_markets if m.has_extended_hours]

    def search_by_name(self, name_fragment: str) -> List[MarketSQLModel]:
        """Search for markets by name fragment.

        Business query: Useful for autocomplete/search features.

        Args:
            name_fragment: Part of market name to search for

        Returns:
            List of matching active markets
        """
        search_pattern = f"%{name_fragment}%"
        statement = select(MarketSQLModel).where(
            MarketSQLModel.name.like(search_pattern),  # type: ignore
            MarketSQLModel.is_active == True
        ).order_by(MarketSQLModel.name)

        return list(self.session.exec(statement).all())

    # ============================================================================
    # PERSISTENCE OPERATIONS
    # ============================================================================

    def save(self, market: MarketSQLModel) -> MarketSQLModel:
        """Persist market to database.

        Handles both INSERT (new) and UPDATE (existing) operations.

        Args:
            market: Market to persist

        Returns:
            Persisted market with updated fields (e.g., id, timestamps)
        """
        self.session.add(market)
        self.session.commit()
        self.session.refresh(market)
        logger.debug(f"Saved market: {market.code} (id={market.id})")
        return market

    def bulk_save(self, markets: List[MarketSQLModel]) -> int:
        """Bulk persist multiple markets.

        Optimized for inserting/updating many markets at once.

        Args:
            markets: List of markets to persist

        Returns:
            Number of markets saved
        """
        self.session.add_all(markets)
        self.session.commit()
        count = len(markets)
        logger.debug(f"Bulk saved {count} markets")
        return count

    def delete(self, market: MarketSQLModel) -> None:
        """Delete market from database.

        Note: In practice, prefer marking as inactive rather than deleting.

        Args:
            market: Market to delete
        """
        self.session.delete(market)
        self.session.commit()
        logger.debug(f"Deleted market: {market.code}")

    def mark_inactive(self, code: str) -> Optional[MarketSQLModel]:
        """Mark market as inactive (soft delete).

        Business operation: Soft delete instead of hard delete.

        Args:
            code: Market code to mark inactive

        Returns:
            Updated market if found, None otherwise
        """
        market = self.get_by_code(code)
        if market:
            market.is_active = False
            return self.save(market)
        return None

    # ============================================================================
    # STATISTICS & COUNTS
    # ============================================================================

    def count_all(self) -> int:
        """Count total number of markets (including inactive).

        Returns:
            Total market count
        """
        statement = select(MarketSQLModel)
        return len(list(self.session.exec(statement).all()))

    def count_active(self) -> int:
        """Count number of active markets.

        Returns:
            Active market count
        """
        statement = select(MarketSQLModel).where(MarketSQLModel.is_active == True)
        return len(list(self.session.exec(statement).all()))

    def count_by_country(self, country: str) -> int:
        """Count active markets in a specific country.

        Args:
            country: Country code

        Returns:
            Count of active markets in the country
        """
        statement = select(MarketSQLModel).where(
            MarketSQLModel.country == country.upper(),
            MarketSQLModel.is_active == True
        )
        return len(list(self.session.exec(statement).all()))
