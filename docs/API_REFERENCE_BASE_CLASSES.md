# API Reference: Base Classes

**Last Updated**: 2025-10-02
**Purpose**: Complete reference documentation for TradeScout base classes

---

## Overview

TradeScout's architecture is built on two foundational base classes that establish patterns for all data access and external API integration:

- **BaseManager** - Abstract base for all database managers
- **BaseAPIProvider** - Abstract base for all API providers

All concrete managers and providers inherit from these classes and implement their abstract methods.

---

## BaseManager

**Location**: `src/database/managers/base_manager.py`

**Purpose**: Abstract base class for all database managers that handle entity persistence, retrieval, and TTL-based caching.

### Responsibilities

Database managers handle:
- Direct database read/write operations for their entity type
- TTL-based refresh logic (deciding when to fetch fresh data)
- Metadata tracking for operation-level cache validation

Database managers do NOT:
- Make API calls (handled by API providers)
- Handle authentication or rate limiting (handled by API providers)
- Contain business logic (handled by service layer)

### Constructor

```python
def __init__(self, db_manager, metadata_manager)
```

**Parameters**:
- `db_manager` (DatabaseManager): Database manager instance for SQLite operations
- `metadata_manager` (DataUpdateMetadataManager): Manager for TTL tracking and update recording

**Example**:
```python
from database.database_manager import DatabaseManager
from database.managers import DataUpdateMetadataManager, TickerSnapshotManager

db_manager = DatabaseManager("tradescout.db")
metadata_manager = DataUpdateMetadataManager(db_manager)
ticker_manager = TickerSnapshotManager(db_manager, metadata_manager)
```

### Public Methods

#### get_or_fetch()

```python
def get_or_fetch(
    self,
    key: str,
    fetch_fn: Callable,
    force_refresh: bool = False
) -> Optional[Any]
```

Get data from database or fetch fresh data if stale.

This is the main entry point for data access. It decides whether to:
1. Force refresh (if force_refresh=True): Always call fetch_fn
2. Use cached data (if TTL valid): Read from database
3. Fetch fresh data (if TTL expired): Call fetch_fn and store result

**Parameters**:
- `key` (str): Entity identifier (e.g., symbol, date, etc.)
- `fetch_fn` (Callable): Callback function that fetches fresh data (provided by orchestration layer)
- `force_refresh` (bool): If True, bypass TTL check and always fetch fresh data (default: False)

**Returns**:
- Entity object or None if error

**Example**:
```python
# Normal fetch (respects TTL)
ticker = ticker_manager.get_or_fetch(
    key="AAPL",
    fetch_fn=lambda: polygon_provider.fetch_single_ticker("AAPL"),
    force_refresh=False
)

# Force refresh (bypasses TTL)
ticker = ticker_manager.get_or_fetch(
    key="AAPL",
    fetch_fn=lambda: polygon_provider.fetch_single_ticker("AAPL"),
    force_refresh=True
)
```

**Data Flow**:
1. If `force_refresh=True`: Skip to step 4
2. Check if data is stale using `_is_data_stale()`
3. If fresh: Return `get_entity_from_database(key)`
4. If stale: Call `fetch_fn()`
5. If fetch successful: Call `set_entity_to_database(key, data)`
6. Record update with `_record_update()`
7. Return fresh data

#### get_stats()

```python
def get_stats(self) -> Dict[str, Any]
```

Get database manager statistics.

**Returns**:
- Dictionary with manager-specific statistics

**Default Implementation**:
Returns basic metadata about last update operation.

**Override This**: Most managers override to provide custom statistics like row counts, coverage, etc.

**Example**:
```python
stats = ticker_manager.get_stats()
# Returns: {"last_update": "2025-10-02 14:30:00", "total_tickers": 7500}
```

### Abstract Methods (Must Implement)

Subclasses must implement these methods:

#### get_entity_from_database()

```python
@abstractmethod
def get_entity_from_database(self, key: str) -> Optional[Any]
```

Read entity from database table.

**Parameters**:
- `key` (str): Entity identifier

**Returns**:
- Entity object or None if not found

