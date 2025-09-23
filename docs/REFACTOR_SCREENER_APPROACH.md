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

---

## YAML-Based Screener Configuration

**Decision:** Screener configurations will be stored as YAML files for easy maintenance and customization.

### Screener Configuration Directory Structure

```
configs/
└── screeners/
    ├── gainers.yaml
    ├── losers.yaml
    ├── gaps.yaml
    ├── extendedhours.yaml
    ├── volume.yaml
    └── custom/
        └── user_defined_screeners.yaml
```

### YAML Screener Definition Format

```yaml
# configs/screeners/gainers.yaml
name: gainers
description: "Top gaining stocks by percentage"
enabled: true

# Data source configuration
data_source:
  universe: "default_universe"  # Which universe to scan
  require_recent_trading: true  # Only include if provider_updated > 0

# Filter criteria
filters:
  - field: "change_percent"
    operator: ">="
    value: 2.0
  - field: "min_volume"
    operator: ">="
    value: 100000
  - field: "min_price"
    operator: ">="
    value: 1.0

# Sorting configuration
sort:
  - field: "change_percent"
    direction: "desc"

# Display configuration
display:
  limit: 50
  columns:
    - symbol
    - name
    - prevday_close
    - min_close
    - change_percent
    - min_volume
```

### Extended Hours Screener Example

```yaml
# configs/screeners/extendedhours.yaml
name: extendedhours
description: "Most active extended hours movers"
enabled: true

data_source:
  universe: "default_universe"
  require_recent_trading: true

filters:
  - field: "abs(change_percent)"
    operator: ">="
    value: 1.0
  - field: "session_type"
    operator: "in"
    value: ["premarket", "afterhours"]

sort:
  - field: "abs(change_percent)"
    direction: "desc"

display:
  limit: 50
  columns:
    - symbol
    - name
    - session_type
    - prevday_close
    - min_close
    - change_percent
    - min_timestamp
```

### Dynamic Screener Loading

```python
class ScreenerConfig:
    """Load and validate screener configurations from YAML."""

    def __init__(self, config_dir: str = "configs/screeners"):
        self.config_dir = config_dir
        self.screeners = {}
        self._load_all_screeners()

    def get_screener(self, name: str) -> Dict:
        """Get screener configuration by name."""
        if name not in self.screeners:
            # Try to load from file if not cached
            yaml_path = os.path.join(self.config_dir, f"{name}.yaml")
            if os.path.exists(yaml_path):
                self.screeners[name] = self._load_yaml(yaml_path)
            else:
                raise ValueError(f"Screener '{name}' not found")
        return self.screeners[name]

    def list_available_screeners(self) -> List[str]:
        """List all available screener names."""
        return list(self.screeners.keys())
```

### CLI Implementation

```python
# In screener_commands.py
@screener.command()
@click.argument("screener_name")
def run(screener_name: str):
    """Run a screener by name, loading from YAML config."""

    # Load screener config from YAML
    try:
        config = ScreenerConfig()
        screener_def = config.get_screener(screener_name)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("[dim]Use 'tradescout screener --list' to see available screeners[/dim]")
        return

    # Execute screener based on YAML definition
    results = execute_screener(screener_def)
    display_results(results, screener_def['display'])
```

### Benefits of YAML Approach

1. **No Code Changes for New Screeners** - Add new YAML file, instantly available
2. **User Customization** - Users can create custom screeners without coding
3. **Version Control Friendly** - YAML changes are easy to review and track
4. **Hot Reload Capability** - Can reload configs without restarting application
5. **Validation** - Schema validation ensures correct structure
6. **Shareability** - Users can share screener definitions easily
