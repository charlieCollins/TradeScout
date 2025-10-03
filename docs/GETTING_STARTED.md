# Getting Started with TradeScout

**Welcome to TradeScout** - A personal market research assistant for real-time stock screening and analysis.

This guide will walk you through installation, configuration, and your first screening operations.

---

## Prerequisites

Before you begin, ensure you have:

- **Python 3.8+** installed
- **Polygon.io Premium API subscription** ($50/month - provides extended hours data)
- **Linux/Ubuntu/WSL2** environment (primary development platform)
- **SQLite** (included with Python)

### Why Polygon.io Premium?

TradeScout uses Polygon.io's Premium tier specifically for:
- Extended hours data (premarket 4-9:30 AM, afterhours 4-8 PM ET)
- Real-time snapshot data (15-minute delayed)
- Bulk market snapshots (all tickers in one API call)
- Market status and holiday calendar data

**Note**: The free tier does NOT provide extended hours data or bulk snapshots required for TradeScout's features.

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/charlieCollins/TradeScout.git
cd TradeScout
```

### 2. Install Dependencies

```bash
# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install required packages
pip install -r requirements.txt
```

**Required packages** (from `requirements.txt`):
- `click` - CLI framework
- `rich` - Beautiful terminal output
- `requests` - HTTP client for API calls
- `python-dotenv` - Environment variable management
- `pyyaml` - YAML configuration parsing

### 3. Configure API Keys

Create a `.env` file in the project root:

```bash
cp .env.example .env
```

Edit `.env` and add your Polygon.io API key:

```bash
# .env file
POLYGON_API_KEY=your_polygon_api_key_here
```

**Get your API key**:
1. Sign up at [https://polygon.io/](https://polygon.io/)
2. Subscribe to the Stocks Starter plan ($50/month)
3. Copy your API key from the dashboard

### 4. Verify Installation

Test that the CLI works:

```bash
./tradescout --help
```

You should see the TradeScout command menu.

---

## Initial Setup

### 1. Initialize Database

Create the SQLite database schema:

```bash
./tradescout database init
```

**What this does**:
- Creates `data/tradescout.db` SQLite database
- Initializes 13 tables (assets, markets, prices, universes, etc.)
- Creates all indexes for query performance
- Inserts schema version record

**Expected output**:
```
✓ Database initialized successfully
✓ Schema version: 001
✓ Tables created: 13
```

### 2. Bootstrap Reference Data

Populate the database with initial market data:

```bash
./tradescout database bootstrap-all
```

**This runs multiple operations in sequence**:

1. **Providers** (1 record) - Polygon.io configuration
2. **Markets** (~10 records) - US stock exchanges (XNYS, XNAS, etc.)
3. **Assets** (~10,000 records) - All active stocks from Polygon
4. **Fundamentals** (~10,000 records) - Company data (market cap, sector, etc.)
5. **Universes** (1 record) - Filtered trading universe

**Note**: This can take 10-30 minutes depending on API rate limits.

**Alternative**: Bootstrap steps individually:

```bash
# Step by step (recommended for first setup)
./tradescout database bootstrap-providers
./tradescout database bootstrap-markets
./tradescout database bootstrap-assets

# Bootstrap fundamentals for subset (faster for testing)
./tradescout database bootstrap-fundamentals --limit 100

# Or bootstrap all fundamentals (takes time)
./tradescout database bootstrap-fundamentals

# Create default universe
./tradescout database bootstrap-universes
```

### 3. Update Market Data

Fetch current market prices:

```bash
./tradescout market update
```

**What this does**:
- Fetches bulk market snapshot from Polygon (all tickers)
- Updates `asset_prices` table with current prices
- Respects 15-minute TTL (won't re-fetch if recently updated)

**Expected output**:
```
Fetching market data for all universe assets...
✓ Updated 7,513 ticker prices
✓ Data age: Fresh (2m ago)
```

---

## Your First Screening

Now that setup is complete, let's run some screeners!

### 1. Check Market Status

Before screening, check current market context:

```bash
./tradescout market context
```

**Example output**:
```
Market Context: XNAS (Nasdaq)
Trading Day: Yes
Session: REGULAR (9:30 AM - 4:00 PM ET)
Market Open: 9:30 AM
Market Close: 4:00 PM
```

### 2. List Available Screeners

See what screeners are available:

```bash
./tradescout screener --list
```

**You'll see**:
- `gainers` - Top gaining stocks (regular session)
- `losers` - Top losing stocks (regular session)
- `gainerspremarket` - Premarket gap-ups
- `gainersafterhours` - Afterhours gainers
- `gaps` - Significant gap ups/downs
- `volume` - Unusual volume activity
- `momentum` - Strong momentum indicators
- And more...

### 3. Run Your First Screener

Find top gaining stocks during regular market hours:

```bash
./tradescout screener gainers
```

**Example output**:
```
Regular Session Gainers (vs day open)

