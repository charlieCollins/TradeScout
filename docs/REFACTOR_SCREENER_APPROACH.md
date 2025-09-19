# Screener Architecture Refactor Plan

**Purpose:** Replace hardcoded view methods (gainers, losers, etc.) with a unified, reusable screener/filter system
**Date:** 2025-09-16
**Status:** Planning Phase

---

## Core Concept

All our different views (gainers, losers, gainers-extended-hours, gap-candidates, etc.) are fundamentally **screeners** - filtered views of our market universe with specific criteria applied.

Instead of creating separate methods for each view, we should build a **unified screener engine** that can apply any criteria to our database and return filtered results.

---

## Proposed Screener Architecture

### **Step 1: Complete Database Schema Redesign**

#### **NEW SCHEMA: Requirements-Driven Design**

**Core Principle:** Design the database WE NEED for gap trading strategy, not what APIs give us.

---

## **1. MARKETS & EXCHANGES**

```sql
-- Markets/Exchanges (NYSE, NASDAQ, etc.)
CREATE TABLE markets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,           -- 'NYSE', 'NASDAQ', 'AMEX'
    name TEXT NOT NULL,                  -- 'New York Stock Exchange'
    country TEXT NOT NULL,               -- 'US', 'CA', 'UK'
    timezone TEXT NOT NULL,              -- 'America/New_York'
    currency TEXT NOT NULL,              -- 'USD', 'CAD', 'GBP'

    -- Trading hours (in market timezone)
    premarket_start_time TIME,           -- '04:00:00'
    premarket_end_time TIME,             -- '09:30:00' (same as regular open)
    regular_open_time TIME NOT NULL,     -- '09:30:00'
    regular_close_time TIME NOT NULL,    -- '16:00:00'
    afterhours_start_time TIME,          -- '16:00:00' (same as regular close)
    afterhours_end_time TIME,            -- '20:00:00'

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_markets_code ON markets(code);
CREATE INDEX idx_markets_active ON markets(is_active);
```

---

## **2. ASSET FUNDAMENTALS**

```sql
-- Asset fundamentals (financial data, updated periodically)
CREATE TABLE asset_fundamentals (
    asset_id INTEGER PRIMARY KEY,        -- One-to-one with assets table

    -- Company identification
    company_name TEXT,                   -- 'Apple Inc.' (for display)

    -- Business classification
    sector TEXT,                         -- 'Technology'
    industry TEXT,                       -- 'Consumer Electronics'
    sic_code TEXT,                       -- Standard Industrial Classification

    -- Key financials
    market_cap BIGINT,                   -- Market capitalization in cents
    shares_outstanding BIGINT,           -- Outstanding shares

    -- Additional metrics for screening
    avg_volume_30d BIGINT,               -- 30-day average volume
    beta DECIMAL(6,3),                   -- Beta coefficient
    pe_ratio DECIMAL(8,2),               -- Price to earnings ratio
    dividend_yield DECIMAL(6,4),         -- Annual dividend yield

    -- Data tracking
    data_source TEXT,                    -- 'polygon', 'manual'
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (asset_id) REFERENCES assets (id)
);

CREATE INDEX idx_fundamentals_sector ON asset_fundamentals(sector);
CREATE INDEX idx_fundamentals_industry ON asset_fundamentals(industry);
CREATE INDEX idx_fundamentals_market_cap ON asset_fundamentals(market_cap);
CREATE INDEX idx_fundamentals_updated ON asset_fundamentals(last_updated);
```

---

## **3. ASSETS (TRADEABLE INSTRUMENTS)**

