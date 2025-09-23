# TradeScout Bootstrap System

**Last Updated**: September 22, 2025
**Current Coverage**: 11,745 total tickers → 7,513 default universe assets
**Data Source**: Polygon.io Premium API

## Overview

TradeScout uses a four-stage bootstrapping process to initialize the system with data providers, market definitions, asset data, and filtered trading universes. The bootstrap system ensures proper dependency order and provides comprehensive error handling.

## Bootstrap Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Database      │───▶│   Providers     │───▶│    Tickers      │───▶│   Universe      │
│   Schema + Tables│    │   (Polygon)     │    │   (~11,745)     │    │   (~7,513)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘    └─────────────────┘
         │                        │                        │                        │
         ▼                        ▼                        ▼                        ▼
    Table Creation         Provider Metadata        Asset Storage           Filtered Membership
```

## Four-Stage Bootstrap Process

### Stage 1: Database Schema
- **Purpose**: Initialize SQLite database with complete schema
- **Command**: `./tradescout bootstrap database init`
- **Behavior**:
  - Creates new database if none exists
  - Verifies existing database if present
  - Runs migrations if needed

### Stage 2: Data Providers
- **Purpose**: Register available data providers (currently Polygon only)
- **Command**: `./tradescout bootstrap providers init`
- **Behavior**:
  - **Upserts** provider records (updates existing, inserts new)
  - Currently only creates Polygon.io provider
  - Sets active/inactive status

### Stage 3: Ticker/Asset Data
- **Purpose**: Fetch and store all available tickers from Polygon API
- **Command**: `./tradescout bootstrap tickers init`
- **Behavior**:
  - **Fetches fresh data** from Polygon API (~11,745 tickers)
  - **INSERT OR IGNORE** - adds new tickers, ignores existing ones
  - **Does NOT update** existing ticker metadata (limitation)
  - Creates market records as needed (XNYS, XNAS, ARCX, etc.)

### Stage 4: Universe Creation
- **Purpose**: Create filtered trading universe from existing assets
- **Command**: `./tradescout bootstrap universe init`
- **Behavior**:
  - **Completely rebuilds** universe membership (deletes all, recreates)
  - Applies strict filtering criteria (see below)
  - Uses existing universe record if found

## Complete Bootstrap Command

### Interactive Mode (Recommended)
```bash
./tradescout bootstrap all
```

**Behavior**:
- Checks for existing data and prompts for confirmation
- Shows current asset count and universe size
- Asks "Continue with bootstrap? [y/N]"

### Force Mode (Automation)
```bash
./tradescout bootstrap all --force
```

**Behavior**:
- Skips confirmation prompt
- Runs all four stages automatically

## Bootstrap Data Handling

| Component | Existing Data | New Data | Behavior |
|-----------|---------------|----------|----------|
| **Database** | Preserved | N/A | Schema verification only |
| **Providers** | Updated | Inserted | Full upsert (UPDATE/INSERT) |
| **Tickers** | Ignored | Inserted | INSERT OR IGNORE (no updates) |
| **Universe** | Deleted | Recreated | Complete rebuild of memberships |

⚠️ **Important**: Ticker data is NOT updated if it already exists. Only new tickers are added.

## Universe Filtering Criteria

The universe bootstrapper applies comprehensive filtering to create a high-quality trading universe:

### Inclusion Criteria
- **Asset Types**: Common Stock (CS), ETF, REIT only
- **Exchanges**: XNYS (NYSE), XNAS (NASDAQ) only
- **Symbol Format**: 1-5 alphabetic characters (`^[A-Z]{1,5}$`)
- **Status**: Active tickers only
- **Market**: Stocks only

### Exclusion Criteria
- **Preferred Stocks**: Symbols ending in -P, -PR, -A, etc.
- **Minor Exchanges**: OTC markets, regional exchanges
- **Invalid Symbols**: Special characters, numbers, test symbols
- **Complex Securities**: Rights, warrants, units

### Filtering Results
- **Total Assets**: 11,745 from Polygon API
- **Filtered Universe**: 7,513 assets (64% inclusion rate)
- **Excluded**: ~4,232 assets (ETFs, preferred stocks, OTC, etc.)

## Command Reference

### Database Commands
```bash
./tradescout bootstrap database init     # Create/verify database
./tradescout bootstrap database reset    # Delete and recreate (--force to skip prompt)
./tradescout bootstrap database info     # Show database statistics
```

### Provider Commands
```bash
./tradescout bootstrap providers init    # Initialize data providers
./tradescout bootstrap providers info    # Show provider status
```

### Ticker Commands
```bash
./tradescout bootstrap tickers init      # Fetch all tickers from Polygon
./tradescout bootstrap tickers info      # Show ticker statistics
./tradescout bootstrap tickers init --limit 100  # Limit for testing
```

### Universe Commands
```bash
./tradescout bootstrap universe init     # Create default trading universe
./tradescout bootstrap universe info     # Show universe statistics
```

### Complete Bootstrap
```bash
./tradescout bootstrap all               # Interactive mode with confirmation
./tradescout bootstrap all --force       # Skip confirmation
```

## Error Handling

The bootstrap system provides clear error messages and dependency checking:

### Provider Dependency
```bash
$ ./tradescout bootstrap tickers init
❌ Ticker initialization failed
ERROR: Provider 'polygon' must be bootstrapped first. Run 'tradescout bootstrap providers init'
```

### Ticker Dependency
```bash
$ ./tradescout bootstrap universe init
❌ Universe initialization failed
ERROR: No assets found in database. Tickers must be bootstrapped first.
```

### Database Dependency
```bash
$ ./tradescout bootstrap providers init
❌ Provider initialization failed
Database not found: data/tradescout.db
Run 'tradescout bootstrap database init' first
```

## Maintenance and Updates

### Regular Data Refresh
For updated ticker data and universe membership:

```bash
# Complete refresh (recommended monthly)
./tradescout bootstrap all --force

