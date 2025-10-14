# Fundamentals Bootstrap - Cache-Aware Implementation Plan

**Created:** 2025-10-13
**Status:** Planning
**Priority:** High (reduces API calls by ~68%)

## Problem Statement

Current `bootstrap_fundamentals` implementation:
- Fetches ALL assets from database (11k+ assets)
- Makes Polygon API call for EVERY asset (expensive, slow, quota-consuming)
- Ignores existing cache files at `data/cache/fundamentals/` (7,564 cached files)
- Doesn't scope to active universe (should only fetch fundamentals for tradable assets)

## Current Cache System (Already Exists!)

- **Location:** `data/cache/fundamentals/`
- **Count:** 7,564 cached JSON files
- **Format:** Raw Polygon API responses with `results`, `status`, etc.
- **Metadata:** `_cache_metadata.json` tracks `cached_at` timestamp per symbol
- **Age:** Most cached Sept 28, 2025 (15 days ago - within 30-day TTL ✅)

### Example Cache File Structure

```json
{
  "request_id": "2ebf9cca94a5494799581ea70719d2bc",
  "results": {
    "ticker": "AAPL",
    "name": "Apple Inc.",
    "market_cap": 3791126029400.0,
    "sector": "Technology",
    "sic_code": "3571",
    ...
  },
  "status": "OK"
}
```

### Example Metadata Entry

```json
{
  "entries": {
    "AAPL": {
      "cached_at": "2025-09-28T14:54:58.026132",
      "file_size": 1968
    },
    ...
  }
}
```

## Proposed Solution

### Architecture Overview

Implement 3-tier checking system for fundamentals bootstrap:

```
For each asset in ACTIVE UNIVERSE:
    ┌─────────────────────────────────────┐
    │ 1. Database Check                    │
    │ If fundamentals exist & < 30 days    │
    │ → Skip (already fresh)               │
    └─────────────────────────────────────┘
                  ↓ (miss/stale)
    ┌─────────────────────────────────────┐
    │ 2. File Cache Check                  │
    │ Load data/cache/fundamentals/AAPL.json│
    │ Check age from _cache_metadata.json  │
    │ If < 30 days → Load from file        │
    └─────────────────────────────────────┘
                  ↓ (miss/stale)
    ┌─────────────────────────────────────┐
    │ 3. API Fetch                         │
    │ fetch_ticker_details_raw(symbol)     │
    │ Save to cache + update metadata      │
    │ (Individual API call - unavoidable)  │
    └─────────────────────────────────────┘
                  ↓
         Save to database
```

### Configuration

From `configs/database_ttl.yaml`:
```yaml
fundamentals_ttl_hours: 168         # 1 week - staleness detection
max_fundamentals_age_days: 30       # Cache/database freshness threshold
```

## Implementation Plan

### 1. Create `src/utils/fundamentals_cache.py` (NEW FILE)

```python
"""Fundamentals Cache Utility - File-based cache for Polygon ticker details.

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
            data: Raw Polygon API response

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
```

### 2. Update `src/repositories/universe_repository.py`

Add method to get full Asset objects for active universe:

```python
def get_active_universe_assets(
    self,
    limit: Optional[int] = None
) -> List[AssetSQLModel]:
    """Get all assets in the active universe.

    Business query: Used by fundamentals bootstrap and other operations
    that need to work with the active trading universe.

    Args:
        limit: Optional limit on number of results

    Returns:
        List of Asset objects in active universe
    """
    active_universe = self.get_active_universe()
    if not active_universe:
        logger.warning("No active universe found")
        return []

    # Join UniverseMembership with Assets to get full asset records
    statement = select(AssetSQLModel).join(
        UniverseMembershipSQLModel,
        AssetSQLModel.id == UniverseMembershipSQLModel.asset_id
    ).where(
        UniverseMembershipSQLModel.universe_id == active_universe.id,
        AssetSQLModel.is_active == True
    ).order_by(AssetSQLModel.symbol)

    if limit:
        statement = statement.limit(limit)

    return list(self.session.exec(statement).all())
```

### 3. Update `src/services/data_service_v2.py` - `bootstrap_fundamentals()`

Major refactor to add cache awareness and universe scoping:

**Key Changes:**

1. **Scope to active universe:**
   ```python
   # OLD: Get all assets
   assets = self.asset_repository.find_all_active(limit=limit)

   # NEW: Get active universe assets
   assets = self.universe_repository.get_active_universe_assets(limit=limit)
   ```

2. **Add cache helper initialization:**
   ```python
   from utils.fundamentals_cache import FundamentalsCacheHelper
   from utils.config_loader import ConfigLoader

   cache_helper = FundamentalsCacheHelper()
   config = ConfigLoader.load_database_ttl()
   max_age_days = config["max_fundamentals_age_days"]  # 30 days
   ```

