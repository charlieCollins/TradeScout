# Getting Started with TradeScout

**TradeScout** - A personal market research assistant for real-time stock screening and gap trading analysis.

---

## Prerequisites

- **Python 3.8+** installed
- **Polygon.io Premium subscription** ($50/month - provides extended hours data)
- **Linux/Ubuntu/WSL2** environment (primary development platform)

### Why Polygon.io Premium?

TradeScout requires Polygon.io Premium for:
- Extended hours data (premarket 4-9:30 AM, after-hours 4-8 PM ET)
- Real-time snapshot data (all tickers in one API call)
- Market status and holiday calendar
- Minute-level aggregates for volume analysis

**Note**: The free tier does NOT provide these features.

---

## Installation

### 1. Clone and Install

```bash
git clone https://github.com/charlieCollins/TradeScout.git
cd TradeScout

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure API Key

Create a `.env` file with your Polygon.io API key:

```bash
cp .env.example .env
nano .env  # Add: POLYGON_API_KEY=your_polygon_api_key_here
```

Get your API key:
1. Sign up at [https://polygon.io/](https://polygon.io/)
2. Subscribe to Stocks Starter plan ($50/month)
3. Copy API key from dashboard

### 3. Verify Installation

```bash
./tradescout --help
```

You should see the TradeScout command menu.

---

## Initial Setup

### 1. Initialize Database

```bash
./tradescout database init
```

Creates `data/tradescout.db` with all required tables.

### 2. Bootstrap Reference Data

```bash
./tradescout database bootstrap-all
```

**This populates** (takes 10-30 minutes):
1. Providers (1 record) - Polygon.io configuration
2. Markets (~10 records) - US stock exchanges
3. Assets (~10,000 records) - All active stocks
4. Fundamentals (~10,000 records) - Market cap, sector, etc.
5. Universes (1 record) - Default trading universe

**Alternative** - Bootstrap individually:

```bash
./tradescout database bootstrap-providers
./tradescout database bootstrap-markets
./tradescout database bootstrap-tickers
./tradescout database bootstrap-fundamentals
./tradescout database bootstrap-sentiment-types
./tradescout database bootstrap-universes
```

### 3. Update Market Prices

```bash
./tradescout market update
```

Fetches current prices for all assets. Has 15-minute TTL (won't re-fetch if recent).

---

## Your First Screening

### 1. Check Market Status

```bash
./tradescout market context
```

Shows current session (premarket/regular/after-hours/closed) and market status.

### 2. Run a Screener

```bash
# List available screeners
./tradescout screener --list

# Run gainers screener (context-aware - adapts to current session)
./tradescout screener gainers

# Run losers screener
./tradescout screener losers
```

**Example output:**
```
Top Gainers (Premarket vs Previous Close)

Symbol  Name                Current    Prev Close  Change %   Volume
------  ------------------  ---------  ----------  ---------  -------
NVDA    NVIDIA Corporation  $523.45    $511.11     +2.41%     1.2M
AAPL    Apple Inc.          $178.92    $175.47     +1.97%     850K
...

📊 Showing 50 results from 7,513 symbols
```

Screeners are **context-aware**: They automatically adjust calculations based on current session (premarket/regular/after-hours).

### 3. Check Individual Stock

```bash
./tradescout asset info AAPL
```

Shows price, fundamentals, market cap, sector, etc.

---

## Gap Trading Analysis

TradeScout includes a sophisticated gap trading analysis system.

### Analyze Gap Candidates

**During premarket (4-9:30 AM) or after-hours (4-8 PM):**

```bash
./tradescout gap analyze
```

**What it does:**
1. Identifies stocks with gaps ≥2% (configurable)
2. Validates volume ratio (≥1.5x normal)
3. Checks market cap (≥$1B default)
4. Filters exhaustion gaps (≥5% gap + ≥3x volume)
5. Fetches news and calculates catalyst scores
6. Calculates quality scores (0-100)
7. Generates comprehensive report

**Example output:**
```
Gap Trading Analysis - Premarket
Trading Date: 2025-10-10

✅ PASSED CANDIDATES (3)
1. NVDA - Quality: 72.5 (Good)
   Gap: +3.2% | Volume: 2.1x | Catalyst: Earnings beat (Score: 85)

2. AAPL - Quality: 68.3 (Good)
   Gap: +2.8% | Volume: 1.8x | Catalyst: Product launch (Score: 70)

❌ REJECTED CANDIDATES (28)
- 22 failed volume test (<1.5x)
- 6 failed exhaustion gap filter

Report saved: tradescout_gap_20251010_083045.txt
```

**Configuration** (optional):

```bash
./tradescout gap analyze --min-gap 3.0 --min-volume-ratio 2.0 --min-market-cap 5000000000
```

See `docs/GAP_TRADING_STRATEGY.md` for detailed strategy documentation.

---

## Common Workflows

### Daily Screening Routine

```bash
# 1. Check market status
./tradescout market context

# 2. Update prices if stale
./tradescout market update

# 3. Run screener for current conditions
./tradescout screener gainers
./tradescout screener losers
```

### Premarket/After-Hours Gap Analysis

```bash
# During premarket (4-9:30 AM) or after-hours (4-8 PM)
./tradescout gap analyze

