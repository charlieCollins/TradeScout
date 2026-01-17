# Capability-Based Provider Architecture

**Created:** December 4, 2025
**Updated:** December 4, 2025
**Status:** 🎯 Design Proposal - UPDATED WITH AVAILABLE PROVIDERS
**Problem:** Current architecture assumes one provider per protocol, but we need to mix providers at the method level

---

## Available API Keys & Providers

You currently have access to:

| Provider | API Key Status | Free Tier Limits | Best For |
|----------|---------------|------------------|----------|
| **Polygon Basic** | ✅ Active | 5 calls/min, EOD only | Historical daily, reference data, Fed data |
| **Alpaca** | ⏳ Can get | 200 calls/min, real-time WS | Bulk snapshots, real-time quotes |
| **Tiingo** | ✅ Active | 50 symbols/hour EOD, IEX real-time | 30+ years history, backup quotes |
| **Finnhub** | ✅ Active | 60 calls/min | News + sentiment |
| **Alpha Vantage** | ✅ Active | 25 calls/day | Too limited - skip |
| **pandas_market_calendars** | N/A (local lib) | Unlimited | Market hours, holidays, sessions |

---

## The Problem

### Current Architecture Limitation
```yaml
providers:
  snapshot: polygon       # ALL snapshot methods use Polygon
  aggregates: polygon     # ALL aggregates methods use Polygon
  news: polygon          # ALL news methods use Polygon
```

**Issue:** We can't mix providers because Polygon Basic (free) supports SOME methods but not others:

| Method | Polygon Basic | Recommended Alternative |
|--------|--------------|------------------------|
| `fetch_bulk_market_snapshot()` | ❌ 403 error | ✅ **Alpaca** (200/min) |
| `fetch_single_ticker_snapshot()` | ❌ 403 error | ✅ **Alpaca** (200/min) or **Tiingo** (IEX) |
| `fetch_market_status()` | ✅ Works (but wastes API call) | ✅ **pandas_market_calendars** (local, unlimited) |
| `fetch_upcoming_holidays()` | ✅ Works (but wastes API call) | ✅ **pandas_market_calendars** (local, unlimited) |
| `fetch_minute_bars()` (intraday) | ❌ EOD only | ✅ **Alpaca** (real-time WS) |
| `get_daily_aggregates()` (historical) | ✅ Works | Keep **Polygon** (5+ years history) |
| `fetch_news_for_ticker()` | ❌ 403 error | ✅ **Finnhub** (60/min) |

**We need method-level routing, not protocol-level routing.**

---

## Proposed Solution: Composite Providers with Method Routing

### Architecture Overview

```
DataServiceV2
    ↓
CompositeSnapshotProvider (implements SnapshotProvider protocol)
    ├─ fetch_bulk_market_snapshot() → routes to AlpacaSnapshotAdapter (200/min)
    │                                   fallback: TiingoSnapshotAdapter (50/hour)
    └─ fetch_single_ticker_snapshot() → routes to AlpacaSnapshotAdapter (200/min)
                                        fallback: TiingoSnapshotAdapter (50/hour)

MarketCalendarProvider (implements MarketStatusProvider protocol)
    ├─ fetch_market_status() → routes to PandasMarketCalendar (local, unlimited)
    └─ fetch_upcoming_holidays() → routes to PandasMarketCalendar (local, unlimited)

CompositeAggregatesProvider (implements AggregatesProvider protocol)
    ├─ fetch_minute_bars() → routes to AlpacaAggregatesAdapter (real-time WS)
    ├─ get_daily_aggregates() → routes to PolygonAggregatesAdapter (5+ years)
    ├─ fetch_grouped_daily_bars() → routes to PolygonAggregatesAdapter (bulk EOD)
    └─ calculate_extended_hours_volume() → routes to AlpacaAggregatesAdapter (minute bars)

FinnhubNewsProvider (implements NewsProvider protocol)
    └─ fetch_news_for_ticker() → routes to FinnhubNewsAdapter (60/min)
```

### Key Design Principles

1. **Composite providers implement the protocol** - They look like regular providers to DataServiceV2
2. **Method-level routing** - Each method call is routed to a specific underlying provider
3. **Configuration-driven** - YAML config specifies routing without code changes
4. **Fallback support** - Can try multiple providers in sequence
5. **Provider caching** - Underlying providers are instantiated once and reused

---

## Configuration Schema

### New `configs/providers.yaml`

