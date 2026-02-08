"""API configuration - loads .env file on import."""

from .api_keys import ensure_env_loaded

__all__ = ["ensure_env_loaded"]