# Review generated report
cat tradescout_gap_*.txt
```

### Universe Management

```bash
# List universes
./tradescout universe list

# Show current universe info
./tradescout universe current

# Switch universe
./tradescout universe activate large_cap
```

---

## Configuration

### Screener Configuration

Screeners are defined in `configs/screeners/*.yaml`:

```yaml
# Example: configs/screeners/gainers.yaml
name: gainers
description: "Top gaining stocks"
enabled: true

# Context-aware: Works in any session
valid_sessions:
  - "premarket"
  - "regular"
  - "afterhours"
  - "closed_post"

# Dynamic filters based on session
filters:
  - field: "change_pct"  # Calculated by template engine
    operator: ">="
    value: 2.0

sort:
  - field: "change_pct"
    direction: "desc"

display:
  limit: 50
```

### Universe Configuration

Universes are defined in `configs/universes/*.yaml`:

```yaml
# Example: configs/universes/default_universe.yaml
name: default_universe
description: "Default trading universe - liquid US stocks"

filters:
  exchanges:
    - XNYS
    - XNAS

  min_market_cap: 5000000000  # $50M in cents
  min_avg_volume_30d: 100000

  symbol:
    min_length: 1
    max_length: 5
    alphabetic_only: true

  exclude:
    - preferred_stocks
    - warrants
```

### Gap Trading Configuration

Edit `configs/gap_trading.yaml` to customize:

```yaml
gap_detection:
  min_gap_percentage: 2.0
  min_volume_ratio: 1.5
  min_market_cap: 1000000000

exhaustion_filter:
  min_gap_percentage: 5.0
  min_volume_ratio: 3.0
  # trend_age_days: 20  # Future: requires historical data

quality_scoring:
  weights:
    gap_size: 0.40
    volume: 0.25
    catalyst: 0.20
    sector_alignment: 0.10
    market_alignment: 0.05
```

---

## Understanding Sessions

TradeScout is session-aware and automatically adjusts calculations:

| Session | Time (ET) | Price Comparison |
|---------|-----------|------------------|
| **Premarket** | 4:00-9:30 AM | Current vs Yesterday Close |
| **Regular** | 9:30 AM-4:00 PM | Current vs Today Open |
| **After-hours** | 4:00-8:00 PM | Current vs Today 4PM Close |
| **Closed** | 8:00 PM-4:00 AM | Last available vs Previous |

### Data Freshness

TradeScout warns when data is stale:
- **Fresh (< 15min)**: ✓ No warning
- **Moderate (15-30min)**: ⚠️ "Data is 20m old"
- **Stale (> 30min)**: ⚠️ "Data stale - run market update"

---

## Maintenance

### Update Reference Data

```bash
# Update asset list (TTL: 3 days)
./tradescout database bootstrap-tickers

# Update fundamentals (TTL: 1 week)
./tradescout database bootstrap-fundamentals

# Update universe membership (TTL: 24 hours)
./tradescout database bootstrap-universes
```

### Database Management

```bash
# Show database statistics
./tradescout database info

# Reset database (WARNING: Deletes all data)
./tradescout database reset

# Re-initialize after reset
./tradescout database init
./tradescout database bootstrap-all
```

---

## Troubleshooting

### "POLYGON_API_KEY not found"

```bash
cp .env.example .env
nano .env  # Add: POLYGON_API_KEY=your_key_here
```

### "Database not found"

```bash
./tradescout database init
./tradescout database bootstrap-all
```

### "No results from screener"

```bash
./tradescout market update  # Update prices
./tradescout database info  # Verify data exists
```

### "Gap analyze only works during premarket/after-hours"

The `gap analyze` command only runs during extended hours sessions when gaps can be detected. During regular hours or closed sessions, there are no gaps to analyze.

---

## Next Steps

### Documentation

**Core Features:**
- `docs/ARCHITECTURE.md` - System architecture and design
- `docs/DATABASE.md` - Complete database schema
- `docs/SCREENERS.md` - Screener system guide
- `docs/BOOTSTRAPPING.md` - Bootstrap operations

**Gap Trading:**
- `docs/GAP_TRADING_STRATEGY.md` - Gap trading strategy overview
- `docs/GAP_TRADING_STRATEGY_RULES.md` - Detailed trading rules
- `docs/GAP_IMPLEMENTATION_COVERAGE.md` - Implementation status

**Data Sources:**
- `docs/POLYGON.md` - Polygon.io API overview
- `docs/POLYGON_IMPLEMENTATION.md` - Implementation details
- `docs/POLYGON_VOLUME_INFO.md` - Volume field reference

**Other Features:**
- `docs/SENTIMENT.md` - News sentiment analysis
- `docs/SECTOR_CLASSIFICATION.md` - Sector mapping

### Advanced Features

**Federal Reserve Data** (if you have access):
```bash
./tradescout fed update  # Update Fed economic data
```

**Validation Tools:**
```bash
./tradescout validate --help  # Data validation commands
```

---

## Getting Help

- **Documentation**: Check `docs/` directory
- **Lessons Learned**: See `CLAUDE_LESSONS_LEARNED.md` for common pitfalls
- **Logs**: Terminal output includes detailed error messages

**Happy Screening!**