```yaml
providers:
  # Snapshot protocol - routes methods to different providers
  snapshot:
    fetch_bulk_market_snapshot:
      provider: alpaca          # 200 calls/min, real-time
      fallback: [tiingo]        # 50 symbols/hour EOD, IEX real-time

    fetch_single_ticker_snapshot:
      provider: alpaca          # 200 calls/min, real-time
      fallback: [tiingo]        # 50 symbols/hour EOD, IEX real-time

  # Market status protocol - use local pandas_market_calendars (no API calls!)
  market_status:
    fetch_market_status:
      provider: pandas_market_calendars   # Local, unlimited

    fetch_upcoming_holidays:
      provider: pandas_market_calendars   # Local, unlimited

  # Aggregates protocol - mix Polygon (historical) + Alpaca (real-time)
  aggregates:
    fetch_minute_bars:
      provider: alpaca          # Real-time WebSocket, 200/min REST
      fallback: []

    get_daily_aggregates:
      provider: polygon         # 5+ years historical, 5/min
      fallback: [tiingo]        # 30+ years backup

    fetch_grouped_daily_bars:
      provider: polygon        # Polygon Basic supports grouped daily
      fallback: []

    calculate_extended_hours_volume:
      provider: alpaca        # Needs intraday minute bars, real-time WS
      fallback: []

  # News protocol - use Finnhub (already have key, 60/min)
  news:
    fetch_news_for_ticker:
      provider: finnhub       # 60 calls/min free
      fallback: []

  # Reference protocol - Polygon Basic still works (5/min)
  reference:
    fetch_all_tickers:
      provider: polygon       # One-time bootstrap, works on Basic

    fetch_ticker_details:
      provider: polygon       # One-time bootstrap, works on Basic

    fetch_ticker_details_raw:
      provider: polygon       # One-time bootstrap, works on Basic

  # Economic protocol - Polygon Basic still works (5/min)
  economic:
    fetch_inflation:
      provider: polygon       # Works on Basic tier

    fetch_inflation_expectations:
      provider: polygon       # Works on Basic tier

    fetch_treasury_yields:
      provider: polygon       # Works on Basic tier

    fetch_all_fed_data:
      provider: polygon       # Works on Basic tier

# API Keys (from environment variables)
api_keys:
  POLYGON_API_KEY: ${POLYGON_API_KEY}       # Already have
  ALPACA_API_KEY: ${ALPACA_API_KEY}         # Need to get
  ALPACA_SECRET_KEY: ${ALPACA_SECRET_KEY}   # Need to get
  TIINGO_API_KEY: ${TIINGO_API_KEY}         # Already have
  FINNHUB_API_KEY: ${FINNHUB_API_KEY}       # Already have

# Provider-specific settings
settings:
  polygon:
    base_url: "https://api.polygon.io"
    rate_limit_per_minute: 5  # Stocks Basic tier

  alpaca:
    base_url: "https://data.alpaca.markets"
    rate_limit_per_minute: 200  # Free tier
    # WebSocket for real-time data
    websocket_url: "wss://stream.data.alpaca.markets"

  tiingo:
    base_url: "https://api.tiingo.com"
    rate_limit_symbols_per_hour: 50  # Free tier EOD
    # IEX real-time data has separate limits

  finnhub:
    base_url: "https://finnhub.io"
    rate_limit_per_minute: 60  # Free tier

  pandas_market_calendars:
    # No settings needed - local library
    calendars: [NYSE, NASDAQ]  # Which calendars to use
```

---

## Implementation Approach

### Step 1: Create Composite Provider Base Class

