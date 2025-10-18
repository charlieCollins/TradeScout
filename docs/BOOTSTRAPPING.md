# TradeScout Bootstrapping Guide

**Last Updated**: 2025-10-18
**Architecture Version**: Repository + BootstrapService + SQLModel

## Overview

Bootstrapping populates TradeScout's database with reference data from external sources (primarily Polygon.io). This guide covers the bootstrap sequence, dependencies, and current implementation.

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

**Purpose**: Initialize data provider configuration (Polygon.io)

**Command**: `./tradescout database bootstrap-providers`

**What It Does**:
- Creates Polygon.io provider record in `providers` table
- Sets provider as active
- Records metadata timestamp

**Dependencies**: None

**Database Tables Updated**:
- `providers`: Polygon configuration
- `data_update_metadata`: Operation timestamp

---

### 2. Markets Bootstrap

**Purpose**: Fetch and store exchange/market reference data

**Command**: `./tradescout database bootstrap-markets`

**What It Does**:
- Fetches exchanges from Polygon `/v3/reference/exchanges` API
- Filters by asset_class="stocks" and locale="us"
- Stores to `markets` table with trading hours and metadata
- Records timestamp

**Dependencies**: None (API-driven)

**Database Tables Updated**:
- `markets`: Exchange records (XNYS, XNAS, ARCX, BATS, etc.)
- `data_update_metadata`: Operation timestamp

**TTL**: 1 year (markets rarely change)

---

### 3. Tickers Bootstrap

**Purpose**: Fetch all available tickers and store as assets

**Command**: `./tradescout database bootstrap-tickers`

**What It Does**:
- Fetches ALL tickers from Polygon `/v3/reference/tickers` API (paginated)
- Maps ticker data to Asset model
- Looks up market_id from primary_exchange → `markets` table
- Stores to `assets` table (~15,000 active stocks)
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
- Iterates through all assets in `assets` table
- For each asset, calls `/v3/reference/tickers/{symbol}` API
- Extracts: market_cap, sector, industry, shares_outstanding, beta, pe_ratio, etc.
- Stores to `fundamentals` table
- Records timestamp

**Dependencies**:
- **Tickers**: Need asset_id for each ticker to fetch fundamentals

**Database Tables Updated**:
- `fundamentals`: Company data linked to asset_id
- `data_update_metadata`: FUNDAMENTALS operation timestamp

**TTL**: 1 week (fundamentals change infrequently)

**Performance Note**: Makes thousands of API calls (one per asset). Can take 30-60 minutes for full bootstrap.

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
- Populates `universe_memberships` table (~7,500 assets in default universe)
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
    """Bootstrap X from Polygon API."""
    # Step 1: Fetch from API provider
    data = self.polygon_X_provider.fetch_all_X(...)

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

# Fetch all tickers (~15,000 stocks)
./tradescout database bootstrap-tickers

# Fetch fundamentals for all assets (30-60 minutes)
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
1. Bootstraps providers
2. Bootstraps markets
3. Bootstraps tickers
4. Bootstraps fundamentals
5. Bootstraps sentiment types
6. Bootstraps universes

**Initial Setup Time**: 30-60 minutes (fundamentals takes longest)

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
# Providers: 1
# Markets: ~10
# Assets: ~15,000
# Fundamentals: ~15,000
# Universes: ~5
# Universe Memberships: ~7,500 (default_universe)
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

Polygon has rate limits. If bootstrap fails:
1. Wait a few minutes
2. Re-run the command (will resume from where it left off via TTL)
3. Consider splitting fundamentals bootstrap into batches

---

## Performance Tips

1. **First Bootstrap**: Expect 30-60 minutes for full bootstrap
2. **Fundamentals**: Longest operation (~15,000 API calls)
3. **Subsequent Updates**: Much faster due to TTL checks
4. **API Key**: Premium subscription required for extended hours data

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
