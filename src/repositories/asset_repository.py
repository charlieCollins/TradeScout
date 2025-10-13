"""Asset Repository - Business-focused data access for Assets.

This repository provides domain-specific operations for Asset data.
It wraps the DAO layer (AssetSQLModel) with business queries.
"""

import logging
from typing import List, Optional
from sqlmodel import Session, select
from models.sqlmodel.asset_sqlmodel import AssetSQLModel

logger = logging.getLogger(__name__)


class AssetRepository:
    """Repository for Asset business operations.

    This layer provides business-focused data access for Assets.
    It wraps the DAO layer (SQLModel) with domain operations.

    Responsibilities:
    - Business queries (get_by_symbol, find_by_market_cap, etc.)
    - Domain operations (filtering, complex joins)
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

    def get_by_symbol(self, symbol: str) -> Optional[AssetSQLModel]:
        """Get active asset by symbol.

        Business rule: Only return active (not delisted) assets.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')

        Returns:
            Asset if found and active, None otherwise
        """
        statement = select(AssetSQLModel).where(
            AssetSQLModel.symbol == symbol.upper(),
            AssetSQLModel.is_active == True
        )
        return self.session.exec(statement).first()

    def get_by_id(self, asset_id: int) -> Optional[AssetSQLModel]:
        """Get asset by database ID.

        Args:
            asset_id: Asset database ID

        Returns:
            Asset if found, None otherwise
        """
        return self.session.get(AssetSQLModel, asset_id)

    def find_all_active(self, limit: Optional[int] = None) -> List[AssetSQLModel]:
        """Get all active assets.

        Business rule: Only return active assets.

        Args:
            limit: Optional limit on number of results

        Returns:
            List of active assets
        """
        statement = select(AssetSQLModel).where(
            AssetSQLModel.is_active == True
        ).order_by(AssetSQLModel.symbol)

        if limit:
            statement = statement.limit(limit)

        return list(self.session.exec(statement).all())

    def find_by_market(self, market_id: int) -> List[AssetSQLModel]:
        """Get all active assets for a specific market.

        Business query: Filter by market and active status.

        Args:
            market_id: Market database ID

        Returns:
            List of active assets in the market
        """
        statement = select(AssetSQLModel).where(
            AssetSQLModel.market_id == market_id,
            AssetSQLModel.is_active == True
        ).order_by(AssetSQLModel.symbol)

        return list(self.session.exec(statement).all())

    def find_by_asset_type(self, asset_type: str) -> List[AssetSQLModel]:
        """Get all active assets of a specific type.

        Business query: Filter by asset type and active status.

        Args:
            asset_type: Asset type (e.g., 'stock', 'etf')

        Returns:
            List of active assets of the specified type
        """
        statement = select(AssetSQLModel).where(
            AssetSQLModel.asset_type == asset_type.lower(),
            AssetSQLModel.is_active == True
        ).order_by(AssetSQLModel.symbol)

        return list(self.session.exec(statement).all())

    def find_tradeable_assets(self) -> List[AssetSQLModel]:
        """Get all tradeable assets (active and not delisted).

        Business rule: Tradeable = active AND not delisted.

        Returns:
            List of tradeable assets
        """
        statement = select(AssetSQLModel).where(
            AssetSQLModel.is_active == True,
            AssetSQLModel.is_delisted == False
        ).order_by(AssetSQLModel.symbol)

        return list(self.session.exec(statement).all())

    def get_by_symbol_with_market(
        self, symbol: str
    ) -> Optional[tuple[AssetSQLModel, "MarketSQLModel"]]:
        """Get asset with its associated market (join query).

        Business query: Get asset and market in single query.

        Args:
            symbol: Stock symbol

        Returns:
            Tuple of (Asset, Market) or None if not found
        """
        from models.sqlmodel.market_sqlmodel import MarketSQLModel

        statement = select(AssetSQLModel, MarketSQLModel).join(
            MarketSQLModel,
            AssetSQLModel.market_id == MarketSQLModel.id
        ).where(
            AssetSQLModel.symbol == symbol.upper(),
            AssetSQLModel.is_active == True
        )

        result = self.session.exec(statement).first()
        return result if result else None

    def search_by_symbol_prefix(
        self, prefix: str, limit: int = 50
    ) -> List[AssetSQLModel]:
        """Search for assets by symbol prefix.

        Business query: Useful for autocomplete/search features.

        Args:
            prefix: Symbol prefix to search for (e.g., 'AAP')
            limit: Maximum number of results (default: 50)

        Returns:
            List of matching active assets
        """
        search_pattern = f"{prefix.upper()}%"
        statement = select(AssetSQLModel).where(
            AssetSQLModel.symbol.like(search_pattern),  # type: ignore
            AssetSQLModel.is_active == True
        ).order_by(AssetSQLModel.symbol).limit(limit)

        return list(self.session.exec(statement).all())

    # ============================================================================
    # PERSISTENCE OPERATIONS
    # ============================================================================

    def save(self, asset: AssetSQLModel) -> AssetSQLModel:
        """Persist asset to database.

        Handles both INSERT (new) and UPDATE (existing) operations.

        Args:
            asset: Asset to persist

        Returns:
            Persisted asset with updated fields (e.g., id, timestamps)
        """
        self.session.add(asset)
        self.session.commit()
        self.session.refresh(asset)
        logger.debug(f"Saved asset: {asset.symbol} (id={asset.id})")
        return asset

    def bulk_save(self, assets: List[AssetSQLModel]) -> int:
        """Bulk persist multiple assets.

        Optimized for inserting/updating many assets at once.

        Args:
            assets: List of assets to persist

        Returns:
            Number of assets saved
        """
        self.session.add_all(assets)
        self.session.commit()
        count = len(assets)
        logger.debug(f"Bulk saved {count} assets")
        return count

    def delete(self, asset: AssetSQLModel) -> None:
        """Delete asset from database.

        Note: In practice, prefer marking as inactive rather than deleting.

        Args:
            asset: Asset to delete
        """
        self.session.delete(asset)
        self.session.commit()
        logger.debug(f"Deleted asset: {asset.symbol}")

    def mark_inactive(self, symbol: str) -> Optional[AssetSQLModel]:
        """Mark asset as inactive (soft delete).

        Business operation: Soft delete instead of hard delete.

        Args:
            symbol: Symbol of asset to mark inactive

        Returns:
            Updated asset if found, None otherwise
        """
        asset = self.get_by_symbol(symbol)
        if asset:
            asset.is_active = False
            return self.save(asset)
        return None

    # ============================================================================
    # STATISTICS & COUNTS
    # ============================================================================

    def count_all(self) -> int:
        """Count total number of assets (including inactive).

        Returns:
            Total asset count
        """
        statement = select(AssetSQLModel)
        return len(list(self.session.exec(statement).all()))

    def count_active(self) -> int:
        """Count number of active assets.

        Returns:
            Active asset count
        """
        statement = select(AssetSQLModel).where(AssetSQLModel.is_active == True)
        return len(list(self.session.exec(statement).all()))

    def count_by_type(self, asset_type: str) -> int:
        """Count active assets of a specific type.

        Args:
            asset_type: Asset type to count

        Returns:
            Count of active assets of the specified type
        """
        statement = select(AssetSQLModel).where(
            AssetSQLModel.asset_type == asset_type.lower(),
            AssetSQLModel.is_active == True
        )
        return len(list(self.session.exec(statement).all()))

    def get_stats(self) -> dict:
        """Get asset repository statistics.

        Returns aggregated statistics about assets in the database.

        Returns:
            Dictionary with keys:
            - total_assets: Count of active assets
            - by_type: Dict of asset_type -> count
            - last_update: Most recent updated_at timestamp
        """
        from typing import Dict, Any
        from sqlmodel import func

        # Count total active assets
        total_assets = self.count_active()

        # Count by asset type
        statement = select(
            AssetSQLModel.asset_type,
            func.count(AssetSQLModel.id).label('count')
        ).where(
            AssetSQLModel.is_active == True
        ).group_by(AssetSQLModel.asset_type)

        results = self.session.exec(statement).all()
        by_type = {asset_type: count for asset_type, count in results}

        # Get most recent update
        statement = select(func.max(AssetSQLModel.updated_at))
        last_update = self.session.exec(statement).first()

        return {
            "total_assets": total_assets,
            "by_type": by_type,
            "last_update": last_update
        }