```python
# src/api/providers/composite_provider.py

class CompositeProvider:
    """Base class for composite providers that route methods to different providers.

    Subclasses implement protocol interfaces and route each method call
    to a configured provider based on YAML configuration.
    """

    def __init__(self, protocol_name: str, config: dict):
        """Initialize composite provider.

        Args:
            protocol_name: Name of protocol (e.g., 'snapshot', 'aggregates')
            config: Method routing configuration from providers.yaml
        """
        self.protocol_name = protocol_name
        self.method_config = config
        self._provider_cache = {}  # Cache instantiated providers

    def _get_provider_for_method(self, method_name: str):
        """Get provider instance for a specific method.

        Args:
            method_name: Name of method being called

        Returns:
            Provider instance that implements this method
        """
        # Get method config
        if method_name not in self.method_config:
            raise ValueError(f"No provider configured for {self.protocol_name}.{method_name}")

        method_cfg = self.method_config[method_name]
        provider_name = method_cfg['provider']

        # Instantiate and cache provider
        if provider_name not in self._provider_cache:
            self._provider_cache[provider_name] = self._instantiate_provider(
                provider_name,
                self.protocol_name
            )

        return self._provider_cache[provider_name]

    def _instantiate_provider(self, provider_name: str, protocol_name: str):
        """Instantiate a specific provider adapter.

        Args:
            provider_name: Provider name (e.g., 'polygon', 'yfinance')
            protocol_name: Protocol name (e.g., 'snapshot', 'aggregates')

        Returns:
            Provider adapter instance
        """
        # Import and instantiate appropriate adapter
        if provider_name == "polygon":
            if protocol_name == "snapshot":
                from api.providers.adapters.polygon_snapshot_adapter import PolygonSnapshotAdapter
                api_key = os.getenv("POLYGON_API_KEY")
                return PolygonSnapshotAdapter(api_key)

            elif protocol_name == "aggregates":
                from api.providers.adapters.polygon_aggregates_adapter import PolygonAggregatesAdapter
                api_key = os.getenv("POLYGON_API_KEY")
                return PolygonAggregatesAdapter(api_key)

            # ... etc for other protocols

        elif provider_name == "yfinance":
            if protocol_name == "snapshot":
                from api.providers.adapters.yfinance_snapshot_adapter import YFinanceSnapshotAdapter
                return YFinanceSnapshotAdapter()

            # ... etc for other protocols

        elif provider_name == "finnhub":
            if protocol_name == "news":
                from api.providers.adapters.finnhub_news_adapter import FinnhubNewsAdapter
                api_key = os.getenv("FINNHUB_API_KEY")
                return FinnhubNewsAdapter(api_key)

        else:
            raise ValueError(f"Unknown provider: {provider_name}")

    def _route_call(self, method_name: str, *args, **kwargs):
        """Route a method call to the configured provider.

        Args:
            method_name: Name of method being called
            *args, **kwargs: Method arguments

        Returns:
            Result from underlying provider
        """
        provider = self._get_provider_for_method(method_name)
        method = getattr(provider, method_name)
        return method(*args, **kwargs)
```

### Step 2: Create Composite Providers for Each Protocol

```python
# src/api/providers/composite/snapshot_provider.py

from api.providers.composite_provider import CompositeProvider
from api.providers.protocols.snapshot_provider import SnapshotProvider

class CompositeSnapshotProvider(CompositeProvider, SnapshotProvider):
    """Composite snapshot provider that routes methods to different providers."""

    def __init__(self, config: dict):
        super().__init__("snapshot", config)

    def fetch_bulk_market_snapshot(self) -> Optional[MarketSnapshot]:
        return self._route_call('fetch_bulk_market_snapshot')

    def fetch_single_ticker_snapshot(self, symbol: str) -> Optional[TickerSnapshot]:
        return self._route_call('fetch_single_ticker_snapshot', symbol)

    def get_provider_name(self) -> str:
        return "composite_snapshot"
```

```python
# src/api/providers/composite/aggregates_provider.py

class CompositeAggregatesProvider(CompositeProvider, AggregatesProvider):
    """Composite aggregates provider that routes methods to different providers."""

    def __init__(self, config: dict):
        super().__init__("aggregates", config)

    def fetch_minute_bars(self, symbol: str, from_datetime: datetime,
                         to_datetime: datetime, adjusted: bool = True) -> Optional[List[PriceBar]]:
        return self._route_call('fetch_minute_bars', symbol, from_datetime, to_datetime, adjusted)

    def get_daily_aggregates(self, symbol: str, from_date: date,
                            to_date: date, adjusted: bool = True) -> Optional[List[PriceBar]]:
        return self._route_call('get_daily_aggregates', symbol, from_date, to_date, adjusted)

    def fetch_grouped_daily_bars(self, target_date: date,
                                adjusted: bool = True) -> Optional[Dict[str, PriceBar]]:
        return self._route_call('fetch_grouped_daily_bars', target_date, adjusted)

    def calculate_extended_hours_volume(self, symbol: str, trading_date: date,
                                       session: str = "afterhours") -> Optional[int]:
        return self._route_call('calculate_extended_hours_volume', symbol, trading_date, session)

    def get_provider_name(self) -> str:
        return "composite_aggregates"
```

### Step 3: Update ProviderFactory

```python
# src/api/providers/provider_factory.py

class ProviderFactory:
    """Factory for creating composite providers based on configuration."""

    @staticmethod
    def create_snapshot_provider():
        """Create composite snapshot provider."""
        config = ConfigLoader().load_yaml("providers.yaml")
        method_config = config["providers"]["snapshot"]

        from api.providers.composite.snapshot_provider import CompositeSnapshotProvider
        return CompositeSnapshotProvider(method_config)

    @staticmethod
    def create_aggregates_provider():
        """Create composite aggregates provider."""
        config = ConfigLoader().load_yaml("providers.yaml")
        method_config = config["providers"]["aggregates"]

        from api.providers.composite.aggregates_provider import CompositeAggregatesProvider
        return CompositeAggregatesProvider(method_config)

    # ... etc for other protocols
```

---

## Migration Path

