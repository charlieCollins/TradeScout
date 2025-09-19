"""
Default Universe Bootstrapper

Reads existing assets from the database and populates the default universe
using strict filtering criteria defined in universe_config.py.

Universe Config (universe_config.py):
  - Defines strict filtering criteria per SUPPORTED_UNIVERSE.md:
    - Ticker type: CS (Common Stock) only
    - Exchange: XNYS, XNAS, BATS only
    - Symbol format: 1-5 alphabetic characters
    - Market: stocks only
    - Status: active only

This creates the filtered ~4,800-5,000 asset default universe from the
~11,700 assets loaded by the ticker bootstrapper.
"""

import logging
import sqlite3
from typing import Dict, List, Optional
from datetime import datetime

from ..config.universe_config import (
    should_include_in_default_universe,
    get_default_universe_config,
)
from ..storage.sqlite_repository import SQLiteDatabaseManager
from ..storage.universe_manager import UniverseManager

logger = logging.getLogger(__name__)


class DefaultUniverseBootstrapper:
    """Bootstrapper for creating default universe from existing assets using filtering criteria"""

    def __init__(self, db_manager: Optional[SQLiteDatabaseManager] = None):
        """
        Initialize bootstrapper

        Args:
            db_manager: Database manager instance (creates new if None)
        """
        self.db_manager = db_manager or SQLiteDatabaseManager()
        self.universe_manager = UniverseManager(self.db_manager)

    def bootstrap_default_universe(self, dry_run: bool = False) -> Dict[str, int]:
        """
        Populate default universe from existing assets using filtering criteria

        Args:
            dry_run: If True, only analyze what would be added without making changes

        Returns:
            Dictionary with statistics about the operation
        """
        logger.info("Starting default universe bootstrap from existing assets...")

        # Get all assets from database
        all_assets = self._get_all_assets_from_db()
        logger.info(f"Found {len(all_assets)} total assets in database")

        # Apply filtering criteria
        qualified_assets = []
        for asset_data in all_assets:
            if should_include_in_default_universe(asset_data):
                qualified_assets.append(asset_data)

        logger.info(
            f"Found {len(qualified_assets)} assets that meet default universe criteria"
        )

        # Get current universe membership to avoid duplicates
        current_universe_assets = set(
            self.universe_manager.get_universe_assets("default_universe")
        )
        new_assets = [
            asset
            for asset in qualified_assets
            if asset["ticker"] not in current_universe_assets
        ]

        logger.info(f"Found {len(new_assets)} new assets to add to default universe")
        logger.info(f"Already in universe: {len(current_universe_assets)} assets")

        stats = {
            "total_assets_in_db": len(all_assets),
            "qualified_assets": len(qualified_assets),
            "already_in_universe": len(current_universe_assets),
            "new_assets_to_add": len(new_assets),
            "assets_added": 0,
            "errors": 0,
        }

        if dry_run:
            logger.info("DRY RUN: No changes made to database")
            self._log_sample_assets(
                new_assets[:10], "Sample assets that would be added:"
            )
            return stats

        # Ensure default universe exists
        universe = self.universe_manager.get_universe("default_universe")
        if not universe:
            logger.info("Creating default_universe...")
            config = get_default_universe_config()
            self.universe_manager.create_universe(config["name"], config["description"])

        # Add qualified assets to default universe
        for asset_data in new_assets:
            try:
                symbol = asset_data["ticker"]
                success = self.universe_manager.add_to_universe(
                    symbol,
                    "default_universe",
                    "Added by default universe bootstrap based on filtering criteria",
                )

                if success:
                    stats["assets_added"] += 1
                else:
                    logger.warning(f"Failed to add {symbol} to default universe")
                    stats["errors"] += 1

            except Exception as e:
                logger.error(
                    f"Error adding {asset_data.get('ticker', 'unknown')} to universe: {e}"
                )
                stats["errors"] += 1

        logger.info("Default universe bootstrap completed")
        logger.info(f"Assets added: {stats['assets_added']}")
        logger.info(f"Errors: {stats['errors']}")

        return stats

    def _get_all_assets_from_db(self) -> List[Dict]:
        """Get all assets from database in format compatible with filtering function"""
        conn = self.db_manager.get_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # Get assets with market information for filtering
            cursor.execute(
                """
                SELECT 
                    a.symbol as ticker,
                    a.name,
                    a.asset_type,
                    a.market_id,
                    a.is_active as active,
                    'stocks' as market
                FROM assets a
                WHERE a.is_active = 1
                ORDER BY a.symbol
            """
            )

            assets = []
            for row in cursor.fetchall():
                asset_dict = dict(row)

                # Convert boolean to match Polygon API format
                asset_dict["active"] = bool(asset_dict["active"])

                # Convert asset_type to Polygon API format
                asset_type = asset_dict["asset_type"]
                if asset_type == "common_stock":
                    asset_dict["type"] = "CS"
                elif asset_type == "etf":
                    asset_dict["type"] = "ETF"
                elif asset_type == "preferred_stock":
                    asset_dict["type"] = "PFD"
                else:
                    asset_dict["type"] = asset_type.upper() if asset_type else ""

                # Convert market_id to Polygon exchange format
                market_id = asset_dict["market_id"]
                if market_id == "NYSE":
                    asset_dict["primary_exchange"] = "XNYS"
                elif market_id == "NASDAQ":
                    asset_dict["primary_exchange"] = "XNAS"
                elif market_id == "AMEX":
                    asset_dict["primary_exchange"] = "AMEX"
                else:
                    asset_dict["primary_exchange"] = market_id

                # Remove the original keys that aren't expected by the filter
                asset_dict.pop("asset_type", None)
                asset_dict.pop("market_id", None)

                assets.append(asset_dict)

            return assets

        finally:
            conn.close()

    def _log_sample_assets(self, assets: List[Dict], title: str) -> None:
        """Log a sample of assets for debugging"""
        if not assets:
            return

        logger.info(title)
        for asset in assets[:10]:
            symbol = asset.get("ticker", "UNKNOWN")
            asset_type = asset.get("type", "UNKNOWN")
            exchange = asset.get("primary_exchange", "UNKNOWN")
            logger.info(f"  {symbol} ({asset_type}) on {exchange}")

        if len(assets) > 10:
            logger.info(f"  ... and {len(assets) - 10} more")

    def get_universe_stats(self) -> Dict[str, int]:
        """Get current universe statistics"""
        try:
            total_assets = len(self._get_all_assets_from_db())
            universe_assets = len(
                self.universe_manager.get_universe_assets("default_universe")
            )
            universe_stats = self.universe_manager.get_universe_statistics(
                "default_universe"
            )

            return {
                "total_assets_in_db": total_assets,
                "default_universe_assets": universe_assets,
                "default_universe_stats": universe_stats,
            }

        except Exception as e:
            logger.error(f"Error getting universe stats: {e}")
            return {}