```sql
-- Assets (stocks, ETFs, etc. - tradeable instruments)
CREATE TABLE assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,                -- 'AAPL'
    name TEXT,                           -- 'Apple Inc.' or 'SPDR S&P 500 ETF'
    market_id INTEGER NOT NULL,          -- Which exchange trades this

    -- Asset classification
    asset_type TEXT NOT NULL,            -- 'stock', 'etf', 'option', 'crypto'
    asset_class TEXT NOT NULL,           -- 'equity', 'fixed_income', 'commodity'

    -- Trading details
    currency TEXT NOT NULL,              -- 'USD'
    lot_size INTEGER DEFAULT 1,          -- Minimum trading unit
    tick_size DECIMAL(10,6),             -- Minimum price movement

    -- Status and metadata
    is_active BOOLEAN DEFAULT TRUE,      -- Currently trading
    is_delisted BOOLEAN DEFAULT FALSE,   -- Delisted but may have historical data
    listing_date DATE,                   -- When asset started trading
    delisting_date DATE,                 -- When asset stopped trading (if applicable)

    -- Data tracking
    data_source TEXT,                    -- 'polygon', 'manual'
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (market_id) REFERENCES markets (id),
    UNIQUE(symbol, market_id)            -- Same symbol can exist on different markets
);

CREATE INDEX idx_assets_symbol ON assets(symbol);
CREATE INDEX idx_assets_market ON assets(market_id);
CREATE INDEX idx_assets_type ON assets(asset_type);
CREATE INDEX idx_assets_active ON assets(is_active);
```

---

### **4. UNIFIED ASSET PRICING (Snapshot-Based)**

Since we're using Polygon snapshot APIs that provide both `day.*` and `min.*` fields in one response, we use a single unified table:

```sql
-- Unified asset pricing from snapshot APIs
CREATE TABLE asset_prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    market_id INTEGER NOT NULL,
    trade_date DATE NOT NULL,

    -- Regular session data (from snapshot day.* fields)
    day_open DECIMAL(12,4),              -- day.o - Regular session open
    day_high DECIMAL(12,4),              -- day.h - Regular session high
    day_low DECIMAL(12,4),               -- day.l - Regular session low
    day_close DECIMAL(12,4),             -- day.c - Regular session close (4:00 PM)
    day_volume BIGINT,                   -- day.v - Regular session volume
    day_vwap DECIMAL(12,4),              -- day.vw - Regular session VWAP

    -- Current/Extended hours data (from snapshot min.* fields)
    current_price DECIMAL(12,4),         -- min.c - Current price (any session)
    current_timestamp BIGINT,            -- min.t - When current price occurred
    current_session TEXT,                -- Derived: 'premarket', 'regular', 'afterhours', 'closed'
    current_volume INTEGER,              -- min.v - Current minute volume

    -- Previous day reference (from snapshot prevDay.* fields)
    prev_close DECIMAL(12,4),            -- prevDay.c - Previous trading day close

    -- Metadata
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
    data_source TEXT DEFAULT 'polygon_snapshot',

    FOREIGN KEY (asset_id) REFERENCES assets (id),
    FOREIGN KEY (market_id) REFERENCES markets (id),

    -- One record per asset per trading day (UPSERT on each snapshot call)
    UNIQUE(asset_id, trade_date)
);

-- Optimized indexes for gap analysis
CREATE INDEX idx_asset_prices_asset_date ON asset_prices(asset_id, trade_date);
CREATE INDEX idx_asset_prices_session ON asset_prices(current_session);
CREATE INDEX idx_asset_prices_updated ON asset_prices(last_updated);
```

**Benefits of Unified Table:**
- **Matches snapshot API structure** - One response populates one row
- **Simple gap analysis queries** - No joins needed between current/daily tables
- **UPSERT pattern** - Each snapshot call updates the same row
- **All gap data in one place** - day_close, current_price, prev_close

---

### **How Updates Work:**

#### **Real-time Updates (ad hoc):**
```sql
-- UPSERT current price (replaces existing row)
INSERT OR REPLACE INTO asset_prices_current (
    asset_id, market_id, current_price, volume_today,
    last_trade_time, session_type, trade_date, data_source
) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
```

#### **Daily Session Updates (Multiple times per day):**
```sql
-- UPSERT snapshot data (updates if exists, inserts if new)
INSERT OR REPLACE INTO asset_prices_daily (
    asset_id, market_id, trade_date,
    open_price, high_price, low_price, close_price, volume,
    data_source, created_at
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
```