Symbol  Name                Current    Change     Change %   Volume
------  ------------------  ---------  ---------  ---------  -------
NVDA    NVIDIA Corporation  $523.45    +$12.34    +2.41%     45.2M
AAPL    Apple Inc.          $178.92    +$3.45     +1.97%     52.1M
TSLA    Tesla Inc.          $245.67    +$4.23     +1.75%     38.5M
...

📊 Showing 50 results from 7,513 symbols
⚠️ Market data is 5m old - results are current
```

### 4. Extended Hours Screening

During premarket (4-9:30 AM ET):

```bash
./tradescout screener gainerspremarket
```

**Example output**:
```
Premarket Gainers (vs previous close)

Symbol  Name                Current    Prev Close  Gap %      Time
------  ------------------  ---------  ----------  ---------  --------
AAPL    Apple Inc.          $181.50    $175.47     +3.44%     08:45 AM
TSLA    Tesla Inc.          $248.30    $241.44     +2.84%     08:50 AM
...

📈 Premarket session - limited trading volume
⚠️ Market data is 15m old - results may be stale
```

During after-hours (4-8 PM ET):

```bash
./tradescout screener gainersafterhours
```

### 5. Check Individual Stock

Get detailed information for a specific symbol:

```bash
./tradescout asset info AAPL
```

**Example output**:
```
Apple Inc. (AAPL)

Price Information:
  Current Price:    $178.92
  Previous Close:   $175.47
  Day Open:         $176.20
  Day High:         $179.45
  Day Low:          $175.80
  Change:           +$3.45 (+1.97%)

Company Information:
  Sector:           Technology
  Industry:         Consumer Electronics
  Market Cap:       $2.85T
  Shares Out:       15.9B
  Avg Volume (30d): 52.3M

Market:             XNAS (Nasdaq)
Status:             Active
Last Updated:       2025-10-02 14:30:00 ET
```

---

## Common Workflows

### Daily Market Screening Routine

```bash
# 1. Check market status
./tradescout market context

# 2. Update prices (if stale)
./tradescout market update

# 3. Run appropriate screeners for current session
# Premarket (4-9:30 AM)
./tradescout screener gainerspremarket

# Regular hours (9:30 AM-4 PM)
./tradescout screener gainers
./tradescout screener gaps
./tradescout screener volume

# After-hours (4-8 PM)
./tradescout screener gainersafterhours
```

### Gap Trading Analysis

```bash
# 1. Find gap candidates
./tradescout screener gaps

# 2. Analyze specific symbols
./tradescout gap analyze AAPL TSLA NVDA

# 3. Get gap up candidates
./tradescout screener gapupcandidates

# 4. Get gap down candidates
./tradescout screener gapdowncandidates
```

### Universe Management

```bash
# List available universes
./tradescout universe list

# Show current universe info
./tradescout universe current

# Get detailed universe stats
./tradescout universe info default_universe

# Create custom universe (future feature)
./tradescout universe create my_universe

# Switch to different universe
./tradescout universe activate my_universe
```

---

## Understanding Sessions

TradeScout is session-aware and automatically validates screener availability:

### Trading Sessions

| Session | Time (ET) | Description |
|---------|-----------|-------------|
| **Premarket** | 4:00-9:30 AM | Low volume, gap detection |
| **Regular** | 9:30 AM-4:00 PM | High volume, primary trading |
| **Afterhours** | 4:00-8:00 PM | Moderate volume, earnings reactions |
| **Closed** | 8:00 PM-4:00 AM | No trading, historical data only |

### Session Validation

If you try to run a screener during the wrong session:

```bash
# Try running regular-hours screener during premarket
./tradescout screener gainers

# Output:
❌ Error: Screener 'gainers' is only valid during sessions: ['regular']
   Current session: PREMARKET
   Try: ./tradescout screener gainerspremarket
