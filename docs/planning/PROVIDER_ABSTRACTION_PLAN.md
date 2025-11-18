# Provider Abstraction Layer - Implementation Plan

**Created:** November 18, 2025
**Status:** Planning
**Goal:** Decouple TradeScout from Polygon.io to support multiple data providers

---

## Executive Summary

This plan outlines the implementation of a **provider abstraction layer** that will:
1. Decouple TradeScout from Polygon-specific implementation
2. Enable easy swapping between data providers (Polygon, YFinance, IEX, Finnhub)
3. Support fallback chains (try Provider A, fall back to Provider B)
4. Optimize costs (use free tiers, pay only when needed)
5. Reduce vendor lock-in

**Estimated Effort:** 3-4 weeks (phased implementation)
**Priority:** High (Dec 2, 2025 deadline approaching)

---

## Current Architecture Analysis

### Existing Provider Structure

TradeScout currently has **7 Polygon-specific providers**, all inheriting from `BaseAPIProvider`:

```
src/api/providers/
├── base_provider.py                   # Abstract base (HTTP, auth, rate limiting)
├── polygon_snapshot_provider.py       # Snapshot API (CRITICAL)
├── polygon_aggregates_provider.py     # Historical bars, minute data
├── polygon_news_provider.py           # News + sentiment
├── polygon_market_status_provider.py  # Session detection, holidays
├── polygon_markets_provider.py        # Exchange reference data
├── polygon_tickers_provider.py        # Ticker reference + fundamentals
└── polygon_fed_provider.py            # Fed economic data
```

### How Providers Are Used

**Direct instantiation in DataServiceV2:**
```python
class DataServiceV2:
    def __init__(self, session: Session, polygon_api_key: str):
        # TIGHTLY COUPLED - instantiates Polygon providers directly
        self.polygon_provider = PolygonTickersProvider(polygon_api_key)
        self.polygon_snapshot_provider = PolygonSnapshotProvider(polygon_api_key)
        self.polygon_aggregates_provider = PolygonAggregatesProvider(polygon_api_key)
        self.polygon_news_provider = PolygonNewsProvider(polygon_api_key)
        self.polygon_markets_provider = PolygonMarketsProvider(polygon_api_key)
        self.polygon_market_status_provider = PolygonMarketStatusProvider(polygon_api_key)
```

**Direct method calls:**
```python
# In DataServiceV2
market_snapshot = self.polygon_snapshot_provider.fetch_bulk_market_snapshot()
ticker_snapshot = self.polygon_snapshot_provider.fetch_single_ticker_snapshot(symbol)
minute_bars = self.polygon_aggregates_provider.fetch_minute_bars(...)
news_articles = self.polygon_news_provider.fetch_news_for_ticker(...)
```

### Problems with Current Architecture

1. **Tight Coupling**: Services directly instantiate and call Polygon providers
2. **No Abstraction**: Swapping providers requires changes in multiple files
3. **Provider-Specific Code**: Business logic knows about Polygon API details
4. **No Fallback**: If Polygon fails, entire system fails
5. **No Cost Optimization**: Can't use free providers for some data, paid for others
6. **Vendor Lock-In**: Moving to another provider = major refactoring

---

## Provider Abstraction Layer Design

### Overview

We'll create **protocol-based interfaces** (Python typing.Protocol) that define contracts for data providers, then implement adapters for each provider (Polygon, YFinance, etc.).

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│                    DataServiceV2                        │
│  (Business logic - provider-agnostic)                   │
└─────────────────────┬───────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────┐
│              ProviderFactory                            │
│  (Creates providers based on config)                    │
└─────────────────────┬───────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
        ▼             ▼             ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│   Polygon   │ │  YFinance   │ │  IEXCloud   │
│   Adapter   │ │   Adapter   │ │   Adapter   │
└──────┬──────┘ └──────┬──────┘ └──────┬──────┘
       │               │               │
       ▼               ▼               ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│  Polygon    │ │  yfinance   │ │  IEX Cloud  │
│  API        │ │  library    │ │  API        │
└─────────────┘ └─────────────┘ └─────────────┘
```

### Provider Protocols (Interfaces)

We'll define **6 protocol interfaces** matching our data needs:

#### 1. SnapshotProvider Protocol
```python
# src/api/providers/protocols/snapshot_provider.py

