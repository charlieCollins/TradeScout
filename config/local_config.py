"""
TradeScout Local Configuration
Linux/WSL Development Environment
"""

import os
from pathlib import Path

# Base Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
STORAGE_DIR = PROJECT_ROOT / "storage"

# Database Configuration (Local SQLite)
DATABASE_CONFIG = {
    'type': 'sqlite',
    'path': STORAGE_DIR / "tradescout.db",
    'backup_enabled': True,
    'backup_interval_hours': 24
}

# API Rate Limits (Free Tier Friendly)
API_RATE_LIMITS = {
    'polygon_calls_per_minute': 5,
    'newsapi_calls_per_day': 1000,
    'yfinance_delay_seconds': 0.1,  # Be nice to Yahoo
    'reddit_requests_per_minute': 60
}

# Market Hours (Eastern Time)
MARKET_HOURS = {
    'market_open': '09:30',
    'market_close': '16:00',
    'after_hours_end': '20:00',
    'pre_market_start': '04:00'
}

# Analysis Parameters
ANALYSIS_CONFIG = {
    'min_volume_surge_ratio': 3.0,      # 3x average volume
    'min_gap_percentage': 1.0,          # 1% gap minimum
    'max_suggestions_per_day': 5,       # Limit suggestions
    'confidence_threshold': 0.70,       # 70% minimum confidence
    'max_position_size_percent': 5.0    # 5% max position size
}

# Email Configuration
EMAIL_CONFIG = {
    'enabled': True,
    'smtp_server': 'smtp.gmail.com',
    'smtp_port': 587,
    'sender_email': os.getenv('TRADESCOUT_EMAIL'),
    'sender_password': os.getenv('TRADESCOUT_EMAIL_PASSWORD'),
    'recipient_email': os.getenv('TRADESCOUT_RECIPIENT_EMAIL'),
    'send_time': '07:00'  # 7 AM EST
}

# Web Dashboard Configuration
WEB_CONFIG = {
    'host': 'localhost',
    'port': 5000,
    'debug': True,
    'auto_reload': True
}

# Logging Configuration
LOGGING_CONFIG = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file_max_bytes': 10 * 1024 * 1024,  # 10MB
    'file_backup_count': 5,
    'console_enabled': True
}

# Cron Job Schedules (for reference)
CRON_SCHEDULES = {
    'evening_analysis': '0 23 * * 1-5',      # 11 PM EST weekdays
    'morning_suggestions': '30 6 * * 1-5',   # 6:30 AM EST weekdays  
    'performance_tracking': '0 19 * * 1-5',  # 7 PM EST weekdays
    'weekly_summary': '0 8 * * 0',           # 8 AM EST Sundays
    'health_check': '0 9-16 * * 1-5'         # Hourly during market hours
}

# Development Settings
DEV_CONFIG = {
    'mock_trading': True,        # Paper trading mode
    'verbose_logging': True,     # Detailed logs during development
    'skip_weekends': True,       # Don't run analysis on weekends
    'test_mode': False          # Set to True for unit tests
}