# TradeScout Screener System

**Last Updated:** 2025-10-05
**Status:** Implemented and Operational

## Overview

TradeScout uses a YAML-based dynamic screener system for real-time market analysis across different trading sessions. Screeners automatically validate market sessions and display contextual warnings.

## Available Screeners

### Regular Session Screeners
- **gainers_regular** - Top gaining stocks (current price vs day open)
- **losers_regular** - Top losing stocks (current price vs day open)

### Extended Hours Screeners
- **gainers_premarket** - Premarket gap-ups from previous day's close (4-9:30 AM)
- **losers_premarket** - Premarket gap-downs from previous day's close (4-9:30 AM)
- **gainers_after_hours** - Afterhours gainers vs 4PM close (4-8 PM + closed)
- **losers_after_hours** - Afterhours losers vs 4PM close (4-8 PM + closed)

### Closed Session Screeners
- **gainers_closed_scope_regular** - Regular session gainers (day open to close)
- **losers_closed_scope_regular** - Regular session losers (day open to close)

## Usage

### Basic Commands
```bash
# List all available screeners
./tradescout screener --list

# Run a specific screener
./tradescout screener gainers_after_hours

# Show market status
./tradescout market info
```

### Session Validation
Screeners only run during their designated sessions:
- **premarket** (4:00-9:30 AM ET)
- **regular** (9:30 AM-4:00 PM ET)
- **afterhours** (4:00-8:00 PM ET)
- **closed** (8:00 PM-4:00 AM ET)

Attempting to run a screener during invalid session shows helpful error message.

### Session Warnings
All screeners display contextual warnings:
- **Closed session**: "⚠️ Markets are closed - showing data from last trading session"
- **Premarket**: "📈 Premarket session - limited trading volume"
- **After-hours**: "🌙 After-hours session - limited trading volume"
- **Stale data**: "⚠️ Warning: Market data is 45m ago old - results may be stale"

## Configuration

### YAML Structure
Screeners are defined in `/configs/screeners/*.yaml` with this structure:

```yaml
name: gainers_after_hours
description: "Afterhours gainers (vs regular session close)"
enabled: true

# Session validation
valid_sessions:
  - "afterhours"
  - "closed"

# Data source
data_source:
  universe: "default_universe"
  require_recent_trading: true

# Filters (converted to SQL WHERE clauses)
filters:
  - field: "ap.day_close"
    operator: "IS NOT NULL"
    value: null
  - field: "((ap.min_close - ap.day_close) / ap.day_close * 100)"
    operator: ">="
    value: 2.0

# Sorting
sort:
  - field: "((ap.min_close - ap.day_close) / ap.day_close * 100)"
    direction: "desc"

# Display
display:
  limit: 50
  columns:
    - name: "Symbol"
      field: "symbol"
      width: 8
    - name: "Current"
      field: "min_close"
      format: "price"
      width: 10
```

### Table Alias Prefix (`ap.`)

The `ap.` prefix is a SQL table alias for the `asset_prices` table.

**Why it's needed:**
- Screener queries join multiple tables (assets, asset_prices, universe_memberships)
- SQL requires disambiguation when column names could exist in multiple tables
- The `ap.` prefix explicitly specifies the column comes from `asset_prices`

**Usage in YAML:**
- `ap.day_open` → `asset_prices.day_open`
- `ap.min_close` → `asset_prices.min_close`
- `symbol` (no prefix) → comes from `assets` table
- `change_percent` (no prefix) → computed field, not a table column

**All asset_prices columns require the `ap.` prefix:**
- Price data: `ap.day_open`, `ap.day_close`, `ap.min_close`, `ap.prevday_close`
- Volume data: `ap.day_volume`, `ap.min_volume`
- Timestamps: `ap.min_timestamp`, `ap.provider_updated_at`

### Field Mappings
YAML fields map to SQL expressions:

