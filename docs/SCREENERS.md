# TradeScout Screener System

**Last Updated:** 2025-09-23
**Status:** Implemented and Operational

## Overview

TradeScout uses a YAML-based dynamic screener system for real-time market analysis across different trading sessions. Screeners automatically validate market sessions and display contextual warnings.

## Available Screeners

### Regular Session Screeners
- **gainers** - Top gaining stocks (day close vs day open), regular session only
- **losers** - Top losing stocks (day close vs day open), regular session only
- **gaps** - Significant gap ups/downs from previous close
- **volume** - Unusual volume activity during regular session
- **momentum** - Strong momentum indicators during regular session

### Extended Hours Screeners
- **gainerspremarket** - Premarket gap-ups from previous day's close (4-9:30 AM)
- **loserspremarket** - Premarket gap-downs from previous day's close (4-9:30 AM)
- **gainersafterhours** - Afterhours gainers vs 4PM close (4-8 PM + closed)
- **losersafterhours** - Afterhours losers vs 4PM close (4-8 PM + closed)

### Closed Session Screeners
- **gainersclosed** - Closed session gainers analysis
- **losersclosed** - Closed session losers analysis

### Gap Analysis Screeners
- **gapupcandidates** - Gap up candidates for next session
- **gapdowncandidates** - Gap down candidates for next session

## Usage

### Basic Commands
```bash
# List all available screeners
./tradescout screener --list

# Run a specific screener
./tradescout screener gainersafterhours

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
name: gainersafterhours
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
  - field: "day_close"
    operator: "IS NOT NULL"
    value: null
  - field: "((min_close - day_close) / day_close * 100)"
    operator: ">="
    value: 2.0

# Sorting
sort:
  - field: "((min_close - day_close) / day_close * 100)"
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

### Field Mappings
YAML fields map to SQL expressions:

| YAML Field | SQL Expression | Description |
|------------|----------------|-------------|
| `change_percent` | `((ap.min_close - ap.prevday_close) / ap.prevday_close * 100)` | Regular gap % |
| `((min_close - day_close) / day_close * 100)` | `((ap.min_close - ap.day_close) / ap.day_close * 100)` | After-hours % |
| `min_close` | `ap.min_close` | Current/last price |
| `day_close` | `ap.day_close` | 4PM close price |
| `prevday_close` | `ap.prevday_close` | Previous day close |

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

## Market Context Integration (Planning)

### What is Market Context?

Market context provides comprehensive understanding of the current market state, combining:
1. **Trading Day Status** - Is today a regular trading day, holiday, or weekend?
2. **Market Session** - Which of 5 sessions: CLOSED_PRE, PREMARKET, REGULAR, AFTERHOURS, or CLOSED_POST?
3. **Reference Prices** - What's the appropriate reference price for calculations based on context?
4. **Data Availability** - Which fields are populated vs NULL based on session timing?

The `MarketContext` model (in `src/models/market_context.py`) provides:
- Current session state (e.g., PREMARKET, REGULAR)
- Previous trading day information
- Appropriate reference prices for gap calculations
- Data freshness requirements

### Current Limitations

Our current screeners are session-aware but not context-intelligent:
- They use fixed field names regardless of session (e.g., always `day_close`)
- Same thresholds apply across all sessions (e.g., 2% gap)
- No dynamic field selection based on data availability
- Cannot handle complex scenarios like holidays or early closes

### Planned Market Context Enhancements

#### 1. Dynamic Field Selection
Instead of hardcoding field names, screeners will select appropriate fields based on context:

```yaml
# Current (static) approach:
filters:
  - field: "day_close"  # Always uses day_close
    operator: "IS NOT NULL"

# Future (context-aware) approach:
field_mapping:
  reference_price:
    premarket: "prevDay.c"     # Previous close for gaps
    regular: "day.o"            # Today's open for intraday
    afterhours: "day.c"         # Today's close for AH moves
    closed: "prevDay.c"         # Last known close
```

#### 2. Adaptive Thresholds
Different sessions require different sensitivity:

```yaml
# Context-aware thresholds
thresholds:
  gap_percent:
    premarket: 2.0      # Higher threshold for pre-market noise
    regular: 1.0        # Lower for intraday moves
    afterhours: 1.5     # Medium for after-hours

  min_volume:
    premarket: 100000   # Lower volume expected
    regular: 500000     # Normal liquidity required
    afterhours: 50000   # Very low volume acceptable
```

#### 3. Intelligent Gap Detection
Gap calculations that understand market structure:

- **Pre-market gaps**: Current price vs yesterday's close (true overnight gap)
- **Opening gaps**: Open vs yesterday's close (market open gap)
- **Intraday gaps**: Current vs today's open (session momentum)
- **After-hours gaps**: Current vs today's 4PM close (news reactions)

#### 4. Data Freshness Intelligence
Requirements vary by session:

```yaml
data_freshness:
  premarket: 60      # 1 hour old OK (low activity)
  regular: 5         # Must be very fresh
  afterhours: 30     # 30 minutes acceptable
  closed: 1440       # 24 hours old OK when closed
```

#### 5. Session-Specific Logic
Different analysis for different times:

```yaml
advanced_rules:
  premarket:
    # Focus on stocks with earnings/news
    require_catalyst: true
    sector_filter: ["Technology"]  # Tech moves more pre-market

  regular:
    # Focus on liquid names
    min_market_cap: 1000000000
    min_average_volume: 1000000

  afterhours:
    # Look for earnings surprises
    include_earnings_today: true
    min_move_percent: 2.0
```

### Implementation Roadmap

#### Phase 1: Market Context Service Enhancement
- [ ] Enhance `MarketContextService` to provide field recommendations
- [ ] Add market calendar integration for holidays/early closes
- [ ] Implement previous trading day detection logic
- [ ] Add data availability predictor (which fields have data when)

#### Phase 2: Screener Engine Updates
- [ ] Update `ScreenerEngine` to accept context objects
- [ ] Implement field mapping resolver
- [ ] Add threshold interpolation based on context
- [ ] Create context-aware SQL generation

#### Phase 3: Configuration Schema Evolution
- [ ] Extend YAML schema to support field mappings
- [ ] Add context-specific threshold definitions
- [ ] Implement session-specific display configurations
- [ ] Support advanced context rules

#### Phase 4: Smart Screeners
- [ ] Create "adaptive gap" screener that changes behavior by session
- [ ] Build "momentum tracker" that uses different signals by time
- [ ] Implement "earnings reactor" for after-hours earnings plays
- [ ] Add "pre-market predictor" using overnight gaps

### Benefits of Market Context Awareness

1. **Accuracy** - Use the right reference prices for the right situation
2. **Relevance** - Show appropriate data for current market state
3. **Intelligence** - Adapt to market conditions automatically
4. **Usability** - Users don't need to remember which screener for which session
5. **Reliability** - Handle edge cases like holidays and early closes

### Example: Context-Aware Gap Screener

See `/configs/screeners/context_aware_gaps.yaml.example` for a full example of how a context-aware screener would be configured.

Key features demonstrated:
- Dynamic field selection based on session
- Adaptive thresholds for different market states
- Session-specific sorting strategies
- Context-aware display columns
- Advanced filtering rules per session

---

*The screener system is fully operational and handles all trading sessions with proper validation and user feedback. Market context integration is planned to make screeners more intelligent and adaptive.*