from typing import Protocol, Optional
from models.dataclass.snapshot import MarketSnapshot, TickerSnapshot


class SnapshotProvider(Protocol):
    """Protocol for snapshot data providers.

    Implementations: PolygonSnapshotAdapter, YFinanceSnapshotAdapter
    """

    def fetch_bulk_market_snapshot(self) -> Optional[MarketSnapshot]:
        """Fetch snapshots for ALL tickers.

        Returns:
            MarketSnapshot containing all ticker snapshots, or None if error
        """
        ...

    def fetch_single_ticker_snapshot(self, symbol: str) -> Optional[TickerSnapshot]:
        """Fetch snapshot for a single ticker.

        Args:
            symbol: Stock symbol (e.g., 'AAPL')

        Returns:
            TickerSnapshot or None if error
        """
        ...

    def get_provider_name(self) -> str:
        """Get provider name for logging/debugging."""
        ...
```

#### 2. AggregatesProvider Protocol
```python
# src/api/providers/protocols/aggregates_provider.py

from typing import Protocol, Optional, List
from datetime import datetime, date
from models.dataclass.price_bar import PriceBar


class AggregatesProvider(Protocol):
    """Protocol for historical aggregates/bars data providers.

    Implementations: PolygonAggregatesAdapter, YFinanceAggregatesAdapter
    """

    def fetch_minute_bars(
        self,
        symbol: str,
        from_datetime: datetime,
        to_datetime: datetime,
        adjusted: bool = True
    ) -> Optional[List[PriceBar]]:
        """Fetch minute-level bars for a symbol within a time range."""
        ...

    def get_daily_aggregates(
        self,
        symbol: str,
        from_date: date,
        to_date: date,
        adjusted: bool = True
    ) -> Optional[List[PriceBar]]:
        """Fetch daily aggregates for a symbol within a date range."""
        ...

    def fetch_grouped_daily_bars(
        self,
        target_date: date,
        adjusted: bool = True
    ) -> Optional[dict[str, PriceBar]]:
        """Fetch end-of-day bars for all stocks traded on a specific date."""
        ...

    def calculate_extended_hours_volume(
        self,
        symbol: str,
        trading_date: date,
        session: str = "afterhours"
    ) -> Optional[int]:
        """Calculate total volume for an extended hours session."""
        ...
```

#### 3. NewsProvider Protocol
```python
# src/api/providers/protocols/news_provider.py

from typing import Protocol, Optional, List
from datetime import date
from models.dataclass.news_article import NewsArticle


class NewsProvider(Protocol):
    """Protocol for news and sentiment data providers.

    Implementations: PolygonNewsAdapter, AlphaVantageNewsAdapter
    """

    def fetch_news_for_ticker(
        self,
        ticker: str,
        limit: int = 10,
        published_after: Optional[date] = None
    ) -> Optional[List[NewsArticle]]:
        """Fetch news articles for a specific ticker."""
        ...

    def fetch_recent_market_news(
        self,
        limit: int = 50
    ) -> Optional[List[NewsArticle]]:
        """Fetch recent market-wide news (not ticker-specific)."""
        ...
```

#### 4. MarketStatusProvider Protocol
```python
# src/api/providers/protocols/market_status_provider.py

from typing import Protocol, Optional, List
from models.dataclass.market_status import MarketStatusSnapshot
from models.dataclass.market_holiday import MarketHoliday


class MarketStatusProvider(Protocol):
    """Protocol for market status and holidays providers.

    Implementations: PolygonMarketStatusAdapter, CustomMarketStatusProvider
    """

    def fetch_market_status(self) -> Optional[MarketStatusSnapshot]:
        """Fetch current market status."""
        ...

    def fetch_upcoming_holidays(self) -> Optional[List[MarketHoliday]]:
        """Fetch upcoming market holidays."""
        ...
```

#### 5. ReferenceDataProvider Protocol
```python
# src/api/providers/protocols/reference_data_provider.py

from typing import Protocol, Optional, List, Dict, Any
from models.dataclass.asset import Asset
from models.dataclass.market import Market


