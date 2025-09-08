# TradeScout Database Architecture

**Purpose:** Centralized data storage for asset universe management, market data caching, and historical analysis

## Core Philosophy: Database-First Caching

TradeScout uses the database as the **primary cache** for all market data, not just storage. This approach provides:

1. **Check database first** for cached data (age-aware)
2. **Only hit APIs** if database cache is stale  
3. **Always update database** when we get fresh API data
4. **Use database as primary data source** for all operations

### Benefits
- Reduced API calls (respect rate limits)
- Persistent cache across CLI sessions
- Historical data accumulation
- Offline capability with stale data
- Centralized data management

## Database Schema

### Core Tables

#### `assets`
Master table for all tradeable symbols
```sql
CREATE TABLE assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol VARCHAR(10) NOT NULL UNIQUE,
    name VARCHAR(255),
    asset_type VARCHAR(50) DEFAULT 'COMMON_STOCK',
    exchange VARCHAR(50),
    sector VARCHAR(100),
    industry VARCHAR(100),
    market_cap_millions REAL,
    avg_daily_volume INTEGER,
    is_active BOOLEAN DEFAULT 1,
    is_tradeable BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `universes`
Configuration for different asset groups
```sql
CREATE TABLE universes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    min_market_cap_millions REAL,
    min_avg_volume INTEGER,
    max_assets INTEGER,
    selection_criteria TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `universe_membership`
Many-to-many relationship between assets and universes
```sql
CREATE TABLE universe_membership (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    universe_name VARCHAR(100) NOT NULL,
    added_date DATE DEFAULT CURRENT_DATE,
    removed_date DATE,
    is_active BOOLEAN DEFAULT 1,
    reason VARCHAR(255),
    FOREIGN KEY (asset_id) REFERENCES assets(id),
    UNIQUE(asset_id, universe_name)
);
```

### Caching Tables

#### `market_snapshots` 
**PRIMARY CACHE** for real-time market data
```sql
CREATE TABLE market_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_time TIMESTAMP NOT NULL,  -- Cache timestamp
    asset_id INTEGER NOT NULL,
    price REAL,
    change_percent REAL,
    change_dollars REAL,
    volume BIGINT,
    day_open REAL,
    day_high REAL,
    day_low REAL,
    previous_close REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (asset_id) REFERENCES assets(id),
    UNIQUE(snapshot_time, asset_id)
);
```

**Cache Logic:**
- TTL: 10 minutes (configurable)
- Check `MAX(snapshot_time)` for cache age
- Load all symbols from latest snapshot
- Auto-refresh when stale

### Historical Tables

#### `price_history`
OHLCV data with extended hours
```sql
CREATE TABLE price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    date DATE NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume BIGINT,
    vwap REAL,
    premarket_open REAL,
    premarket_close REAL,
    premarket_volume BIGINT,
    afterhours_open REAL,
    afterhours_close REAL,
    afterhours_volume BIGINT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (asset_id) REFERENCES assets(id),
    UNIQUE(asset_id, date)
);
```

#### `gap_history`
Gap events for trading analysis
```sql
CREATE TABLE gap_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    gap_date DATE NOT NULL,
    gap_type VARCHAR(20), -- 'up' or 'down'
    gap_size_percent REAL NOT NULL,
    gap_size_dollars REAL,
    previous_close REAL,
    open_price REAL,
    session_type VARCHAR(20), -- 'premarket', 'regular', 'afterhours'
    volume_at_open BIGINT,
    filled BOOLEAN DEFAULT 0,
    fill_time TIME,
    fill_price REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (asset_id) REFERENCES assets(id)
);
```

#### `fundamental_history`
Company financial data over time
```sql
CREATE TABLE fundamental_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    report_date DATE NOT NULL,
    market_cap BIGINT,
    pe_ratio REAL,
    earnings_per_share REAL,
    dividend_yield REAL,
    beta REAL,
    shares_outstanding BIGINT,
    revenue_ttm BIGINT,
    profit_margin REAL,
    operating_margin REAL,
    return_on_equity REAL,
    debt_to_equity REAL,
    current_ratio REAL,
    book_value REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (asset_id) REFERENCES assets(id),
    UNIQUE(asset_id, report_date)
);
```

#### `asset_performance`
Trading performance metrics
```sql
CREATE TABLE asset_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    date DATE NOT NULL,
    gap_count INTEGER DEFAULT 0,
    successful_gaps INTEGER DEFAULT 0,
    total_gap_return REAL DEFAULT 0,
    avg_gap_size REAL,
    last_gap_date DATE,
    notes TEXT,
    FOREIGN KEY (asset_id) REFERENCES assets(id),
    UNIQUE(asset_id, date)
);
```

## Data Flow Architecture