**Snapshot API Usage Pattern:**
- **During trading day:** Current incomplete OHLCV (whatever has happened so far)
- **After regular close:** Complete regular session OHLCV
- **Historical queries:** Call with specific date to get previous sessions
- Example: `/v2/snapshot/locale/us/markets/stocks/tickers?date=2025-09-17`

#### **Gap Analysis Screener Queries:**
```sql
-- Extended hours gaps - simple single table query
SELECT
    a.symbol,
    ap.current_price,
    ap.current_session,
    ap.day_close AS regular_close,
    ap.current_price - ap.day_close AS gap_amount,
    ((ap.current_price - ap.day_close) / ap.day_close) * 100 AS gap_percent,
    ap.current_volume,
    ap.current_timestamp
FROM asset_prices ap
JOIN assets a ON ap.asset_id = a.id
WHERE ap.current_session IN ('premarket', 'afterhours')  -- Extended hours only
AND ABS(((ap.current_price - ap.day_close) / ap.day_close) * 100) >= 2.0
ORDER BY ABS(((ap.current_price - ap.day_close) / ap.day_close) * 100) DESC;

-- Overnight gaps (pre-market vs previous day close)
SELECT
    a.symbol,
    ap.current_price,
    ap.prev_close,
    ap.current_price - ap.prev_close AS overnight_gap,
    ((ap.current_price - ap.prev_close) / ap.prev_close) * 100 AS overnight_gap_percent
FROM asset_prices ap
JOIN assets a ON ap.asset_id = a.id
WHERE ap.current_session = 'premarket'
AND ABS(((ap.current_price - ap.prev_close) / ap.prev_close) * 100) >= 2.0
ORDER BY ABS(overnight_gap_percent) DESC;
```

---

### **Benefits of This Approach:**

#### **Performance:**
- **Fast screeners** - scan ~10K current prices vs millions of historical ticks
- **Optimized indexes** - separate optimization for real-time vs historical queries
- **Minimal storage** - only essential data in high-frequency table

#### **Data Clarity:**
- **Clear update semantics** - current state vs historical summaries
- **No mixed concerns** - real-time queries separate from historical analysis
- **Immutable history** - session data never changes once written

#### **Gap Analysis Optimized:**
- **Current vs previous close** - natural query pattern
- **Session type filtering** - easy extended hours identification
- **Volume ratio calculations** - historical averages readily available

#### **Data Quality:**
- **Single source of truth** - current table has latest known state
- **Audit trail** - session table preserves historical OHLCV
- **Flexible updates** - can handle different API update frequencies

---

## **5. UNIVERSES (ASSET GROUPINGS)**

```sql
-- Universes (collections of assets for analysis)
CREATE TABLE universes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,           -- 'default_universe', 'sp500', 'nasdaq100'
    description TEXT,                    -- 'Primary universe for gap analysis'

    -- Universe criteria (for documentation)
    criteria_description TEXT,           -- 'Large cap US equities, >$1B market cap'
    min_market_cap BIGINT,              -- Minimum market cap for inclusion
    max_market_cap BIGINT,              -- Maximum market cap (nullable)
    required_exchanges TEXT,             -- JSON array: ['NYSE', 'NASDAQ']
    required_asset_types TEXT,           -- JSON array: ['stock']

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    auto_update BOOLEAN DEFAULT FALSE,   -- Automatically update membership
    last_updated DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Universe membership (many-to-many: assets can be in multiple universes)
CREATE TABLE universe_memberships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    universe_id INTEGER NOT NULL,
    asset_id INTEGER NOT NULL,

    -- Membership metadata
    added_date DATE NOT NULL,            -- When asset was added to universe
    removed_date DATE,                   -- When asset was removed (nullable)
    reason TEXT,                         -- 'initial_load', 'market_cap_growth', 'delisted'

    -- Status
    is_active BOOLEAN DEFAULT TRUE,      -- Currently in universe

    FOREIGN KEY (universe_id) REFERENCES universes (id),
    FOREIGN KEY (asset_id) REFERENCES assets (id),
    UNIQUE(universe_id, asset_id, added_date)
);

CREATE INDEX idx_universe_memberships_universe ON universe_memberships(universe_id);
CREATE INDEX idx_universe_memberships_asset ON universe_memberships(asset_id);
CREATE INDEX idx_universe_memberships_active ON universe_memberships(is_active);
```