class ReferenceDataProvider(Protocol):
    """Protocol for reference data (tickers, exchanges, fundamentals).

    Implementations: PolygonReferenceAdapter, YFinanceReferenceAdapter
    """

    def fetch_ticker_details(
        self,
        symbol: str,
        market_code_to_id: Optional[Dict[str, int]] = None
    ) -> Optional[Asset]:
        """Fetch details for a single ticker."""
        ...

    def fetch_ticker_details_raw(
        self,
        symbol: str
    ) -> Optional[Dict[str, Any]]:
        """Fetch raw ticker details (includes fundamentals data)."""
        ...

    def fetch_all_tickers(
        self,
        market: str = "stocks",
        active: bool = True,
        limit: Optional[int] = None,
        market_code_to_id: Optional[Dict[str, int]] = None
    ) -> List[Asset]:
        """Fetch all tickers (paginated)."""
        ...

    def fetch_all_exchanges(
        self,
        asset_class: str = "stocks",
        locale: str = "us"
    ) -> List[Market]:
        """Fetch all exchanges."""
        ...
```

#### 6. EconomicDataProvider Protocol
```python
# src/api/providers/protocols/economic_data_provider.py

from typing import Protocol, List, Dict
from models.dataclass.fed_data import FedData


class EconomicDataProvider(Protocol):
    """Protocol for economic data (Fed, inflation, yields).

    Implementations: PolygonFedAdapter, FREDAdapter (future)
    """

    def fetch_inflation(self, limit: int = 10) -> List[FedData]:
        """Fetch recent inflation data."""
        ...

    def fetch_inflation_expectations(self, limit: int = 10) -> List[FedData]:
        """Fetch recent inflation expectations data."""
        ...

    def fetch_treasury_yields(self, limit: int = 10) -> List[FedData]:
        """Fetch recent treasury yields data."""
        ...

    def fetch_all_fed_data(self, limit: int = 10) -> Dict[str, List[FedData]]:
        """Fetch all types of Fed data in one call."""
        ...
```

### Adapter Pattern

Each provider implementation will be an **adapter** that wraps the actual provider:

```python
# src/api/providers/adapters/polygon_snapshot_adapter.py

from api.providers.protocols.snapshot_provider import SnapshotProvider
from api.providers.polygon_snapshot_provider import PolygonSnapshotProvider
from models.dataclass.snapshot import MarketSnapshot, TickerSnapshot
from typing import Optional


class PolygonSnapshotAdapter:
    """Adapter for Polygon Snapshot API.

    Wraps PolygonSnapshotProvider to implement SnapshotProvider protocol.
    """

    def __init__(self, api_key: str):
        self._provider = PolygonSnapshotProvider(api_key)

    def fetch_bulk_market_snapshot(self) -> Optional[MarketSnapshot]:
        """Delegate to Polygon provider."""
        return self._provider.fetch_bulk_market_snapshot()

    def fetch_single_ticker_snapshot(self, symbol: str) -> Optional[TickerSnapshot]:
        """Delegate to Polygon provider."""
        return self._provider.fetch_single_ticker_snapshot(symbol)

    def get_provider_name(self) -> str:
        return "polygon"
```

```python
# src/api/providers/adapters/yfinance_snapshot_adapter.py

import yfinance as yf
from api.providers.protocols.snapshot_provider import SnapshotProvider
from models.dataclass.snapshot import MarketSnapshot, TickerSnapshot
from typing import Optional


class YFinanceSnapshotAdapter:
    """Adapter for YFinance snapshot data.

    Implements SnapshotProvider protocol using yfinance library.
    """

    def __init__(self):
        pass  # YFinance doesn't require API key

    def fetch_bulk_market_snapshot(self) -> Optional[MarketSnapshot]:
        """
        YFinance doesn't have bulk snapshot - need to fetch individually.
        This is SLOWER than Polygon but FREE.
        """
        # Implementation: fetch tickers from database, query each
        ...

    def fetch_single_ticker_snapshot(self, symbol: str) -> Optional[TickerSnapshot]:
        """Fetch single ticker using yfinance library."""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info

            # Transform yfinance data to our TickerSnapshot model
            return self._transform_to_ticker_snapshot(info)
        except Exception as e:
            logger.error(f"YFinance error for {symbol}: {e}")
            return None

    def get_provider_name(self) -> str:
        return "yfinance"

    def _transform_to_ticker_snapshot(self, yf_data: dict) -> TickerSnapshot:
        """Transform YFinance data format to our TickerSnapshot model."""
        # Implementation: map YFinance fields to our model
        ...
