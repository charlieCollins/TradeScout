# TradeScout Screener System

**Last Updated:** 2025-10-18
**Status:** Implemented and Operational

## Overview

TradeScout uses a **template-based context-aware screener system** that automatically adapts to market conditions. Screeners automatically select appropriate price/volume calculations based on the current trading session (premarket, regular, afterhours, or closed).

## Available Screeners

### Context-Aware Screeners (4 total)

All screeners automatically adapt to the current market session:

1. **gainers** - Top gaining stocks
   - Premarket: Current price vs previous close
   - Regular: Current price vs day open
   - Afterhours: Current price vs 4PM close
   - Closed: Last available price vs appropriate reference

2. **losers** - Top losing stocks
   - Mirror of gainers for downward price movements

3. **momentum** - High momentum stocks
   - Largest absolute price moves regardless of direction
   - Useful for finding volatile stocks in any session

4. **volume** - High volume stocks
   - Unusual trading activity (volume vs 30-day average)
   - Filters for stocks with significant above-average volume

## Usage

### Basic Commands

```bash
# List all available screeners
./tradescout screener --list

# Run a screener (automatically adapts to current session)
./tradescout screener gainers

# Run during different sessions
./tradescout screener losers      # Works anytime
./tradescout screener momentum    # Works anytime
./tradescout screener volume      # Works anytime

# Show current market status
./tradescout market context
```

### Session Adaptation

The screener engine automatically:
1. Detects current market session (premarket/regular/afterhours/closed)
2. Selects appropriate price comparison template
3. Applies session-specific filters
4. Displays contextual warnings about data freshness

**Example: Gainers screener across sessions:**

| Session | Price Comparison | What It Shows |
|---------|-----------------|---------------|
| Premarket | `min_close` vs `prevday_close` | Gap-ups from previous close |
| Regular | `min_close` vs `day_open` | Intraday gainers from open |
| Afterhours | `min_close` vs `day_close` | After-hours gainers from 4PM close |
| Closed | `min_close` vs `prevday_close` | Last session's performance |

### Session Warnings

Screeners display contextual warnings based on market state:

- **Closed session**: "⚠️ Markets are closed - showing data from last trading session"
- **Premarket**: "📈 Premarket session - limited trading volume"
- **After-hours**: "🌙 After-hours session - limited trading volume"
- **Stale data**: "⚠️ Warning: Market data is 45m old - results may be stale"

## Configuration

### YAML Structure

Screeners are defined in `configs/screeners/*.yaml`:

```yaml
# Example: configs/screeners/gainers.yaml
name: gainers
description: "Top gaining stocks"
enabled: true

# Session validation - works in all sessions
valid_sessions:
  - "premarket"
  - "regular"
  - "afterhours"
  - "closed_post"

# Data source
data_source:
  universe: "default_universe"
  require_recent_trading: true

# Template-based filters (resolved by template engine)
filters:
  - field: "change_pct"      # Resolved to session-appropriate calculation
    operator: ">="
    value: 2.0
  - field: "current_price"   # Resolved to session-appropriate price field
    operator: "IS NOT NULL"
    value: null

# Sorting (template variable)
sort:
  - field: "change_pct"
    direction: "desc"

# Display
display:
  limit: 50
  columns:
    - name: "Symbol"
      field: "symbol"
      width: 8
    - name: "Current"
      field: "current_price"
      format: "price"
      width: 10
    - name: "Change %"
      field: "change_pct"
      format: "percent"
      width: 12
```

### Template Variables

The template engine resolves these variables based on market session:

| Variable | Premarket | Regular | Afterhours | Closed |
|----------|-----------|---------|------------|--------|
| `current_price` | `ap.min_close` | `ap.min_close` | `ap.min_close` | `ap.min_close` |
| `reference_price` | `ap.prevday_close` | `ap.day_open` | `ap.day_close` | `ap.prevday_close` |
| `change_pct` | `((min_close - prevday_close) / prevday_close * 100)` | `((min_close - day_open) / day_open * 100)` | `((min_close - day_close) / day_close * 100)` | `((min_close - prevday_close) / prevday_close * 100)` |
| `volume_field` | `ap.min_volume` | `ap.day_volume` | `ap.min_volume` | `ap.day_volume` |

### Table Alias Prefix (`ap.`)

The `ap.` prefix is a SQL table alias for the `asset_prices` table.

**Why it's needed:**
- Screener queries join multiple tables (assets, asset_prices, universe_memberships, fundamentals)
- SQL requires disambiguation when column names exist in multiple tables
- The `ap.` prefix explicitly specifies columns from `asset_prices`

**All asset_prices columns require the `ap.` prefix:**
- Price data: `ap.day_open`, `ap.day_close`, `ap.min_close`, `ap.prevday_close`
- Volume data: `ap.day_volume`, `ap.min_volume`
- Timestamps: `ap.min_timestamp`, `ap.provider_updated_at`

## Architecture

### Components

1. **ScreenerEngine** (`src/screener/screener_engine.py`)
   - SQL generation and execution
   - Interfaces with repositories for data access

2. **TemplateResolver** (`src/screener/template_resolver.py`)
   - Resolves template variables based on market session
   - Generates session-appropriate SQL expressions

3. **ScreenerConfig** (`src/screener/screener_config.py`)
   - Loads and validates YAML configuration files

4. **CLI Commands** (`src/cli/screener_commands.py`)
   - User interface with output adapters

5. **Output Adapters** (`src/output/`)
   - `CLIScreenerOutputAdapter` - Rich terminal formatting
   - `WebScreenerOutputAdapter` - JSON API responses

### Data Flow

