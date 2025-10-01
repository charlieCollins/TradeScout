"""Universe database manager for internal universe/membership operations.

SPECIAL NOTE: Universes are INTERNAL-ONLY entities that do NOT come from external APIs.
Unlike other managers (TickerSnapshot, Asset, etc.), UniverseManager has NO associated
API provider. Universes are created, updated, and managed entirely within TradeScout's
database through bootstrap operations and manual configuration.

This manager handles:
- Universe CRUD operations (create, read, update, delete)
- Universe membership management (add/remove assets from universes)
- Active universe tracking (which universe is currently selected)
- Metadata tracking for membership refresh operations (bootstrap TTL)
"""

import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from models.universe import Universe, UniverseMembership, UniverseStats
from models.data_update_metadata import DataUpdateMetadataType
from database.config.ttl_config import UNIVERSES_TTL_HOURS
from .base_manager import BaseManager

logger = logging.getLogger(__name__)


class UniverseManager(BaseManager):
    """Database manager for universe and membership operations.

    Universes define groups of assets for screening and analysis. They are
    internal entities created through bootstrap processes, not fetched from APIs.

    Universe membership changes over time as market caps shift, requiring periodic
    refresh (tracked via 24hr TTL metadata).
    """

    def get_data_update_metadata_type(self) -> DataUpdateMetadataType:
        """Get the data update metadata type for TTL validation."""
        return DataUpdateMetadataType.UNIVERSES

    def get_ttl_seconds(self) -> int:
        """Get TTL in seconds for this data type.

        Universe memberships change as market caps shift (e.g., a stock moves
        from small-cap to mid-cap). Use 24-hour TTL for membership refresh checks.
        """
        return UNIVERSES_TTL_HOURS * 3600  # 24 hours = 1 day

    def get_entity_from_database(self, key: str) -> Optional[Universe]:
        """Get Universe from database by name.

        Args:
            key: Universe name (e.g., 'default_universe', 'momentum')

        Returns:
            Universe object or None if not found
        """
        universe_name = key
        if not self._check_dependencies():
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                query = """
                    SELECT id, name, description, is_active, min_market_cap, min_volume,
                           max_assets, last_updated, created_at, updated_at
                    FROM universes
                    WHERE name = ?
                """

                cursor.execute(query, (universe_name,))
                row = cursor.fetchone()

                if not row:
                    logger.debug(f"No universe found with name: {universe_name}")
                    return None

                return Universe.from_db_row(row)

        except Exception as e:
            logger.error(f"Error getting universe from database for {universe_name}: {e}")
            return None

    def set_entity_to_database(self, key: str, entity: Universe) -> bool:
        """Store Universe to database.

        Args:
            key: Universe name (should match entity.name)
            entity: Universe object to store

        Returns:
            True if successful, False otherwise
        """
        if not self._check_dependencies() or not entity:
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Use INSERT OR REPLACE to handle both new and existing universes
                query = """
                    INSERT OR REPLACE INTO universes (
                        name, description, is_active, min_market_cap, min_volume,
                        max_assets, last_updated, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """

                values = (
                    entity.name,
                    entity.description,
                    entity.is_active,
                    entity.min_market_cap,
                    entity.min_volume,
                    entity.max_assets,
                    entity.last_updated.isoformat() if entity.last_updated else None,
                    entity.created_at.isoformat(),
                    datetime.now().isoformat()  # Update updated_at
                )

                cursor.execute(query, values)
                conn.commit()

                logger.debug(f"Successfully stored universe: {entity.name}")
                return True

        except Exception as e:
            logger.error(f"Error storing universe to database for {entity.name}: {e}")
            return False

    # ============================================================================
    # UNIVERSE-SPECIFIC OPERATIONS
    # ============================================================================

    def get_all_universes(self) -> List[Universe]:
        """Get all universes from database.

        Returns:
            List of Universe objects, ordered by name
        """
        if not self._check_dependencies():
            return []

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, name, description, is_active, min_market_cap, min_volume,
                           max_assets, last_updated, created_at, updated_at
                    FROM universes
                    ORDER BY name
                """)
                return [Universe.from_db_row(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error getting all universes: {e}")
            return []

    def get_active_universe(self) -> Optional[Universe]:
        """Get the currently active universe.

        Returns:
            Active Universe object or None if no active universe
        """
        if not self._check_dependencies():
            return None

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, name, description, is_active, min_market_cap, min_volume,
                           max_assets, last_updated, created_at, updated_at
                    FROM universes
                    WHERE is_active = 1
                    LIMIT 1
                """)
                row = cursor.fetchone()
                return Universe.from_db_row(row) if row else None

        except Exception as e:
            logger.error(f"Error getting active universe: {e}")
            return None

    def set_active_universe(self, universe_name: str) -> bool:
        """Set the active universe by name.

        Sets all universes to inactive, then activates the specified one.

        Args:
            universe_name: Name of universe to activate

        Returns:
            True if successful, False otherwise
        """
        if not self._check_dependencies():
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # First, deactivate all universes
                cursor.execute("UPDATE universes SET is_active = 0")

                # Then activate the specified one
                cursor.execute(
                    "UPDATE universes SET is_active = 1 WHERE name = ?",
                    (universe_name,)
                )

                if cursor.rowcount == 0:
                    logger.warning(f"Universe not found: {universe_name}")
                    return False

                conn.commit()
                logger.info(f"Set active universe to: {universe_name}")
                return True

        except Exception as e:
            logger.error(f"Error setting active universe to {universe_name}: {e}")
            return False

    def delete_universe(self, universe_name: str) -> Tuple[bool, int]:
        """Delete a universe and all its memberships.

        Args:
            universe_name: Name of universe to delete

        Returns:
            Tuple of (success: bool, deleted_memberships_count: int)
        """
        if not self._check_dependencies():
            return False, 0

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Get universe ID
                cursor.execute("SELECT id FROM universes WHERE name = ?", (universe_name,))
                row = cursor.fetchone()
                if not row:
                    logger.warning(f"Universe not found: {universe_name}")
                    return False, 0

                universe_id = row[0]

                # Delete memberships first (foreign key constraint)
                cursor.execute(
                    "DELETE FROM universe_memberships WHERE universe_id = ?",
                    (universe_id,)
                )
                deleted_count = cursor.rowcount

                # Delete universe
                cursor.execute("DELETE FROM universes WHERE id = ?", (universe_id,))

                conn.commit()
                logger.info(f"Deleted universe '{universe_name}' and {deleted_count} memberships")
                return True, deleted_count

        except Exception as e:
            logger.error(f"Error deleting universe {universe_name}: {e}")
            return False, 0

    # ============================================================================
    # MEMBERSHIP OPERATIONS
    # ============================================================================

    def get_universe_memberships(
        self,
        universe_name: str,
        active_only: bool = True
    ) -> List[UniverseMembership]:
        """Get memberships for a universe.

        Args:
            universe_name: Name of universe
            active_only: If True, only return active memberships

        Returns:
            List of UniverseMembership objects
        """
        if not self._check_dependencies():
            return []

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Get universe ID
                cursor.execute("SELECT id FROM universes WHERE name = ?", (universe_name,))
                row = cursor.fetchone()
                if not row:
                    logger.warning(f"Universe not found: {universe_name}")
                    return []

                universe_id = row[0]

                # Get memberships
                query = """
                    SELECT id, universe_id, asset_id, added_date, removed_date, reason, is_active
                    FROM universe_memberships
                    WHERE universe_id = ?
                """
                params = [universe_id]

                if active_only:
                    query += " AND is_active = 1"

                cursor.execute(query, params)
                return [UniverseMembership.from_db_row(row) for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error getting memberships for {universe_name}: {e}")
            return []

    def add_universe_memberships(
        self,
        universe_name: str,
        asset_ids: List[int]
    ) -> int:
        """Add assets to a universe.

        Args:
            universe_name: Name of universe
            asset_ids: List of asset IDs to add

        Returns:
            Number of memberships added
        """
        if not self._check_dependencies():
            return 0

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Get universe ID
                cursor.execute("SELECT id FROM universes WHERE name = ?", (universe_name,))
                row = cursor.fetchone()
                if not row:
                    logger.warning(f"Universe not found: {universe_name}")
                    return 0

                universe_id = row[0]
                added_count = 0

                for asset_id in asset_ids:
                    try:
                        cursor.execute("""
                            INSERT INTO universe_memberships (
                                universe_id, asset_id, added_date, is_active
                            ) VALUES (?, ?, ?, 1)
                        """, (universe_id, asset_id, datetime.now().isoformat()))
                        added_count += 1
                    except Exception as e:
                        logger.debug(f"Asset {asset_id} already in universe or error: {e}")
                        continue

                conn.commit()
                logger.info(f"Added {added_count} memberships to universe '{universe_name}'")
                return added_count

        except Exception as e:
            logger.error(f"Error adding memberships to {universe_name}: {e}")
            return 0

    def clear_universe_memberships(self, universe_name: str) -> bool:
        """Mark all memberships as inactive for a universe.

        Args:
            universe_name: Name of universe

        Returns:
            True if successful, False otherwise
        """
        if not self._check_dependencies():
            return False

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Get universe ID
                cursor.execute("SELECT id FROM universes WHERE name = ?", (universe_name,))
                row = cursor.fetchone()
                if not row:
                    logger.warning(f"Universe not found: {universe_name}")
                    return False

                universe_id = row[0]

                # Mark all memberships as inactive
                cursor.execute("""
                    UPDATE universe_memberships
                    SET is_active = 0, removed_date = ?
                    WHERE universe_id = ? AND is_active = 1
                """, (datetime.now().isoformat(), universe_id))

                updated_count = cursor.rowcount
                conn.commit()

                logger.info(f"Cleared {updated_count} memberships from universe '{universe_name}'")
                return True

        except Exception as e:
            logger.error(f"Error clearing memberships from {universe_name}: {e}")
            return False

    # ============================================================================
    # STATISTICS
    # ============================================================================

    def get_stats(self) -> Dict[str, Any]:
        """Get universe manager statistics."""
        if not self._check_dependencies():
            return {"error": "Dependencies not available"}

        try:
            with self.db_manager.get_connection() as conn:
                cursor = conn.cursor()

                # Count total universes
                cursor.execute("SELECT COUNT(*) FROM universes")
                total_universes = cursor.fetchone()[0]

                # Get active universe
                cursor.execute("SELECT name FROM universes WHERE is_active = 1 LIMIT 1")
                row = cursor.fetchone()
                active_universe = row[0] if row else None

                # Count total memberships
                cursor.execute("SELECT COUNT(*) FROM universe_memberships WHERE is_active = 1")
                total_memberships = cursor.fetchone()[0]

                return {
                    "metadata_type": self.get_data_update_metadata_type().value,
                    "ttl_hours": UNIVERSES_TTL_HOURS,
                    "total_universes": total_universes,
                    "active_universe": active_universe,
                    "total_active_memberships": total_memberships,
                    "storage": "universes + universe_memberships tables"
                }

        except Exception as e:
            logger.error(f"Error getting universe manager stats: {e}")
            return {"error": str(e)}
