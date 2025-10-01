# API Providers Architecture

## Overview

API Providers are the **external data source layer** in TradeScout's three-layer architecture. They handle all communication with external APIs (Polygon, Alpha Vantage, etc.), authentication, rate limiting, and parsing responses into our internal model objects.

```
┌─────────────────────────────────────────────────────────────┐
│                      DataService Layer                       │
│              (Orchestration & Business Logic)                │
└──────────────────┬────────────────────┬─────────────────────┘
                   │                    │
         ┌─────────▼────────┐  ┌────────▼─────────┐
         │  Database Layer  │  │   API Layer      │ ← YOU ARE HERE
         │   (Managers)     │  │  (Providers)     │
         └──────────────────┘  └────────┬─────────┘
                                        │
                                ┌───────▼────────┐
                                │  External APIs │
                                │  - Polygon.io  │
                                │  - Alpha Vant. │
                                │  - Finnhub     │
                                └────────────────┘
```

## Role of API Providers

### Responsibilities

API Providers handle:
- **HTTP Communication**: Making requests to external REST APIs
- **Authentication**: Adding API keys, tokens, or other auth mechanisms
- **Rate Limiting**: Detecting and handling rate limit responses (HTTP 429)
- **Error Handling**: Network errors, API errors, timeouts
- **Response Parsing**: Converting API JSON responses → Model objects
- **Retry Logic**: Retrying failed requests with exponential backoff

### What Providers Do NOT Do

Providers do **NOT**:
- Store data to database (that's the manager's job)
- Make caching decisions (that's the manager's job)
- Implement TTL logic (that's the manager's job)
- Contain business logic (that's the service layer's job)

### Clean Separation of Concerns

```python
# ❌ BAD: Provider storing to database
class PolygonProvider:
    def fetch_ticker(self, symbol):
        data = requests.get(f"https://api.polygon.io/v2/snapshot/{symbol}")
        self.db.save(data)  # ❌ Provider should NOT touch database

# ✅ GOOD: Provider returns model object
class PolygonProvider:
    def fetch_ticker(self, symbol):
        response = requests.get(f"https://api.polygon.io/v2/snapshot/{symbol}")
        return TickerSnapshot.from_api_response(response.json())
```

The orchestration layer (DataService) coordinates:
```python
# DataService coordinates between provider and manager
snapshot = provider.fetch_ticker(symbol)  # Provider: API call
manager.store(snapshot)                   # Manager: Database storage
```

## Base Provider Interface

All providers inherit from `BaseAPIProvider`:

**Location**: `src/api/provider/base_provider.py`

### Key Features

```python
class BaseAPIProvider(ABC):
    """Abstract base class for all API providers."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize with optional API key."""
        self.api_key = api_key
        self.base_url = None  # Set by subclass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return provider name (e.g., 'polygon', 'alpha_vantage')."""
        pass

    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        timeout: int = 30
    ) -> requests.Response:
        """Make HTTP request with auth, rate limiting, and error handling."""

        # Add authentication
        params = self._add_authentication(params)

        # Make request
        url = f"{self.base_url}{endpoint}"
        response = requests.request(method, url, params=params, timeout=timeout)

        # Handle rate limiting
        if response.status_code == 429:
            self._handle_rate_limit(response)
            # Retry after waiting
            response = requests.request(method, url, params=params, timeout=timeout)

        # Check for errors
        response.raise_for_status()
        return response

    def _add_authentication(self, params: Dict) -> Dict:
        """Add API key to request parameters."""
        if self.api_key:
            params = params or {}
            params["apiKey"] = self.api_key
        return params

    def _handle_rate_limit(self, response: requests.Response):
        """Handle rate limit response with exponential backoff."""
        retry_after = int(response.headers.get("Retry-After", 60))
        logger.warning(f"Rate limited by {self.get_provider_name()}, waiting {retry_after}s")
        time.sleep(retry_after)

    def health_check(self) -> bool:
        """Check if API is accessible."""
        try:
            self._make_request("GET", self.health_check_endpoint)
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
```

### Benefits of Base Provider

- **Consistent error handling** across all providers
- **Automatic rate limit handling** (429 responses)
- **Authentication abstraction** (different APIs use different auth)
- **Health check interface** for monitoring
- **Logging and debugging** built-in

## Current Implementation: Polygon Snapshot Provider

**Location**: `src/api/provider/polygon_snapshot_provider.py`

### Polygon.io API Details

