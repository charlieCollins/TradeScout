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

# Cron Job Schedules (for reference)
CRON_SCHEDULES = {
    "evening_analysis": "0 23 * * 1-5",  # 11 PM EST weekdays
    "morning_suggestions": "30 6 * * 1-5",  # 6:30 AM EST weekdays
    "performance_tracking": "0 19 * * 1-5",  # 7 PM EST weekdays
    "weekly_summary": "0 8 * * 0",  # 8 AM EST Sundays
    "health_check": "0 9-16 * * 1-5",  # Hourly during market hours
}
