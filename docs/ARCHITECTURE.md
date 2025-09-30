# TradeScout Architecture

*Note: This is a partial architecture documentation. Full architecture documentation is in progress and will be completed in future iterations.*

## Layer Separation: DataProvider vs Services

TradeScout follows a clear separation of concerns between data access and business logic:

### DataProvider (Data Access Layer)
- **Pure data fetching**: Makes API calls, database queries
- **No business logic**: Just gets raw data and transforms it to models
- **Caching**: Handles TTL-based caching of API responses
- **Examples**: `get_market_status()`, `get_market_holidays()`, `get_ticker_overview()`

**Responsibilities:**
- Polygon API integration
- Database CRUD operations
- Model transformation (API response → model objects)
- TTL-based caching using `data_update_metadata`
- Rate limiting and error handling

### Services (Business Logic Layer)
- **Complex business logic**: Combines multiple data sources with rules
- **Decision making**: Interprets raw data to make business decisions
- **Stateful operations**: May maintain context or state
- **Examples**: `MarketContextService.get_context()`

**Responsibilities:**
- Multi-source data combination
- Business rule application
- Complex calculations and interpretations
- Rich business object creation

## Example: MarketContextService

**DataProvider provides raw data:**
```python
market_status = data_provider.get_market_status()
# Returns: {"market": "extended-hours", "earlyHours": false, "afterHours": true}
```

**Service provides business intelligence:**
```python
context = market_context_service.get_context("XNYS")
# Returns: MarketContext with is_trading_day=True, current_session=AFTERHOURS,
#          previous_trading_date=Friday (skipping weekend), next_trading_date=Monday
```

**What MarketContextService adds:**
1. **Combines multiple data sources**: Market status + holidays + Market model + timezone logic
2. **Business rules**: "Is today a trading day?" "What session are we in?"
3. **Complex calculations**: Previous/next trading day logic (skip weekends + holidays)
4. **Context creation**: Builds rich `MarketContext` object with interpreted business meaning

## Benefits of This Separation

- **Single Responsibility**: DataProvider focuses on data access, Services focus on business logic
- **Testability**: Can test business logic separately from data access
- **Reusability**: Multiple services can use same DataProvider methods
- **Complexity management**: Keeps DataProvider clean and focused

---

*TODO: Complete architecture documentation including:*
- *Database schema and relationships*
- *Caching architecture and TTL strategy*
- *API integration patterns*
- *Model object hierarchy*
- *CLI command structure*
- *Screener engine architecture*
- *Bootstrap process flow*