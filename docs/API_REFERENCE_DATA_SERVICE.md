# API Reference: DataService

**Last Updated**: 2025-10-02
**Location**: `src/services/data_service.py`
**Purpose**: Complete reference for TradeScout's central data orchestration service

---

## Overview

**DataService** is the central orchestration layer that coordinates between database managers and API providers. It provides a clean public interface for all data operations in TradeScout.

### Responsibilities

- Initialize database managers and API providers with dependencies
- Coordinate between storage layer (managers) and API layer (providers)
- Provide clean public interface for data access
- Handle force refresh parameters and TTL logic coordination
- Bootstrap reference data from external APIs

### What DataService Does NOT Do

- Make database calls directly (delegates to managers)
- Make API calls directly (delegates to providers)
- Implement TTL logic (delegates to managers via BaseManager)

---

## Constructor

```python
def __init__(self, db_manager, polygon_api_key: str)
```

Initialize data service with dependencies.

**Parameters**:
- `db_manager` (DatabaseManager): Database manager for SQLite operations
- `polygon_api_key` (str): Polygon.io API key for all API providers

**Example**:
```python
from database.database_manager import DatabaseManager
from services.data_service import DataService
import os

db_manager = DatabaseManager("data/tradescout.db")
polygon_api_key = os.getenv("POLYGON_API_KEY")

data_service = DataService(db_manager, polygon_api_key)
```

**Initialization**: The constructor initializes:
- Metadata manager for TTL tracking
- All database managers (ticker, asset, fundamentals, universe, etc.)
- All API providers (Polygon snapshot, tickers, markets, news, etc.)

---

## Snapshot Operations

### get_ticker_snapshot()

```python
def get_ticker_snapshot(
    self,
    symbol: str,
    force_refresh: bool = False
) -> Optional[TickerSnapshot]
```

Get real-time snapshot for a single ticker with automatic cache/refresh logic.

**Parameters**:
- `symbol` (str): Stock symbol (e.g., 'AAPL')
- `force_refresh` (bool): If True, bypass cache and fetch fresh data (default: False)

**Returns**:
- `TickerSnapshot` object or None if not found

**TTL**: 15 minutes

**Example**:
```python
# Get cached if fresh (< 15 min old)
snapshot = data_service.get_ticker_snapshot("AAPL")

# Force fresh fetch from API
snapshot = data_service.get_ticker_snapshot("AAPL", force_refresh=True)

# Access snapshot data
if snapshot:
    print(f"Current: ${snapshot.last_price}")
    print(f"Previous close: ${snapshot.prev_close}")
    print(f"Change: {snapshot.change_percent}%")
```

**TickerSnapshot Fields**:
- `symbol` - Stock symbol
- `prev_close` - Previous trading session close
- `open_price`, `high_price`, `low_price`, `last_price` - Current session OHLC
- `volume` - Trading volume
- `change_percent` - Percentage change from previous close
- `updated_ns` - Polygon's update timestamp (nanoseconds)

### refresh_market_data()

```python
def refresh_market_data(
    self,
    symbols: Optional[List[str]] = None,
    force_refresh: bool = False
) -> Optional[MarketSnapshot]
```

Refresh market data for all universe assets or specific symbols (bulk operation).

**Parameters**:
- `symbols` (Optional[List[str]]): List of symbols to refresh, or None for all (default: None)
- `force_refresh` (bool): If True, bypass TTL and always fetch (default: False)

**Returns**:
- `MarketSnapshot` object or None if skipped due to TTL

**TTL**: 15 minutes (for bulk refresh operation)

**Behavior**:
- Fetches bulk snapshot from Polygon (thousands of tickers in one API call)
- Stores each ticker individually to `asset_prices` table
- Returns None if bulk refresh done recently (within TTL)