```
User Command
    ↓
CLI Command (screener_commands.py)
    ↓
Market Context Service (detect session)
    ↓
Template Resolver (resolve variables)
    ↓
Screener Config (load YAML)
    ↓
Screener Engine (generate SQL)
    ↓
Repositories (query database)
    ↓
Result Model (ScreenerResult)
    ↓
Output Adapter (CLI or Web)
    ↓
Formatted Output
```

### SQL Generation

Example generated SQL for gainers during premarket:

```sql
WITH latest_prices AS (
    SELECT asset_id, prevday_close, min_close, min_volume, min_timestamp,
           ROW_NUMBER() OVER (PARTITION BY asset_id ORDER BY updated_at DESC) as rn
    FROM asset_prices
    WHERE provider_updated_at > 0
)
SELECT
    a.symbol,
    a.name,
    ap.prevday_close as reference_price,
    ap.min_close as current_price,
    ((ap.min_close - ap.prevday_close) / ap.prevday_close * 100) as change_pct,
    ap.min_volume,
    ap.min_timestamp
FROM assets a
JOIN universe_memberships um ON a.id = um.asset_id
JOIN universes u ON um.universe_id = u.id
JOIN latest_prices ap ON a.id = ap.asset_id AND ap.rn = 1
WHERE u.name = 'default_universe'
  AND ap.prevday_close IS NOT NULL
  AND ((ap.min_close - ap.prevday_close) / ap.prevday_close * 100) >= 2.0
ORDER BY ((ap.min_close - ap.prevday_close) / ap.prevday_close * 100) DESC
LIMIT 50
```

The same screener during regular session uses `day_open` instead of `prevday_close` automatically.

## Display Features

### Result Model → Adapter Pattern

Screeners use the **output-agnostic result model pattern**:

1. **ScreenerEngine** builds `ScreenerResult` (dataclass)
2. **CLI Adapter** formats for terminal (Rich tables, colors)
3. **Web Adapter** formats for JSON API

This allows the same screener logic to work for both CLI and web interface.

### Rich Terminal Formatting

- **Color-coded changes**: Green for positive, red for negative
- **Volume formatting**: 1.5M, 250K with proper suffixes
- **Price formatting**: $123.45 with currency symbols
- **Timestamp formatting**: 07:05 PM (Eastern Time)
- **Percentage formatting**: +3.45%, -2.31%

### Column Configuration

All screeners specify column widths for proper alignment:
- Symbol: 8 chars
- Name: 25-30 chars
- Prices: 10 chars
- Changes: 12 chars
- Volume: 10 chars
- Time: 12 chars

## Data Sources

### Price Data Fields

Screeners query the `asset_prices` table with these key fields:

- **prevday_close** - Previous trading session close (reference for gaps)
- **day_open/high/low/close** - Current regular session (9:30 AM-4:00 PM)
- **min_close** - Current/last traded price (any session)
- **min_volume** - Minute-level volume (extended hours)
- **day_volume** - Day volume (regular session)
- **min_timestamp** - Last trade timestamp
- **provider_updated_at** - Data freshness indicator

### Universe Filtering

- **Total assets**: ~15,000 from Polygon API
- **Trading universe**: ~7,500 filtered stocks (XNYS/XNAS exchanges, active, 1-5 char symbols)
- **Recent trading filter**: Only symbols with `provider_updated_at > 0`

## Performance

### Optimization Features

- **Latest prices CTE**: Single scan of asset_prices table using ROW_NUMBER()
- **Database indexes**: Optimized queries on asset_id, universe membership
- **Result limiting**: Default 50 results per screener
- **Repository pattern**: Efficient SQLModel-based queries

### Typical Performance

- **Query time**: 50-200ms for ~7,500 symbol universe
- **Display time**: <100ms for Rich table rendering
- **Memory usage**: <50MB for largest result sets

## Comparison to Previous Architecture

### Old System (Session-Specific Screeners)

❌ **Problems:**
- 9 separate screeners (gainers_premarket, gainers_regular, gainers_afterhours, etc.)
- Duplicate YAML configuration
- Fixed field mappings
- Users had to choose correct screener for session
- Hard to maintain (9 files to update for any change)

### New System (Context-Aware Templates)

✅ **Benefits:**
- 4 screeners work across all sessions
- Single configuration per screener type
- Template-based field resolution
- Automatic session detection
- Easy to maintain (4 files, shared template engine)

## Extending the System

### Creating New Screeners

1. **Create YAML config** in `configs/screeners/your_screener.yaml`:

```yaml
name: your_screener
description: "Description of what it finds"
enabled: true

valid_sessions:
  - "premarket"
  - "regular"
  - "afterhours"
  - "closed_post"

data_source:
  universe: "default_universe"

filters:
  - field: "your_criteria"
    operator: ">="
    value: threshold

sort:
  - field: "your_criteria"
    direction: "desc"

display:
  limit: 50
```

2. **Use template variables** for session adaptation
3. **Test across sessions** to verify behavior
4. **Add to documentation** and commit

### Template Variable Reference

Available template variables for custom screeners:

- `current_price` - Current/last price (session-aware)
- `reference_price` - Comparison price (session-aware)
- `change_pct` - Percentage change calculation (session-aware)
- `volume_field` - Volume field (session-aware)
- Direct field references: `ap.min_close`, `ap.day_open`, `ap.prevday_close`, etc.

---

## Summary

The TradeScout screener system provides:

✅ **Context-aware automation** - Screeners adapt to market sessions
✅ **Template-based flexibility** - Easy to create new screeners
✅ **Consistent user experience** - Same commands work anytime
✅ **Output flexibility** - Works for CLI and web interface
✅ **Performance** - Fast queries with proper indexing
✅ **Maintainability** - Centralized template logic

*The screener system is fully operational and production-ready for all trading sessions.*
