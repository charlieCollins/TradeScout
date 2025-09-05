"""
Screening Universe Configuration Manager

Manages the configuration of stock universes used for market screening.
Provides access to different screening universes based on strategy needs.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class ScreeningUniverseConfig:
    """Configuration manager for screening universes"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize screening universe configuration

        Args:
            config_path: Path to screening universe YAML file
        """
        if config_path is None:
            # Default to config file in same directory
            config_dir = Path(__file__).parent
            config_path = config_dir / "screening_universe.yaml"

        self.config_path = Path(config_path)
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """Load screening universe configuration from YAML"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Screening universe config not found: {self.config_path}")

        with open(self.config_path, "r") as f:
            config = yaml.safe_load(f)

        logger.debug(f"Loaded screening universe config from {self.config_path}")
        return config

    def get_universe(self, universe_name: str = "default_liquid_universe") -> List[str]:
        """
        Get symbols for a specific screening universe

        Args:
            universe_name: Name of universe to retrieve

        Returns:
            List of stock symbols
        """
        try:
            universe_config = self.config.get(universe_name, {})
            symbols = universe_config.get("symbols", [])

            if not symbols:
                raise ValueError(f"No symbols found for universe '{universe_name}'")

            logger.debug(
                f"Retrieved {len(symbols)} symbols from universe '{universe_name}'"
            )
            return symbols

        except Exception as e:
            logger.error(f"Error getting universe '{universe_name}': {e}")
            return []

    def get_universe_info(self, universe_name: str = "default_liquid_universe") -> Dict:
        """
        Get metadata for a screening universe

        Args:
            universe_name: Name of universe

        Returns:
            Dictionary with universe metadata
        """
        try:
            universe_config = self.config.get(universe_name, {})
            symbols = universe_config.get("symbols", [])

            return {
                "name": universe_name,
                "description": universe_config.get("description", ""),
                "symbol_count": len(symbols),
                "source": universe_config.get("source", ""),
                "last_updated": universe_config.get("last_updated", ""),
                "min_avg_volume": universe_config.get("min_avg_volume"),
                "min_market_cap": universe_config.get("min_market_cap"),
            }

        except Exception as e:
            logger.error(f"Error getting universe info for '{universe_name}': {e}")
            return {}

    def list_available_universes(self) -> List[str]:
        """
        Get list of all available screening universes

        Returns:
            List of universe names
        """
        try:
            # Get all keys that contain 'symbols' (indicating they're universes)
            universes = []
            for key, value in self.config.items():
                if isinstance(value, dict) and "symbols" in value:
                    universes.append(key)

            return universes

        except Exception as e:
            logger.error(f"Error listing universes: {e}")
            return ["default_liquid_universe"]

    def validate_universe(self, universe_name: str) -> bool:
        """
        Validate that a universe exists and has symbols

        Args:
            universe_name: Name of universe to validate

        Returns:
            True if valid, False otherwise
        """
        try:
            symbols = self.get_universe(universe_name)
            return len(symbols) > 0

        except Exception as e:
            logger.error(f"Error validating universe '{universe_name}': {e}")
            return False

    def get_dynamic_config(self) -> Dict:
        """
        Get dynamic screening configuration

        Returns:
            Dictionary with dynamic screening settings
        """
        return self.config.get("dynamic_screening", {})


# Global instance for easy access
_screening_config = None


def get_screening_universe_config() -> ScreeningUniverseConfig:
    """Get global screening universe configuration instance"""
    global _screening_config
    if _screening_config is None:
        _screening_config = ScreeningUniverseConfig()
    return _screening_config


def get_default_screening_universe() -> List[str]:
    """Get default screening universe symbols"""
    config = get_screening_universe_config()
    return config.get_universe("default_liquid_universe")


def get_universe_symbols(universe_name: str) -> List[str]:
    """Get symbols for a specific universe"""
    config = get_screening_universe_config()
    return config.get_universe(universe_name)