**Example**:
```python
# Refresh all universe assets (respects TTL)
market_snapshot = data_service.refresh_market_data()

if market_snapshot:
    print(f"Refreshed {market_snapshot.total_symbols} symbols")
else:
    print("Data is fresh, skipped refresh")

# Refresh specific symbols (bypasses TTL)
symbols = ["AAPL", "MSFT", "TSLA"]
market_snapshot = data_service.refresh_market_data(symbols, force_refresh=True)
```

**MarketSnapshot Fields**:
- `tickers` - Dict[str, TickerSnapshot] of all ticker snapshots
- `total_symbols` - Total number of symbols in snapshot
- `timestamp` - Snapshot timestamp

---

## Asset Operations

### get_asset()

```python
def get_asset(
    self,
    symbol: str,
    force_refresh: bool = False
) -> Optional[Asset]
```

Get asset information with automatic cache/refresh logic.

**Parameters**:
- `symbol` (str): Stock symbol (e.g., 'AAPL')
- `force_refresh` (bool): If True, bypass cache and fetch fresh data (default: False)

**Returns**:
- `Asset` object or None if not found

**TTL**: 3 days

**Example**:
```python
asset = data_service.get_asset("AAPL")

if asset:
    print(f"Name: {asset.name}")
    print(f"Market: {asset.market_id}")
    print(f"Active: {asset.is_active}")
```

**Asset Fields**:
- `id` - Database primary key
- `symbol` - Stock symbol
- `name` - Company name
- `market_id` - Foreign key to markets table
- `asset_type` - 'stock', 'etf', etc.
- `is_active` - Trading status
- `currency` - Trading currency

### get_asset_with_market()

```python
def get_asset_with_market(
    self,
    symbol: str,
    force_refresh: bool = False
) -> Optional[Tuple[Asset, Market]]
```

Get asset with market information in a single call.

**Parameters**:
- `symbol` (str): Stock symbol
- `force_refresh` (bool): Bypass cache

**Returns**:
- Tuple of (Asset, Market) or None if not found

**Example**:
```python
result = data_service.get_asset_with_market("AAPL")

if result:
    asset, market = result
    print(f"{asset.symbol} - {asset.name}")
    print(f"Market: {market.name} ({market.code})")
    print(f"Timezone: {market.timezone}")
```

### bootstrap_assets()

```python
def bootstrap_assets(
    self,
    market: str = "stocks",
    active: bool = True
) -> int
```

Bootstrap all assets from Polygon tickers API (bulk operation).

**Parameters**:
- `market` (str): Market type - "stocks", "crypto", "forex" (default: "stocks")
- `active` (bool): Only fetch active tickers (default: True)

**Returns**:
- Number of assets successfully stored

**Operation**: Fetches all tickers from Polygon `/v3/reference/tickers` API and stores to database.

**Example**:
```python
# Bootstrap all active stocks
count = data_service.bootstrap_assets(market="stocks", active=True)
print(f"Bootstrapped {count} assets")
```

**Note**: This can fetch 10,000+ tickers. Runs automatically during initial setup.

---

## Fundamentals Operations

### get_fundamentals()

```python
def get_fundamentals(
    self,
    symbol: str,
    force_refresh: bool = False
) -> Optional[AssetFundamentals]
```

Get asset fundamentals with automatic cache/refresh logic.

**Parameters**:
- `symbol` (str): Stock symbol
- `force_refresh` (bool): Bypass cache

**Returns**:
- `AssetFundamentals` object or None if not found

**TTL**: 1 week

**Example**:
```python
fundamentals = data_service.get_fundamentals("AAPL")

if fundamentals:
    print(f"Market Cap: ${fundamentals.market_cap / 100:,.0f}")
    print(f"Sector: {fundamentals.sector}")
    print(f"Industry: {fundamentals.industry}")
    print(f"P/E Ratio: {fundamentals.pe_ratio}")
```

**AssetFundamentals Fields**:
- `asset_id` - Foreign key to assets table
- `market_cap` - Market capitalization (in cents)
- `sector` - Business sector
- `industry` - Industry classification
- `shares_outstanding` - Total shares
- `avg_volume_30d` - 30-day average volume
- `beta` - Volatility metric
- `pe_ratio` - Price-to-earnings ratio
- `dividend_yield` - Dividend yield percentage