3. **Add 3-tier checking in fetch loop:**
   ```python
   stats = {
       "from_database": 0,
       "from_cache": 0,
       "from_api": 0,
       "errors": 0
   }

   for asset_sql in assets:
       # Tier 1: Check database
       existing = self.fundamentals_repository.get_by_asset_id(asset_sql.id)
       if existing:
           age_days = (datetime.now() - existing.last_updated).days
           if age_days < max_age_days:
               stats["from_database"] += 1
               continue

       # Tier 2: Check file cache
       if cache_helper.is_cache_fresh(asset_sql.symbol, max_age_days):
           cached_data = cache_helper.load_from_cache(asset_sql.symbol)
           if cached_data:
               fundamentals = AssetFundamentals.from_polygon_data(
                   asset_id=asset_sql.id,
                   provider_id=1,
                   polygon_data=cached_data["results"]
               )
               fundamentals_data[asset_sql.id] = fundamentals
               stats["from_cache"] += 1
               continue

       # Tier 3: Fetch from API (unavoidable)
       try:
           ticker_data = self.polygon_provider.fetch_ticker_details_raw(asset_sql.symbol)
           if ticker_data:
               # Save to cache for future use
               cache_helper.save_to_cache(
                   asset_sql.symbol,
                   {"status": "OK", "results": ticker_data}
               )

               fundamentals = AssetFundamentals.from_polygon_data(
                   asset_id=asset_sql.id,
                   provider_id=1,
                   polygon_data=ticker_data
               )
               fundamentals_data[asset_sql.id] = fundamentals
               stats["from_cache"] += 1
           else:
               stats["errors"] += 1
       except Exception as e:
           stats["errors"] += 1
           fetch_errors.append(f"{asset_sql.symbol}: {str(e)}")
   ```

4. **Update progress reporting:**
   ```python
   logger.info(
       f"Fundamentals sources: {stats['from_database']} from DB (fresh), "
       f"{stats['from_cache']} from cache, "
       f"{stats['from_api']} from API, "
       f"{stats['errors']} errors"
   )
   ```

### 4. Update `src/cli/database_commands.py` - Display Stats

Update bootstrap fundamentals display to show cache statistics:

```python
# After result = data_service.bootstrap_fundamentals(...)

console.print(f"\n[cyan]Data Sources:[/cyan]")
console.print(f"  From database (fresh): {result.from_database:,}")
console.print(f"  From cache files: {result.from_cache:,}")
console.print(f"  From Polygon API: {result.from_api:,}")
console.print(f"  Cache hit rate: {cache_hit_rate:.1f}%")
```

## Expected Results

### Before (Current Implementation)
```
Processing all assets from database (11,000 assets)
Making 11,000 Polygon API calls...
Duration: ~30-60 minutes
API quota used: 11,000 calls
```

### After (Cache-Aware Implementation)
```
Processing active universe assets (11,000 assets)
Fundamentals sources:
  - 0 from database (fresh after reset)
  - 7,564 from cache files (68% cache hit rate)
  - 3,436 from Polygon API (only missing/stale)
Duration: ~10-15 minutes
API quota used: 3,436 calls (68% reduction!)
```

## Benefits

1. **Performance:** ~68% faster by avoiding API calls for cached data
2. **API Quota:** Saves ~68% of Polygon API calls
3. **Cost:** Reduces API costs proportionally
4. **Reliability:** Cached data available even during API issues
5. **Scope:** Only fetches fundamentals for tradable assets (active universe)
6. **Transparency:** User sees exactly where data came from

## Configuration

Uses existing config from `configs/database_ttl.yaml`:
```yaml
# Bootstrap operation staleness - in hours
fundamentals_ttl_hours: 168         # 1 week - for staleness warnings

# Data validation and refresh intervals
max_fundamentals_age_days: 30       # Cache/database freshness threshold
```

## Implementation Phases

### Phase 1: Core Implementation
- [ ] Create `FundamentalsCacheHelper` utility
- [ ] Add `get_active_universe_assets()` to UniverseRepository
- [ ] Update `bootstrap_fundamentals()` with 3-tier checking
- [ ] Add cache statistics to BootstrapResult

### Phase 2: CLI/Display
- [ ] Update CLI to show cache statistics
- [ ] Add `--ignore-cache` flag to force API refresh
- [ ] Improve progress reporting with data sources

### Phase 3: Testing & Validation
- [ ] Test with empty database
- [ ] Test with stale cache (> 30 days)
- [ ] Test with fresh cache
- [ ] Verify universe scoping works correctly

## Open Questions

1. **Cache invalidation:** Should we provide a command to clear stale cache entries?
2. **Universe changes:** What happens if universe membership changes? (Answer: Next bootstrap will fetch missing symbols)
3. **Partial failures:** Should we continue if some cache files are corrupted? (Answer: Yes, fall back to API)

## References

- Current implementation: `src/services/data_service_v2.py:1069`
- Existing cache: `data/cache/fundamentals/` (7,564 files)
- Config: `configs/database_ttl.yaml:26`
- Universe operations: `src/repositories/universe_repository.py:88`
