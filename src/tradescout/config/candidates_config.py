"""
Candidates Configuration Manager

Manages trading rules and thresholds for candidate identification.
Provides access to gap trading rules, volume analysis, risk management, etc.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any
import logging

logger = logging.getLogger(__name__)


class CandidatesConfig:
    """Configuration manager for candidate identification rules"""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize candidates configuration

        Args:
            config_path: Path to candidates YAML file
        """
        if config_path is None:
            # Default to config file in same directory
            config_dir = Path(__file__).parent
            config_path = config_dir / "candidates_config.yaml"

        self.config_path = Path(config_path)
        self.config = self._load_config()

    def _load_config(self) -> Dict:
        """Load candidates configuration from YAML"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Candidates config not found: {self.config_path}")

        try:
            with open(self.config_path, "r") as f:
                config = yaml.safe_load(f)

            if config is None:
                raise ValueError(f"Candidates config is empty or invalid: {self.config_path}")

            logger.debug(f"Loaded candidates config from {self.config_path}")
            return config

        except Exception as e:
            raise RuntimeError(f"Failed to load candidates config from {self.config_path}: {e}")

    def get_gap_trading_config(self) -> Dict[str, Any]:
        """Get gap trading rules and thresholds"""
        return self.config.get("gap_trading", {})

    def get_volume_analysis_config(self) -> Dict[str, Any]:
        """Get volume analysis rules"""
        return self.config.get("volume_analysis", {})

    def get_price_movement_config(self) -> Dict[str, Any]:
        """Get price movement thresholds"""
        return self.config.get("price_movement", {})

    def get_liquidity_filters_config(self) -> Dict[str, Any]:
        """Get liquidity and market cap filters"""
        return self.config.get("liquidity_filters", {})

    def get_risk_management_config(self) -> Dict[str, Any]:
        """Get risk management rules"""
        return self.config.get("risk_management", {})

    def get_scoring_config(self) -> Dict[str, Any]:
        """Get candidate scoring and selection rules"""
        return self.config.get("scoring", {})

    def get_timing_config(self) -> Dict[str, Any]:
        """Get time-based rules"""
        return self.config.get("timing", {})

    def get_catalysts_config(self) -> Dict[str, Any]:
        """Get news and catalyst integration rules"""
        return self.config.get("catalysts", {})

    def get_exclusions_config(self) -> Dict[str, Any]:
        """Get exclusion rules"""
        return self.config.get("exclusions", {})

    def get_validation_config(self) -> Dict[str, Any]:
        """Get backtesting and validation rules"""
        return self.config.get("validation", {})

    # Convenience methods for commonly used values
    def get_min_gap_percentage(self) -> float:
        """Get minimum gap percentage threshold"""
        gap_config = self.get_gap_trading_config()
        if "min_gap_percentage" not in gap_config:
            raise KeyError("min_gap_percentage not found in gap_trading config")
        return gap_config["min_gap_percentage"]

    def get_max_gap_percentage(self) -> float:
        """Get maximum gap percentage threshold"""
        gap_config = self.get_gap_trading_config()
        if "max_gap_percentage" not in gap_config:
            raise KeyError("max_gap_percentage not found in gap_trading config")
        return gap_config["max_gap_percentage"]

    def get_min_volume_surge_ratio(self) -> float:
        """Get minimum volume surge ratio"""
        volume_config = self.get_volume_analysis_config()
        if "min_volume_surge_ratio" not in volume_config:
            raise KeyError("min_volume_surge_ratio not found in volume_analysis config")
        return volume_config["min_volume_surge_ratio"]

    def get_confidence_threshold(self) -> float:
        """Get minimum confidence threshold"""
        scoring_config = self.get_scoring_config()
        if "confidence_threshold" not in scoring_config:
            raise KeyError("confidence_threshold not found in scoring config")
        return scoring_config["confidence_threshold"]

    def get_max_position_size_percent(self) -> float:
        """Get maximum position size percentage"""
        risk_config = self.get_risk_management_config()
        if "max_position_size_percent" not in risk_config:
            raise KeyError("max_position_size_percent not found in risk_management config")
        return risk_config["max_position_size_percent"]

    def get_max_suggestions_per_day(self) -> int:
        """Get maximum suggestions per day"""
        scoring_config = self.get_scoring_config()
        if "max_suggestions_per_day" not in scoring_config:
            raise KeyError("max_suggestions_per_day not found in scoring config")
        return scoring_config["max_suggestions_per_day"]

    def get_market_movers_limit(self) -> int:
        """Get market movers limit for gap candidate sourcing"""
        gap_config = self.get_gap_trading_config()
        if "market_movers_limit" not in gap_config:
            raise KeyError("market_movers_limit not found in gap_trading config")
        return gap_config["market_movers_limit"]

    def get_minimum_absolute_volume(self) -> int:
        """Get minimum absolute volume threshold"""
        volume_config = self.get_volume_analysis_config()
        if "minimum_absolute_volume" not in volume_config:
            raise KeyError("minimum_absolute_volume not found in volume_analysis config")
        return volume_config["minimum_absolute_volume"]

    def get_min_market_cap_millions(self) -> float:
        """Get minimum market cap in millions"""
        liquidity_config = self.get_liquidity_filters_config()
        if "min_market_cap_millions" not in liquidity_config:
            raise KeyError("min_market_cap_millions not found in liquidity_filters config")
        return liquidity_config["min_market_cap_millions"]

    def get_scoring_weights(self) -> Dict[str, float]:
        """Get scoring weights for different factors"""
        scoring_config = self.get_scoring_config()
        if "scoring_weights" not in scoring_config:
            raise KeyError("scoring_weights not found in scoring config")
        return scoring_config["scoring_weights"]

    def get_excluded_asset_types(self) -> List[str]:
        """Get list of excluded asset types"""
        exclusions_config = self.get_exclusions_config()
        if "excluded_asset_types" not in exclusions_config:
            raise KeyError("excluded_asset_types not found in exclusions config")
        return exclusions_config["excluded_asset_types"]

    def is_gap_trading_enabled(self, direction: str = "up") -> bool:
        """Check if gap trading is enabled for given direction"""
        gap_config = self.get_gap_trading_config()
        if direction.lower() == "up":
            return gap_config.get("gap_up_enabled", True)
        elif direction.lower() == "down":
            return gap_config.get("gap_down_enabled", False)
        return False

    def validate_config(self) -> Dict[str, Any]:
        """Validate configuration and return any issues"""
        issues = []

        # Validate scoring weights sum to 1.0
        weights = self.get_scoring_weights()
        weight_sum = sum(weights.values())
        if abs(weight_sum - 1.0) > 0.01:
            issues.append(f"Scoring weights sum to {weight_sum:.3f}, should be 1.0")

        # Validate gap percentages
        min_gap = self.get_min_gap_percentage()
        max_gap = self.get_max_gap_percentage()
        if min_gap >= max_gap:
            issues.append(f"Min gap ({min_gap}%) >= max gap ({max_gap}%)")

        # Validate position sizing
        max_pos_size = self.get_max_position_size_percent()
        if max_pos_size > 20.0:
            issues.append(f"Max position size ({max_pos_size}%) seems excessive")

        return {
            "valid": len(issues) == 0,
            "issues": issues,
            "config_sections": list(self.config.keys()),
        }


# Global instance for easy access
_candidates_config = None


def get_candidates_config() -> CandidatesConfig:
    """Get global candidates configuration instance"""
    global _candidates_config
    if _candidates_config is None:
        _candidates_config = CandidatesConfig()
    return _candidates_config


# Convenience functions for commonly used values
def get_min_gap_percentage() -> float:
    """Get minimum gap percentage threshold"""
    return get_candidates_config().get_min_gap_percentage()


def get_min_volume_surge_ratio() -> float:
    """Get minimum volume surge ratio"""
    return get_candidates_config().get_min_volume_surge_ratio()


def get_confidence_threshold() -> float:
    """Get minimum confidence threshold"""
    return get_candidates_config().get_confidence_threshold()


def get_max_position_size_percent() -> float:
    """Get maximum position size percentage"""
    return get_candidates_config().get_max_position_size_percent()


def get_max_suggestions_per_day() -> int:
    """Get maximum suggestions per day"""
    return get_candidates_config().get_max_suggestions_per_day()


def get_market_movers_limit() -> int:
    """Get market movers limit for gap candidate sourcing"""
    return get_candidates_config().get_market_movers_limit()
