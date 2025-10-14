"""Universe Repository - Business-focused data access for Universes.

This repository provides domain-specific operations for Universe and UniverseMembership data.
It wraps the DAO layer (UniverseSQLModel) with business queries.

IMPORTANT: Universes are INTERNAL-ONLY entities. They do NOT come from external APIs.
All operations are local database CRUD.
"""

import logging
from typing import List, Optional, Dict, Any, Tuple
from sqlmodel import Session, select, func
from models.sqlmodel.universe_sqlmodel import UniverseSQLModel, UniverseMembershipSQLModel
from models.sqlmodel.asset_sqlmodel import AssetSQLModel
from models.sqlmodel.market_sqlmodel import MarketSQLModel
from models.sqlmodel.fundamentals_sqlmodel import FundamentalsSQLModel

logger = logging.getLogger(__name__)


class UniverseRepository:
    """Repository for Universe business operations.

    This layer provides business-focused data access for Universes.
    Since universes are internal-only, there's no API provider involved.
    All operations are pure CRUD against the local database.

    Responsibilities:
    - Universe CRUD (create, read, update, delete)
    - Membership management (add/remove assets)
    - Active universe tracking
    - Statistics and breakdowns
    """

    def __init__(self, session: Session):
        """Initialize repository with database session.

        Args:
            session: SQLModel session for database operations
        """
        self.session = session

    # ============================================================================
    # BASIC QUERIES - Universe
    # ============================================================================

    def get_by_name(self, name: str) -> Optional[UniverseSQLModel]:
        """Get universe by name.

        Args:
            name: Universe name (e.g., 'gap_trading_universe')

        Returns:
            Universe if found, None otherwise
        """
        statement = select(UniverseSQLModel).where(
            UniverseSQLModel.name == name
        )
        return self.session.exec(statement).first()

    def get_by_id(self, universe_id: int) -> Optional[UniverseSQLModel]:
        """Get universe by ID."""
        return self.session.get(UniverseSQLModel, universe_id)

    def find_all(self) -> List[UniverseSQLModel]:
        """Get all universes.

        Returns:
            List of all universes, ordered by name
        """
        statement = select(UniverseSQLModel).order_by(UniverseSQLModel.name)
        return list(self.session.exec(statement).all())

    def find_all_active(self) -> List[UniverseSQLModel]:
        """Get all active universes.

        Note: Typically only one universe is active at a time, but this
        returns all in case multiple are accidentally set active.

        Returns:
            List of active universes
        """
        statement = select(UniverseSQLModel).where(
            UniverseSQLModel.is_active == True
        ).order_by(UniverseSQLModel.name)
        return list(self.session.exec(statement).all())

    def get_active_universe(self) -> Optional[UniverseSQLModel]:
        """Get the currently active universe.

        Business rule: Only one universe should be active at a time.

        Returns:
            Active universe or None
        """
        statement = select(UniverseSQLModel).where(
            UniverseSQLModel.is_active == True
        ).limit(1)
        return self.session.exec(statement).first()

    # ============================================================================
    # ACTIVE UNIVERSE MANAGEMENT
    # ============================================================================

    def set_active_universe(self, universe_name: str) -> bool:
        """Set the active universe by name.

        Business rule: Only one universe can be active at a time.
        This deactivates all others before activating the specified one.

        Args:
            universe_name: Name of universe to activate

        Returns:
            True if successful, False if universe not found
        """
        try:
            # First, deactivate all universes
            statement = select(UniverseSQLModel)
            all_universes = self.session.exec(statement).all()

            for universe in all_universes:
                universe.is_active = False

            # Find and activate the specified universe
            target_universe = self.get_by_name(universe_name)
            if not target_universe:
                logger.warning(f"Universe not found: {universe_name}")
                return False

            target_universe.is_active = True

            self.session.commit()
            logger.info(f"Set active universe to: {universe_name}")
            return True

        except Exception as e:
            logger.error(f"Error setting active universe to {universe_name}: {e}")
            self.session.rollback()
            return False

    # ============================================================================
    # PERSISTENCE - Universe
    # ============================================================================

    def save(self, universe: UniverseSQLModel) -> UniverseSQLModel:
        """Persist universe to database.

        Handles both INSERT (new) and UPDATE (existing) operations.

        Args:
            universe: Universe to persist

        Returns:
            Persisted universe
        """
        self.session.add(universe)
        self.session.commit()
        self.session.refresh(universe)
        logger.debug(f"Saved universe: {universe.name}")
        return universe

    def upsert_universe(
        self,
        name: str,
        description: str,
        is_active: bool = False
    ) -> UniverseSQLModel:
        """Create or update a universe by name.

        Args:
            name: Universe name
            description: Universe description
            is_active: Whether universe should be active

        Returns:
            Universe record (created or updated)
        """
        existing = self.get_by_name(name)

        if existing:
            # Update existing
            existing.description = description
            existing.is_active = is_active
            return self.save(existing)
        else:
            # Create new
            from datetime import datetime
            new_universe = UniverseSQLModel(
                name=name,
                description=description,
                is_active=is_active,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            return self.save(new_universe)

    def delete(self, universe: UniverseSQLModel) -> int:
        """Delete universe and all its memberships.

        Args:
            universe: Universe to delete

        Returns:
            Number of memberships deleted
        """
        # Get membership count before deletion
        memberships_count = self.count_memberships(universe.id)

        # Delete memberships first (foreign key constraint)
        statement = select(UniverseMembershipSQLModel).where(
            UniverseMembershipSQLModel.universe_id == universe.id
        )
        memberships = self.session.exec(statement).all()
        for membership in memberships:
            self.session.delete(membership)

        # Delete universe
        self.session.delete(universe)
        self.session.commit()

        logger.info(f"Deleted universe '{universe.name}' and {memberships_count} memberships")
        return memberships_count

    # ============================================================================
    # MEMBERSHIP QUERIES
    # ============================================================================

    def get_memberships(
        self,
        universe_id: int,
        limit: Optional[int] = None
    ) -> List[UniverseMembershipSQLModel]:
        """Get memberships for a universe.

        Args:
            universe_id: Universe database ID
            limit: Optional limit on number of results

        Returns:
            List of memberships
        """
        statement = select(UniverseMembershipSQLModel).where(
            UniverseMembershipSQLModel.universe_id == universe_id
        )

        if limit:
            statement = statement.limit(limit)

        return list(self.session.exec(statement).all())

    def get_memberships_by_universe_name(
        self,
        universe_name: str
    ) -> List[UniverseMembershipSQLModel]:
        """Get memberships for a universe by name.

        Args:
            universe_name: Universe name

        Returns:
            List of memberships
        """
        universe = self.get_by_name(universe_name)
        if not universe:
            return []

        return self.get_memberships(universe.id)

    def get_active_universe_asset_ids(self) -> List[int]:
        """Get list of asset IDs in the active universe.

        Business query: Used by gap trading screeners.

        Returns:
            List of asset IDs
        """
        active_universe = self.get_active_universe()
        if not active_universe:
            return []

        statement = select(UniverseMembershipSQLModel.asset_id).where(
            UniverseMembershipSQLModel.universe_id == active_universe.id
        )

        return list(self.session.exec(statement).all())

    def get_active_universe_symbols(self) -> List[str]:
        """Get list of symbols in the active universe.

        Business query: Returns tradable symbols.

        Returns:
            List of symbol strings, sorted alphabetically
        """
        active_universe = self.get_active_universe()
        if not active_universe:
            return []

        # Join with assets to get symbols
        statement = select(AssetSQLModel.symbol).join(
            UniverseMembershipSQLModel,
            AssetSQLModel.id == UniverseMembershipSQLModel.asset_id
        ).where(
            UniverseMembershipSQLModel.universe_id == active_universe.id,
            AssetSQLModel.is_active == True
        ).order_by(AssetSQLModel.symbol)

        return list(self.session.exec(statement).all())

    def get_active_universe_assets(
        self,
        limit: Optional[int] = None
    ) -> List[AssetSQLModel]:
        """Get all assets in the active universe.

        Business query: Used by fundamentals bootstrap and other operations
        that need to work with the active trading universe.

        Args:
            limit: Optional limit on number of results

        Returns:
            List of Asset objects in active universe
        """
        active_universe = self.get_active_universe()
        if not active_universe:
            logger.warning("No active universe found")
            return []

        # Join UniverseMembership with Assets to get full asset records
        statement = select(AssetSQLModel).join(
            UniverseMembershipSQLModel,
            AssetSQLModel.id == UniverseMembershipSQLModel.asset_id
        ).where(
            UniverseMembershipSQLModel.universe_id == active_universe.id,
            AssetSQLModel.is_active == True
        ).order_by(AssetSQLModel.symbol)

        if limit:
            statement = statement.limit(limit)

        return list(self.session.exec(statement).all())

    def is_symbol_in_universe(self, symbol: str, universe_name: str) -> bool:
        """Check if a symbol is in a specific universe.

        Args:
            symbol: Asset symbol to check
            universe_name: Name of universe

        Returns:
            True if symbol is in universe, False otherwise
        """
        universe = self.get_by_name(universe_name)
        if not universe:
            return False

        # Check if asset with symbol exists in universe
        statement = select(func.count()).select_from(AssetSQLModel).join(
            UniverseMembershipSQLModel,
            AssetSQLModel.id == UniverseMembershipSQLModel.asset_id
        ).where(
            AssetSQLModel.symbol == symbol.upper(),
            UniverseMembershipSQLModel.universe_id == universe.id
        )

        count = self.session.exec(statement).one()
        return count > 0

    # ============================================================================
    # MEMBERSHIP MANAGEMENT
    # ============================================================================

    def add_memberships(
        self,
        universe_id: int,
        asset_ids: List[int]
    ) -> int:
        """Add assets to a universe.

        Args:
            universe_id: Universe database ID
            asset_ids: List of asset IDs to add

        Returns:
            Number of memberships added
        """
        added_count = 0

        for asset_id in asset_ids:
            try:
                # Check if membership already exists
                statement = select(UniverseMembershipSQLModel).where(
                    UniverseMembershipSQLModel.universe_id == universe_id,
                    UniverseMembershipSQLModel.asset_id == asset_id
                )
                existing = self.session.exec(statement).first()

                if not existing:
                    membership = UniverseMembershipSQLModel(
                        universe_id=universe_id,
                        asset_id=asset_id
                    )
                    self.session.add(membership)
                    added_count += 1

            except Exception as e:
                logger.debug(f"Error adding asset {asset_id} to universe: {e}")
                continue

        self.session.commit()
        logger.info(f"Added {added_count} memberships to universe_id {universe_id}")
        return added_count

    def bulk_add_memberships(
        self,
        universe_id: int,
        asset_ids: List[int]
    ) -> int:
        """Bulk add memberships to a universe (optimized for large lists).

        Assumes memberships were cleared first, so no duplicate checking.

        Args:
            universe_id: Universe database ID
            asset_ids: List of asset IDs to add

        Returns:
            Number of memberships added
        """
        if not asset_ids:
            return 0

        memberships = [
            UniverseMembershipSQLModel(
                universe_id=universe_id,
                asset_id=asset_id
            )
            for asset_id in asset_ids
        ]

        self.session.add_all(memberships)
        self.session.commit()

        count = len(memberships)
        logger.info(f"Bulk added {count} memberships to universe_id {universe_id}")
        return count

    def clear_memberships(self, universe_id: int) -> int:
        """Clear all memberships from a universe.

        Args:
            universe_id: Universe database ID

        Returns:
            Number of memberships deleted
        """
        statement = select(UniverseMembershipSQLModel).where(
            UniverseMembershipSQLModel.universe_id == universe_id
        )
        memberships = self.session.exec(statement).all()

        count = len(memberships)
        for membership in memberships:
            self.session.delete(membership)

        self.session.commit()
        logger.info(f"Cleared {count} memberships from universe_id {universe_id}")
        return count

    # ============================================================================
    # STATISTICS & BREAKDOWNS
    # ============================================================================

    def count_all(self) -> int:
        """Count total number of universes."""
        statement = select(func.count()).select_from(UniverseSQLModel)
        return self.session.exec(statement).one()

    def count_memberships(self, universe_id: int) -> int:
        """Count memberships in a universe.

        Args:
            universe_id: Universe database ID

        Returns:
            Count of memberships
        """
        statement = select(func.count()).select_from(UniverseMembershipSQLModel).where(
            UniverseMembershipSQLModel.universe_id == universe_id
        )
        return self.session.exec(statement).one()

    def get_market_breakdown(
        self,
        universe_name: str
    ) -> List[Tuple[str, str, int]]:
        """Get market breakdown for a universe.

        Business query: Shows distribution of assets across markets.

        Args:
            universe_name: Universe name

        Returns:
            List of tuples (market_code, market_name, asset_count)
        """
        from sqlalchemy import text

        # Look up universe by name first
        universe = self.get_by_name(universe_name)
        if not universe:
            return []

        # This requires GROUP BY which SQLModel doesn't handle well
        # Use raw SQL for this complex query
        query = text("""
            SELECT m.code, m.name, COUNT(um.asset_id) as count
            FROM universe_memberships um
            JOIN assets a ON um.asset_id = a.id
            JOIN markets m ON a.market_id = m.id
            WHERE um.universe_id = :universe_id
            GROUP BY m.id
            ORDER BY count DESC
        """)

        # Use execute() for raw SQL, not exec()
        result = self.session.execute(query, {"universe_id": universe.id})
        return result.fetchall()

    def get_assets_with_fundamentals(self) -> List[Dict[str, Any]]:
        """Get all active assets with their fundamentals for filtering.

        Business query: Used by universe bootstrap to filter assets by criteria.

        Returns:
            List of dictionaries containing asset + fundamentals data
        """
        # Join assets + fundamentals + markets
        statement = select(
            AssetSQLModel.id,
            AssetSQLModel.symbol,
            AssetSQLModel.name,
            AssetSQLModel.asset_type,
            MarketSQLModel.code.label("market_code"),
            AssetSQLModel.is_active,
            FundamentalsSQLModel.sector,
            FundamentalsSQLModel.market_cap,
            FundamentalsSQLModel.avg_volume_30d.label("volume")
        ).join(
            MarketSQLModel,
            AssetSQLModel.market_id == MarketSQLModel.id,
            isouter=True
        ).join(
            FundamentalsSQLModel,
            AssetSQLModel.id == FundamentalsSQLModel.asset_id,
            isouter=True
        ).where(
            AssetSQLModel.is_active == True
        ).order_by(AssetSQLModel.symbol)

        results = self.session.exec(statement).all()

        # Convert to list of dicts
        assets = []
        for row in results:
            assets.append({
                "id": row[0],
                "symbol": row[1],
                "name": row[2],
                "asset_type": row[3],
                "market_code": row[4],
                "is_active": row[5],
                "sector": row[6],
                "market_cap": row[7],
                "volume": row[8]
            })

        return assets

    def get_universe_stats(self, universe_name: str) -> Optional["UniverseStats"]:
        """Get statistics for a universe.

        Args:
            universe_name: Universe name

        Returns:
            UniverseStats object or None if universe not found
        """
        from models.dataclass.universe import UniverseStats
        from sqlmodel import func

        # Get universe
        universe = self.get_by_name(universe_name)
        if not universe:
            return None

        # Get memberships with assets
        statement = select(
            UniverseMembershipSQLModel.asset_id,
            AssetSQLModel.is_active,
            AssetSQLModel.asset_type,
            MarketSQLModel.name.label("market_name")
        ).join(
            AssetSQLModel,
            UniverseMembershipSQLModel.asset_id == AssetSQLModel.id
        ).join(
            MarketSQLModel,
            AssetSQLModel.market_id == MarketSQLModel.id,
            isouter=True
        ).where(
            UniverseMembershipSQLModel.universe_id == universe.id
        )

        results = self.session.exec(statement).all()

        # Calculate statistics
        total_members = len(results)
        active_members = sum(1 for r in results if r[1])  # r[1] is is_active
        inactive_members = total_members - active_members

        # Count by asset type
        by_asset_type = {}
        for r in results:
            asset_type = r[2]  # r[2] is asset_type
            by_asset_type[asset_type] = by_asset_type.get(asset_type, 0) + 1

        # Count by market
        by_market = {}
        for r in results:
            market_name = r[3]  # r[3] is market_name
            if market_name:
                by_market[market_name] = by_market.get(market_name, 0) + 1

        # Get last updated
        last_updated = universe.updated_at.isoformat() if universe.updated_at else None

        return UniverseStats(
            universe_name=universe_name,
            total_members=total_members,
            active_members=active_members,
            inactive_members=inactive_members,
            by_asset_type=by_asset_type,
            by_market=by_market,
            last_updated=last_updated
        )
