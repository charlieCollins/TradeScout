# TradeScout Database Schema

## Overview
SQLite database storing market data, assets, pricing, and system metadata for gap analysis and market screening.

## Tables

### 1. providers
Stores data provider references.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-incrementing ID |
| name | TEXT UNIQUE | Provider name (e.g., 'polygon', 'yahoo_finance') |
| display_name | TEXT | Display name (e.g., 'Polygon.io') |
| base_url | TEXT | API base URL |
| api_key_required | BOOLEAN | Whether API key is required |
| is_active | BOOLEAN | Currently active |
| created_at | DATETIME | Record creation timestamp |

### 2. markets
Stores exchange and market information.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-incrementing ID |
| code | TEXT UNIQUE | Exchange code (e.g., 'NYSE', 'NASDAQ') |
| name | TEXT | Exchange name (e.g., 'New York Stock Exchange') |
| country | TEXT | Country code (e.g., 'US') |
| timezone | TEXT | Timezone (e.g., 'America/New_York') |
| currency | TEXT | Trading currency (e.g., 'USD') |
| premarket_start_time | TIME | Pre-market session start |
| premarket_end_time | TIME | Pre-market session end |
| regular_open_time | TIME | Regular session open |
| regular_close_time | TIME | Regular session close |
| afterhours_start_time | TIME | After-hours session start |
| afterhours_end_time | TIME | After-hours session end |
| is_active | BOOLEAN | Whether market is currently active |
| created_at | DATETIME | Record creation timestamp |
| updated_at | DATETIME | Last update timestamp |

### 3. assets
Stores tradeable instruments.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-incrementing ID |
| symbol | TEXT UNIQUE | Trading symbol (e.g., 'AAPL') |
| name | TEXT | Asset name (e.g., 'Apple Inc.') |
| market_id | INTEGER FK | Reference to markets table |
| asset_type | TEXT | Type: 'stock', 'etf', 'crypto', 'option', 'forex' |
| asset_class | TEXT | Class: 'equity', 'commodity', 'currency', 'crypto', 'derivative' |
| currency | TEXT | Trading currency |
| lot_size | INTEGER | Minimum trading unit |
| tick_size | DECIMAL(10,6) | Minimum price movement |
| is_active | BOOLEAN | Currently trading |
| is_delisted | BOOLEAN | No longer trading |
| listing_date | DATE | When asset started trading |
| delisting_date | DATE | When asset stopped trading |
| provider_id | INTEGER FK | Reference to providers table |
| created_at | DATETIME | Record creation timestamp |
| updated_at | DATETIME | Last update timestamp |

### 4. asset_fundamentals
Stores fundamental data for assets (one-to-one with assets table).

| Column | Type | Description |
|--------|------|-------------|
| asset_id | INTEGER PRIMARY KEY FK | Reference to assets table |
| company_name | TEXT | Company name for display |
| sector | TEXT | Business sector |
| industry | TEXT | Business industry |
| sic_code | TEXT | Standard Industrial Classification |
| market_cap | BIGINT | Market capitalization in cents |
| shares_outstanding | BIGINT | Outstanding shares |
| avg_volume_30d | BIGINT | 30-day average volume |
| beta | DECIMAL(6,3) | Beta coefficient |
| pe_ratio | DECIMAL(8,2) | Price to earnings ratio |
| dividend_yield | DECIMAL(6,4) | Annual dividend yield |
| provider_id | INTEGER FK | Reference to providers table |
| last_updated | DATETIME | Last update timestamp |

### 5. asset_prices
Stores snapshot pricing data from providers.

**Important Semantic Notes:**
- **"day"** = Most recent trading day relative to 'updated' timestamp (On Saturday, this is Friday. During Monday premarket, this is still Friday)
- **"prevDay"** = Trading day before "day" (On Saturday, this is Thursday. During Monday premarket, this is still Thursday)
- **"min"** = Last traded minute bar before 'updated' timestamp (Could be regular, premarket, or afterhours depending on when fetched)

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-incrementing ID |
| asset_id | INTEGER FK | Reference to assets table |
| symbol | TEXT | Trading symbol (redundant for queries) |
| provider_id | INTEGER FK | Reference to providers table |
| provider_updated_at | BIGINT | Provider's update timestamp (nanoseconds for Polygon) |
| trade_date | DATE | Trading date from provider |
| **Previous Day Data** | | |
| prevday_open | DECIMAL(12,4) | Previous day open price |
| prevday_high | DECIMAL(12,4) | Previous day high price |
| prevday_low | DECIMAL(12,4) | Previous day low price |
| prevday_close | DECIMAL(12,4) | Previous day close - THE reference price |
| prevday_volume | BIGINT | Previous day volume |
| prevday_vwap | DECIMAL(12,4) | Previous day VWAP |
| **Current Day Data** | | |
| day_open | DECIMAL(12,4) | Current day open price |
| day_high | DECIMAL(12,4) | Current day high price |
| day_low | DECIMAL(12,4) | Current day low price |
| day_close | DECIMAL(12,4) | Current day close (4:00 PM) |
| day_volume | BIGINT | Current day volume |
| day_vwap | DECIMAL(12,4) | Current day VWAP |
| **Last Minute Bar** | | |
| min_timestamp | BIGINT | Last minute timestamp (milliseconds) |
| min_open | DECIMAL(12,4) | Last minute open |
| min_high | DECIMAL(12,4) | Last minute high |
| min_low | DECIMAL(12,4) | Last minute low |
| min_close | DECIMAL(12,4) | Last traded price |
| min_volume | BIGINT | Last minute volume |
| min_vwap | DECIMAL(12,4) | Last minute VWAP |
| min_accumulated_volume | BIGINT | Accumulated volume |
| min_num_trades | INTEGER | Number of trades |
| updated_at | DATETIME | When we updated this record |