# Incremental updates (limitation: tickers won't update existing records)
./tradescout bootstrap tickers init
./tradescout bootstrap universe init
```

### Monitoring
```bash
# Check overall system status
./tradescout bootstrap database info

# Check specific components
./tradescout bootstrap providers info
./tradescout bootstrap tickers info
./tradescout bootstrap universe info
```

## Configuration Files

### Core Configuration
- **API Keys**: `src/config/api_keys.py`
- **Universe Filtering**: `src/config/universe_config.py`
- **Database Path**: Configured in CLI config

### Schema Files
- **Database Schema**: `src/database/schema/001_initial_schema.sql`
- **11 Tables**: providers, markets, assets, universes, universe_memberships, etc.

## Performance Characteristics

### Timing Expectations
- **Database Init**: < 1 second
- **Providers Init**: < 1 second
- **Tickers Init**: 60-90 seconds (API rate limited)
- **Universe Init**: 5-10 seconds
- **Complete Bootstrap**: 90-120 seconds

### API Usage
- **Polygon Calls**: ~12-15 paginated requests
- **Rate Limiting**: Built-in backoff handling
- **Data Volume**: ~11,745 ticker records

## Troubleshooting

### Common Issues

**1. Missing API Key**
```bash
ERROR: Polygon API key not found
```
**Solution**: Configure API key in `src/config/api_keys.py`

**2. Bootstrap Order Error**
```bash
ERROR: Provider 'polygon' must be bootstrapped first
```
**Solution**: Run bootstrap stages in order, or use `bootstrap all`

**3. Universe Empty**
```bash
ERROR: No assets found in database
```
**Solution**: Run ticker bootstrap first: `./tradescout bootstrap tickers init`

### Debug Logging
Bootstrap operations log extensively. Check logs for detailed error information and progress tracking.

## Database Schema

### Key Tables
- **providers**: Data source definitions (Polygon)
- **markets**: Exchange definitions (XNYS, XNAS, etc.)
- **assets**: Ticker data (11,745 records)
- **universes**: Universe metadata
- **universe_memberships**: Asset-universe relationships (7,513 records)

### Relationships
- Assets → Markets (foreign key)
- Assets → Providers (foreign key)
- Universe Memberships → Assets + Universes (foreign keys)

---

This bootstrap system ensures reliable, repeatable initialization of the TradeScout database with high-quality, filtered trading data from Polygon.io.