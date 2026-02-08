# TradeScout Bootstrapping Guide

**Last Updated**: 2026-02-08
**Architecture Version**: Repository + BootstrapService + SQLModel

## Overview

Bootstrapping populates TradeScout's database with reference data from free external sources (NASDAQ Trader, SEC EDGAR, yfinance, pandas_market_calendars). This guide covers the bootstrap sequence, dependencies, and current implementation.

## Bootstrap Dependency Chain

The bootstrap process follows this strict dependency order:

```
1. Providers (no dependencies)
   ↓
2. Markets (no dependencies)
   ↓
3. Tickers (depends on: Providers + Markets)
   ↓
4. Fundamentals (depends on: Tickers)
   ↓
5. Sentiment Types (no dependencies)
   ↓
6. Universes (depends on: Tickers + Fundamentals)
```

**Critical**: Each step must complete successfully before the next, as later steps require data from earlier steps.

---

## Bootstrap Operations

### 1. Providers Bootstrap

**Purpose**: Initialize data provider configuration

**Command**: `./tradescout database bootstrap-providers`

**What It Does**:
- Creates provider records for all 6 active providers:
  - **nasdaq_trader** — Bulk ticker listing (no API key)
  - **yfinance** — Market snapshots, aggregates, reference data (no API key)
  - **finnhub** — News and sentiment (free API key)
  - **fred** — Federal Reserve economic data (free API key)
  - **pandas_market_calendars** — Market status and holidays (local, no API)
  - **edgar** — SEC EDGAR bulk fundamentals (no API key)
- Sets all providers as active
- Records metadata timestamp

**Dependencies**: None

**Database Tables Updated**:
- `providers`: All 6 provider configurations
- `data_update_metadata`: Operation timestamp

---

### 2. Markets Bootstrap

**Purpose**: Fetch and store exchange/market reference data

**Command**: `./tradescout database bootstrap-markets`

**What It Does**:
- Creates hardcoded US exchange records (XNYS/NYSE, XNAS/NASDAQ)
- Stores to `markets` table with trading hours and metadata
- Records timestamp

**Dependencies**: None

**Database Tables Updated**:
- `markets`: Exchange records (XNYS, XNAS)
- `data_update_metadata`: Operation timestamp

**TTL**: 1 year (markets rarely change)

---

### 3. Tickers Bootstrap

**Purpose**: Fetch all available tickers and store as assets

**Command**: `./tradescout database bootstrap-tickers`

**What It Does**:
- Downloads NASDAQ Trader bulk ticker file (nasdaqtraded.txt, ~12,000 securities)
- Parses pipe-delimited data, maps exchange codes to MIC codes (Q/G/S→XNAS, N/A/P/Z→XNYS)
- Maps ETF flag to asset type (stock/etf)
- Stores to `assets` table (~12,000 active stocks/ETFs)
- Records timestamp

**Dependencies**:
- **Providers**: Need provider_id for asset records
- **Markets**: Need market_id lookup for primary_exchange mapping

**Database Tables Updated**:
- `assets`: Ticker records with symbol, name, market_id, provider_id
- `data_update_metadata`: TICKERS operation timestamp

**TTL**: 3 days (new listings/delistings are infrequent)

---

### 4. Fundamentals Bootstrap

**Purpose**: Fetch company fundamentals for each asset

**Command**: `./tradescout database bootstrap-fundamentals`

**What It Does**:
- Downloads bulk data from SEC EDGAR (free government data, no API key):
  1. **Ticker→CIK mapping** — Maps ~10K tickers to SEC CIK numbers (1 bulk download)
  2. **SIC codes** — Fetches SIC code + description per company from SEC submissions (parallel, 10 req/sec rate limit)
  3. **Shares outstanding** — Downloads from XBRL Frames API (1 bulk download per quarter, ~5K records)
  4. **Market cap** — Calculated as shares_outstanding × last_price (prices via yfinance bulk download in batches of 500)