**Unique constraint**: (asset_id, provider_id, provider_updated_at)

### 6. universes
Stores asset groupings for screening.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-incrementing ID |
| name | TEXT UNIQUE | Universe identifier |
| description | TEXT | Human-readable description |
| min_market_cap | BIGINT | Minimum market cap |
| min_volume | BIGINT | Minimum volume |
| max_assets | INTEGER | Maximum number of assets |
| is_active | BOOLEAN | Currently active |
| last_updated | DATETIME | Last update timestamp |
| created_at | DATETIME | Creation timestamp |
| updated_at | DATETIME | Last modification timestamp |

### 7. universe_memberships
Maps assets to universes (many-to-many).

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-incrementing ID |
| universe_id | INTEGER FK | Reference to universes table |
| asset_id | INTEGER FK | Reference to assets table |
| added_date | DATE | When asset was added |
| removed_date | DATE | When asset was removed |
| reason | TEXT | Addition/removal reason |
| is_active | BOOLEAN | Currently in universe |

**Unique constraint**: (universe_id, asset_id, added_date)

### 8. sentiment_types
Defines types of sentiment events.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-incrementing ID |
| name | TEXT UNIQUE | Event type identifier (e.g., 'gap_up', 'gap_down') |
| description | TEXT | Human-readable description |
| category | TEXT | Category: 'price_action', 'volume', 'technical' |
| parameters | TEXT | JSON calculation parameters |
| is_active | BOOLEAN | Currently active |
| created_at | DATETIME | Creation timestamp |

### 9. sentiment_events
Stores sentiment and market events.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-incrementing ID |
| asset_id | INTEGER FK | Reference to assets table |
| sentiment_type_id | INTEGER FK | Reference to sentiment_types table |
| event_date | DATE | When event occurred |
| event_time | TIME | Event time |
| session | TEXT | Session: 'premarket', 'regular', 'afterhours' |
| value | DECIMAL(12,4) | Event measurement (e.g., gap percentage) |
| magnitude | TEXT | Magnitude: 'small', 'medium', 'large', 'extreme' |
| details | TEXT | JSON additional data |
| created_at | DATETIME | Creation timestamp |

### 10. market_snapshot_metadata
Tracks market-wide snapshot update operations.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-incrementing ID |
| started_at | DATETIME | When snapshot run started |
| completed_at | DATETIME | When snapshot run completed |
| total_symbols | INTEGER | Number of symbols attempted |
| successful_updates | INTEGER | Successfully updated count |
| failed_updates | INTEGER | Failed update count |
| status | TEXT | Status: 'running', 'completed', 'failed', 'partial' |
| error_message | TEXT | Error message if failed |
| api_calls_made | INTEGER | Number of API calls made |
| created_at | DATETIME | Creation timestamp |

### 11. schema_versions
Tracks schema migrations.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Auto-incrementing ID |
| version | TEXT UNIQUE | Version number |
| description | TEXT | Migration description |
| applied_at | DATETIME | When applied |

**Default Data:** Initial schema version '001' is automatically inserted during database creation.

## Indexes

### asset_prices indexes
- idx_asset_prices_symbol (symbol)
- idx_asset_prices_asset (asset_id)
- idx_asset_prices_date (trade_date)
- idx_asset_prices_updated (updated_at)

### Other key indexes
- idx_assets_symbol (assets.symbol)
- idx_assets_market (assets.market_id)
- idx_assets_type (assets.asset_type)
- idx_assets_active (assets.is_active)
- idx_fundamentals_sector (asset_fundamentals.sector)
- idx_fundamentals_industry (asset_fundamentals.industry)
- idx_fundamentals_market_cap (asset_fundamentals.market_cap)
- idx_universe_memberships_universe (universe_memberships.universe_id)
- idx_universe_memberships_asset (universe_memberships.asset_id)
- idx_universe_memberships_active (universe_memberships.is_active)
- idx_sentiment_events_asset (sentiment_events.asset_id)
- idx_sentiment_events_type (sentiment_events.sentiment_type_id)
- idx_sentiment_events_date (sentiment_events.event_date)
- idx_snapshot_metadata_completed (market_snapshot_metadata.completed_at)
- idx_snapshot_metadata_status (market_snapshot_metadata.status)

## Key Relationships
- assets → markets (many-to-one)
- assets → providers (many-to-one)
- asset_fundamentals → assets (one-to-one)
- asset_fundamentals → providers (many-to-one)
- asset_prices → assets (many-to-one)
- asset_prices → providers (many-to-one)
- universe_memberships → universes (many-to-one)
- universe_memberships → assets (many-to-one)
- sentiment_events → assets (many-to-one)
- sentiment_events → sentiment_types (many-to-one)

## Default Data

### Providers
- polygon (Polygon.io)
- yahoo_finance (Yahoo Finance)
- finnhub (Finnhub)

### Markets
- NYSE (New York Stock Exchange)
- NASDAQ (NASDAQ Stock Market)

### Sentiment Types
- gap_up (Opening price significantly higher than previous close)
- gap_down (Opening price significantly lower than previous close)
- volume_spike (Abnormally high trading volume)