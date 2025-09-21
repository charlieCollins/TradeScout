"""Bootstrap filtered universe from tickers based on configuration."""

import re
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from src.config.universe_config import UNIVERSE_CONFIG

logger = logging.getLogger(__name__)


class UniverseBootstrapper:
    """Bootstrap filtered asset universes based on configuration criteria."""

    def __init__(self, db_path=None, db_manager=None):
        """Initialize with database path or manager."""
        if db_manager:
            self.db_manager = db_manager
        elif db_path:
            from src.database.database_manager import DatabaseManager
            self.db_manager = DatabaseManager(db_path)
        else:
            raise ValueError("Either db_path or db_manager required")

    def apply_filters(self, assets: List[Dict[str, Any]], universe_name: str = "default_universe") -> List[Dict[str, Any]]:
        """Apply filtering criteria to assets based on universe config."""
        config = UNIVERSE_CONFIG.get(universe_name)
        if not config:
            raise ValueError(f"Unknown universe: {universe_name}")

        included = config["included"]
        excluded = config["excluded"]
        filtered_assets = []

        for asset in assets:
            if self._should_include_asset(asset, included, excluded):
                filtered_assets.append(asset)

        logger.info(f"Filtered {len(assets)} assets to {len(filtered_assets)} for {universe_name}")
        return filtered_assets

    def _should_include_asset(self, asset: Dict[str, Any], included: Dict, excluded: Dict) -> bool:
        """Check if asset meets inclusion criteria and doesn't meet exclusion criteria."""

        # Check included criteria
        if not self._meets_inclusion_criteria(asset, included):
            return False

        # Check excluded criteria
        if self._meets_exclusion_criteria(asset, excluded):
            return False

        return True

    def _meets_inclusion_criteria(self, asset: Dict[str, Any], criteria: Dict) -> bool:
        """Check if asset meets all inclusion criteria."""

        # Check asset types (stock, ETF, REIT)
        if "ticker_types" in criteria:
            asset_type = asset.get("asset_type", "")
            # Map database asset_type to config ticker_types
            type_mapping = {
                "stock": "CS",  # Common Stock
                "etf": "ETF",
                "reit": "REIT"
            }
            mapped_type = type_mapping.get(asset_type.lower(), asset_type)
            if mapped_type not in criteria["ticker_types"]:
                return False

        # Check markets (should be 'stocks')
        if "markets" in criteria:
            # All our assets are from stock market, so this should pass
            pass

        # Check exchanges (XNYS, XNAS)
        if "exchanges" in criteria:
            market_code = asset.get("market_code", "")
            if market_code not in criteria["exchanges"]:
                return False

        # Check symbol pattern (1-5 alphabetic characters)
        if "symbol_pattern" in criteria:
            symbol = asset.get("symbol", "")
            if not re.match(criteria["symbol_pattern"], symbol):
                return False

        # Check active status
        if criteria.get("active_only", False):
            if not asset.get("is_active", False):
                return False

        return True

    def _meets_exclusion_criteria(self, asset: Dict[str, Any], criteria: Dict) -> bool:
        """Check if asset meets any exclusion criteria (should be excluded)."""

        symbol = asset.get("symbol", "")
        asset_type = asset.get("asset_type", "")
        market_code = asset.get("market_code", "")

        # Exclude preferred stocks (symbols ending in -P, -PR, -A, etc.)
        if criteria.get("preferred_stocks", False):
            if re.search(r"-[PA-Z]+$", symbol):
                return True

        # Exclude non-major exchanges (only keep XNYS and XNAS)
        if criteria.get("minor_exchanges", {}).get("otc_markets", False):
            if market_code not in ["XNYS", "XNAS"]:
                return True

        # Exclude test symbols and special characters (covered by inclusion pattern)
        if criteria.get("invalid_symbols", {}).get("special_characters", False):
            if not re.match(r"^[A-Z]{1,5}$", symbol):
                return True

        return False

    def create_universe(self, universe_name: str = "default_universe") -> Dict[str, Any]:
        """Create a universe by filtering assets and storing membership."""
        if not self.db_manager:
            raise ValueError("Database manager required")

        config = UNIVERSE_CONFIG.get(universe_name)
        if not config:
            raise ValueError(f"Unknown universe: {universe_name}")

        logger.info(f"Creating universe: {universe_name}")

        # Fetch all assets from database
        all_assets = self._fetch_all_assets()
        logger.info(f"Found {len(all_assets)} total assets in database")

        # Apply filters
        filtered_assets = self.apply_filters(all_assets, universe_name)
        logger.info(f"Filtered to {len(filtered_assets)} assets for {universe_name}")

        # Get or create universe record
        universe_id = self._get_or_create_universe(universe_name, config)

        # Clear existing universe memberships
        self._clear_universe_memberships(universe_id)

        # Add filtered assets to universe
        membership_count = self._add_universe_memberships(universe_id, filtered_assets)

        result = {
            "universe_name": universe_name,
            "total_assets_considered": len(all_assets),
            "assets_included": len(filtered_assets),
            "membership_records_created": membership_count,
            "config": config
        }

        logger.info(f"Universe creation complete: {result}")
        return result

    def _fetch_all_assets(self) -> List[Dict[str, Any]]:
        """Fetch all assets from the database."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT a.id, a.symbol, a.name, a.asset_type, a.asset_class,
                       a.currency, a.is_active, a.provider_id,
                       m.code as market_code, m.name as market_name
                FROM assets a
                JOIN markets m ON a.market_id = m.id
            """)

            rows = cursor.fetchall()
            assets = []
            for row in rows:
                assets.append({
                    'id': row[0],
                    'symbol': row[1],
                    'name': row[2],
                    'asset_type': row[3],
                    'asset_class': row[4],
                    'currency': row[5],
                    'is_active': bool(row[6]),
                    'provider_id': row[7],
                    'market_code': row[8],
                    'market_name': row[9]
                })

            return assets

    def _get_or_create_universe(self, universe_name: str, config: Dict[str, Any]) -> int:
        """Get existing universe ID or create new one."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()

            # Check if universe exists
            cursor.execute("SELECT id FROM universes WHERE name = ?", (universe_name,))
            result = cursor.fetchone()

            if result:
                universe_id = result[0]
                # Update last_updated
                cursor.execute("""
                    UPDATE universes SET
                        last_updated = ?,
                        updated_at = ?
                    WHERE id = ?
                """, (datetime.now().isoformat(), datetime.now().isoformat(), universe_id))
            else:
                # Create new universe
                cursor.execute("""
                    INSERT INTO universes (name, description, criteria_description, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    universe_name,
                    config.get('description', ''),
                    f"Auto-generated from config: {config.get('name', universe_name)}",
                    True,
                    datetime.now().isoformat(),
                    datetime.now().isoformat()
                ))
                universe_id = cursor.lastrowid

            conn.commit()
            return universe_id

    def _clear_universe_memberships(self, universe_id: int):
        """Clear existing memberships for a universe."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM universe_memberships WHERE universe_id = ?", (universe_id,))
            conn.commit()
            logger.debug(f"Cleared existing memberships for universe_id {universe_id}")

    def _add_universe_memberships(self, universe_id: int, assets: List[Dict[str, Any]]) -> int:
        """Add assets to universe membership table."""
        if not assets:
            return 0

        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()

            current_date = datetime.now().date().isoformat()

            # Prepare batch insert data
            insert_data = [
                (universe_id, asset['id'], current_date, 'initial_load', True)
                for asset in assets
            ]

            cursor.executemany("""
                INSERT INTO universe_memberships (universe_id, asset_id, added_date, reason, is_active)
                VALUES (?, ?, ?, ?, ?)
            """, insert_data)

            conn.commit()
            return len(insert_data)

    def bootstrap_universe(self, universe_name: str = "default_universe") -> bool:
        """Bootstrap universe by creating it from current assets."""
        try:
            result = self.create_universe(universe_name)
            return result.get("assets_included", 0) >= 0
        except Exception as e:
            logger.error(f"Universe bootstrap failed: {e}")
            return False

    def get_universe_stats(self, universe_name: str = "default_universe") -> Dict[str, Any]:
        """Get statistics for a universe."""
        with self.db_manager.get_connection() as conn:
            cursor = conn.cursor()

            # Get universe ID
            cursor.execute("SELECT id FROM universes WHERE name = ?", (universe_name,))
            universe_result = cursor.fetchone()
            if not universe_result:
                return {
                    "total_members": 0,
                    "active_members": 0,
                    "inactive_members": 0,
                    "by_type": {},
                    "by_market": {},
                    "last_updated": "Never"
                }

            universe_id = universe_result[0]

            # Total members
            cursor.execute("""
                SELECT COUNT(*) FROM universe_memberships
                WHERE universe_id = ? AND is_active = 1
            """, (universe_id,))
            total_members = cursor.fetchone()[0]

            # Active vs inactive assets (not membership active/inactive)
            cursor.execute("""
                SELECT a.is_active, COUNT(*)
                FROM universe_memberships um
                JOIN assets a ON um.asset_id = a.id
                WHERE um.universe_id = ? AND um.is_active = 1
                GROUP BY a.is_active
            """, (universe_id,))
            active_stats = dict(cursor.fetchall())

            # By asset type
            cursor.execute("""
                SELECT a.asset_type, COUNT(*)
                FROM universe_memberships um
                JOIN assets a ON um.asset_id = a.id
                WHERE um.universe_id = ? AND um.is_active = 1
                GROUP BY a.asset_type
            """, (universe_id,))
            by_type = dict(cursor.fetchall())

            # By market
            cursor.execute("""
                SELECT m.name, COUNT(*)
                FROM universe_memberships um
                JOIN assets a ON um.asset_id = a.id
                JOIN markets m ON a.market_id = m.id
                WHERE um.universe_id = ? AND um.is_active = 1
                GROUP BY m.name
            """, (universe_id,))
            by_market = dict(cursor.fetchall())

            # Last updated
            cursor.execute("""
                SELECT last_updated
                FROM universes
                WHERE id = ?
            """, (universe_id,))
            last_updated = cursor.fetchone()[0]

        stats = {
            "total_members": total_members,
            "active_members": active_stats.get(1, 0),
            "inactive_members": active_stats.get(0, 0),
            "by_type": by_type,
            "by_market": by_market,
            "last_updated": last_updated or "Never"
        }

        return stats