**Subscription**: Stocks Starter Plan (~$50/month)
- ✅ 15-minute delayed data
- ✅ Extended hours data (premarket + afterhours)
- ✅ Snapshot approach (aggregated bars, not tick-by-tick)

### Implemented Endpoints

```python
class PolygonSnapshotProvider(BaseAPIProvider):
    """Polygon.io snapshot API provider."""

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.base_url = "https://api.polygon.io"

    # Single ticker snapshot
    def fetch_single_ticker_snapshot(self, symbol: str) -> Optional[TickerSnapshot]:
        """Fetch snapshot for single ticker.

        Endpoint: GET /v2/snapshot/locale/us/markets/stocks/tickers/{symbol}

        Returns:
            TickerSnapshot model object or None if error
        """

    # Bulk market snapshot
    def fetch_bulk_market_snapshot(
        self,
        symbols: Optional[List[str]] = None
    ) -> Optional[MarketSnapshot]:
        """Fetch snapshot for multiple tickers in single API call.

        Endpoint: GET /v2/snapshot/locale/us/markets/stocks/tickers

        Args:
            symbols: Optional list of symbols (None = all tickers)

        Returns:
            MarketSnapshot containing multiple TickerSnapshot objects
        """
```

### Response Parsing

Providers transform API JSON → Model objects:

```python
def fetch_single_ticker_snapshot(self, symbol: str) -> Optional[TickerSnapshot]:
    """Fetch single ticker snapshot."""
    try:
        response = self._make_request(
            "GET",
            f"/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}"
        )

        data = response.json()

        # Parse API response into model object
        return self._parse_ticker_snapshot(data["ticker"], symbol)

    except requests.HTTPError as e:
        if e.response.status_code == 404:
            logger.warning(f"Ticker {symbol} not found")
            return None
        raise
    except Exception as e:
        logger.error(f"Error fetching {symbol}: {e}")
        return None

def _parse_ticker_snapshot(self, data: Dict, symbol: str) -> TickerSnapshot:
    """Parse Polygon API response into TickerSnapshot model."""
    # Extract nested data
    day = data.get("day", {})
    prev_day = data.get("prevDay", {})
    min_bar = data.get("min", {})

    # Construct model object
    return TickerSnapshot(
        symbol=symbol,
        prev_close=Decimal(str(prev_day.get("c", 0))),
        prev_volume=prev_day.get("v"),
        open_price=Decimal(str(day.get("o", 0))),
        high_price=Decimal(str(day.get("h", 0))),
        # ... more fields
    )
```

## Polygon Snapshot API Behavior

### Critical Field Definitions

The Polygon snapshot API returns three key data groups:

| Field Group | Represents | Session |
|-------------|------------|---------|
| `prevDay.*` | Previous **completed** trading session | Previous regular session (9:30-4:00 PM) |
| `day.*` | Current **regular** trading session | Today's regular session (9:30-4:00 PM) |
| `min.*` | Last traded **minute bar** | ANY session (premarket, regular, afterhours) |

**CRITICAL**: `prevDay.c` is ALWAYS the reference price for change calculations.

### Snapshot Behavior by Market Session

#### 1. Premarket Session (4:00 AM - 9:30 AM ET)

```json
{
  "ticker": "AAPL",
  "prevDay": {
    "c": 237.88  // ← Previous day close (REFERENCE PRICE)
  },
  "day": {
    "o": 0,  // ← Regular session not started yet
    "h": 0,
    "l": 0,
    "c": 0,
    "v": 0
  },
  "min": {
    "c": 239.52,  // ← Current premarket price
    "t": 1726743780000  // ← Premarket timestamp
  }
}
```