- Stores to `asset_fundamentals` table with: company_name, sector (from SIC mapping), industry, sic_code, market_cap, shares_outstanding
- Skips assets with fresh data (< 30 days old)

**Dependencies**:
- **Tickers**: Need asset_id for each ticker to fetch fundamentals

**Database Tables Updated**:
- `asset_fundamentals`: Company data linked to asset_id
- `data_update_metadata`: FUNDAMENTALS operation timestamp

**TTL**: 30 days (fundamentals change infrequently)

**Coverage**: ~6,900 of ~11,700 tickers (59%). ETFs, foreign listings, warrants, and units have no SEC CIK match and are skipped.

**Performance**: ~13 minutes for full bootstrap (bulk downloads + parallel SIC fetch at 10 req/sec + batched price downloads).

---

### 5. Sentiment Types Bootstrap

**Purpose**: Initialize sentiment type categories

**Command**: `./tradescout database bootstrap-sentiment-types`

**What It Does**:
- Creates predefined sentiment type categories
- Stores to `sentiment_types` table

**Dependencies**: None

**Database Tables Updated**:
- `sentiment_types`: Sentiment categories (earnings, analyst, news, etc.)
- `data_update_metadata`: Operation timestamp

---

### 6. Universes Bootstrap

**Purpose**: Create filtered asset universes based on criteria

**Command**: `./tradescout database bootstrap-universes`

**What It Does**:
- Reads universe configuration from `configs/universes/*.yaml`
- Fetches all assets + fundamentals from database
- Applies filtering criteria:
  - Asset types (stocks only)
  - Exchanges (XNYS, XNAS)
  - Symbol patterns (alphabetic, length 1-5 chars)
  - Market cap ranges
  - Volume thresholds
- Excludes unwanted assets (preferred stocks, warrants, special characters)
- Creates/updates `universes` table record
- Populates `universe_memberships` table (~11,700 assets in default universe)
- Records timestamp

**Dependencies**:
- **Tickers**: Need ticker data
- **Fundamentals**: Need market_cap, sector for filtering

**Database Tables Updated**:
- `universes`: Universe configuration
- `universe_memberships`: Asset membership records
- `data_update_metadata`: UNIVERSES operation timestamp

**TTL**: 24 hours (membership can change with market cap shifts)

---

## Architecture

### Current Implementation

Bootstrap operations are implemented in **BootstrapService** (`src/services/bootstrap_service.py`):

```
BootstrapService
    ├── Uses: DataServiceV2 (runtime data operations)
    ├── Uses: Repositories (data access)
    ├── Uses: API Providers (external data fetching)
    └── Handles: All bootstrap orchestration
```

### Why BootstrapService?

Bootstrap is an **orchestration operation** requiring coordination between components:

```python
def bootstrap_X(self, ...):
    """Bootstrap X from external data source."""
    # Step 1: Fetch from API provider
    data = self.X_provider.fetch_all_X(...)

    # Step 2: Store via repository
    for item in data:
        repository.save(item)

    # Step 3: Record metadata timestamp
    self._record_update("X")

    return stored_count
```

All components (provider, repository, metadata) are orchestrated by **BootstrapService**.

---

## TTL-Based Refresh

Each bootstrap operation records a timestamp in `data_update_metadata` table. Future bootstrap calls check this timestamp against configured TTL:

| Operation | TTL | Refresh Frequency |
|-----------|-----|-------------------|
| Providers | 1 year | Essentially static |
| Markets | 1 year | Exchanges added infrequently |
| Tickers | 3 days | New listings/delistings |
| Fundamentals | 1 week | Company data changes |
| Sentiment Types | 1 year | Static categories |
| Universes | 24 hours | Membership shifts |

**Force Refresh**: Not currently implemented, but can be added if needed.

---

## CLI Commands

### Individual Bootstrap Operations

