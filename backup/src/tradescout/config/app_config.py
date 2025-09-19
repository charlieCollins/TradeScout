"""
TradeScout Application Configuration

Core application settings that apply across all environments.
These are general business logic and operational parameters.
"""

# Market Data Caching Configuration
MARKET_SNAPSHOT_CONFIG = {
    "ttl_minutes": 10,  # Market snapshot cache TTL in minutes
    "snapshot_type": "full_market",  # Type identifier for database metadata
}