**Key Points**:
- ✅ `day.*` fields are **all zeros** (regular session hasn't started)
- ✅ `min.c` shows current premarket price
- ✅ Gap calculation: `min.c - prevDay.c = 239.52 - 237.88 = +$1.64`

#### 2. Regular Session (9:30 AM - 4:00 PM ET)

```json
{
  "ticker": "AAPL",
  "prevDay": {
    "c": 237.88  // ← Previous day close (REFERENCE PRICE)
  },
  "day": {
    "o": 238.50,  // ← Today's open
    "h": 245.67,  // ← Intraday high
    "l": 237.90,  // ← Intraday low
    "c": 245.50,  // ← Current price (if live) or 4 PM close
    "v": 42500000  // ← Regular session volume
  },
  "min": {
    "c": 245.50,  // ← Current trading price
    "t": 1726766340000  // ← Current timestamp
  }
}
```

**Key Points**:
- ✅ `day.*` fields show live regular session data
- ✅ `min.c` updates in real-time during trading
- ✅ Change calculation: `min.c - prevDay.c`

#### 3. After-Hours Session (4:00 PM - 8:00 PM ET)

```json
{
  "ticker": "MSFT",
  "prevDay": {
    "c": 508.45  // ← Previous day close (REFERENCE PRICE)
  },
  "day": {
    "o": 510.56,    // ← Today's regular open
    "h": 519.30,    // ← Regular session high
    "l": 510.31,    // ← Regular session low
    "c": 517.93,    // ← 4:00 PM close (NOT reference price!)
    "v": 52697252   // ← Regular session volume
  },
  "min": {
    "c": 517.40,  // ← Current after-hours price
    "t": 1726776540000,  // ← After-hours timestamp (7:59 PM)
    "v": 1602
  }
}
```

**Key Points**:
- ✅ `day.*` fields contain **COMPLETE regular session data**
- ✅ `day.c` is the 4 PM close, **NOT the reference price**
- ✅ `min.c` shows current after-hours price
- ✅ Change calculation: `min.c - prevDay.c = 517.40 - 508.45 = +$8.95`

**CRITICAL DISCOVERY**: After 4 PM, `day.*` fields are populated with complete regular session data, allowing screeners to work correctly during extended hours.

#### 4. Weekend / Market Closed

```json
{
  "ticker": "AAPL",
  "prevDay": {
    "c": 237.88  // ← Thursday's close (last trading day)
  },
  "day": {
    "o": 238.50,
    "h": 245.67,
    "l": 237.90,
    "c": 245.50,   // ← Friday's 4 PM close
    "v": 42500000
  },
  "min": {
    "c": 245.69,  // ← Friday's last after-hours trade
    "t": 1726779540000  // ← Friday 7:59 PM timestamp
  }
}
```

**Key Points**:
- ✅ Data **frozen** from Friday 8 PM until Monday premarket
- ✅ `prevDay.c` references **Thursday's close** (skips weekend)
- ✅ `day.*` shows Friday's completed regular session
- ✅ `min.*` shows Friday's last after-hours trade

### Universal Change Calculation Formula

**For ALL market sessions** (premarket, regular, afterhours, weekends):

```python
current_price = min.c
reference_price = prevDay.c
change = min.c - prevDay.c
change_percent = (change / prevDay.c) * 100
```

**Why this works**:
- `prevDay.c` is always the previous completed trading session close
- `min.c` is always the most recent price (any session)
- Formula works identically across all market conditions

### The `updated` Field Behavior

The `updated` timestamp has important daily reset behavior:

```python
# Each trading day starts fresh
if updated == 0:
    # Symbol hasn't traded yet today
    # - prevDay.* still populated
    # - day.* fields are zeros/NULL
    # - min.* fields missing/NULL

if updated > 0:
    # Symbol has traded today
    # - All fields populated based on trading activity
    # - min.* shows most recent trade
    # - day.* updates during regular session
```

**Implications**:
- In premarket: ~2,000-2,500 of ~7,500 symbols have `updated > 0`
- Many legitimate stocks won't show activity until regular session starts
- Use `updated > 0` to filter for "actively trading today"

### Session Behavior Summary Table

| Session | Time (ET) | `prevDay.c` | `day.*` | `min.c` | Formula |
|---------|-----------|-------------|---------|---------|---------|
| **Premarket** | 4:00-9:30 AM | Previous close | All zeros | Premarket price | `min.c - prevDay.c` |
| **Regular** | 9:30-4:00 PM | Previous close | Live session | Current price | `min.c - prevDay.c` |
| **After-hours** | 4:00-8:00 PM | Previous close | Complete session | After-hours price | `min.c - prevDay.c` |
| **Closed/Weekend** | Outside trading | Previous close | Last session | Last traded | `min.c - prevDay.c` |

**Status**: ✅ All sessions tested and confirmed with real production data

## Provider Testing

### Unit Tests

**Location**: `tests/test_polygon_snapshot_provider.py`

Tests cover:
- ✅ Initialization with/without API key
- ✅ Authentication header addition
- ✅ Single ticker fetch (success, not found, API error)
- ✅ Bulk market snapshot (all tickers, filtered symbols)
- ✅ Rate limit handling (HTTP 429)
- ✅ Health check (success, failure)
- ✅ Model object construction from API responses

### Integration Tests

**Location**: `tests/test_data_service_integration.py`

Tests providers through DataService:
- ✅ Cache hit/miss scenarios
- ✅ Force refresh behavior
- ✅ Bulk operations with individual ticker storage
- ✅ Error propagation

### End-to-End Tests

**Location**: `data/examples/test_new_ticker_snapshot_architecture.py`

Real API testing:
- ✅ Single ticker fetch with real Polygon API
- ✅ Bulk market refresh
- ✅ Extended hours data verification
- ✅ TTL-based caching validation

## Future Providers

### Planned Implementations

**Alpha Vantage Provider** (planned):
- Top gainers/losers endpoint
- Sector performance data
- Market overview metrics

**Finnhub Provider** (planned):
- Company fundamentals
- News sentiment analysis
- Earnings data

**YFinance Provider** (planned):
- Fallback for free data
- Historical price data
- Dividend information

### Provider Implementation Pattern

When adding a new provider:

1. **Extend BaseAPIProvider**:
```python
class NewProvider(BaseAPIProvider):
    def __init__(self, api_key: str):
        super().__init__(api_key)
        self.base_url = "https://api.newprovider.com"

    def get_provider_name(self) -> str:
        return "new_provider"
```

2. **Implement data fetch methods**:
```python
    def fetch_ticker_data(self, symbol: str) -> Optional[TickerSnapshot]:
        """Fetch ticker data from provider."""
        response = self._make_request("GET", f"/ticker/{symbol}")
        return self._parse_response(response.json())
```

3. **Parse to model objects**:
```python
    def _parse_response(self, data: Dict) -> TickerSnapshot:
        """Convert provider JSON → TradeScout model."""
        return TickerSnapshot(
            symbol=data["ticker"],
            prev_close=Decimal(str(data["prevClose"])),
            # ... map provider fields to model
        )
```

4. **Add to DataService**:
```python
class DataService:
    def __init__(self, ..., new_provider_key: str):
        self.new_provider = NewProvider(new_provider_key)
```

5. **Write tests**:
   - Unit tests for provider methods
   - Integration tests through DataService
   - Mock external API calls

## Best Practices

### Do's ✅

- **Return model objects**, not raw API responses
- **Use base provider** for HTTP communication
- **Handle rate limits** gracefully (exponential backoff)
- **Log errors** with context (symbol, endpoint, error message)
- **Test with mocks** (don't hit real APIs in unit tests)
- **Validate API keys** on initialization
- **Implement health checks** for monitoring

### Don'ts ❌

- **Don't store to database** - that's the manager's job
- **Don't implement caching** - that's the manager's job
- **Don't contain business logic** - that's the service layer
- **Don't hardcode delays** - use Retry-After headers
- **Don't expose raw API responses** - always return models
- **Don't ignore rate limits** - respect provider quotas

## Configuration

### API Keys

**Location**: Environment variables or config files

```bash
# .env file
POLYGON_API_KEY=your_polygon_key_here
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key
FINNHUB_API_KEY=your_finnhub_key
```

**Loading in DataService**:
```python
import os

polygon_key = os.getenv("POLYGON_API_KEY")
if not polygon_key:
    raise ValueError("POLYGON_API_KEY not set")

data_service = DataService(
    db_manager=db_manager,
    update_tracker=tracker,
    polygon_api_key=polygon_key
)
```

### Rate Limits

Different providers have different limits:

| Provider | Free Tier | Paid Tier | Our Plan |
|----------|-----------|-----------|----------|
| Polygon | 5 calls/min | Unlimited | Stocks Starter ($50/mo) |
| Alpha Vantage | 25 calls/day | 75-1200/day | Free tier |
| Finnhub | 60 calls/min | 300-600/min | Not configured |

**Rate Limit Protection**:
- Base provider handles HTTP 429 responses
- Exponential backoff with `Retry-After` header
- Manager TTL prevents excessive calls
- Bulk operations minimize API usage

## Summary

| Aspect | Responsibility | Implementation |
|--------|---------------|----------------|
| **HTTP Calls** | Make REST API requests | `BaseAPIProvider._make_request()` |
| **Authentication** | Add API keys to requests | `BaseAPIProvider._add_authentication()` |
| **Rate Limiting** | Handle 429 responses | `BaseAPIProvider._handle_rate_limit()` |
| **Error Handling** | Network/API errors | Try/except with logging |
| **Parsing** | JSON → Model objects | Provider-specific `_parse_*()` methods |
| **Health Checks** | Verify API accessibility | `health_check()` method |
| **Testing** | Unit + integration tests | Mocked responses in tests |

**Key Principle**: Providers are a **pure I/O layer** - they fetch data from external APIs and return model objects, nothing more.