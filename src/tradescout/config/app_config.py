"""
TradeScout Application Configuration

Core application settings that apply across all environments.
These are general business logic and operational parameters.
"""

# NOTE: Market hours are defined in markets_config.yaml

# NOTE: Trading rules and candidate thresholds are in candidates_config.yaml

# Logging Configuration
LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "file_max_bytes": 10 * 1024 * 1024,  # 10MB
    "file_backup_count": 5,
    "console_enabled": True,
}

# Market Data Caching Configuration
MARKET_SNAPSHOT_CONFIG = {
    "ttl_minutes": 10,  # Market snapshot cache TTL in minutes
    "snapshot_type": "full_market",  # Type identifier for database metadata
}


