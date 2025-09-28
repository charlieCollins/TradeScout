"""API keys configuration."""

import os
from pathlib import Path

# Try to load from .env file if it exists
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent.parent.parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    # python-dotenv not installed, skip .env file loading
    pass

# Get API key from environment variable
POLYGON_API_KEY = os.getenv('POLYGON_API_KEY')

if not POLYGON_API_KEY:
    raise ValueError(
        "POLYGON_API_KEY environment variable is required. "
        "Set it with: export POLYGON_API_KEY='your_api_key' "
        "or create a .env file with POLYGON_API_KEY=your_api_key"
    )