```

### Provider Factory

A factory creates providers based on configuration:

```python
# src/api/providers/provider_factory.py

from typing import Optional
from utils.config_loader import ConfigLoader
from api.providers.protocols.snapshot_provider import SnapshotProvider
from api.providers.protocols.aggregates_provider import AggregatesProvider
from api.providers.protocols.news_provider import NewsProvider
# ... other protocols


class ProviderFactory:
    """Factory for creating data providers based on configuration.

    Supports:
    - Single provider mode: Use one provider for everything
    - Hybrid mode: Different providers for different data types
    - Fallback chains: Try provider A, fall back to provider B
    """

    @staticmethod
    def create_snapshot_provider(
        provider_name: Optional[str] = None,
        api_key: Optional[str] = None
    ) -> SnapshotProvider:
        """Create snapshot provider based on config or override.

        Args:
            provider_name: Override provider (default: from config)
            api_key: Override API key (default: from env/config)

        Returns:
            SnapshotProvider implementation
        """
        # Load from config if not provided
        if not provider_name:
            config = ConfigLoader().load_yaml("providers.yaml")
            provider_name = config["providers"]["snapshot"]["default"]

        # Create appropriate adapter
        if provider_name == "polygon":
            from api.providers.adapters.polygon_snapshot_adapter import PolygonSnapshotAdapter
            api_key = api_key or ConfigLoader().get_polygon_api_key()
            return PolygonSnapshotAdapter(api_key)

        elif provider_name == "yfinance":
            from api.providers.adapters.yfinance_snapshot_adapter import YFinanceSnapshotAdapter
            return YFinanceSnapshotAdapter()

        elif provider_name == "iex":
            from api.providers.adapters.iex_snapshot_adapter import IEXSnapshotAdapter
            api_key = api_key or ConfigLoader().get_iex_api_key()
            return IEXSnapshotAdapter(api_key)

        else:
            raise ValueError(f"Unknown snapshot provider: {provider_name}")

    @staticmethod
    def create_aggregates_provider(
        provider_name: Optional[str] = None,
        api_key: Optional[str] = None
    ) -> AggregatesProvider:
        """Create aggregates provider based on config."""
        ...

    @staticmethod
    def create_news_provider(
        provider_name: Optional[str] = None,
        api_key: Optional[str] = None
    ) -> NewsProvider:
        """Create news provider based on config."""
        ...

    # ... other factory methods
```

### Configuration File

```yaml
# configs/providers.yaml

# Provider configuration for TradeScout
# Allows easy swapping between data providers without code changes

providers:
  # Snapshot data (current prices, OHLCV)
  snapshot:
    default: "polygon"  # Options: polygon, yfinance, iex
    fallback: ["yfinance"]  # Try these if primary fails

  # Aggregates/bars data (historical, minute-level)
  aggregates:
    default: "polygon"
    fallback: ["yfinance"]

  # News and sentiment
  news:
    default: "polygon"
    fallback: []  # No free alternatives with sentiment

  # Market status and holidays
  market_status:
    default: "polygon"
    fallback: ["custom"]  # Use hardcoded US market hours

  # Reference data (tickers, exchanges)
  reference:
    default: "polygon"
    fallback: ["yfinance"]

  # Economic data (Fed, inflation, yields)
  economic:
    default: "polygon"
    fallback: ["fred"]  # FRED API (free, official source)

# API keys (read from environment variables)
api_keys:
  polygon: "${POLYGON_API_KEY}"
  iex: "${IEX_API_KEY}"
  alpha_vantage: "${ALPHA_VANTAGE_API_KEY}"
  finnhub: "${FINNHUB_API_KEY}"
  fred: "${FRED_API_KEY}"

# Provider-specific settings
settings:
  polygon:
    base_url: "https://api.polygon.io"
    rate_limit_per_minute: 5  # Stocks Basic tier

  yfinance:
    # YFinance has no official rate limits, but be respectful
    delay_between_calls_ms: 100

  iex:
    base_url: "https://cloud.iexapis.com"
    rate_limit_per_second: 100  # Launch plan
```

### DataServiceV2 Refactoring

Update DataServiceV2 to use the factory:

```python
# src/services/data_service_v2.py

from api.providers.provider_factory import ProviderFactory


