# TradeScout Database Schema

**Last Updated**: September 22, 2025
**Database Type**: SQLite
**Schema Version**: 001

## Overview

SQLite database storing market data, assets, pricing, and system metadata. Contains 11 tables organized into logical groups: providers, assets, pricing, universes, sentiment, and system metadata.

## Database Tables (11 Total)

### Provider and Market Tables

#### 1. providers
Data source provider definitions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique provider ID |
| name | TEXT | NOT NULL UNIQUE | Provider identifier |
| display_name | TEXT | NOT NULL | Human-readable name |
| base_url | TEXT | | API base URL |
| api_key_required | BOOLEAN | DEFAULT TRUE | Whether API key required |
| is_active | BOOLEAN | DEFAULT TRUE | Currently active |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |

#### 2. markets
Exchange and market definitions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique market ID |
| code | TEXT | NOT NULL UNIQUE | Exchange code (XNYS, XNAS) |
| name | TEXT | NOT NULL | Exchange full name |
| country | TEXT | DEFAULT 'US' | Country code |
| timezone | TEXT | DEFAULT 'America/New_York' | Market timezone |
| currency | TEXT | DEFAULT 'USD' | Trading currency |
| premarket_start_time | TIME | | Pre-market session start |
| premarket_end_time | TIME | | Pre-market session end |
| regular_open_time | TIME | | Regular session open |
| regular_close_time | TIME | | Regular session close |
| afterhours_start_time | TIME | | After-hours session start |
| afterhours_end_time | TIME | | After-hours session end |
| is_active | BOOLEAN | DEFAULT TRUE | Currently active |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |
| updated_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | Last update timestamp |

### Asset Tables

#### 3. assets
Core asset/ticker data.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique asset ID |
| symbol | TEXT | NOT NULL UNIQUE | Trading symbol (AAPL, MSFT) |
| name | TEXT | NOT NULL | Asset name |
| market_id | INTEGER | NOT NULL, FK→markets.id | Market reference |
| asset_type | TEXT | | Type: stock, etf, crypto, etc. |
| asset_class | TEXT | | Class: equity, commodity, etc. |
| currency | TEXT | | Trading currency |
| lot_size | INTEGER | | Minimum trading unit |
| tick_size | DECIMAL(10,6) | | Minimum price movement |
| is_active | BOOLEAN | | Currently trading |
| is_delisted | BOOLEAN | | No longer trading |
| listing_date | DATE | | Trading start date |
| delisting_date | DATE | | Trading end date |
| provider_id | INTEGER | NOT NULL, FK→providers.id | Provider reference |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |
| updated_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | Last update timestamp |

#### 4. asset_fundamentals
Fundamental data for assets (one-to-one with assets).

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| asset_id | INTEGER | PRIMARY KEY, FK→assets.id | Asset reference |
| company_name | TEXT | | Company display name |
| sector | TEXT | | Business sector |
| industry | TEXT | | Business industry |
| sic_code | TEXT | | Standard Industrial Classification |
| market_cap | BIGINT | | Market capitalization (cents) |
| shares_outstanding | BIGINT | | Outstanding shares |
| avg_volume_30d | BIGINT | | 30-day average volume |
| beta | DECIMAL(6,3) | | Beta coefficient |
| pe_ratio | DECIMAL(8,2) | | Price to earnings ratio |
| dividend_yield | DECIMAL(6,4) | | Annual dividend yield |
| provider_id | INTEGER | FK→providers.id | Provider reference |
| last_updated | DATETIME | | Last update timestamp |

### Pricing Tables

#### 5. asset_prices
Snapshot pricing data from providers.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique price record ID |
| asset_id | INTEGER | NOT NULL, FK→assets.id | Asset reference |
| symbol | TEXT | NOT NULL | Trading symbol (denormalized) |
| provider_id | INTEGER | NOT NULL, FK→providers.id | Provider reference |
| provider_updated_at | BIGINT | | Provider timestamp (nanoseconds) |
| trade_date | DATE | | Trading date from provider |
| **Previous Day Fields** | | | |
| prevday_open | DECIMAL(12,4) | | Previous day open |
| prevday_high | DECIMAL(12,4) | | Previous day high |
| prevday_low | DECIMAL(12,4) | | Previous day low |
| prevday_close | DECIMAL(12,4) | | Previous day close |
| prevday_volume | BIGINT | | Previous day volume |
| prevday_vwap | DECIMAL(12,4) | | Previous day VWAP |
| **Current Day Fields** | | | |
| day_open | DECIMAL(12,4) | | Current day open |
| day_high | DECIMAL(12,4) | | Current day high |
| day_low | DECIMAL(12,4) | | Current day low |
| day_close | DECIMAL(12,4) | | Current day close |
| day_volume | BIGINT | | Current day volume |
| day_vwap | DECIMAL(12,4) | | Current day VWAP |
| **Last Minute Fields** | | | |
| min_timestamp | BIGINT | | Last minute timestamp (milliseconds) |
| min_open | DECIMAL(12,4) | | Last minute open |
| min_high | DECIMAL(12,4) | | Last minute high |
| min_low | DECIMAL(12,4) | | Last minute low |
| min_close | DECIMAL(12,4) | | Last minute close |
| min_volume | BIGINT | | Last minute volume |
| min_vwap | DECIMAL(12,4) | | Last minute VWAP |
| min_accumulated_volume | BIGINT | | Accumulated volume |
| min_num_trades | INTEGER | | Number of trades |
| updated_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | Record update timestamp |

