"""Aggressive file-based caching for fundamentals data.

This implements fast file-based caching for Polygon fundamentals API responses,
separate from database storage. Following development principle:
"Exploration code uses simple file saving"
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from config.ttl_config import FUNDAMENTALS_TTL_HOURS

logger = logging.getLogger(__name__)


class FundamentalsCacheManager:
    """Manages aggressive file-based caching for fundamentals API responses."""

    def __init__(self, cache_dir: str = "data/cache/fundamentals"):
        """Initialize cache manager.

        Args:
            cache_dir: Directory to store cache files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Cache metadata file
        self.metadata_file = self.cache_dir / "_cache_metadata.json"
        self._metadata = self._load_metadata()

    def _load_metadata(self) -> Dict[str, Any]:
        """Load cache metadata."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error loading cache metadata: {e}")

        return {"entries": {}, "stats": {"hits": 0, "misses": 0, "saves": 0}}

    def _save_metadata(self):
        """Save cache metadata."""
        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(self._metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving cache metadata: {e}")

    def _get_cache_file(self, symbol: str) -> Path:
        """Get cache file path for symbol."""
        return self.cache_dir / f"{symbol.upper()}.json"

    def _is_cache_valid(self, symbol: str, max_age_hours: int = FUNDAMENTALS_TTL_HOURS) -> bool:
        """Check if cached data is still valid."""
        symbol = symbol.upper()

        if symbol not in self._metadata["entries"]:
            return False

        cached_time_str = self._metadata["entries"][symbol].get("cached_at")
        if not cached_time_str:
            return False

        try:
            cached_time = datetime.fromisoformat(cached_time_str)
            age_hours = (datetime.now() - cached_time).total_seconds() / 3600
            return age_hours < max_age_hours
        except Exception as e:
            logger.warning(f"Error checking cache validity for {symbol}: {e}")
            return False

    def get_cached_data(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get cached fundamentals data for symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Cached API response data or None if not cached/expired
        """
        symbol = symbol.upper()

        if not self._is_cache_valid(symbol):
            self._metadata["stats"]["misses"] += 1
            self._save_metadata()
            return None

        cache_file = self._get_cache_file(symbol)
        if not cache_file.exists():
            self._metadata["stats"]["misses"] += 1
            self._save_metadata()
            return None

        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)

            self._metadata["stats"]["hits"] += 1
            self._save_metadata()

            logger.debug(f"Cache HIT for {symbol}")
            return data

        except Exception as e:
            logger.error(f"Error reading cache for {symbol}: {e}")
            self._metadata["stats"]["misses"] += 1
            self._save_metadata()
            return None

    def cache_data(self, symbol: str, data: Dict[str, Any]):
        """Cache fundamentals data for symbol.

        Args:
            symbol: Stock symbol
            data: API response data to cache
        """
        symbol = symbol.upper()
        cache_file = self._get_cache_file(symbol)

        try:
            # Save data to file
            with open(cache_file, 'w') as f:
                json.dump(data, f, indent=2)

            # Update metadata
            self._metadata["entries"][symbol] = {
                "cached_at": datetime.now().isoformat(),
                "file_size": cache_file.stat().st_size
            }
            self._metadata["stats"]["saves"] += 1
            self._save_metadata()

            logger.debug(f"Cached fundamentals data for {symbol}")

        except Exception as e:
            logger.error(f"Error caching data for {symbol}: {e}")

    def invalidate_cache(self, symbol: str):
        """Invalidate cached data for symbol.

        Args:
            symbol: Stock symbol to invalidate
        """
        symbol = symbol.upper()
        cache_file = self._get_cache_file(symbol)

        # Remove file
        if cache_file.exists():
            try:
                cache_file.unlink()
                logger.debug(f"Removed cache file for {symbol}")
            except Exception as e:
                logger.error(f"Error removing cache file for {symbol}: {e}")

        # Remove from metadata
        if symbol in self._metadata["entries"]:
            del self._metadata["entries"][symbol]
            self._save_metadata()

    def clear_cache(self):
        """Clear all cached data."""
        try:
            # Remove all cache files
            for cache_file in self.cache_dir.glob("*.json"):
                if cache_file.name != "_cache_metadata.json":
                    cache_file.unlink()

            # Reset metadata
            self._metadata = {"entries": {}, "stats": {"hits": 0, "misses": 0, "saves": 0}}
            self._save_metadata()

            logger.info("Cleared all fundamentals cache")

        except Exception as e:
            logger.error(f"Error clearing cache: {e}")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dict with cache stats and entries
        """
        total_entries = len(self._metadata["entries"])
        total_size = sum(
            entry.get("file_size", 0)
            for entry in self._metadata["entries"].values()
        )

        stats = self._metadata["stats"].copy()
        stats.update({
            "total_entries": total_entries,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "cache_dir": str(self.cache_dir)
        })

        return stats

    def cleanup_expired(self, max_age_hours: int = FUNDAMENTALS_TTL_HOURS):
        """Clean up expired cache entries.

        Args:
            max_age_hours: Maximum age in hours before expiring
        """
        expired_symbols = []

        for symbol in list(self._metadata["entries"].keys()):
            if not self._is_cache_valid(symbol, max_age_hours):
                expired_symbols.append(symbol)

        for symbol in expired_symbols:
            self.invalidate_cache(symbol)

        if expired_symbols:
            logger.info(f"Cleaned up {len(expired_symbols)} expired cache entries")

        return len(expired_symbols)