**Implementation Pattern**:
```python
def get_entity_from_database(self, key: str) -> Optional[TickerSnapshot]:
    """Get ticker snapshot from database."""
    query = "SELECT * FROM asset_prices WHERE symbol = ? ORDER BY updated_at DESC LIMIT 1"
    row = self.db_manager.fetch_one(query, (key,))

    if not row:
        return None

    return TickerSnapshot(
        symbol=row["symbol"],
        prev_close=Decimal(str(row["prevday_close"])),
        # ... map all fields
    )
```

#### set_entity_to_database()

```python
@abstractmethod
def set_entity_to_database(self, key: str, entity: Any) -> bool
```

Write entity to database table.

**Parameters**:
- `key` (str): Entity identifier
- `entity` (Any): Entity object to store

**Returns**:
- True if successful, False otherwise

**Implementation Pattern**:
```python
def set_entity_to_database(self, key: str, entity: TickerSnapshot) -> bool:
    """Store ticker snapshot to database."""
    query = """
        INSERT OR REPLACE INTO asset_prices
        (symbol, prevday_close, day_open, ...)
        VALUES (?, ?, ?, ...)
    """

    try:
        self.db_manager.execute(query, (
            entity.symbol,
            float(entity.prev_close),
            float(entity.open_price),
            # ... all fields
        ))
        return True
    except Exception as e:
        logger.error(f"Failed to store {key}: {e}")
        return False
```

#### get_data_update_metadata_type()

```python
@abstractmethod
def get_data_update_metadata_type(self) -> DataUpdateMetadataType
```

Return the metadata type for this manager.

**Returns**:
- DataUpdateMetadataType enum value

**Implementation Pattern**:
```python
def get_data_update_metadata_type(self) -> DataUpdateMetadataType:
    """Return metadata type for ticker snapshots."""
    return DataUpdateMetadataType.TICKER_SNAPSHOTS
```

**Available Types** (from `models/data_update_metadata.py`):
- `TICKER_SNAPSHOTS`
- `MARKET_SNAPSHOTS`
- `MARKETS`
- `TICKERS`
- `FUNDAMENTALS`
- `UNIVERSES`
- `MARKET_HOLIDAYS`
- `MARKET_CONTEXT`
- `SENTIMENT_TYPES`
- `SENTIMENT_EVENTS`

#### get_ttl_seconds()

```python
@abstractmethod
def get_ttl_seconds(self) -> int
```

Return TTL (time-to-live) for this data type in seconds.

**Returns**:
- TTL in seconds

**Implementation Pattern**:
```python
def get_ttl_seconds(self) -> int:
    """Return 15 minutes TTL for ticker snapshots."""
    return 15 * 60  # 15 minutes
```

**Common TTL Values**:
- Ticker snapshots: 900 seconds (15 minutes)
- Market snapshots: 900 seconds (15 minutes)
- Markets: 31,536,000 seconds (1 year)
- Fundamentals: 604,800 seconds (1 week)
- Market context: 300 seconds (5 minutes)

### Protected Methods

These methods are used internally by BaseManager and can be overridden if needed:

#### _is_data_stale()

```python
def _is_data_stale(self) -> bool
```

Check if cached data has exceeded TTL.

**Returns**:
- True if data is stale, False if fresh

**Logic**:
1. Get last update timestamp from metadata manager
2. If no timestamp found: Return True (stale)
3. Calculate age: `current_time - last_update_time`
4. Return `age > get_ttl_seconds()`