---

## **6. SENTIMENT TRACKING**

```sql
-- Sentiment event types (news, social media, analyst ratings, etc.)
CREATE TABLE sentiment_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,           -- 'earnings_announcement', 'analyst_upgrade'
    category TEXT NOT NULL,              -- 'fundamental', 'technical', 'social'
    description TEXT,                    -- Human readable description

    -- Sentiment scoring
    default_weight DECIMAL(4,2) DEFAULT 1.0,  -- Default weight for this type
    impact_duration_hours INTEGER DEFAULT 24,  -- How long sentiment typically lasts

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Sentiment events (news, social media mentions, analyst changes, etc.)
CREATE TABLE sentiment_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    sentiment_type_id INTEGER NOT NULL,

    -- Event details
    event_date DATETIME NOT NULL,        -- When the event occurred
    event_source TEXT,                   -- 'reuters', 'twitter', 'sec_filing'
    event_title TEXT,                    -- 'Apple announces Q4 earnings beat'
    event_description TEXT,              -- Full text or summary
    event_url TEXT,                      -- Link to original source

    -- Sentiment scoring
    sentiment_score DECIMAL(4,2),        -- -1.0 (very negative) to +1.0 (very positive)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (asset_id) REFERENCES assets (id),
    FOREIGN KEY (sentiment_type_id) REFERENCES sentiment_types (id)
);

CREATE INDEX idx_sentiment_events_asset_date ON sentiment_events(asset_id, event_date);
CREATE INDEX idx_sentiment_events_type ON sentiment_events(sentiment_type_id);
CREATE INDEX idx_sentiment_events_date ON sentiment_events(event_date);
CREATE INDEX idx_sentiment_events_score ON sentiment_events(sentiment_score);
```

---

## **7. VERSIONING & DATA LINEAGE**

```sql
-- Data versions (track schema and data changes)
CREATE TABLE data_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_number TEXT NOT NULL UNIQUE, -- 'v1.0.0', 'v1.1.0'
    description TEXT NOT NULL,           -- 'Initial schema', 'Added sentiment tracking'

    -- Schema changes
    schema_version TEXT NOT NULL,        -- 'schema_v1', 'schema_v2'
    migration_script TEXT,               -- SQL script that created this version

    -- Data changes
    data_sources_changed TEXT,           -- JSON array of affected data sources
    tables_affected TEXT,                -- JSON array of tables modified

    -- Deployment info
    deployed_at DATETIME NOT NULL,
    deployed_by TEXT,                    -- 'system', 'admin', 'migration_script'

    -- Validation
    validation_passed BOOLEAN DEFAULT FALSE,
    validation_notes TEXT,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Data source tracking (where did each piece of data come from)
CREATE TABLE data_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,           -- 'polygon_api', 'yahoo_finance', 'manual_entry'
    description TEXT,                    -- Human readable description

    -- Source details
    source_type TEXT NOT NULL,           -- 'api', 'file', 'manual', 'calculated'
    base_url TEXT,                       -- For APIs
    api_version TEXT,                    -- API version if applicable
    rate_limit_per_minute INTEGER,       -- Rate limiting info

    -- Data quality
    reliability_score DECIMAL(4,2) DEFAULT 1.0,  -- 0.0 to 1.0
    latency_minutes INTEGER,             -- Typical data delay
    coverage_description TEXT,           -- What data this source provides

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    last_successful_update DATETIME,
    last_error_at DATETIME,
    last_error_message TEXT,

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Data lineage (track where each record came from)
CREATE TABLE data_lineage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT NOT NULL,            -- 'asset_prices', 'sentiment_events'
    record_id INTEGER NOT NULL,          -- ID of the record in that table
    data_source_id INTEGER NOT NULL,     -- Which data source provided this

    -- Lineage details
    source_reference TEXT,               -- External ID, URL, or reference
    extraction_timestamp DATETIME NOT NULL, -- When we got the data
    processing_timestamp DATETIME NOT NULL, -- When we processed/stored it

    -- Processing info
    processing_method TEXT,              -- 'direct_api', 'batch_import', 'calculation'
    confidence_score DECIMAL(4,2) DEFAULT 1.0,  -- How confident we are in this data

    FOREIGN KEY (data_source_id) REFERENCES data_sources (id)
);

CREATE INDEX idx_data_lineage_table_record ON data_lineage(table_name, record_id);
CREATE INDEX idx_data_lineage_source ON data_lineage(data_source_id);
CREATE INDEX idx_data_lineage_timestamp ON data_lineage(extraction_timestamp);
```