### Phase 1: Implement Base Infrastructure
1. Create `CompositeProvider` base class
2. Update `providers.yaml` with new schema
3. Test config loading

### Phase 2: Implement yfinance Adapter
1. Add `yfinance` to requirements.txt
2. Create `yfinance_snapshot_adapter.py`
3. Create `yfinance_aggregates_adapter.py`
4. Test adapters in isolation

### Phase 3: Create Composite Providers
1. Create `CompositeSnapshotProvider`
2. Create `CompositeAggregatesProvider`
3. Create `CompositeMarketStatusProvider`
4. Create `CompositeNewsProvider`
5. Keep reference/economic as simple (single provider)

### Phase 4: Update Factory & Test
1. Update `ProviderFactory` to use composite providers
2. Test with real API calls
3. Validate data matches expected format
4. Performance testing

### Phase 5: Deploy
1. Set API keys in environment
2. Update config to route methods
3. Deploy and monitor
4. Validate all features work

---

## Benefits

### 1. Granular Control
Route each method to the best provider for that capability:
- Current prices → yfinance (free, unlimited)
- Historical EOD → Polygon Basic (free, works)
- News/sentiment → Finnhub (free, 60/min)

### 2. Cost Optimization
Mix free providers where possible, keep Polygon Basic for what works:
- **Before**: $29/month Polygon Starter
- **After**: $0/month (all free providers)

### 3. Future-Proof
Easy to add new providers or change routing:
- Just update YAML config
- No code changes needed
- Can A/B test providers

### 4. Fallback Support
Built-in support for provider failover:
```yaml
fetch_bulk_market_snapshot:
  provider: yfinance
  fallback: [polygon, finnhub]  # Try these if yfinance fails
```

### 5. Testability
Easy to inject mock providers per method for testing.

---

## Testing Strategy

### Unit Tests
- Test each composite provider method routes correctly
- Test fallback logic
- Test provider caching
- Test error handling

### Integration Tests
- Test full workflow: CLI → DataService → Composite → Adapter → API
- Validate data transformations
- Test rate limiting
- Test all screeners work

### Comparison Tests
- Run same queries against multiple providers
- Compare data quality
- Identify provider quirks

---

## Cost/Benefit Summary

### Before (Polygon Starter)
- **Cost:** $29/month
- **Snapshot API:** ✅ Unlimited
- **Rate Limit:** Unlimited calls/min
- **Single provider:** Easy but expensive

### After (Multi-Provider Free Tier)
- **Cost:** $0/month (100% savings)
- **Snapshot API:** ✅ Alpaca 200/min (fallback: Tiingo)
- **Market Status:** ✅ pandas_market_calendars (local, unlimited)
- **News/Sentiment:** ✅ Finnhub 60/min
- **Rate Limits:** Higher than Polygon Basic (200/min vs 5/min)

**Net Result:** Better performance + $0 cost

### API Call Optimization

| Operation | Before (Polygon Starter) | After (Multi-Provider) | Savings |
|-----------|-------------------------|------------------------|---------|
| Market update (bulk snapshot) | 1 call (unlimited) | 1 Alpaca call (200/min) | 40x better than Basic |
| Market status check | 1 Polygon call | 0 calls (local library) | 100% saved |
| Holiday calendar | 1 Polygon call | 0 calls (local library) | 100% saved |
| News per ticker | 1 Polygon call | 1 Finnhub call (60/min) | Still works (was 403) |
| Single ticker quote | 1 call (unlimited) | 1 Alpaca call (200/min) | 40x better than Basic |

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| Alpaca API changes | Version pin in requirements.txt, monitoring |
| Tiingo rate limits (50 symbols/hour) | Use as fallback only, cache aggressively |
| Rate limit exceeded | Implement exponential backoff, caching |
| Data format differences | Comprehensive adapter testing before deployment |
| Provider downtime | Automatic fallback chains (Alpaca → Tiingo) |
| pandas_market_calendars calendar updates | Update library quarterly, verify holidays |

---

## Next Steps

1. **Get Alpaca API key** (free account signup)
2. **Review & Approve** this design
3. **Implement Phase 1** (base infrastructure: composite providers)
4. **Implement Phase 2** (Alpaca, Tiingo, Finnhub adapters)
5. **Implement Phase 3** (pandas_market_calendars integration)
6. **Test thoroughly** before deploying
7. **Deploy & Monitor**

---

## Questions for Review

1. Does this architecture meet your needs for mixing providers at the method level?
2. Should we implement fallback chains (Alpaca → Tiingo) in Phase 1 or defer to later?
3. Are you comfortable with pandas_market_calendars for market status (vs API)?
4. Any other protocols/methods that need special routing?
5. Ready to get Alpaca API key and start implementation?