def main():
    """Main function for command line usage"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Bootstrap default universe from existing assets"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Analyze what would be added without making changes",
    )
    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="Show current universe statistics only",
    )

    args = parser.parse_args()

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    try:
        bootstrapper = DefaultUniverseBootstrapper()

        if args.stats_only:
            stats = bootstrapper.get_universe_stats()
            print("Current Universe Statistics:")
            print(
                f"  Total assets in database: {stats.get('total_assets_in_db', 'Unknown')}"
            )
            print(
                f"  Assets in default universe: {stats.get('default_universe_assets', 'Unknown')}"
            )

            universe_stats = stats.get("default_universe_stats", {})
            if universe_stats:
                print(
                    f"  Active assets in universe: {universe_stats.get('active_assets', 'Unknown')}"
                )
                print(
                    f"  First asset added: {universe_stats.get('first_asset_added', 'Unknown')}"
                )
                print(
                    f"  Last asset added: {universe_stats.get('last_asset_added', 'Unknown')}"
                )
        else:
            print("Starting default universe bootstrap...")

            if args.dry_run:
                print("DRY RUN MODE: No changes will be made")

            stats = bootstrapper.bootstrap_default_universe(dry_run=args.dry_run)

            print("\nBootstrap Results:")
            print(f"  Total assets in database: {stats['total_assets_in_db']}")
            print(f"  Assets meeting criteria: {stats['qualified_assets']}")
            print(f"  Already in universe: {stats['already_in_universe']}")
            print(f"  New assets to add: {stats['new_assets_to_add']}")

            if not args.dry_run:
                print(f"  Assets successfully added: {stats['assets_added']}")
                print(f"  Errors: {stats['errors']}")

            print("\n✅ Default universe bootstrap completed")

    except Exception as e:
        logger.error(f"Bootstrap failed: {e}")
        print(f"❌ Bootstrap failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