### bootstrap_fundamentals()

```python
def bootstrap_fundamentals(
    self,
    limit: Optional[int] = None
) -> int
```

Bootstrap fundamentals for all assets in database.

**Parameters**:
- `limit` (Optional[int]): Optional limit on number of assets to process (default: None = all)

**Returns**:
- Number of fundamentals successfully stored

**Operation**: For each asset, fetches ticker details from Polygon and extracts fundamentals.

**Example**:
```python
# Bootstrap first 100 assets (testing)
count = data_service.bootstrap_fundamentals(limit=100)

# Bootstrap all assets (can take time!)
count = data_service.bootstrap_fundamentals()
print(f"Bootstrapped {count} fundamentals")
```

**Note**: Makes one API call per asset. Use limit for batch processing.

---

## Universe Operations

### get_universe()

```python
def get_universe(self, universe_name: str) -> Optional[Universe]
```

Get universe by name.

**Parameters**:
- `universe_name` (str): Universe name (e.g., "default_universe")

**Returns**:
- `Universe` object or None if not found

**Example**:
```python
universe = data_service.get_universe("default_universe")

if universe:
    print(f"Name: {universe.name}")
    print(f"Description: {universe.description}")
    print(f"Active: {universe.is_active}")
```

### get_active_universe()

```python
def get_active_universe(self) -> Optional[Universe]
```

Get the currently active universe.

**Returns**:
- Active `Universe` object or None

**Example**:
```python
universe = data_service.get_active_universe()
if universe:
    print(f"Active universe: {universe.name}")
```

### set_active_universe()

```python
def set_active_universe(self, universe_name: str) -> bool
```

Set a universe as active (deactivates others).

**Parameters**:
- `universe_name` (str): Universe name to activate

**Returns**:
- True if successful, False otherwise

**Example**:
```python
success = data_service.set_active_universe("default_universe")
if success:
    print("Universe activated successfully")
```

### get_active_universe_symbols()

```python
def get_active_universe_symbols(self) -> List[str]
```

Get all symbols in the active universe.

**Returns**:
- List of symbol strings

**Example**:
```python
symbols = data_service.get_active_universe_symbols()
print(f"Universe has {len(symbols)} symbols")
print(f"First 5: {symbols[:5]}")
```

### bootstrap_universes()

```python
def bootstrap_universes(
    self,
    universe_name: str = "default_universe",
    force_refresh: bool = False
) -> Dict[str, int]
```

Bootstrap a universe by filtering assets based on configuration criteria.

**Parameters**:
- `universe_name` (str): Universe name from config (default: "default_universe")
- `force_refresh` (bool): Force re-creation even if exists (default: False)

**Returns**:
- Dictionary with statistics: `{"created": 1, "memberships_added": 7513}`

**Operation**: Applies filters from `config/universe_config.py` to create filtered universe.

**Example**:
```python
stats = data_service.bootstrap_universes()
print(f"Created {stats['created']} universe")
print(f"Added {stats['memberships_added']} members")
```

**Filters Applied** (from config):
- Exchange filtering (XNYS, XNAS)
- Market cap thresholds
- Symbol patterns (length, characters)
- Volume thresholds
- Asset type filtering
- Exclusions (preferred stocks, warrants, etc.)

---

## Market Operations

### get_market()

```python
def get_market(self, market_code: str) -> Optional[Market]
```

Get market/exchange information by code.

**Parameters**:
- `market_code` (str): Exchange code (e.g., "XNYS", "XNAS")

**Returns**:
- `Market` object or None if not found

**Example**:
```python
market = data_service.get_market("XNAS")

if market:
    print(f"Name: {market.name}")
    print(f"Timezone: {market.timezone}")
    print(f"Regular hours: {market.regular_open_time} - {market.regular_close_time}")
```