class DataServiceV2:
    def __init__(self, session: Session, polygon_api_key: str = None):
        """Initialize DataService V2 with provider abstraction.

        Args:
            session: SQLModel session
            polygon_api_key: Polygon API key (optional, reads from config if not provided)
        """
        self.session = session

        # Initialize repositories (unchanged)
        self.asset_repository = AssetRepository(session)
        # ... other repositories

        # Initialize providers via factory (NEW - provider-agnostic)
        self.snapshot_provider = ProviderFactory.create_snapshot_provider()
        self.aggregates_provider = ProviderFactory.create_aggregates_provider()
        self.news_provider = ProviderFactory.create_news_provider()
        self.market_status_provider = ProviderFactory.create_market_status_provider()
        self.reference_provider = ProviderFactory.create_reference_provider()
        self.economic_provider = ProviderFactory.create_economic_provider()

        # Cache services (unchanged)
        self.asset_cache = CacheService[AssetSQLModel](...)
        # ...

    def update_market_snapshot(self, force_refresh: bool = False) -> MarketSnapshotUpdateStats:
        """Update market snapshot - now provider-agnostic."""
        # Business logic stays the same, just uses self.snapshot_provider
        market_snapshot = self.snapshot_provider.fetch_bulk_market_snapshot()
        # ... rest of logic unchanged
```

---

## Implementation Phases

### Phase 1: Protocol Definitions (Week 1)
**Goal:** Define interfaces without breaking existing code

**Tasks:**
1. Create `src/api/providers/protocols/` directory
2. Define 6 protocol interfaces:
   - `snapshot_provider.py`
   - `aggregates_provider.py`
   - `news_provider.py`
   - `market_status_provider.py`
   - `reference_data_provider.py`
   - `economic_data_provider.py`
3. Add type hints using `typing.Protocol`
4. Document each protocol method with docstrings

**Deliverable:** Protocol interfaces that existing providers can implement

**Testing:** Type checking with mypy, no runtime changes

---

### Phase 2: Polygon Adapters (Week 1-2)
**Goal:** Wrap existing Polygon providers with adapters

**Tasks:**
1. Create `src/api/providers/adapters/` directory
2. Create 6 Polygon adapters (one per protocol):
   - `polygon_snapshot_adapter.py` - wraps `PolygonSnapshotProvider`
   - `polygon_aggregates_adapter.py` - wraps `PolygonAggregatesProvider`
   - `polygon_news_adapter.py` - wraps `PolygonNewsProvider`
   - `polygon_market_status_adapter.py` - wraps `PolygonMarketStatusProvider`
   - `polygon_reference_adapter.py` - wraps `PolygonTickersProvider` + `PolygonMarketsProvider`
   - `polygon_economic_adapter.py` - wraps `PolygonFedProvider`
3. Each adapter delegates to existing Polygon provider
4. Update existing providers to implement protocols (if needed)

**Deliverable:** Polygon adapters that work identically to existing providers

**Testing:** Integration tests showing adapters work same as direct providers

---

### Phase 3: Provider Factory + Config (Week 2)
**Goal:** Add factory and configuration system

**Tasks:**
1. Create `src/api/providers/provider_factory.py`
2. Implement factory methods for each protocol
3. Create `configs/providers.yaml` configuration file
4. Add configuration loading in factory
5. Add environment variable support for API keys

**Deliverable:** Factory that creates providers based on config

**Testing:** Unit tests for factory, verify config loading works

---

### Phase 4: DataServiceV2 Refactoring (Week 2)
**Goal:** Update DataServiceV2 to use factory

**Tasks:**
1. Update DataServiceV2.__init__() to use ProviderFactory
2. Replace direct provider instantiation with factory calls
3. Update all method calls to use protocol types instead of Polygon types
4. Add backward compatibility (accept polygon_api_key param but also read from config)
5. Update BootstrapService to use factory

**Deliverable:** DataServiceV2 using provider abstraction layer

**Testing:** Full integration tests, verify all commands work identically

---

### Phase 5: YFinance Adapter (Week 3)
**Goal:** Implement first alternative provider

**Tasks:**
1. Research YFinance library API
2. Create YFinance adapters:
   - `yfinance_snapshot_adapter.py` - most critical
   - `yfinance_aggregates_adapter.py` - historical data
   - `yfinance_reference_adapter.py` - ticker metadata
3. Implement data transformation (YFinance format → our models)
4. Handle YFinance limitations (no bulk snapshot, rate limits)
5. Add YFinance to factory
6. Update `providers.yaml` config

**Deliverable:** Working YFinance adapters for snapshot + aggregates + reference

**Testing:**
- Unit tests for each adapter
- Integration tests comparing YFinance vs Polygon data
- Performance tests (YFinance is slower for bulk operations)

---

### Phase 6: Fallback Chains (Week 3-4)
**Goal:** Add automatic failover between providers

**Tasks:**
1. Create `FallbackProvider` wrapper class
2. Implement retry logic with fallback chain
3. Add logging for provider switches
4. Update factory to create fallback chains from config
5. Add circuit breaker pattern (stop trying failed provider temporarily)

**Example:**
```python
class FallbackSnapshotProvider:
    def __init__(self, providers: List[SnapshotProvider]):
        self.providers = providers

    def fetch_bulk_market_snapshot(self) -> Optional[MarketSnapshot]:
        for provider in self.providers:
            try:
                result = provider.fetch_bulk_market_snapshot()
                if result:
                    logger.info(f"Success with provider: {provider.get_provider_name()}")
                    return result
            except Exception as e:
                logger.warning(f"Provider {provider.get_provider_name()} failed: {e}")
                continue

        logger.error("All snapshot providers failed")
        return None