```bash
# Initialize data provider
./tradescout database bootstrap-providers

# Fetch market/exchange data
./tradescout database bootstrap-markets

# Fetch all tickers (~12,000 stocks/ETFs via NASDAQ Trader)
./tradescout database bootstrap-tickers

# Fetch fundamentals via SEC EDGAR bulk (~13 minutes)
./tradescout database bootstrap-fundamentals

# Initialize sentiment types
./tradescout database bootstrap-sentiment-types

# Create asset universes from configs
./tradescout database bootstrap-universes
```

### Full Bootstrap Sequence

```bash
# Run all bootstrap operations in dependency order
./tradescout database bootstrap-all
```

This command automatically:
1. Schema initialization
2. Providers (6 providers)
3. Markets (NYSE, NASDAQ)
4. Tickers (~12K from NASDAQ Trader)
5. Fundamentals (SEC EDGAR bulk — prompts for confirmation)
6. Universes (default, tech, large_cap, small_cap)
7. Sentiment Types

**Initial Setup Time**: ~15 minutes with fundamentals, ~2 minutes without

---

## Complete Bootstrap Example

```bash
# 1. Initialize database schema
./tradescout database init

# 2. Run full bootstrap
./tradescout database bootstrap-all

# 3. Verify data
./tradescout database info

# Expected output:
# Providers: 6 (nasdaq_trader, yfinance, finnhub, fred, pandas_market_calendars, edgar)
# Markets: 2 (XNYS, XNAS)
# Assets: ~12,000
# Fundamentals: ~6,900 (after bootstrap-fundamentals via SEC EDGAR)
# Universes: 4 (default_universe, tech, large_cap, small_cap)
# Universe Memberships: ~11,700 (default_universe)
```

---

## Updating Reference Data

### When to Update

- **Tickers**: Weekly (new listings, delistings)
- **Fundamentals**: Monthly (market cap, sector changes)
- **Universes**: Daily (automatic via TTL if running screeners regularly)

### Update Commands

```bash
# Update tickers (TTL: 3 days, auto-updates if stale)
./tradescout database bootstrap-tickers

# Update fundamentals (TTL: 1 week, auto-updates if stale)
./tradescout database bootstrap-fundamentals

# Update universes (TTL: 24 hours, auto-updates if stale)
./tradescout database bootstrap-universes

# Or update everything
./tradescout database bootstrap-all
```

---

## Database Backup/Restore

### Backup Gap Results

```bash
# Backup gap analysis results to JSON
./tradescout database results-backup

# Restore gap analysis results from JSON
./tradescout database results-restore
```

These commands handle gap candidate and gap result data separately from bootstrap operations.

---

## Troubleshooting

### "No providers found"

```bash
./tradescout database bootstrap-providers
```

### "No markets found"

```bash
./tradescout database bootstrap-markets
```

### "Universe is empty"

Ensure prerequisites are met:
```bash
./tradescout database info  # Check asset and fundamentals counts
./tradescout database bootstrap-tickers
./tradescout database bootstrap-fundamentals
./tradescout database bootstrap-universes
```

### "API rate limit exceeded"

If bootstrap fails due to rate limits:
1. Wait a few minutes
2. Re-run the command (will resume from where it left off via TTL)
3. Consider splitting fundamentals bootstrap into batches

---

## Performance Tips

1. **First Bootstrap**: ~15 minutes with fundamentals, ~2 minutes without
2. **Fundamentals**: Longest operation (~13 min via SEC EDGAR bulk + batched yfinance prices)
3. **Subsequent Updates**: Much faster due to TTL checks (30-day freshness for fundamentals)
4. **API Keys**: Only Finnhub (news) and FRED (economic data) require free API keys. SEC EDGAR and yfinance need no keys.

---

## Reference

- **Bootstrap Service**: `src/services/bootstrap_service.py`
- **Data Service**: `src/services/data_service_v2.py`
- **Repositories**: `src/repositories/`
- **Providers**: `src/api/providers/`
- **CLI Commands**: `src/cli/database_commands.py`
- **Universe Configs**: `configs/universes/*.yaml`

---

*Bootstrap operations are essential for initial setup and ongoing data maintenance in TradeScout.*
