"""Configuration loader for YAML config files."""

import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


class ConfigLoader:
    """Loads configuration from YAML files in configs/ directory."""

    def __init__(self, config_dir: Optional[Path] = None):
        """Initialize config loader.

        Args:
            config_dir: Path to configs directory. Defaults to project root/configs.
        """
        if config_dir is None:
            # Default to configs/ at project root
            # This file is at src/utils/config_loader.py, so go up 2 levels
            project_root = Path(__file__).parent.parent.parent
            config_dir = project_root / "configs"

        self.config_dir = Path(config_dir)
        if not self.config_dir.exists():
            raise FileNotFoundError(f"Config directory not found: {self.config_dir}")

        # Cache loaded configs to avoid repeated disk I/O
        self._cache: Dict[str, Dict[str, Any]] = {}

    def load_yaml(self, relative_path: str) -> Dict[str, Any]:
        """Load a YAML config file with caching.

        Args:
            relative_path: Path relative to config_dir (e.g., "universes/tech.yaml")

        Returns:
            Parsed YAML content as dictionary
        """
        # Check cache first
        if relative_path in self._cache:
            return self._cache[relative_path]

        config_path = self.config_dir / relative_path
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        # Cache for future calls
        self._cache[relative_path] = config
        return config

    def load_universe_config(self, universe_name: str) -> Dict[str, Any]:
        """Load a universe configuration.

        Args:
            universe_name: Name of universe to load

        Returns:
            Universe configuration dictionary
        """
        return self.load_yaml(f"universes/{universe_name}.yaml")

    def load_all_universes(self) -> Dict[str, Dict[str, Any]]:
        """Load all universe configurations.

        Returns:
            Dictionary mapping universe names to their configs
        """
        universes = {}
        universes_dir = self.config_dir / "universes"

        if not universes_dir.exists():
            return universes

        for yaml_file in universes_dir.glob("*.yaml"):
            universe_config = self.load_yaml(f"universes/{yaml_file.name}")
            universe_name = universe_config.get("name", yaml_file.stem)
            universes[universe_name] = universe_config

        return universes

    def load_market_context_rules(self) -> Dict[str, Any]:
        """Load market context rules configuration.

        Returns:
            Market context rules dictionary

        Raises:
            ConfigValidationError: If required config keys are missing
        """
        from utils.config_validator import validate_required_keys

        config = self.load_yaml("market_context_rules.yaml")

        # Validate top-level structure
        validate_required_keys(
            config,
            required_keys=["field_mappings", "required_fields"],
            config_name="configs/market_context_rules.yaml"
        )

        return config

    def load_sic_sector_mapping(self) -> Dict[str, str]:
        """Load SIC sector mapping configuration.

        Returns:
            Dictionary mapping SIC codes (str) to sector names

        Raises:
            ConfigValidationError: If config is not a dictionary
        """
        from utils.config_validator import ConfigValidationError

        config = self.load_yaml("sic_sector_mapping.yaml")

        # Validate that it's a dictionary (can be empty)
        if not isinstance(config, dict):
            raise ConfigValidationError(
                f"configs/sic_sector_mapping.yaml must be a dictionary, got {type(config).__name__}"
            )

        return config

    def load_database_ttl_config(self) -> Dict[str, Any]:
        """Load database TTL configuration.

        Returns:
            Database TTL configuration dictionary

        Raises:
            ConfigValidationError: If required config keys are missing
        """
        from utils.config_validator import validate_required_keys

        config = self.load_yaml("database_ttl.yaml")

        # Validate all required TTL keys
        validate_required_keys(
            config,
            required_keys=[
                "asset_price_ttl_minutes",
                "ticker_snapshot_ttl_minutes",
                "market_snapshot_ttl_minutes",
                "fundamentals_ttl_hours",
                "tickers_ttl_hours",
                "assets_ttl_hours",
                "universes_ttl_hours",
                "markets_ttl_hours",
                "news_ttl_minutes",
                "fed_data_ttl_hours",
                "market_context_ttl_minutes",
                "market_holidays_ttl_days",
                "max_fundamentals_age_days",
                "max_tickers_age_days",
                "market_data_stale_hours",
            ],
            config_name="configs/database_ttl.yaml"
        )

        return config

    def load_gap_trading_config(self) -> Dict[str, Any]:
        """Load gap trading strategy configuration.

        Returns:
            Gap trading configuration dictionary

        Raises:
            ConfigValidationError: If required config keys are missing
        """
        from utils.config_validator import validate_required_keys, validate_nested_keys

        config = self.load_yaml("gap_trading.yaml")

        # Validate top-level structure
        validate_required_keys(
            config,
            required_keys=[
                "minimum_criteria",
                "session_hours",
                "quality_scoring",
                "risk_levels",
                "gap_significance",
                "exhaustion_gap",
                "weekend_risk",
            ],
            config_name="configs/gap_trading.yaml"
        )

        # Validate minimum_criteria structure
        validate_nested_keys(
            config,
            parent_key="minimum_criteria",
            required_nested_keys=["gap_percent", "market_cap", "volume_ratio"],
            config_name="configs/gap_trading.yaml"
        )

        # Validate session_hours structure
        validate_nested_keys(
            config,
            parent_key="session_hours",
            required_nested_keys=["premarket", "afterhours", "regular"],
            config_name="configs/gap_trading.yaml"
        )

        # Validate risk_levels structure
        validate_nested_keys(
            config,
            parent_key="risk_levels",
            required_nested_keys=["low", "medium", "high"],
            config_name="configs/gap_trading.yaml"
        )

        return config

    def load_sentiment_config(self) -> Dict[str, Any]:
        """Load sentiment analysis configuration.

        Returns:
            Sentiment configuration dictionary

        Raises:
            ConfigValidationError: If required config keys are missing
            FileNotFoundError: If config file doesn't exist
        """
        from utils.config_validator import validate_required_keys, validate_nested_keys

        config = self.load_yaml("sentiment.yaml")

        # Validate top-level structure
        validate_required_keys(
            config,
            required_keys=["analysis", "confidence_thresholds", "score_thresholds"],
            config_name="configs/sentiment.yaml"
        )

        # Validate analysis section
        validate_nested_keys(
            config,
            parent_key="analysis",
            required_nested_keys=["default_time_window_days", "max_time_window_days", "max_articles", "recency_weight"],
            config_name="configs/sentiment.yaml"
        )

        # Validate confidence_thresholds structure
        validate_nested_keys(
            config,
            parent_key="confidence_thresholds",
            required_nested_keys=["very_high", "high", "medium", "low", "very_low"],
            config_name="configs/sentiment.yaml"
        )

        # Validate score_thresholds structure
        validate_nested_keys(
            config,
            parent_key="score_thresholds",
            required_nested_keys=["very_positive", "positive", "neutral_high", "neutral_low", "negative", "very_negative"],
            config_name="configs/sentiment.yaml"
        )

        return config