```

### Data Freshness Warnings

TradeScout warns you when data might be stale:

- **Fresh (< 15min)**: ✓ No warning
- **Moderate (15-30min)**: ⚠️ "Market data is 20m old"
- **Stale (> 30min)**: ⚠️ "Market data is stale - consider running market update"
- **Closed Market**: 🌙 "Markets are closed - showing data from last session"

---

## Configuration

### Universe Configuration

Edit `src/config/universe_config.py` to customize filtering criteria:

```python
UNIVERSE_CONFIG = {
    "default_universe": {
        "name": "default_universe",
        "description": "Default trading universe - liquid US stocks",
        "filters": {
            # Exchange filtering
            "exchanges": ["XNYS", "XNAS"],  # NYSE and Nasdaq only

            # Symbol filtering
            "min_symbol_length": 1,
            "max_symbol_length": 5,
            "alphabetic_only": True,  # No numbers in symbol

            # Market cap filtering (in cents)
            "min_market_cap": 50_000_000_00,  # $50M minimum

            # Volume filtering
            "min_avg_volume_30d": 100_000,  # 100k shares/day minimum

            # Asset type filtering
            "asset_types": ["stock"],  # Stocks only, no ETFs/REITs

            # Exclusions
            "exclude_preferred": True,  # No preferred stocks (symbols with -)
            "exclude_warrants": True,   # No warrants (symbols with W)
        }
    }
}
```

### Screener Configuration

Screeners are defined in `configs/screeners/*.yaml`. Example:

```yaml
# configs/screeners/custom_gainers.yaml
name: custom_gainers
description: "Custom gainers with higher threshold"
enabled: true

valid_sessions:
  - "regular"

data_source:
  universe: "default_universe"
  require_recent_trading: true

filters:
  - field: "change_percent"
    operator: ">="
    value: 3.0  # 3% minimum gain (vs default 2%)

  - field: "day_volume"
    operator: ">="
    value: 500000  # 500k volume minimum

sort:
  - field: "change_percent"
    direction: "desc"

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
    # ... more columns
```

---

## Maintenance

### Update Reference Data

Reference data has TTL-based auto-refresh, but you can force update:

```bash
# Update markets (TTL: 1 year)
./tradescout database bootstrap-markets

# Update asset list (TTL: 3 days)
./tradescout database bootstrap-assets

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

### Check Data Freshness

```bash
# Show market data age
./tradescout market info

# Force refresh market data
./tradescout market update
```

---

## Troubleshooting

### Common Issues

#### 1. "POLYGON_API_KEY not found"

**Problem**: API key not configured

**Solution**:
```bash
# Create .env file
cp .env.example .env

# Edit .env and add your key
nano .env
# Add: POLYGON_API_KEY=your_key_here

# Verify
cat .env | grep POLYGON
```

#### 2. "Database not found"

**Problem**: Database not initialized

**Solution**:
```bash
./tradescout database init
./tradescout database bootstrap-all
```

#### 3. "No results from screener"

**Problem**: Market data not fetched

**Solution**:
```bash
# Update market prices
./tradescout market update

# Verify data exists
./tradescout database info
```

#### 4. "Rate limit exceeded"

**Problem**: Too many API calls

**Solution**:
- TradeScout automatically handles rate limits
- Wait 60 seconds and retry
- Check you're using Premium tier (not free tier)

#### 5. "Screener not valid for current session"

**Problem**: Wrong screener for current market session

**Solution**:
```bash
# Check current session
./tradescout market context

# Use appropriate screener:
# Premarket: gainerspremarket, loserspremarket
# Regular: gainers, losers, gaps, volume, momentum
# Afterhours: gainersafterhours, losersafterhours
```

---

## Next Steps

Now that you're set up, explore advanced features:

1. **Architecture Documentation** - Learn how TradeScout is built
   - `docs/ARCHITECTURE_MANAGERS.md` - Database layer patterns
   - `docs/ARCHITECTURE_API_PROVIDERS.md` - API integration patterns
   - `docs/DATABASE.md` - Complete schema reference

2. **API Reference** - Developer documentation
   - `docs/API_REFERENCE_BASE_CLASSES.md` - BaseManager and BaseProvider
   - `docs/API_REFERENCE_DATA_SERVICE.md` - DataService public API
   - `docs/API_REFERENCE_MANAGERS.md` - All database managers
   - `docs/API_REFERENCE_PROVIDERS.md` - All API providers

3. **Feature Guides** - Detailed feature documentation
   - `docs/SCREENERS.md` - Screener system guide
   - `docs/GAP_TRADING_STRATEGY.md` - Gap trading analysis
   - `docs/SENTIMENT.md` - Sentiment detection (future feature)
   - `docs/BOOTSTRAPPING.md` - Bootstrap operations reference

4. **Data Sources** - Provider-specific documentation
   - `docs/DATA_SOURCE_POLYGON.md` - Polygon.io integration
   - `docs/DATA_SOURCE_POLYGON_SNAPSHOT_INFO.md` - Snapshot API details

---

## Getting Help

- **Documentation**: Check `docs/` directory for detailed guides
- **Issues**: Review `CLAUDE_LESSONS_LEARNED.md` for common pitfalls
- **Logs**: Check terminal output for error messages with context

**Happy Screening!**