**Unique Constraint**: (asset_id, provider_id, provider_updated_at)

### Universe Tables

#### 6. universes
Asset grouping definitions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique universe ID |
| name | TEXT | NOT NULL UNIQUE | Universe identifier |
| description | TEXT | | Human-readable description |
| min_market_cap | BIGINT | | Minimum market cap filter |
| min_volume | BIGINT | | Minimum volume filter |
| max_assets | INTEGER | | Maximum asset count |
| is_active | BOOLEAN | DEFAULT TRUE | Currently active |
| last_updated | DATETIME | | Last membership update |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |
| updated_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | Last modification timestamp |

#### 7. universe_memberships
Asset-universe many-to-many relationships.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique membership ID |
| universe_id | INTEGER | NOT NULL, FK→universes.id | Universe reference |
| asset_id | INTEGER | NOT NULL, FK→assets.id | Asset reference |
| added_date | DATE | | Addition date |
| removed_date | DATE | | Removal date |
| reason | TEXT | | Addition/removal reason |
| is_active | BOOLEAN | | Currently active membership |

**Unique Constraint**: (universe_id, asset_id, added_date)

### Sentiment Tables

#### 8. sentiment_types
Sentiment event type definitions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique sentiment type ID |
| name | TEXT | NOT NULL UNIQUE | Event type identifier |
| description | TEXT | | Human-readable description |
| category | TEXT | | Category grouping |
| parameters | TEXT | | JSON calculation parameters |
| is_active | BOOLEAN | | Currently active |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |

#### 9. sentiment_events
Market sentiment and event records.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique event ID |
| asset_id | INTEGER | NOT NULL, FK→assets.id | Asset reference |
| sentiment_type_id | INTEGER | NOT NULL, FK→sentiment_types.id | Sentiment type reference |
| event_date | DATE | | Event occurrence date |
| event_time | TIME | | Event occurrence time |
| session | TEXT | | Trading session context |
| value | DECIMAL(12,4) | | Event measurement |
| magnitude | TEXT | | Event magnitude classification |
| details | TEXT | | JSON additional data |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |

### System Tables

#### 10. market_snapshot_metadata
Market-wide snapshot operation tracking.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique snapshot run ID |
| started_at | DATETIME | | Snapshot start time |
| completed_at | DATETIME | | Snapshot completion time |
| total_symbols | INTEGER | | Symbols attempted |
| successful_updates | INTEGER | | Successful update count |
| failed_updates | INTEGER | | Failed update count |
| status | TEXT | | Status: running, completed, failed, partial |
| error_message | TEXT | | Error details |
| api_calls_made | INTEGER | | API call count |
| created_at | DATETIME | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |

#### 11. schema_versions
Database schema migration tracking.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| id | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique version ID |
| version | TEXT | NOT NULL UNIQUE | Version identifier |
| description | TEXT | | Migration description |
| applied_at | DATETIME | | Application timestamp |

## Database Indexes

### Performance Indexes
- **idx_asset_prices_symbol** (asset_prices.symbol)
- **idx_asset_prices_asset** (asset_prices.asset_id)
- **idx_asset_prices_date** (asset_prices.trade_date)
- **idx_asset_prices_updated** (asset_prices.updated_at)
- **idx_assets_symbol** (assets.symbol)
- **idx_assets_market** (assets.market_id)
- **idx_assets_type** (assets.asset_type)
- **idx_assets_active** (assets.is_active)
- **idx_fundamentals_sector** (asset_fundamentals.sector)
- **idx_fundamentals_industry** (asset_fundamentals.industry)
- **idx_fundamentals_market_cap** (asset_fundamentals.market_cap)
- **idx_universe_memberships_universe** (universe_memberships.universe_id)
- **idx_universe_memberships_asset** (universe_memberships.asset_id)
- **idx_universe_memberships_active** (universe_memberships.is_active)
- **idx_sentiment_events_asset** (sentiment_events.asset_id)
- **idx_sentiment_events_type** (sentiment_events.sentiment_type_id)
- **idx_sentiment_events_date** (sentiment_events.event_date)
- **idx_snapshot_metadata_completed** (market_snapshot_metadata.completed_at)
- **idx_snapshot_metadata_status** (market_snapshot_metadata.status)

## Foreign Key Relationships

```
providers ←─ assets
         ←─ asset_fundamentals
         ←─ asset_prices

markets ←─ assets

assets ←─ asset_fundamentals (1:1)
       ←─ asset_prices (1:many)
       ←─ universe_memberships (1:many)
       ←─ sentiment_events (1:many)

universes ←─ universe_memberships (1:many)

sentiment_types ←─ sentiment_events (1:many)
```

## Database File Location

- **Development**: `data/tradescout.db`
- **Schema File**: `src/database/schema/001_initial_schema.sql`
- **Migrations**: Handled by `DatabaseManager` class

## Current Data Volumes

| Table | Records | Description |
|-------|---------|-------------|
| providers | 1 | Polygon.io only |
| markets | 7 | US exchanges (XNYS, XNAS, ARCX, etc.) |
| assets | 11,745 | All tickers from Polygon API |
| universe_memberships | 7,513 | Default universe filtered assets |
| universes | 1 | Default universe only |
| schema_versions | 1 | Initial schema version |
| Others | 0 | Not yet populated |

---

This schema supports comprehensive market data storage, asset management, pricing history, universe-based screening, and sentiment analysis for the TradeScout trading system.