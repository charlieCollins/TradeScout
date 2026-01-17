"""Fundamentals Repository - Business-focused data access for AssetFundamentals.

This repository provides domain-specific operations for fundamental data.
It wraps the DAO layer (FundamentalsSQLModel) with business queries.
"""

import logging
from typing import List, Optional
from sqlmodel import Session, select
from models.sqlmodel.fundamentals_sqlmodel import FundamentalsSQLModel

logger = logging.getLogger(__name__)


class FundamentalsRepository:
    """Repository for AssetFundamentals business operations.

    This layer provides business-focused data access for fundamentals.
    It wraps the DAO layer (SQLModel) with domain operations.

    Responsibilities:
    - Business queries (market cap filtering, sector analysis, etc.)
    - Domain operations (screening, filtering)
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
    # BASIC QUERIES
    # ============================================================================

    def get_by_asset_id(self, asset_id: int) -> Optional[FundamentalsSQLModel]:
        """Get fundamentals for a specific asset.

        Args:
            asset_id: Asset database ID

        Returns:
            Fundamentals if found, None otherwise
        """
        return self.session.get(FundamentalsSQLModel, asset_id)

    def find_all(self, limit: Optional[int] = None) -> List[FundamentalsSQLModel]:
        """Get all fundamentals records.

        Args:
            limit: Optional limit on number of results

        Returns:
            List of fundamentals
        """
        statement = select(FundamentalsSQLModel)

        if limit:
            statement = statement.limit(limit)

        return list(self.session.exec(statement).all())

    # ============================================================================
    # MARKET CAP QUERIES (Critical for screeners!)
    # ============================================================================

    def find_by_market_cap_range(
        self, min_cap: int, max_cap: Optional[int] = None
    ) -> List[FundamentalsSQLModel]:
        """Find assets within market cap range.

        Business query: Filter by market capitalization.
        This is critical for gap trading screeners (min $300M market cap).

        Args:
            min_cap: Minimum market cap in dollars (will be converted to cents)
            max_cap: Maximum market cap in dollars (optional)

        Returns:
            List of fundamentals within the range
        """
        min_cap_cents = min_cap * 100  # Convert dollars to cents

        if max_cap:
            max_cap_cents = max_cap * 100
            statement = select(FundamentalsSQLModel).where(
                FundamentalsSQLModel.market_cap >= min_cap_cents,
                FundamentalsSQLModel.market_cap <= max_cap_cents
            ).order_by(FundamentalsSQLModel.market_cap.desc())  # type: ignore
        else:
            statement = select(FundamentalsSQLModel).where(
                FundamentalsSQLModel.market_cap >= min_cap_cents
            ).order_by(FundamentalsSQLModel.market_cap.desc())  # type: ignore

        return list(self.session.exec(statement).all())

    def find_large_cap(self) -> List[FundamentalsSQLModel]:
        """Find large-cap stocks (>$10B market cap).

        Business query: Large-cap filter.

        Returns:
            List of large-cap fundamentals
        """
        return self.find_by_market_cap_range(min_cap=10_000_000_000)

    def find_mid_cap(self) -> List[FundamentalsSQLModel]:
        """Find mid-cap stocks ($2B - $10B market cap).

        Business query: Mid-cap filter.

        Returns:
            List of mid-cap fundamentals
        """
        return self.find_by_market_cap_range(
            min_cap=2_000_000_000,
            max_cap=10_000_000_000
        )

    def find_small_cap(self) -> List[FundamentalsSQLModel]:
        """Find small-cap stocks ($300M - $2B market cap).

        Business query: Small-cap filter.

        Returns:
            List of small-cap fundamentals
        """
        return self.find_by_market_cap_range(
            min_cap=300_000_000,
            max_cap=2_000_000_000
        )

    # ============================================================================
    # SECTOR / INDUSTRY QUERIES
    # ============================================================================

    def find_by_sector(self, sector: str) -> List[FundamentalsSQLModel]:
        """Find assets by sector.

        Business query: Sector filtering.

        Args:
            sector: Sector name (e.g., 'Technology', 'Healthcare')

        Returns:
            List of fundamentals in the sector
        """
        statement = select(FundamentalsSQLModel).where(
            FundamentalsSQLModel.sector == sector
        ).order_by(FundamentalsSQLModel.market_cap.desc())  # type: ignore

        return list(self.session.exec(statement).all())

    def find_by_industry(self, industry: str) -> List[FundamentalsSQLModel]:
        """Find assets by industry.

        Business query: Industry filtering.

        Args:
            industry: Industry name

        Returns:
            List of fundamentals in the industry
        """
        statement = select(FundamentalsSQLModel).where(
            FundamentalsSQLModel.industry == industry
        ).order_by(FundamentalsSQLModel.market_cap.desc())  # type: ignore

        return list(self.session.exec(statement).all())

    def get_all_sectors(self) -> List[str]:
        """Get list of all unique sectors.

        Business query: Sector discovery.

        Returns:
            List of sector names (sorted)
        """
        statement = select(FundamentalsSQLModel.sector).distinct()
        sectors = self.session.exec(statement).all()
        # Filter out None values and sort
        return sorted([s for s in sectors if s])

    def get_all_industries(self) -> List[str]:
        """Get list of all unique industries.

        Business query: Industry discovery.

        Returns:
            List of industry names (sorted)
        """
        statement = select(FundamentalsSQLModel.industry).distinct()
        industries = self.session.exec(statement).all()
        # Filter out None values and sort
        return sorted([i for i in industries if i])

    # ============================================================================
    # SCREENING QUERIES (For gap trading and other strategies)
    # ============================================================================

    def find_for_gap_trading(
        self, min_market_cap: int = 300_000_000
    ) -> List[FundamentalsSQLModel]:
        """Find assets suitable for gap trading strategy.

        Business rule: Gap trading requires minimum $300M market cap
        to ensure liquidity and institutional interest.

        Args:
            min_market_cap: Minimum market cap in dollars (default: $300M)

        Returns:
            List of fundamentals meeting gap trading criteria
        """
        return self.find_by_market_cap_range(min_cap=min_market_cap)

    def find_high_volume(
        self, min_volume: int = 1_000_000
    ) -> List[FundamentalsSQLModel]:
        """Find high-volume assets.

        Business query: Volume filtering for liquid stocks.

        Args:
            min_volume: Minimum 30-day average volume

        Returns:
            List of high-volume fundamentals
        """
        statement = select(FundamentalsSQLModel).where(
            FundamentalsSQLModel.avg_volume_30d >= min_volume
        ).order_by(FundamentalsSQLModel.avg_volume_30d.desc())  # type: ignore

        return list(self.session.exec(statement).all())

    # ============================================================================
    # PERSISTENCE OPERATIONS
    # ============================================================================

    def save(self, fundamentals: FundamentalsSQLModel) -> FundamentalsSQLModel:
        """Persist fundamentals to database.

        Handles both INSERT (new) and UPDATE (existing) operations.

        Args:
            fundamentals: Fundamentals to persist

        Returns:
            Persisted fundamentals
        """
        self.session.add(fundamentals)
        self.session.commit()
        self.session.refresh(fundamentals)
        logger.debug(f"Saved fundamentals for asset_id: {fundamentals.asset_id}")
        return fundamentals

    def bulk_save(self, fundamentals_list: List[FundamentalsSQLModel]) -> int:
        """Bulk persist multiple fundamentals.

        Optimized for inserting/updating many fundamentals at once.
        Uses merge to handle both INSERT (new) and UPDATE (existing) operations.

        Args:
            fundamentals_list: List of fundamentals to persist

        Returns:
            Number of fundamentals saved
        """
        for fundamentals in fundamentals_list:
            self.session.merge(fundamentals)
        self.session.commit()
        count = len(fundamentals_list)
        logger.debug(f"Bulk saved {count} fundamentals")
        return count

    def delete(self, fundamentals: FundamentalsSQLModel) -> None:
        """Delete fundamentals from database.

        Args:
            fundamentals: Fundamentals to delete
        """
        self.session.delete(fundamentals)
        self.session.commit()
        logger.debug(f"Deleted fundamentals for asset_id: {fundamentals.asset_id}")

    # ============================================================================
    # STATISTICS
    # ============================================================================

    def count_all(self) -> int:
        """Count total number of fundamentals records.

        Returns:
            Total count
        """
        from sqlmodel import func
        statement = select(func.count(FundamentalsSQLModel.id))
        return self.session.exec(statement).one() or 0

    def get_last_updated(self) -> Optional["datetime"]:
        """Get the most recent update timestamp across all fundamentals.

        Returns:
            Latest last_updated timestamp or None
        """
        from datetime import datetime
        from sqlmodel import func

        stmt = select(func.max(FundamentalsSQLModel.last_updated))
        return self.session.exec(stmt).first()

    def count_by_sector(self, sector: str) -> int:
        """Count fundamentals in a specific sector.

        Args:
            sector: Sector name

        Returns:
            Count
        """
        from sqlmodel import func
        statement = select(func.count(FundamentalsSQLModel.id)).where(
            FundamentalsSQLModel.sector == sector
        )
        return self.session.exec(statement).one() or 0

    def count_with_market_cap(self) -> int:
        """Count fundamentals with market cap data available.

        Returns:
            Count of records with market cap
        """
        from sqlmodel import func
        statement = select(func.count(FundamentalsSQLModel.id)).where(
            FundamentalsSQLModel.market_cap.is_not(None),  # type: ignore
            FundamentalsSQLModel.market_cap > 0
        )
        return self.session.exec(statement).one() or 0

    def get_stats(self) -> dict:
        """Get fundamentals repository statistics.

        Returns aggregated statistics about fundamentals in the database.

        Returns:
            Dictionary with keys:
            - total_fundamentals: Total count
            - top_sectors: Dict of sector -> count (top 10)
            - last_update: Most recent last_updated timestamp
            - with_market_cap: Count with market cap data
        """
        from sqlmodel import func

        # Count total
        total_fundamentals = self.count_all()

        # Count by sector (top 10)
        statement = select(
            FundamentalsSQLModel.sector,
            func.count(FundamentalsSQLModel.asset_id).label('count')
        ).where(
            FundamentalsSQLModel.sector.is_not(None)  # type: ignore
        ).group_by(
            FundamentalsSQLModel.sector
        ).order_by(
            func.count(FundamentalsSQLModel.asset_id).desc()
        ).limit(10)

        results = self.session.exec(statement).all()
        top_sectors = {sector: count for sector, count in results}

        # Get most recent update
        statement = select(func.max(FundamentalsSQLModel.last_updated))
        last_update = self.session.exec(statement).first()

        # Count with market cap
        with_market_cap = self.count_with_market_cap()

        return {
            "total_fundamentals": total_fundamentals,
            "top_sectors": top_sectors,
            "last_update": last_update,
            "with_market_cap": with_market_cap
        }
