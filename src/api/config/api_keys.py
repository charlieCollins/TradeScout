"""API keys configuration - loads .env file into environment."""

import os
from pathlib import Path

# Try to load from .env file if it exists
try:
    from dotenv import load_dotenv

    # Try multiple paths to find .env file
    # 1. First try relative to this file (src/api/config -> project root)
    env_path = Path(__file__).parent.parent.parent.parent / '.env'

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
except ImportError:
    pass


def ensure_env_loaded():
    """Ensure .env has been loaded. Call this early in app startup."""
    pass  # Loading happens at import time above