---

## **8. SYSTEM METADATA**

```sql
-- System configuration
CREATE TABLE system_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key TEXT NOT NULL UNIQUE,     -- 'default_universe', 'gap_analysis_version'
    config_value TEXT NOT NULL,          -- Value (can be JSON)
    config_type TEXT NOT NULL,           -- 'string', 'integer', 'json', 'boolean'
    description TEXT,                    -- Human readable description

    -- Change tracking
    previous_value TEXT,                 -- Previous value before last change
    changed_at DATETIME,                 -- When it was last changed
    changed_by TEXT,                     -- Who changed it

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- System performance metrics
CREATE TABLE system_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_date DATE NOT NULL,

    -- Database metrics
    total_assets INTEGER,                -- Number of assets in system
    total_price_records INTEGER,         -- Number of price records
    total_sentiment_events INTEGER,      -- Number of sentiment events

    -- Data freshness
    latest_price_data_date DATE,         -- Most recent price data
    price_data_staleness_hours INTEGER,  -- Hours since latest price data
    sentiment_data_staleness_hours INTEGER,

    -- Performance metrics
    avg_screener_query_ms INTEGER,       -- Average screener performance
    data_load_time_ms INTEGER,           -- Time to load reference data

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(metric_date)
);
```

---

## **POLYGON API USAGE MAP**

### **IMPORTANT: Polygon Starter Plan Limitations**

**What we have:**
- **Stocks Starter Plan** (paid, ~$50/month)
- Access to aggregated bars (OHLCV)
- NO access to real-time trades or quotes

**Tested and Confirmed:**
- Snapshot API returns regular session OHLCV
- Snapshot API "min" field CAN show after-hours prices
- Custom Bars API DOES return extended hours minute bars
- **ALL data has 15-minute delay** (standard for Starter plan)
- This is fine for gap analysis - we don't need real-time

### **Complete API Strategy for Each Data Need:**

| **Data Need** | **API Endpoint** | **Frequency** | **Database Tables** | **Purpose** |
|---------------|------------------|---------------|-------------------|------------|
| **0. Exchanges/Markets** | `/v3/reference/exchanges` | Once at setup | `markets` | Get exchange metadata and trading hours |
| **1. Asset Universe** | `/v3/reference/tickers` | Weekly/Monthly | `assets`, `asset_fundamentals` | Bootstrap all available tickers |
| **2. Bulk Market Data** | `/v2/snapshot/locale/us/markets/stocks/tickers` | 2-3x daily | `asset_prices_daily` | Regular session OHLCV for ALL stocks |
| **3. Extended Hours Data** | `/v2/aggs/ticker/{ticker}/range/1/minute/{from}/{to}` | On-demand | `asset_prices_current` | Pre-market & after-hours prices |
| **4. Fundamentals** | `/v3/reference/tickers/{ticker}` | On-demand/Weekly | `asset_fundamentals` | Market cap, sector, industry |
| **5. News/Sentiment** | `/v2/reference/news` | Hourly/On-demand | `sentiment_events` | Market-moving news events |
| **6. Market Status** | `/v1/marketstatus/now` | As needed | N/A | Get current session times and status |