**Market Fields**:
- `id` - Database primary key
- `code` - MIC code (XNYS, XNAS, etc.)
- `name` - Exchange name
- `timezone` - Trading timezone
- `currency` - Trading currency
- `premarket_start_time`, `premarket_end_time` - Premarket hours
- `regular_open_time`, `regular_close_time` - Regular session hours
- `afterhours_start_time`, `afterhours_end_time` - After-hours times

### get_all_markets()

```python
def get_all_markets(self, active_only: bool = True) -> List[Market]
```

Get all markets/exchanges.

**Parameters**:
- `active_only` (bool): Filter to active markets only (default: True)

**Returns**:
- List of Market objects

**Example**:
```python
markets = data_service.get_all_markets()
for market in markets:
    print(f"{market.code} - {market.name}")
```

### bootstrap_markets()

```python
def bootstrap_markets(
    self,
    asset_class: str = "stocks",
    locale: str = "us"
) -> int
```

Bootstrap markets/exchanges from Polygon API.

**Parameters**:
- `asset_class` (str): Asset class filter (default: "stocks")
- `locale` (str): Locale filter (default: "us")

**Returns**:
- Number of markets successfully stored

**Operation**: Fetches from Polygon `/v3/reference/exchanges` API.

**Example**:
```python
count = data_service.bootstrap_markets(asset_class="stocks", locale="us")
print(f"Bootstrapped {count} markets")
```

---

## Market Holidays Operations

### get_market_holidays()

```python
def get_market_holidays(
    self,
    force_refresh: bool = False
) -> List[MarketHoliday]
```

Get market holidays with automatic cache/refresh logic.

**Parameters**:
- `force_refresh` (bool): Bypass cache

**Returns**:
- List of MarketHoliday objects

**TTL**: 30 days

**Example**:
```python
holidays = data_service.get_market_holidays()

for holiday in holidays:
    print(f"{holiday.date}: {holiday.name} ({holiday.status})")
```

**MarketHoliday Fields**:
- `date` - Holiday date (YYYY-MM-DD string)
- `name` - Holiday name
- `status` - "closed" or "early_close"

### get_upcoming_holidays()

```python
def get_upcoming_holidays(
    self,
    from_date: Optional[date] = None
) -> List[MarketHoliday]
```

Get upcoming holidays from a specific date.

**Parameters**:
- `from_date` (Optional[date]): Starting date (default: None = today)

**Returns**:
- List of future MarketHoliday objects

**Example**:
```python
from datetime import date

# Get holidays from today
upcoming = data_service.get_upcoming_holidays()

# Get holidays from specific date
future_date = date(2025, 12, 1)
december_holidays = data_service.get_upcoming_holidays(from_date=future_date)
```

---

## Provider Operations

### bootstrap_providers()

```python
def bootstrap_providers(self) -> int
```

Bootstrap data provider configuration (Polygon.io).

**Returns**:
- Number of providers configured (always 1)

**Operation**: Stores hardcoded Polygon provider configuration.

**Example**:
```python
count = data_service.bootstrap_providers()
print(f"Configured {count} provider(s)")
```

---

## Sentiment Operations

### bootstrap_sentiment_types()

```python
def bootstrap_sentiment_types(self) -> int
```

Bootstrap sentiment event type definitions.

**Returns**:
- Number of sentiment types created

**Operation**: Creates predefined sentiment types (news_positive, news_negative, etc.)

**Example**:
```python
count = data_service.bootstrap_sentiment_types()
print(f"Created {count} sentiment type(s)")
```

### get_sentiment_events()

```python
def get_sentiment_events(
    self,
    asset_id: Optional[int] = None,
    sentiment_type_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None
) -> List[SentimentEvent]
```

Get sentiment events with optional filtering.

**Parameters**:
- `asset_id` (Optional[int]): Filter by asset
- `sentiment_type_id` (Optional[int]): Filter by type
- `start_date` (Optional[date]): Filter by start date
- `end_date` (Optional[date]): Filter by end date

