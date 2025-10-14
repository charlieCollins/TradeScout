"""Configuration validation utilities.

Provides reusable validation for config files to ensure required structure exists
and give helpful error messages when configuration is malformed.
"""

from typing import Dict, Any, List


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    pass


def validate_required_keys(
    config: Dict[str, Any],
    required_keys: List[str],
    config_name: str
) -> None:
    """Validate that all required keys exist in configuration.

    Args:
        config: Configuration dictionary to validate
        required_keys: List of required top-level keys
        config_name: Name of config file (for error messages)

    Raises:
        ConfigValidationError: If any required key is missing
    """
    missing_keys = [key for key in required_keys if key not in config]

    if missing_keys:
        raise ConfigValidationError(
            f"Missing required key(s) in {config_name}: {missing_keys}. "
            f"Expected keys: {required_keys}"
        )


def validate_nested_keys(
    config: Dict[str, Any],
    parent_key: str,
    required_nested_keys: List[str],
    config_name: str
) -> None:
    """Validate that all required nested keys exist under a parent key.

    Args:
        config: Configuration dictionary to validate
        parent_key: Parent key that should contain nested structure
        required_nested_keys: List of required keys under parent
        config_name: Name of config file (for error messages)

    Raises:
        ConfigValidationError: If parent key missing or nested keys missing
    """
    if parent_key not in config:
        raise ConfigValidationError(
            f"Missing parent key '{parent_key}' in {config_name}"
        )

    parent_value = config[parent_key]

    if not isinstance(parent_value, dict):
        raise ConfigValidationError(
            f"Key '{parent_key}' in {config_name} must be a dictionary, got {type(parent_value).__name__}"
        )

    missing_keys = [key for key in required_nested_keys if key not in parent_value]

    if missing_keys:
        raise ConfigValidationError(
            f"Missing required key(s) in {config_name} under '{parent_key}': {missing_keys}. "
            f"Expected keys: {required_nested_keys}"
        )
