"""Bootstrap filtered universe from tickers based on configuration."""

import re
import logging
from typing import List, Dict, Any, Optional
from src.config.universe_config import UNIVERSE_CONFIG

logger = logging.getLogger(__name__)


class UniverseBootstrapper:
    """Bootstrap filtered asset universes based on configuration criteria."""

    def __init__(self, db_manager=None):
        """Initialize with database manager."""
        self.db_manager = db_manager
        if not self.db_manager:
            raise ValueError("Database manager required")

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

        # Check ticker types (e.g., CS for Common Stock)
        if "ticker_types" in criteria:
            asset_type = asset.get("type", "")
            if asset_type not in criteria["ticker_types"]:
                return False

        # Check markets
        if "markets" in criteria:
            market = asset.get("market", "")
            if market not in criteria["markets"]:
                return False

        # Check exchanges
        if "exchanges" in criteria:
            # TODO: Map asset exchange to our exchange codes
            # For now, assume all assets from API are on major exchanges
            pass

        # Check symbol pattern (1-5 alphabetic characters)
        if "symbol_pattern" in criteria:
            symbol = asset.get("ticker", "")
            if not re.match(criteria["symbol_pattern"], symbol):
                return False

        # Check active status
        if criteria.get("active_only", False):
            if not asset.get("active", False):
                return False

        return True

    def _meets_exclusion_criteria(self, asset: Dict[str, Any], criteria: Dict) -> bool:
        """Check if asset meets any exclusion criteria (should be excluded)."""

        symbol = asset.get("ticker", "")
        asset_type = asset.get("type", "")

        # Exclude preferred stocks (symbols ending in -P, -PR, -A, etc.)
        if criteria.get("preferred_stocks", False):
            if re.search(r"-[PA-Z]+$", symbol):
                return True

        # TODO: Implement other exclusion criteria based on asset metadata
        # - ETFs, ETNs, REITs, etc. (would need additional data from API)
        # - OTC markets (would need exchange information)
        # - Invalid symbols (partially covered by inclusion pattern)

        return False

    def create_universe(self, universe_name: str = "default_universe") -> Dict[str, Any]:
        """Create a universe by filtering assets and storing membership."""
        if not self.db_manager:
            raise ValueError("Database manager required")

        config = UNIVERSE_CONFIG.get(universe_name)
        if not config:
            raise ValueError(f"Unknown universe: {universe_name}")

        logger.info(f"Creating universe: {universe_name}")

        # TODO: Fetch all assets from database
        # For now, this is a placeholder showing the logic
        all_assets = []  # Would be: self.db_manager.get_all_assets()

        # Apply filters
        filtered_assets = self.apply_filters(all_assets, universe_name)

        # TODO: Create universe record in database
        universe_id = None  # Would be: self.db_manager.create_universe(config)

        # TODO: Add assets to universe membership
        membership_count = 0  # Would be: self.db_manager.add_universe_memberships(universe_id, filtered_assets)

        result = {
            "universe_name": universe_name,
            "universe_id": universe_id,
            "total_assets_considered": len(all_assets),
            "assets_included": len(filtered_assets),
            "membership_records_created": membership_count,
            "config": config
        }

        logger.info(f"Universe creation complete: {result}")
        return result