**Override This**: If you need custom staleness logic (most managers don't need to)

#### _record_update()

```python
def _record_update(self) -> None
```

Record that a data update operation completed.

**Purpose**: Updates the metadata timestamp used for TTL validation.

**Implementation**: Delegates to metadata_manager.record_update()

**When Called**: Automatically called by get_or_fetch() after successful data fetch.

---

## BaseAPIProvider

**Location**: `src/api/providers/base_provider.py`

**Purpose**: Abstract base class for all API providers that handle external API communication.

### Responsibilities

API providers handle:
- External API authentication
- HTTP request/response handling
- Rate limiting and retry logic
- Response parsing into model objects

API providers do NOT:
- Store data to database (handled by database managers)
- Handle TTL logic (handled by database managers)
- Manage caching (handled by database managers)

### Constructor

```python
def __init__(self, api_key: str, base_url: str)
```

**Parameters**:
- `api_key` (str): API authentication key
- `base_url` (str): Base URL for API endpoints

**Raises**:
- ValueError: If api_key is empty or None

**Example**:
```python
from api.providers import PolygonSnapshotProvider

provider = PolygonSnapshotProvider(
    api_key="your_polygon_api_key",
    base_url="https://api.polygon.io"
)
```

### Public Methods

#### health_check()

```python
def health_check(self) -> bool
```

Check if API is accessible and authenticated.

**Returns**:
- True if API is healthy, False otherwise

**Example**:
```python
if provider.health_check():
    print("API is accessible")
else:
    print("API is down or authentication failed")
```

**Implementation**: Calls `_get_health_endpoint()` and checks for successful response.

### Protected Methods

These methods are available to subclasses:

#### _make_request()

```python
def _make_request(
    self,
    endpoint: str,
    params: Optional[Dict[str, Any]] = None,
    method: str = "GET"
) -> Dict[str, Any]
```

Make authenticated request to API.

**Parameters**:
- `endpoint` (str): API endpoint path (e.g., "/v2/snapshot/...")
- `params` (Optional[Dict]): Query parameters (default: None)
- `method` (str): HTTP method (default: "GET")

**Returns**:
- Parsed JSON response dictionary

**Raises**:
- Exception: If API request fails

**Features**:
- Automatically adds authentication
- Handles rate limiting (HTTP 429)
- Retries failed requests
- Parses JSON responses

**Example**:
```python
def fetch_ticker(self, symbol: str):
    response = self._make_request(
        endpoint=f"/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}",
        params={"adjusted": "true"}
    )
    return response
```

**Request Flow**:
1. Add authentication via `_add_authentication(params)`
2. Make HTTP request
3. If HTTP 429 (rate limit): Call `_handle_rate_limit(response)`, wait, retry
4. If HTTP error: Call `_handle_error_response(response)`
5. Parse and return JSON

#### _handle_rate_limit()

```python
def _handle_rate_limit(self, response: requests.Response) -> None
```

Handle rate limit response.

**Parameters**:
- `response` (requests.Response): HTTP response with 429 status

**Default Behavior**: Waits 60 seconds before retry.

**Override This**: For provider-specific rate limit handling.

**Example**:
```python
def _handle_rate_limit(self, response: requests.Response) -> None:
    """Polygon-specific rate limit handling."""
    retry_after = int(response.headers.get("X-RateLimit-Reset", 60))
    logger.warning(f"Polygon rate limit hit, waiting {retry_after}s")
    time.sleep(retry_after)
```

#### _handle_error_response()

```python
def _handle_error_response(self, response: requests.Response) -> None
```

Handle error response.

**Parameters**:
- `response` (requests.Response): HTTP error response

**Raises**:
- Exception: With formatted error message

**Behavior**:
1. Extract status code
2. Try to parse error message from JSON response
3. Log error with context
4. Raise exception

**Example Error Messages**:
- "API error: 404 - Ticker not found"
- "API error: 401 - Invalid API key"
- "API error: 500 - Internal server error"

### Abstract Methods (Must Implement)

Subclasses must implement these methods:

#### _add_authentication()

```python
@abstractmethod
def _add_authentication(self, params: Dict[str, Any]) -> Dict[str, Any]
```

Add authentication to request parameters.

**Parameters**:
- `params` (Dict): Request parameters

**Returns**:
- Parameters with authentication added

**Implementation Examples**:
```python
# Polygon (API key in query params)
def _add_authentication(self, params: Dict[str, Any]) -> Dict[str, Any]:
    params["apiKey"] = self.api_key
    return params

# Alternative (API key in headers)
def _add_authentication(self, params: Dict[str, Any]) -> Dict[str, Any]:
    # Note: For header-based auth, you'd modify _make_request() to use headers
    self.headers = {"Authorization": f"Bearer {self.api_key}"}
    return params
```

#### _get_health_endpoint()

```python
@abstractmethod
def _get_health_endpoint(self) -> str
```

Get endpoint for health check.

**Returns**:
- Endpoint path for health checking

**Implementation Examples**:
```python
def _get_health_endpoint(self) -> str:
    """Use market status endpoint for health check."""
    return "/v1/marketstatus/now"
```

---

## Usage Patterns

### Standard Manager Implementation

```python
from database.managers.base_manager import BaseManager
from models.data_update_metadata import DataUpdateMetadataType

class MyEntityManager(BaseManager):
    """Manages MyEntity persistence and retrieval."""

    def get_entity_from_database(self, key: str) -> Optional[MyEntity]:
        """Read entity from database."""
        query = "SELECT * FROM my_table WHERE id = ?"
        row = self.db_manager.fetch_one(query, (key,))

        if not row:
            return None

        return MyEntity(
            id=row["id"],
            name=row["name"],
            # ... map fields
        )

    def set_entity_to_database(self, key: str, entity: MyEntity) -> bool:
        """Write entity to database."""
        query = "INSERT OR REPLACE INTO my_table (id, name) VALUES (?, ?)"

        try:
            self.db_manager.execute(query, (entity.id, entity.name))
            return True
        except Exception as e:
            logger.error(f"Failed to store {key}: {e}")
            return False

    def get_data_update_metadata_type(self) -> DataUpdateMetadataType:
        """Return metadata type."""
        return DataUpdateMetadataType.MY_ENTITIES

    def get_ttl_seconds(self) -> int:
        """Return 1 hour TTL."""
        return 3600
```

### Standard Provider Implementation

```python
from api.providers.base_provider import BaseAPIProvider
from typing import Optional, Dict, Any

class MyAPIProvider(BaseAPIProvider):
    """Provider for My External API."""

    def __init__(self, api_key: str):
        super().__init__(
            api_key=api_key,
            base_url="https://api.example.com"
        )

    def fetch_entity(self, entity_id: str) -> Optional[MyEntity]:
        """Fetch entity from API."""
        try:
            response = self._make_request(
                endpoint=f"/v1/entities/{entity_id}"
            )

            return self._parse_entity(response)

        except Exception as e:
            logger.error(f"Failed to fetch {entity_id}: {e}")
            return None

    def _parse_entity(self, data: Dict[str, Any]) -> MyEntity:
        """Parse API response into model object."""
        return MyEntity(
            id=data["id"],
            name=data["name"],
            # ... map API fields to model
        )

    def _add_authentication(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Add API key to params."""
        params["api_key"] = self.api_key
        return params

    def _get_health_endpoint(self) -> str:
        """Health check endpoint."""
        return "/v1/status"
```

### Coordinating Manager and Provider

```python
# In DataService or orchestration layer
class DataService:
    def __init__(self, db_manager, api_key):
        # Initialize metadata manager
        self.metadata_manager = DataUpdateMetadataManager(db_manager)

        # Initialize manager
        self.entity_manager = MyEntityManager(db_manager, self.metadata_manager)

        # Initialize provider
        self.entity_provider = MyAPIProvider(api_key)

    def get_entity(self, entity_id: str, force_refresh: bool = False) -> Optional[MyEntity]:
        """Get entity with cache-or-fetch logic."""
        return self.entity_manager.get_or_fetch(
            key=entity_id,
            fetch_fn=lambda: self.entity_provider.fetch_entity(entity_id),
            force_refresh=force_refresh
        )
```

---

## Best Practices

### For Managers

1. **Immutable Models**: Always use immutable dataclasses for entities
2. **SQL Injection**: Use parameterized queries (never string concatenation)
3. **Error Handling**: Log errors with context, return None on failure
4. **Field Mapping**: Be explicit about type conversions (Decimal for prices)
5. **Statistics**: Override get_stats() with meaningful metrics

### For Providers

1. **Model Objects**: Always return model objects, never raw API responses
2. **Error Handling**: Catch exceptions, log with context, return None
3. **Rate Limits**: Respect provider rate limits, implement exponential backoff
4. **Field Parsing**: Handle missing/null fields gracefully
5. **Testing**: Use mocks for unit tests, don't hit real APIs

### For Both

1. **Single Responsibility**: Managers handle database, providers handle APIs
2. **No Cross-Concerns**: Managers don't make API calls, providers don't store data
3. **Type Hints**: Use type hints for all method signatures
4. **Logging**: Use logger, not print statements
5. **Documentation**: Document public methods with docstrings

---

## See Also

- **Manager Implementations**: `docs/API_REFERENCE_MANAGERS.md`
- **Provider Implementations**: `docs/API_REFERENCE_PROVIDERS.md`
- **Architecture Overview**: `docs/ARCHITECTURE_MANAGERS.md`
- **DataService**: `docs/API_REFERENCE_DATA_SERVICE.md`
