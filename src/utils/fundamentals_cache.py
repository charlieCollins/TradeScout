"""Fundamentals Cache Utility - File-based cache for ticker details.

Works with existing cache structure at data/cache/fundamentals/
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Set

logger = logging.getLogger(__name__)


class FundamentalsCacheHelper:
    """Helper for working with file-based fundamentals cache."""

    def __init__(self, cache_dir: str = "data/cache/fundamentals"):
        """Initialize cache helper.

        Args:
            cache_dir: Directory containing cache files
        """
        self.cache_dir = Path(cache_dir)
        self.metadata_file = self.cache_dir / "_cache_metadata.json"

    def load_from_cache(self, symbol: str) -> Optional[Dict]:
        """Load cached fundamentals for a symbol.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')

        Returns:
            Cached data dict or None if not found/invalid
        """
        cache_file = self.cache_dir / f"{symbol.upper()}.json"

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)

            # Validate structure
            if data.get("status") != "OK" or "results" not in data:
                logger.warning(f"Invalid cache structure for {symbol}")
                return None

            return data

        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Failed to load cache for {symbol}: {e}")
            return None

    def save_to_cache(self, symbol: str, data: Dict) -> bool:
        """Save API response to cache.

        Args:
            symbol: Stock symbol
            data: Raw API response

        Returns:
            True if saved successfully
        """
        try:
            # Ensure cache directory exists
            self.cache_dir.mkdir(parents=True, exist_ok=True)

            # Save data file
            cache_file = self.cache_dir / f"{symbol.upper()}.json"
            with open(cache_file, 'w') as f:
                json.dump(data, f, indent=2)

            # Update metadata
            self._update_metadata(symbol, cache_file.stat().st_size)

            logger.debug(f"Saved cache for {symbol}")
            return True

        except IOError as e:
            logger.error(f"Failed to save cache for {symbol}: {e}")
            return False

    def get_cache_age(self, symbol: str) -> Optional[timedelta]:
        """Get age of cached data for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Age as timedelta or None if not cached
        """
        metadata = self._load_metadata()

        symbol_upper = symbol.upper()
        if symbol_upper not in metadata.get("entries", {}):
            return None

        cached_at_str = metadata["entries"][symbol_upper].get("cached_at")
        if not cached_at_str:
            return None

        try:
            cached_at = datetime.fromisoformat(cached_at_str)
            return datetime.now() - cached_at
        except ValueError:
            return None

    def is_cache_fresh(self, symbol: str, max_age_days: int) -> bool:
        """Check if cached data is fresh enough.

        Args:
            symbol: Stock symbol
            max_age_days: Maximum age in days to consider fresh

        Returns:
            True if cache exists and is fresh
        """
        age = self.get_cache_age(symbol)
        if age is None:
            return False

        return age.days < max_age_days

    def get_cached_symbols(self) -> Set[str]:
        """Get set of all symbols with cache files.

        Returns:
            Set of symbol strings
        """
        if not self.cache_dir.exists():
            return set()

        symbols = set()
        for cache_file in self.cache_dir.glob("*.json"):
            if cache_file.name != "_cache_metadata.json":
                symbols.add(cache_file.stem)

        return symbols

    def _load_metadata(self) -> Dict:
        """Load cache metadata file."""
        if not self.metadata_file.exists():
            return {"entries": {}}

        try:
            with open(self.metadata_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"entries": {}}

    def _update_metadata(self, symbol: str, file_size: int):
        """Update metadata file with new cache entry."""
        metadata = self._load_metadata()

        metadata["entries"][symbol.upper()] = {
            "cached_at": datetime.now().isoformat(),
            "file_size": file_size
        }

        try:
            with open(self.metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
        except IOError as e:
            logger.warning(f"Failed to update cache metadata: {e}")