**Returns**:
- List of SentimentEvent objects

**Example**:
```python
from datetime import date, timedelta

# Get events for specific asset
events = data_service.get_sentiment_events(asset_id=123)

# Get recent events (last 7 days)
end = date.today()
start = end - timedelta(days=7)
recent_events = data_service.get_sentiment_events(start_date=start, end_date=end)

for event in recent_events:
    print(f"{event.event_date}: {event.value}")
```

---

## Statistics Operations

All `get_*_stats()` methods return dictionaries with relevant statistics for monitoring and debugging.

### get_ticker_snapshot_stats()

```python
def get_ticker_snapshot_stats(self) -> dict
```

Get ticker snapshot statistics.

**Returns**:
- Dict with last update time and ticker count

### get_asset_stats()

```python
def get_asset_stats(self) -> dict
```

Get asset statistics.

**Returns**:
- Dict with total assets, by market breakdown, active count

### get_fundamentals_stats()

```python
def get_fundamentals_stats(self) -> dict
```

Get fundamentals coverage statistics.

**Returns**:
- Dict with coverage percentage, total count

### get_universe_stats()

```python
def get_universe_stats(self, name: str) -> Optional[Dict[str, Any]]
```

Get statistics for a specific universe.

**Parameters**:
- `name` (str): Universe name

**Returns**:
- Dict with member count, market breakdown, or None if not found

**Example**:
```python
stats = data_service.get_universe_stats("default_universe")

if stats:
    print(f"Universe: {stats['universe_name']}")
    print(f"Members: {stats['total_members']}")
    print("\nBy Market:")
    for code, name, count in stats['by_market']:
        print(f"  {code} ({name}): {count}")
```

---

## Health Check Operations

### check_api_health()

```python
def check_api_health(self) -> bool
```

Check if Polygon API is accessible.

**Returns**:
- True if API is healthy, False otherwise

**Example**:
```python
if data_service.check_api_health():
    print("✓ API is accessible")
else:
    print("✗ API connection failed")
```

---

## Database Query Operations

### execute_screener_query()

```python
def execute_screener_query(self, sql: str) -> List[Dict[str, Any]]
```

Execute a screener SQL query.

**Parameters**:
- `sql` (str): Complete SQL query

**Returns**:
- List of result dictionaries

**Example**:
```python
sql = """
    SELECT symbol, name, day_close
    FROM assets a
    JOIN asset_prices ap ON a.id = ap.asset_id
    WHERE day_close > 100
    LIMIT 10
"""

results = data_service.execute_screener_query(sql)
for row in results:
    print(f"{row['symbol']}: ${row['day_close']}")
```

**Note**: Used by screener engine to run dynamic queries.

---

## Usage Patterns

### Standard Get Pattern

```python
# Get with automatic cache/refresh
entity = data_service.get_entity(key)

# Force refresh
entity = data_service.get_entity(key, force_refresh=True)

# Check if entity exists
if entity:
    # Use entity data
    pass
```

### Bootstrap Pattern

```python
# Bootstrap in dependency order
data_service.bootstrap_providers()
data_service.bootstrap_markets()
data_service.bootstrap_assets()
data_service.bootstrap_fundamentals(limit=100)
data_service.bootstrap_universes()
data_service.bootstrap_sentiment_types()
```

### Statistics Pattern

```python
# Get statistics for monitoring
asset_stats = data_service.get_asset_stats()
universe_stats = data_service.get_universe_stats("default_universe")

print(f"Total assets: {asset_stats['total']}")
print(f"Universe members: {universe_stats['total_members']}")
```

---

## See Also

- **Base Classes**: `docs/API_REFERENCE_BASE_CLASSES.md`
- **Managers**: `docs/API_REFERENCE_MANAGERS.md`
- **Providers**: `docs/API_REFERENCE_PROVIDERS.md`
- **Architecture**: `docs/ARCHITECTURE_MANAGERS.md`
- **Database**: `docs/DATABASE.md`