### Market Data Caching Flow
```
1. Market Command Called (gainers, losers, suggest)
   ↓
2. Check Database Cache Age
   - Query: SELECT MAX(snapshot_time) FROM market_snapshots
   - Compare with TTL (10 minutes)
   ↓
3a. Cache Fresh? → Load from database
   - Query: Get all symbols from latest snapshot_time
   - Convert to API format for compatibility
   - Return cached data
   
3b. Cache Stale? → Fetch from API
   - Call Polygon full market snapshot API
   - Process ~11,700 symbols
   ↓
4. Update Database Cache
   - Add new symbols to assets table
   - Add to default_liquid_universe
   - Save all snapshot data with current timestamp
   ↓
5. Return Fresh Data
```

### Symbol Discovery Flow  
```
New Symbol in API Response
   ↓
Check: EXISTS in assets table?
   ↓
No? → Add to Database
   - INSERT INTO assets (symbol, asset_type, is_active)
   - INSERT INTO universe_membership (default_liquid_universe)
   - Log: "Added new symbol: XXXX"
   ↓
Save Market Data
   - INSERT INTO market_snapshots (current snapshot)
```

## Implementation Classes

### `AssetUniverseManager`
**Location:** `src/tradescout/storage/asset_universe_manager.py`

**Key Methods:**
- `add_asset(symbol, **kwargs)` - Add new symbol to database
- `get_asset(symbol)` - Retrieve symbol metadata  
- `add_to_universe(symbol, universe_name)` - Manage universe membership
- `get_universe_symbols(universe_name)` - Get symbols in universe
- `save_market_snapshot(snapshot_data, timestamp)` - Cache market data
- `get_gap_history(symbol, days_back)` - Historical gap analysis

### `AssetDataProviderPolygon` 
**Location:** `src/tradescout/data_sources_api/asset_data_provider_polygon.py`

**Database-Aware Methods:**
- `_is_database_cache_stale()` - Check cache age vs TTL
- `_load_from_database_cache()` - Load cached market data
- `_save_to_database_cache(snapshot_data)` - Update cache + add symbols
- `_get_fresh_market_data()` - Main caching orchestrator

## Default Universes

| Universe Name | Description | Min Market Cap | Min Volume | Max Assets |
|---------------|-------------|----------------|------------|------------|
| `liquid_universe` | High-volume liquid stocks | $10B | 1M | 1000 |
| `gap_trading` | Gap trading candidates | $1B | 500K | 500 |
| `small_cap` | Small cap growth | $100M | 100K | 200 |
| `mega_cap` | Mega cap stable stocks | $50B | 5M | 100 |
| `default_liquid_universe` | Auto-discovered from API | $10B | 1M | unlimited |

## Performance Considerations

### Indexes
```sql
-- Cache performance
CREATE INDEX idx_market_snapshots_time ON market_snapshots(snapshot_time);
CREATE INDEX idx_assets_symbol ON assets(symbol);

-- Query performance  
CREATE INDEX idx_universe_membership_active ON universe_membership(universe_name, is_active);
CREATE INDEX idx_gap_history_date ON gap_history(gap_date, asset_id);
CREATE INDEX idx_price_history_date ON price_history(asset_id, date);
```

### Query Patterns
- **Cache Check:** `SELECT MAX(snapshot_time) FROM market_snapshots`
- **Cache Load:** `SELECT * FROM market_snapshots ms JOIN assets a WHERE snapshot_time = ?`
- **Universe Query:** `SELECT symbol FROM assets a JOIN universe_membership um WHERE universe_name = ?`

### Batch Operations
- Market snapshots saved in single transaction (~11K records)
- New symbols added in batches with proper error handling
- Foreign key constraints ensure data integrity

## CLI Commands

### Universe Management
```bash
# View universe info (from database)
./tradescout system universe --name default_liquid_universe

# List all universes with stats
./tradescout system universe-list

# Add symbol to universe
./tradescout system universe-add AAPL gap_trading --reason "High gap frequency"
```

### Database Queries
```bash
# Check cache status
sqlite3 data/tradescout.db "SELECT COUNT(*) as total_symbols FROM assets"

# View recent snapshots  
sqlite3 data/tradescout.db "SELECT MAX(snapshot_time), COUNT(*) FROM market_snapshots"

# Gap analysis
sqlite3 data/tradescout.db "SELECT symbol, COUNT(*) as gaps FROM gap_history gh JOIN assets a ON gh.asset_id = a.id GROUP BY symbol ORDER BY gaps DESC LIMIT 10"
```

## Migration Management

### Initial Schema
**File:** `src/tradescout/storage/migrations/001_create_asset_universe.sql`

### Data Migration  
**Script:** `scripts/migrate_universe_to_db.py`
- Imports existing YAML universe files
- Creates default universes
- Handles data validation and deduplication

## Best Practices

1. **Always check database first** before API calls
2. **Batch database operations** for performance
3. **Use transactions** for data consistency  
4. **Handle errors gracefully** with fallbacks
5. **Log new symbol discoveries** for monitoring
6. **Respect TTL configurations** for caching
7. **Index frequently queried columns**
8. **Use foreign keys** for data integrity