| YAML Field | SQL Expression | Description |
|------------|----------------|-------------|
| `change_percent` | `((ap.min_close - ap.prevday_close) / ap.prevday_close * 100)` | Regular gap % |
| `((ap.min_close - ap.day_close) / ap.day_close * 100)` | `((ap.min_close - ap.day_close) / ap.day_close * 100)` | After-hours % |
| `ap.min_close` | `ap.min_close` | Current/last price |
| `ap.day_close` | `ap.day_close` | 4PM close price |
| `ap.prevday_close` | `ap.prevday_close` | Previous day close |

## Data Sources

### Price Data Fields
Screeners query the `asset_prices` table with these key fields:
- **prevday_close** - Previous trading session close (reference price)
- **day_open/high/low/close** - Current regular session (9:30-4:00 PM)
- **min_close** - Current/last traded price (any session)
- **min_timestamp** - Last trade timestamp
- **provider_updated_at** - Data freshness indicator

### Universe Filtering
- **Total assets**: 11,745 from Polygon API
- **Trading universe**: 7,513 filtered stocks (XNYS/XNAS, active, 1-5 char symbols)
- **Recent trading filter**: Only symbols with `provider_updated_at > 0`

## Architecture

### Components
1. **ScreenerEngine** (`src/screener/screener_engine.py`) - SQL generation and execution
2. **ScreenerDisplay** (`src/screener/screener_display.py`) - Rich table formatting
3. **ScreenerConfig** (`src/screener/screener_config.py`) - YAML loading
4. **CLI Commands** (`src/cli/screener_commands.py`) - User interface

### Data Flow
1. Load YAML configuration
2. Validate current market session
3. Generate SQL query with filters/sorting
4. Execute against asset_prices table
5. Format results with Rich tables
6. Display with session warnings

### SQL Generation
Example generated SQL for afterhours screener:
```sql
WITH latest_prices AS (
    SELECT asset_id, day_close, min_close, min_timestamp,
           ROW_NUMBER() OVER (PARTITION BY asset_id ORDER BY updated_at DESC) as rn
    FROM asset_prices
)
SELECT a.symbol, a.name, ap.day_close, ap.min_close,
       ((ap.min_close - ap.day_close) / ap.day_close * 100) as ah_change_percent
FROM assets a
JOIN universe_memberships um ON a.id = um.asset_id
JOIN latest_prices ap ON a.id = ap.asset_id AND ap.rn = 1
WHERE ap.day_close IS NOT NULL
AND ((ap.min_close - ap.day_close) / ap.day_close * 100) >= 2.0
ORDER BY ((ap.min_close - ap.day_close) / ap.day_close * 100) DESC
LIMIT 50
```

## Display Features

### Rich Formatting
- **Color-coded changes**: Green for gains, red for losses
- **Volume formatting**: 1.5M, 250K, etc.
- **Price formatting**: $123.45 with proper alignment
- **Timestamp formatting**: 07:05 PM (Eastern Time)

### Column Widths
All screeners use explicit column widths for proper table rendering:
- Symbol: 8 chars
- Name: 25 chars
- Prices: 10 chars
- Changes: 12 chars
- Volume: 10 chars
- Time: 12 chars

### Warning System
Multiple warnings display on separate lines:
```
⚠️  Warning: Market data is 45m ago old - results may be stale
⚠️  Markets are closed - showing data from last trading session
```

## Performance

### Optimization Features
- **Latest prices CTE**: Single scan of asset_prices table
- **Database indexes**: Optimized queries on asset_id, universe membership
- **Result limiting**: Default 50 results per screener
- **Data caching**: 10-minute TTL on price data

### Typical Performance
- **Query time**: 50-200ms for 7,513 universe
- **Display time**: <100ms for Rich table rendering
- **Memory usage**: <50MB for largest result sets

## Future Enhancements

### Context-Aware Screeners (Planned)

Current screeners use fixed field names and thresholds. Future enhancement will add dynamic field selection and adaptive thresholds based on market context (session, trading day status, data availability).

**Benefits:**
- Automatic field selection based on session
- Adaptive thresholds for different market states
- Intelligent handling of holidays and early closes

See `docs/SCREENERS_CONTEXT_AWARE_PLANNING.md` for detailed implementation roadmap.

---

*The screener system is fully operational and handles all trading sessions with proper validation and user feedback.*