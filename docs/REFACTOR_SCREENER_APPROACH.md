# Screener Architecture Refactor Plan

**Purpose:** Replace hardcoded view methods (gainers, losers, etc.) with a unified, reusable screener/filter system
**Date:** 2025-09-16
**Status:** Planning Phase

---

## Core Concept

All our different views (gainers, losers, gainers-extended-hours, gap-candidates, etc.) are fundamentally **screeners** - filtered views of our market universe with specific criteria applied.

Instead of creating separate methods for each view, we should build a **unified screener engine** that can apply any criteria to our database and return filtered results.

---

## Proposed Screener Architecture

### 1. Unified Screener Query Builder

Create a flexible query builder that can handle any combination of filters:

```python
class ScreenerQuery:
    """Build complex screening queries dynamically."""

    def __init__(self, universe="default"):
        self.universe = universe
        self.filters = []
        self.sort_by = []
        self.limit = None

    def filter_by_change_percent(self, min_pct=None, max_pct=None):
        """Filter by price change percentage."""
        pass

    def filter_by_volume(self, min_volume=None):
        """Filter by trading volume."""
        pass

    def filter_by_session(self, sessions: List[str]):
        """Filter by trading session (premarket, regular, afterhours)."""
        pass

    def filter_by_gap(self, min_gap_pct=None):
        """Filter by gap percentage."""
        pass

    def order_by(self, field, desc=True):
        """Add sorting criteria."""
        pass

    def to_sql(self) -> str:
        """Generate optimized SQL query."""
        pass
```

### 2. Predefined Screener Templates

Common screeners as configuration:

```python
SCREENER_TEMPLATES = {
    "gainers": {
        "filters": {
            "change_percent_min": 2.0,
            "session": ["regular"]
        },
        "sort": "change_percent_desc",
        "limit": 50
    },

    "losers": {
        "filters": {
            "change_percent_max": -2.0,
            "session": ["regular"]
        },
        "sort": "change_percent_asc",
        "limit": 50
    },

    "gap_up": {
        "filters": {
            "gap_percent_min": 2.0,
            "session": ["premarket"]
        },
        "sort": "gap_percent_desc",
        "limit": 50
    },

    "high_volume": {
        "filters": {
            "volume_vs_avg_min": 2.0,  # 2x average volume
        },
        "sort": "volume_vs_avg_desc",
        "limit": 50
    },

    "extended_hours_movers": {
        "filters": {
            "change_percent_abs_min": 1.0,
            "session": ["premarket", "afterhours"]
        },
        "sort": "change_percent_abs_desc",
        "limit": 50
    }
}
```

### 3. CLI Integration

Simple CLI commands that use screener templates:

```bash
# Use predefined screeners
tradescout screen gainers
tradescout screen losers
tradescout screen gap-up

# Custom screeners with filters
tradescout screen --change-min 5.0 --volume-min 1000000
tradescout screen --session premarket --change-min 2.0
tradescout screen --sector "Technology" --change-min 3.0

# Combine filters
tradescout screen --template gainers --sector "Technology"
```
