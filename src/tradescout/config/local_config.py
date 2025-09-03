"""
TradeScout Local Configuration
Linux/WSL Development Environment
"""

import os
from pathlib import Path

# Base Paths
PROJECT_ROOT = Path(
    __file__
).parent.parent.parent.parent  # Go up to actual project root
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
DATABASE_DIR = DATA_DIR / "databases"

# Database Configuration (Local SQLite)
DATABASE_CONFIG = {
    "type": "sqlite",
    "path": DATABASE_DIR / "tradescout.db",
    "backup_enabled": True,
    "backup_interval_hours": 24,
}



# Development Settings
DEV_CONFIG = {
    "mock_trading": True,  # Paper trading mode
    "verbose_logging": True,  # Detailed logs during development
    "skip_weekends": True,  # Don't run analysis on weekends
    "test_mode": False,  # Set to True for unit tests
}

# NOTE: API provider configuration is in data_sources_config.yaml