# Singleton instance for easy access
_loader: Optional[ConfigLoader] = None


def get_config_loader() -> ConfigLoader:
    """Get or create the singleton ConfigLoader instance."""
    global _loader
    if _loader is None:
        _loader = ConfigLoader()
    return _loader


# Helper functions for market context rules


def get_field_for_context(
    field_type: str,
    session: str,
    available_data: Dict[str, Any]
) -> Optional[Any]:
    """Get the appropriate field value based on context and availability.

    Args:
        field_type: Type of field needed (e.g., 'current_price', 'volume')
        session: Current market session
        available_data: Dictionary of available data fields

    Returns:
        The first non-NULL value from the priority list, or None if all are NULL
    """
    loader = get_config_loader()
    rules = loader.load_market_context_rules()
    field_mappings = rules.get("field_mappings", {})

    if field_type not in field_mappings:
        return None

    session_mappings = field_mappings[field_type].get(session, [])

    for field_name in session_mappings:
        value = available_data.get(field_name)
        if value is not None:
            return value

    return None


def validate_required_fields(
    operation: str,
    session: str,
    available_data: Dict[str, Any]
) -> bool:
    """Check if required fields are available for an operation.

    Args:
        operation: The operation being performed (e.g., 'change_calculation')
        session: Current market session
        available_data: Dictionary of available data fields

    Returns:
        True if all required fields are non-NULL, False otherwise
    """
    loader = get_config_loader()
    rules = loader.load_market_context_rules()
    required_fields = rules.get("required_fields", {})

    if operation not in required_fields:
        return True  # No requirements defined, assume OK

    requirements = required_fields[operation]

    # Check session-specific requirements
    session_fields = requirements.get(session, [])
    for field in session_fields:
        if available_data.get(field) is None:
            return False

    # Check all-session requirements
    all_session_fields = requirements.get("all_sessions", [])
    for field in all_session_fields:
        if available_data.get(field) is None:
            return False

    return True

# Helper functions for SIC sector mapping


def get_sector_from_sic(sic_code: str) -> str:
    """Map SIC code to broad sector using first 2 digits.

    Args:
        sic_code: 4-digit SIC code (e.g., "3571")

    Returns:
        Broad sector name or "Other" if unmapped

    Example:
        >>> get_sector_from_sic("3571")  # Electronic Computers
        "Technology"
        >>> get_sector_from_sic("6022")  # State Commercial Banks
        "Financials"
    """
    if not sic_code or len(sic_code) < 2:
        return "Other"

    loader = get_config_loader()
    mapping = loader.load_sic_sector_mapping()

    major_group = sic_code[:2]
    return mapping.get(major_group, "Other")
