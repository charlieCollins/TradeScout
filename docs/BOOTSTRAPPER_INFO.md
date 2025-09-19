# TradeScout Bootstrapper Guide

## Overview

TradeScout uses a two-stage bootstrapping process to populate the asset database and create the default trading universe. This guide explains the architecture, usage, and relationship between the different bootstrapping components.

## Architecture Overview

```
┌─────────────────┐    ┌─────────────────────┐    ┌─────────────────┐
│  Polygon API    │    │   Assets Table      │    │ Default Universe│
│   ~11,700       │───▶│    ~11,700         │───▶│    ~5,000       │
│   All Tickers   │    │   All Assets       │    │ Filtered Assets │
└─────────────────┘    └─────────────────────┘    └─────────────────┘
         │                        │                        │
         │                        │                        │
         ▼                        ▼                        ▼
┌─────────────────┐    ┌─────────────────────┐    ┌─────────────────┐
│ Ticker          │    │ Database Storage    │    │ Universe        │
│ Bootstrapper    │    │ (SQLite)           │    │ Management      │
└─────────────────┘    └─────────────────────┘    └─────────────────┘
```

## Two-Stage Process

### Stage 1: Ticker Bootstrapping
**Purpose**: Fetch and store ALL available ticker data from Polygon.io

**Component**: `polygon_ticker_bootstrapper.py`
- Only applies basic API-level filtering: `market=stocks`, `active=true`
- No filtering for exchange, ticker type, symbol format, etc.
- Stores ALL ~11,700 tickers that match basic criteria

**Result**: Complete ticker coverage in `assets` table for future expansion

### Stage 2: Universe Bootstrapping  
**Purpose**: Create filtered default universe from existing asset data

**Component**: `default_universe_bootstrapper.py`
- Defines strict filtering criteria per SUPPORTED_UNIVERSE.md:
  - Ticker type: CS (Common Stock) only
  - Exchange: XNYS, XNAS, BATS only
  - Symbol format: 1-5 alphabetic characters
  - Market: stocks only
  - Status: active only

**Result**: Quality-filtered ~5,000 assets in `default_universe`

## Usage Guide

### Prerequisites

1. **Polygon API Key**: Ensure your Polygon API key is configured
2. **Database**: SQLite database will be created automatically
3. **Python Environment**: Virtual environment with dependencies installed

### Step 1: Bootstrap All Tickers

```bash
# Basic ticker bootstrap (recommended)
python -m tradescout.scripts.bootstrap_tickers

# Check current universe statistics (preview mode)
python -m tradescout.scripts.bootstrap_tickers --stats-only
```

**Expected Output**:
```
Starting Polygon universe bootstrap...
Market types: stocks only

✅ Retrieved 11698 total tickers from Polygon (12 pages)
Processing batch 1: 1000 tickers
Processing batch 2: 1000 tickers
...
Processing batch 12: 698 tickers

Bootstrap Results:
  Total tickers fetched: 11698
  Assets inserted: 11450
  Assets updated: 248
  Assets skipped: 0
  Errors: 0

✅ Ticker bootstrap completed in 142.3 seconds
```

### Step 2: Bootstrap Default Universe

```bash
# Check current universe status
python -m tradescout.scripts.bootstrap_default_universe --stats-only

# Preview what would be added (no changes)
python -m tradescout.scripts.bootstrap_default_universe --dry-run

# Actually populate the default universe
python -m tradescout.scripts.bootstrap_default_universe
```

**Expected Output**:
```
Starting default universe bootstrap...

Bootstrap Results:
  Total assets in database: 11700
  Assets meeting criteria: 5000
  Already in universe: 0
  New assets to add: 5000
  Assets successfully added: 5000
  Errors: 0

✅ Default universe bootstrap completed
```

## Filtering Criteria Details

### Stage 1: Ticker Bootstrapper Filtering
- ✅ **Market**: `stocks` only (excludes crypto, forex, etc.)
- ✅ **Status**: `active=true` only (excludes delisted/inactive)
- ❌ **No exchange filtering** (includes all exchanges)
- ❌ **No asset type filtering** (includes ETFs, REITs, etc.)
- ❌ **No symbol format filtering** (includes complex symbols)

### Stage 2: Universe Bootstrapper Filtering
- ✅ **Asset Type**: Common Stock (`CS`) only
- ✅ **Exchange**: Major US exchanges only (`XNYS`, `XNAS`, `BATS`)
- ✅ **Symbol Format**: 1-5 alphabetic characters only
- ✅ **Market**: Stocks only (redundant with Stage 1)
- ✅ **Status**: Active only (redundant with Stage 1)

### Excluded Categories (~6,700 assets filtered out)