---

### **Detailed API Usage:**

#### **0. Exchanges API (Market Setup)**
- **Endpoint:** `/v3/reference/exchanges`
- **Purpose:** Get all available exchanges and their metadata
- **When to Call:**
  - Once during initial setup
  - Rarely needs updating (exchanges don't change often)
- **Filtering:**
  - `asset_class=stocks` - Only equity exchanges
  - `locale=us` - US exchanges only
- **Data Stored:**
  ```sql
  -- Populates markets table
  INSERT INTO markets (code, name, country, timezone, currency)
  VALUES ('XNYS', 'New York Stock Exchange', 'US', 'America/New_York', 'USD')

  -- Note: Trading hours must be set manually or from another source
  -- as the exchanges API doesn't provide session times
  ```
- **Important:**
  - MIC codes (e.g., XNYS for NYSE, XNAS for NASDAQ)
  - Maps exchange IDs from tickers API to our markets table

#### **1. Reference Tickers API (Universe Bootstrap)**
- **Endpoint:** `/v3/reference/tickers`
- **Purpose:** Get complete list of all tradeable assets
- **When to Call:**
  - Initial database bootstrap
  - Weekly refresh to catch new listings
  - Monthly full refresh
- **Filtering:**
  - `market=stocks` - Only equities
  - `active=true` - Only active tickers
  - `limit=1000` - Paginate through results
- **Data Stored:**
  ```sql
  -- Populates assets table
  INSERT INTO assets (symbol, name, market_id, asset_type, currency, is_active)

  -- Populates asset_fundamentals table
  INSERT INTO asset_fundamentals (asset_id, market_cap, sector, industry)
  ```
- **Universe Creation:**
  - After bootstrap, create `default_universe` with filters:
    - Market cap > $100M
    - Average volume > 100K shares
    - Price > $1
    - US exchanges only (NYSE, NASDAQ, AMEX)

#### **2. Market Snapshot API (Bulk Daily Data)**
- **Endpoint:** `/v2/snapshot/locale/us/markets/stocks/tickers`
- **Purpose:** Get current state of ALL stocks (whatever point in trading day)
- **When to Call:**
  - **Anytime during trading** - Get current OHLCV (incomplete if market open)
  - **After market close** - Get complete regular session OHLCV
  - **With date parameter** - Get historical snapshot for previous days
- **Data Stored:**
  ```sql
  -- UPSERT into asset_prices table (unified approach)
  INSERT OR REPLACE INTO asset_prices (
    asset_id, trade_date, day_open, day_high, day_low, day_close, day_volume,
    current_price, current_timestamp, prev_close
  ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
  ```
- **Key Points:**
  - Snapshot = "current state whenever called"
  - Can be called multiple times per day (data gets updated)
  - Historical data via date parameter: `?date=2025-09-17`
  - Table always has "latest known state" for each trade_date

#### **CONFIRMED: Snapshot API Data Structure**

**Testing Results (AAPL premarket, 2025-09-19 6:43 AM ET):**

```json
{
  "day": { "o": 0, "h": 0, "l": 0, "c": 0, "v": 0 },        // Current session (zeros until complete)
  "min": { "c": 239.52, "t": 1758278580000, "v": 928 },      // Current real-time price
  "prevDay": { "o": 239.97, "h": 241.2, "l": 236.65, "c": 237.88, "v": 44249576 }  // Previous completed session
}
```

**Key Data Rules (CONFIRMED):**
1. **`prevDay.c`** = Previous completed regular session close (REFERENCE PRICE)
   - Handles weekends/holidays automatically - always last trading day
   - This is what we compare against for gap calculations

2. **`min.c`** = Current real-time price (any session: premarket/regular/afterhours)
   - Live price data with 15-minute delay (Starter plan)
   - Updated continuously during extended hours

3. **`day.*`** = Current regular session data
   - **Zeros during premarket/afterhours** (session incomplete)
   - Populates during regular session with running OHLCV
   - Final values after 4:00 PM ET close

**Gap Calculation Formula:**
```
Gap = min.c - prevDay.c
Gap % = (Gap / prevDay.c) × 100

Example: $239.52 - $237.88 = $1.64 (0.69% overnight gap)
```

**Session Detection:**
- Use market status API to determine if current time is premarket/regular/afterhours
- Don't hardcode session times (handles holidays/half-days)
- `min.c` price is always "current" regardless of session

#### **3. Custom Bars API (Extended Hours & Real-Time)**
- **Endpoint:** `/v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}`
- **Purpose:** Get minute-level data INCLUDING extended hours
- **When to Call:**
  - **Pre-market screening** (9:00 AM) - Get 4:00-9:00 AM bars
  - **After-hours screening** (5:00 PM) - Get 4:00-5:00 PM bars
  - **Gap analysis** - Get full day including extended hours
  - **Real-time updates** - Get latest bars for specific stocks
- **Data Stored:**
  ```sql
  -- Populates asset_prices_current table
  INSERT OR REPLACE INTO asset_prices_current (
    asset_id, current_price, session_type,
    bar_timestamp, volume
  )

  -- Updates extended hours in asset_prices_daily
  UPDATE asset_prices_daily SET
    premarket_open = ?, premarket_close = ?,
    afterhours_open = ?, afterhours_close = ?
  ```
- **Session Detection Logic:**
  ```python
  def get_session_type(timestamp):
      hour = timestamp.hour
      minute = timestamp.minute
      time_decimal = hour + minute/60

      if 4 <= time_decimal < 9.5:
          return "premarket"
      elif 9.5 <= time_decimal < 16:
          return "regular"
      elif 16 <= time_decimal < 20:
          return "afterhours"
      else:
          return "closed"
  ```
- **API Optimization:**
  - Only call for stocks in universe or watchlist
  - Cache bars for 5 minutes
  - Batch requests during quiet periods

#### **4. Ticker Details API (Fundamentals)**
- **Endpoint:** `/v3/reference/tickers/{ticker}`
- **Purpose:** Get detailed fundamentals for single ticker
- **When to Call:**
  - When user requests fundamental data
  - Weekly refresh for universe stocks
- **Data Stored:**
  ```sql
  UPDATE asset_fundamentals SET
    market_cap = ?, sector = ?, industry = ?,
    last_updated = CURRENT_TIMESTAMP
  ```

#### **5. News API (Sentiment/Events)**
- **Endpoint:** `/v2/reference/news`
- **Purpose:** Get market-moving news
- **When to Call:**
  - Hourly for general market news
  - On-demand for specific tickers
- **Parameters:**
  - `ticker` - Filter by symbol
  - `published_utc.gte` - Recent news only
  - `limit=10` - Most recent stories
- **Data Stored:**
  ```sql
  INSERT INTO sentiment_events (
    asset_id, event_date, event_title,
    event_url, sentiment_score
  )
  ```

#### **6. Market Status API (Session Detection)**
- **Endpoint:** `/v1/marketstatus/now`
- **Purpose:** Get current market session and exact hours
- **When to Call:**
  - Before gap analysis calculations
  - When determining which session a price belongs to
  - To handle holidays and half-days properly
- **Returns:**
  ```json
  {
    "market": "open",
    "serverTime": "2025-09-18T14:30:00.000Z",
    "exchanges": {
      "nasdaq": "open",
      "nyse": "open"
    },
    "currencies": {...}
  }
  ```
- **Critical Usage:**
  - **Don't hardcode session times** (9:30 AM, etc.)
  - Use this API to determine if current time is premarket/regular/afterhours
  - Essential for knowing which reference price to use in gap calculations

---



