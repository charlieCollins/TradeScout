"""API keys configuration."""

import os
from pathlib import Path

# Try to load from .env file if it exists
try:
    from dotenv import load_dotenv

    # Try multiple paths to find .env file
    # 1. First try relative to this file
    env_path = Path(__file__).parent.parent.parent / '.env'

    # 2. If not found, try current working directory
    if not env_path.exists():
        env_path = Path.cwd() / '.env'

    # 3. If still not found, try to find project root by looking for tradescout script
    if not env_path.exists():
        current = Path(__file__).parent
        while current != current.parent:
            if (current / 'tradescout').exists() and (current / '.env').exists():
                env_path = current / '.env'
                break
            current = current.parent

    if env_path.exists():
        load_dotenv(env_path)
        # Explicitly set the environment variable if it's in the .env file
        from dotenv import dotenv_values
        env_vars = dotenv_values(env_path)
        if 'POLYGON_API_KEY' in env_vars and not os.getenv('POLYGON_API_KEY'):
            os.environ['POLYGON_API_KEY'] = env_vars['POLYGON_API_KEY']
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