**Investment Vehicles** (~2,000 assets):
- ETFs, ETNs, REITs, Mutual funds, Closed-end funds

**Non-US Securities** (~1,500 assets):
- International stocks, Canadian exchanges, Foreign ADRs

**Non-Common Stock Types** (~1,000 assets):
- Preferred stocks, Rights, Warrants, Units, Convertible securities

**Minor/Alternative Exchanges** (~800 assets):
- OTC Markets, Regional exchanges, Dark pools

**Invalid/Unusable Symbols** (~342 assets):
- Symbols with numbers/special characters, Test symbols, Duplicates

## Data Storage Structure

### Assets Table
```sql
-- Stores ALL ticker data from Polygon
CREATE TABLE assets (
    id INTEGER PRIMARY KEY,
    symbol VARCHAR(20) UNIQUE,
    name VARCHAR(255),
    asset_type VARCHAR(30),    -- common_stock, etf, preferred_stock, etc.
    market_id VARCHAR(20),     -- NYSE, NASDAQ, AMEX, etc.
    currency VARCHAR(10),
    is_active BOOLEAN,
    -- ... additional fields
);
```

### Universes Table
```sql
-- Defines universe metadata
CREATE TABLE universes (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100) UNIQUE,
    description TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### Universe Memberships Table
```sql
-- Links assets to universes
CREATE TABLE universe_memberships (
    id INTEGER PRIMARY KEY,
    asset_id INTEGER,
    universe_id INTEGER,
    added_date DATE,
    removed_date DATE,
    reason TEXT,
    is_active BOOLEAN,
    FOREIGN KEY (asset_id) REFERENCES assets(id),
    FOREIGN KEY (universe_id) REFERENCES universes(id)
);
```

## Maintenance and Updates

### Regular Updates
**Frequency**: Weekly or monthly

**Process**:
1. Run ticker bootstrapper to update ticker data
2. Run universe bootstrapper to add any new qualifying assets

```bash
# Update all tickers
python -m tradescout.scripts.bootstrap_tickers

# Update default universe with any new qualifying assets
python -m tradescout.scripts.bootstrap_default_universe
```

### Monitoring
```bash
# Check ticker coverage
python -m tradescout.scripts.bootstrap_tickers --stats-only

# Check universe statistics  
python -m tradescout.scripts.bootstrap_default_universe --stats-only
```

## Configuration

### Ticker Bootstrapper Configuration
Located in: `src/tradescout/config/data_source_config.py`
- Polygon API settings
- Rate limiting configuration
- Batch processing settings

### Universe Bootstrapper Configuration
Located in: `src/tradescout/config/universe_config.py`
- Filtering criteria definitions
- Exchange mappings
- Asset type mappings

## Troubleshooting

### Common Issues

**1. API Rate Limiting**
```
ERROR: Polygon API error: 429 - Rate limit exceeded
```
**Solution**: The bootstrapper automatically handles rate limiting with backoff

**2. No Assets Added to Universe**
```
Assets meeting criteria: 0
```
**Solution**: Check that ticker bootstrapping completed successfully first

**3. Database Connection Errors**
```
ERROR: no such table: assets
```
**Solution**: Ensure migrations have run by starting the application once

### Debug Mode
```bash
# Enable detailed logging
export PYTHONPATH=/path/to/TradeScout
python -m tradescout.scripts.bootstrap_tickers --verbose

python -m tradescout.scripts.bootstrap_default_universe --dry-run --verbose
```

## Performance Characteristics

### Ticker Bootstrapper
- **API Calls**: ~12-15 requests (paginated)
- **Processing Time**: ~2-3 minutes
- **Rate Limiting**: 5 calls per minute (built-in backoff)
- **Memory Usage**: Streaming processing (low memory)

### Universe Bootstrapper
- **Database Queries**: 2-3 queries total
- **Processing Time**: ~5-10 seconds
- **Memory Usage**: Loads all assets in memory briefly
- **Concurrent Safe**: Uses database transactions

## Strategic Benefits

### Complete Coverage
- **Market Scanning**: Access to nearly all tradeable US stocks
- **Future Expansion**: Easy to add new universes with different criteria
- **Sector Analysis**: Complete coverage across all US sectors

### Quality Assurance
- **Two-Stage Filtering**: Ensures data quality at multiple levels
- **Deduplication**: Prevents duplicate assets in universes
- **Validation**: Consistent symbol formatting and exchange verification

### Operational Efficiency
- **Incremental Updates**: Only adds new assets, preserves existing
- **Dry-Run Mode**: Safe testing before making changes
- **Audit Trail**: Tracks when and why assets were added

---

**Last Updated**: January 2025
**Current Coverage**: 11,700 total tickers → ~5,000 default universe assets
**Data Source**: Polygon.io Premium API