```

**Deliverable:** Automatic failover working between providers

**Testing:**
- Mock provider failures
- Verify fallback logic
- Test circuit breaker prevents infinite retries

---

### Phase 7: Additional Providers (Week 4+)
**Goal:** Add more provider options

**Optional providers to implement:**
1. **IEX Cloud** - High-quality data, $9/month minimum
2. **Alpha Vantage** - News sentiment API, free tier limited
3. **Finnhub** - Good free tier (60 calls/min)
4. **FRED** - Federal Reserve economic data (official source, free)
5. **Custom Market Status** - Hardcoded US market hours (fallback)

**Tasks per provider:**
1. Research provider API
2. Create adapter implementing relevant protocols
3. Add to factory
4. Update config file
5. Test integration

---

## Migration Strategy

### Migration Path

**Before Dec 2, 2025:**
1. Complete Phases 1-4 (protocols, adapters, factory, refactoring)
2. System still uses Polygon by default (no behavior change)
3. Config set to `default: "polygon"` for all data types
4. Thoroughly test in production

**On Dec 2, 2025 (Polygon downgrade):**
- Option A: Keep Polygon Starter ($29/month) - no config changes needed
- Option B: Switch to hybrid:
  ```yaml
  providers:
    snapshot:
      default: "yfinance"  # FREE
      fallback: ["polygon"]  # Use Polygon Basic as fallback
    aggregates:
      default: "polygon"  # Polygon Basic still has aggregates (EOD)
    news:
      default: "alpha_vantage"  # Or disable news feature
    market_status:
      default: "polygon"  # Still works on Basic
    reference:
      default: "polygon"  # Still works on Basic
    economic:
      default: "polygon"  # Still works on Basic
  ```

### Rollback Plan

If something breaks during migration:
1. Revert `providers.yaml` to use Polygon for everything
2. DataServiceV2 still works with Polygon providers
3. No code changes needed, just config change
4. Deploy config update via git

### Testing Strategy

**Unit Tests:**
- Each protocol has test suite
- Each adapter has test suite mocking underlying provider
- Factory has tests for provider creation

**Integration Tests:**
- End-to-end tests for each provider
- Verify data transformation is correct
- Compare output between providers (Polygon vs YFinance)

**Performance Tests:**
- Benchmark each provider (API call time, rate limits)
- Test bulk operations (10k tickers)
- Identify bottlenecks

**Production Testing:**
- Use fallback chains in production
- Monitor logs for provider failures
- Track provider usage metrics

---

## Cost Optimization Strategy

### Hybrid Provider Usage

**Free Tier Maximization:**
```yaml
# Most cost-effective configuration using free tiers

providers:
  snapshot:
    default: "yfinance"  # FREE (slower but works)
    fallback: ["polygon"]  # Polygon Basic as backup

  aggregates:
    default: "polygon"  # Polygon Basic has historical (EOD)
    fallback: ["yfinance"]

  news:
    # News is tough - either pay or skip
    default: null  # Disable news feature
    fallback: []

  market_status:
    default: "polygon"  # Works on Basic
    fallback: ["custom"]  # Hardcoded US hours

  reference:
    default: "polygon"  # Works on Basic (one-time bootstrap)
    fallback: ["yfinance"]

  economic:
    default: "fred"  # FREE official source
    fallback: ["polygon"]
```

**Monthly Cost:** $0 (fully free)

**Trade-offs:**
- YFinance snapshot is slower (no bulk API, must fetch individually)
- No real-time news/sentiment
- Polygon Basic rate limits (5/min) for reference data

### Performance Optimization for YFinance

YFinance doesn't have bulk snapshot, so we need to optimize:

**Parallel Fetching:**
```python
import concurrent.futures

class YFinanceSnapshotAdapter:
    def fetch_bulk_market_snapshot(self) -> Optional[MarketSnapshot]:
        # Get all symbols from database
        symbols = self._get_all_symbols()

        # Fetch in parallel (respect rate limits)
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(self.fetch_single_ticker_snapshot, sym)
                      for sym in symbols]

            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        # Combine into MarketSnapshot
        return MarketSnapshot(tickers={r.symbol: r for r in results if r})
```

**Caching:**
- Cache YFinance results aggressively (10-minute TTL)
- Use Polygon Basic for reference data (works well on Basic)
- Only fetch snapshots during market hours

---

## Benefits of This Approach

1. **Flexibility**: Swap providers via config file, no code changes
2. **Resilience**: Automatic failover if provider fails
3. **Cost Optimization**: Use free providers where possible, pay only for critical features
4. **Testing**: Easy to test with mock providers
5. **Future-Proof**: Adding new providers is straightforward
6. **Vendor Independence**: No lock-in to any single provider

---

## Risks & Mitigation

### Risk 1: Data Quality Differences
**Risk:** YFinance data may differ from Polygon (timestamps, precision, availability)

**Mitigation:**
- Comprehensive integration tests comparing providers
- Document known differences in `docs/PROVIDER_COMPARISON.md`
- Monitor data discrepancies in production
- Use Polygon as fallback for critical operations

### Risk 2: Performance Degradation
**Risk:** YFinance bulk snapshot is significantly slower than Polygon

**Mitigation:**
- Parallel fetching (10-20 concurrent requests)
- Aggressive caching (10-minute TTL)
- Only fetch during market hours
- Consider keeping Polygon Starter for critical performance needs

### Risk 3: Rate Limiting
**Risk:** Free providers have undocumented rate limits

**Mitigation:**
- Add configurable delays between requests
- Implement exponential backoff
- Monitor provider error rates
- Fall back to Polygon Basic if rate limited

### Risk 4: Breaking Changes
**Risk:** Providers change APIs without notice (especially YFinance)

**Mitigation:**
- Pin provider library versions
- Comprehensive test suite detects breakages
- Monitor provider status/changelogs
- Have fallback providers configured

---

## Success Metrics

**Week 1-2:**
- ✅ All protocols defined and documented
- ✅ Polygon adapters passing tests
- ✅ Factory creates providers from config

**Week 2-3:**
- ✅ DataServiceV2 refactored to use factory
- ✅ All existing commands work identically
- ✅ Zero regressions in functionality

**Week 3-4:**
- ✅ YFinance adapters implemented
- ✅ Fallback chains working
- ✅ Can switch between providers via config

**Production Readiness:**
- ✅ 100% test coverage for adapters
- ✅ Performance benchmarks documented
- ✅ Rollback plan tested
- ✅ Provider comparison guide written

---

## Next Steps

1. **Review this plan** - Discuss with stakeholders, adjust timeline
2. **Create GitHub issues** - One issue per phase
3. **Start Phase 1** - Define protocol interfaces
4. **Set up project board** - Track progress through phases

**Target Completion:** December 1, 2025 (before Polygon downgrade)

---

## References

- **Current Architecture:** `src/api/providers/*.py`, `src/services/data_service_v2.py`
- **Polygon API Audit:** `docs/POLYGON.md`
- **Provider Comparison:** `docs/PROVIDER_COMPARISON.md` (to be created)
- **Python Protocols:** https://peps.python.org/pep-0544/
- **Adapter Pattern:** https://refactoring.guru/design-patterns/adapter
