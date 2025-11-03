# Assets Commands Architecture - Planning

**Status:** Planning Phase
**Date:** 2025-10-20
**Purpose:** Refactor market data updates into separate, composable commands with proper separation of concerns

---

## Overview

This plan separates the current monolithic `market update` command into distinct data type updates, enabling:
- Independent updates for prices, ratios, indicators, and statistics
- Consistent naming conventions (singular vs plural)
- Market update as an orchestrator that runs all updates
- Better screening capabilities across all data types

---

## Naming Convention

**Singular = Operations on ONE asset:**
- `./tradescout asset AAPL` - Show info for one asset (existing command, no changes)

**Plural = Bulk operations on MANY assets:**
- `./tradescout assets prices update` - Update prices for all assets
- `./tradescout assets ratios update` - Update ratios for all assets
- `./tradescout assets indicators update` - Update indicators for all assets
- `./tradescout assets stats update` - Update statistics for all assets

**Market = Orchestrator:**
- `./tradescout market update` - Runs all four `assets` updates in sequence

---

## Command Structure

```
tradescout
├── asset SYMBOL              # Singular - info for ONE asset (existing)
│
├── assets                    # NEW - Plural - bulk operations
│   ├── prices
│   │   ├── update [--date YYYY-MM-DD] [--force]
│   │   └── info SYMBOL
│   ├── ratios
│   │   ├── update [--symbols AAPL,MSFT] [--universe default] [--force]
│   │   └── info SYMBOL [--history] [--quarters N]
│   ├── indicators
│   │   ├── update [--symbols AAPL,MSFT] [--universe default] [--force]
│   │   └── info SYMBOL [--type rsi|macd|sma|ema]
│   └── stats
│       ├── update [--symbols AAPL,MSFT] [--universe default] [--force]
│       └── info SYMBOL
│
└── market
    ├── update [--force]      # Orchestrator - runs all assets updates
    └── context               # Existing - no changes
```

---

## Database Architecture

### Three Separate Tables (Option B from discussion)

**1. `asset_ratios` - Quarterly Fundamental Data**
```sql
CREATE TABLE asset_ratios (
    id INTEGER PRIMARY KEY,
    asset_id INTEGER NOT NULL,
    provider_id INTEGER NOT NULL,

    -- Time period
    period_type TEXT NOT NULL,       -- 'quarterly', 'annual', 'ttm'
    fiscal_period TEXT,               -- 'Q1', 'Q2', 'Q3', 'Q4'
    fiscal_year INTEGER,
    period_end_date DATE,

    -- Profitability Ratios
    roe REAL,                        -- Return on Equity
    roa REAL,                        -- Return on Assets
    roic REAL,                       -- Return on Invested Capital
    profit_margin REAL,
    operating_margin REAL,
    gross_margin REAL,

    -- Liquidity Ratios
    current_ratio REAL,
    quick_ratio REAL,
    cash_ratio REAL,

    -- Leverage Ratios
    debt_to_equity REAL,
    debt_to_assets REAL,
    interest_coverage REAL,

    -- Efficiency Ratios
    asset_turnover REAL,
    inventory_turnover REAL,
    receivables_turnover REAL,

    -- Valuation Ratios
    pe_ratio REAL,
    pb_ratio REAL,
    ps_ratio REAL,
    ev_ebitda REAL,
    dividend_yield REAL,

    -- Growth Metrics
    revenue_growth REAL,             -- YoY
    earnings_growth REAL,            -- YoY

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (asset_id) REFERENCES assets(id),
    FOREIGN KEY (provider_id) REFERENCES providers(id),
    UNIQUE(asset_id, period_type, fiscal_year, fiscal_period)
);

CREATE INDEX idx_asset_ratios_asset ON asset_ratios(asset_id);
CREATE INDEX idx_asset_ratios_period ON asset_ratios(fiscal_year, fiscal_period);
```

**Update Frequency:** Quarterly (after earnings releases)
**TTL:** 7-14 days
**API Source:** `/vX/reference/financials` (Polygon)

---

**2. `asset_indicators` - Daily Technical Signals**
```sql
CREATE TABLE asset_indicators (
    id INTEGER PRIMARY KEY,
    asset_id INTEGER NOT NULL,
    provider_id INTEGER NOT NULL,

    -- Time info
    timestamp INTEGER NOT NULL,      -- Unix milliseconds
    timespan TEXT NOT NULL,          -- 'minute', 'hour', 'day', 'week'

    -- RSI
    rsi_14 REAL,                     -- 14-period RSI
    rsi_window INTEGER DEFAULT 14,

    -- MACD
    macd_value REAL,                 -- MACD line
    macd_signal REAL,                -- Signal line
    macd_histogram REAL,             -- MACD - Signal
    macd_short_window INTEGER DEFAULT 12,
    macd_long_window INTEGER DEFAULT 26,
    macd_signal_window INTEGER DEFAULT 9,

    -- Moving Averages
    sma_20 REAL,
    sma_50 REAL,
    sma_200 REAL,
    ema_12 REAL,
    ema_20 REAL,
    ema_50 REAL,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (asset_id) REFERENCES assets(id),
    FOREIGN KEY (provider_id) REFERENCES providers(id),
    UNIQUE(asset_id, timestamp, timespan)
);

CREATE INDEX idx_asset_indicators_asset ON asset_indicators(asset_id);
CREATE INDEX idx_asset_indicators_timestamp ON asset_indicators(timestamp DESC);
CREATE INDEX idx_asset_indicators_lookup ON asset_indicators(asset_id, timespan, timestamp DESC);
```

**Update Frequency:** Daily (or intraday for minute/hour timespans)
**TTL:** 1 hour (intraday), 24 hours (daily)
**API Source:** `/v1/indicators/*` (Polygon)

---

**3. `asset_price_statistics` - Daily Price Aggregations**
```sql
CREATE TABLE asset_price_statistics (
    id INTEGER PRIMARY KEY,
    asset_id INTEGER NOT NULL,
    provider_id INTEGER NOT NULL,

    -- As-of date
    as_of_date DATE NOT NULL,

    -- 52-Week Statistics
    high_52w REAL,                   -- 52-week high
    low_52w REAL,                    -- 52-week low
    range_52w_pct REAL,              -- Position in 52w range (0-100%)

    -- Volume Statistics
    avg_volume_30d INTEGER,          -- 30-day average volume
    avg_volume_90d INTEGER,          -- 90-day average volume
    avg_volume_1y INTEGER,           -- 1-year average volume

    -- Returns
    return_1d_pct REAL,              -- 1-day return
    return_5d_pct REAL,              -- 5-day return
    return_1m_pct REAL,              -- 1-month return
    return_3m_pct REAL,              -- 3-month return
    return_ytd_pct REAL,             -- Year-to-date return
    return_1y_pct REAL,              -- 1-year return

    -- Volatility
    volatility_30d REAL,             -- 30-day historical volatility
    volatility_90d REAL,             -- 90-day historical volatility
    atr_14 REAL,                     -- Average True Range (14-day)

    -- Beta
    beta_1y REAL,                    -- 1-year beta vs S&P 500

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (asset_id) REFERENCES assets(id),
    FOREIGN KEY (provider_id) REFERENCES providers(id),
    UNIQUE(asset_id, as_of_date)
);

CREATE INDEX idx_asset_price_stats_asset ON asset_price_statistics(asset_id);
CREATE INDEX idx_asset_price_stats_date ON asset_price_statistics(as_of_date DESC);
```

**Update Frequency:** Daily
**TTL:** 24 hours
**Calculation:** Computed from `PolygonAggregatesProvider` historical data (no new API)

---

### Screening View

**Create unified view for easy screening:**
```sql
CREATE VIEW asset_latest_statistics AS
SELECT
    a.id as asset_id,
    a.symbol,
    a.name,

    -- Latest Ratios (most recent quarter)
    ar.pe_ratio,
    ar.roe,
    ar.roa,
    ar.profit_margin,
    ar.current_ratio,
    ar.debt_to_equity,
    ar.fiscal_quarter,
    ar.fiscal_year,

    -- Latest Indicators (most recent day)
    ai.rsi_14,
    ai.macd_value,
    ai.macd_signal,
    ai.macd_histogram,
    ai.sma_50,
    ai.ema_20,
    ai.timestamp as indicators_timestamp,

    -- Latest Price Statistics
    aps.high_52w,
    aps.low_52w,
    aps.range_52w_pct,
    aps.avg_volume_30d,
    aps.return_ytd_pct,
    aps.volatility_30d,
    aps.as_of_date as stats_date

FROM assets a
LEFT JOIN asset_ratios ar ON a.id = ar.asset_id
    AND ar.id = (
        SELECT id FROM asset_ratios
        WHERE asset_id = a.id
        ORDER BY fiscal_year DESC, fiscal_period DESC
        LIMIT 1
    )
LEFT JOIN asset_indicators ai ON a.id = ai.asset_id
    AND ai.id = (
        SELECT id FROM asset_indicators
        WHERE asset_id = a.id AND timespan = 'day'
        ORDER BY timestamp DESC
        LIMIT 1
    )
LEFT JOIN asset_price_statistics aps ON a.id = aps.asset_id
    AND aps.id = (
        SELECT id FROM asset_price_statistics
        WHERE asset_id = a.id
        ORDER BY as_of_date DESC
        LIMIT 1
    );
```

**Usage:**
```sql
-- Screen for value + momentum + technical strength
SELECT * FROM asset_latest_statistics
WHERE pe_ratio < 20
  AND roe > 0.15
  AND rsi_14 < 30
  AND range_52w_pct > 0.8
  AND avg_volume_30d > 1000000;
```

---

## Implementation Phases

### Phase 1: Planning & Documentation (Week 1)

**Deliverables:**
- [ ] Create `docs/planning/PRICE_STATISTICS_PLANNING.md`
- [ ] Review/update `docs/planning/RATIOS_PLANNING.md`
- [ ] Review/update `docs/planning/INDICATORS_PLANNING.md`
- [ ] Document API endpoints, TTL strategies, calculation methods
- [ ] Define screening use cases and query patterns

---

### Phase 2: Database Schema & Models (Week 1)

**SQLModels:**
- [ ] `src/models/sqlmodel/asset_ratios_sqlmodel.py`
- [ ] `src/models/sqlmodel/asset_indicators_sqlmodel.py`
- [ ] `src/models/sqlmodel/asset_price_statistics_sqlmodel.py`

**Dataclasses:**
- [ ] `src/models/dataclass/ratios.py`
- [ ] `src/models/dataclass/indicators.py`
- [ ] `src/models/dataclass/price_statistics.py`

**Result Models:**
- [ ] `src/models/result/ratios_result.py` (for update stats)
- [ ] `src/models/result/indicators_result.py` (for update stats)
- [ ] `src/models/result/stats_result.py` (for update stats)

**Database Migration:**
- [ ] Create migration script to add three tables
- [ ] Create `asset_latest_statistics` view
- [ ] Add indexes

---

### Phase 3: Providers (Week 2)

**1. PolygonRatiosProvider** (`src/api/providers/polygon_ratios_provider.py`)
```python
class PolygonRatiosProvider(BaseAPIProvider):
    def fetch_ratios(
        self,
        symbol: str,
        period: str = 'quarterly',
        limit: int = 8
    ) -> List[AssetRatios]:
        """Fetch financial ratios from Polygon /vX/reference/financials"""
```

**2. PolygonIndicatorsProvider** (`src/api/providers/polygon_indicators_provider.py`)
```python
class PolygonIndicatorsProvider(BaseAPIProvider):
    def fetch_rsi(self, symbol: str, window: int = 14, timespan: str = 'day') -> List[Indicator]:
    def fetch_macd(self, symbol: str, short: int = 12, long: int = 26, signal: int = 9) -> List[Indicator]:
    def fetch_sma(self, symbol: str, window: int = 50, timespan: str = 'day') -> List[Indicator]:
    def fetch_ema(self, symbol: str, window: int = 20, timespan: str = 'day') -> List[Indicator]:
    def fetch_all_indicators(self, symbol: str) -> Dict[str, List[Indicator]]:
```

**3. PriceStatisticsCalculator** (`src/services/price_statistics_calculator.py`)
```python
class PriceStatisticsCalculator:
    """Calculate price statistics from historical aggregates data"""

    def __init__(self, aggregates_provider: PolygonAggregatesProvider):
        self.aggregates_provider = aggregates_provider

    def calculate_statistics(self, symbol: str, as_of_date: date) -> PriceStatistics:
        """Calculate all statistics for a symbol"""
        # Fetch last 252 trading days
        # Calculate 52w high/low, avg volumes, returns, volatility, beta
```

---

### Phase 4: Repositories (Week 2)

**1. AssetRatiosRepository** (`src/repositories/asset_ratios_repository.py`)
```python
class AssetRatiosRepository(BaseRepository):
    def get_latest_ratios(self, asset_id: int) -> Optional[AssetRatios]
    def get_ratios_by_period(self, asset_id: int, fiscal_quarter: str, fiscal_year: int) -> Optional[AssetRatios]
    def get_ratios_history(self, asset_id: int, num_periods: int = 8) -> List[AssetRatios]
    def bulk_upsert(self, ratios_list: List[AssetRatios]) -> int
```

**2. AssetIndicatorsRepository** (`src/repositories/asset_indicators_repository.py`)
```python
class AssetIndicatorsRepository(BaseRepository):
    def get_latest_indicators(self, asset_id: int, timespan: str = 'day') -> Optional[AssetIndicators]
    def get_indicator_history(self, asset_id: int, indicator_type: str, limit: int = 30) -> List[AssetIndicators]
    def bulk_upsert(self, indicators_list: List[AssetIndicators]) -> int
```

**3. AssetPriceStatisticsRepository** (`src/repositories/asset_price_statistics_repository.py`)
```python
class AssetPriceStatisticsRepository(BaseRepository):
    def get_latest_stats(self, asset_id: int) -> Optional[PriceStatistics]
    def get_stats_by_date(self, asset_id: int, as_of_date: date) -> Optional[PriceStatistics]
    def bulk_upsert(self, stats_list: List[PriceStatistics]) -> int
```

---

### Phase 5: Services (Week 3)

**Extend DataServiceV2:**

```python
class DataServiceV2:
    # ... existing methods ...

    # ========================================
    # RATIOS
    # ========================================
    def update_asset_ratios(
        self,
        symbols: Optional[List[str]] = None,
        force_refresh: bool = False
    ) -> RatiosUpdateResult:
        """Update ratios for specified symbols or all universe assets"""

    def get_asset_ratios(self, asset_id: int) -> Optional[AssetRatios]:
        """Get latest ratios for an asset"""

    # ========================================
    # INDICATORS
    # ========================================
    def update_asset_indicators(
        self,
        symbols: Optional[List[str]] = None,
        force_refresh: bool = False
    ) -> IndicatorsUpdateResult:
        """Update indicators for specified symbols or all universe assets"""

    def get_asset_indicators(self, asset_id: int) -> Optional[AssetIndicators]:
        """Get latest indicators for an asset"""

    # ========================================
    # PRICE STATISTICS
    # ========================================
    def update_asset_price_statistics(
        self,
        symbols: Optional[List[str]] = None,
        force_refresh: bool = False
    ) -> StatsUpdateResult:
        """Update price statistics for specified symbols or all universe assets"""

    def get_asset_price_statistics(self, asset_id: int) -> Optional[PriceStatistics]:
        """Get latest price statistics for an asset"""
```

---

### Phase 6: CLI Commands (Week 3-4)

**Create new file:** `src/cli/assets_commands.py`

```python
import click
from rich.console import Console
from .main import pass_config

console = Console()

@click.group()
@pass_config
def assets(app_context):
    """Bulk operations for asset data (prices, ratios, indicators, statistics)"""
    pass

# ============================================
# PRICES SUBCOMMAND
# ============================================
@assets.group()
def prices():
    """Asset price data operations"""
    pass

@prices.command()
@click.option("--date", help="Specific date to backfill (YYYY-MM-DD)")
@click.option("--force", is_flag=True, help="Force refresh, bypass TTL cache")
@pass_config
def update(app_context, date, force):
    """Update asset prices (current snapshot or historical backfill)"""
    # Extract current market update logic from market_commands.py
    pass

@prices.command()
@click.argument("symbol")
@pass_config
def info(app_context, symbol):
    """Show price data for a symbol"""
    pass

# ============================================
# RATIOS SUBCOMMAND
# ============================================
@assets.group()
def ratios():
    """Asset financial ratios operations"""
    pass

@ratios.command()
@click.option("--symbols", help="Comma-separated list of symbols")
@click.option("--universe", help="Update all symbols in universe")
@click.option("--force", is_flag=True, help="Force refresh, bypass TTL cache")
@pass_config
def update(app_context, symbols, universe, force):
    """Update financial ratios for assets"""
    pass

@ratios.command()
@click.argument("symbol")
@click.option("--history", is_flag=True, help="Show historical ratios")
@click.option("--quarters", type=int, default=8, help="Number of quarters of history")
@pass_config
def info(app_context, symbol, history, quarters):
    """Show financial ratios for a symbol"""
    pass

# ============================================
# INDICATORS SUBCOMMAND
# ============================================
@assets.group()
def indicators():
    """Asset technical indicators operations"""
    pass

@indicators.command()
@click.option("--symbols", help="Comma-separated list of symbols")
@click.option("--universe", help="Update all symbols in universe")
@click.option("--force", is_flag=True, help="Force refresh, bypass TTL cache")
@pass_config
def update(app_context, symbols, universe, force):
    """Update technical indicators for assets"""
    pass

@indicators.command()
@click.argument("symbol")
@click.option("--type", help="Specific indicator: rsi, macd, sma, ema")
@pass_config
def info(app_context, symbol, type):
    """Show technical indicators for a symbol"""
    pass

# ============================================
# STATS SUBCOMMAND
# ============================================
@assets.group()
def stats():
    """Asset price statistics operations"""
    pass

@stats.command()
@click.option("--symbols", help="Comma-separated list of symbols")
@click.option("--universe", help="Update all symbols in universe")
@click.option("--force", is_flag=True, help="Force refresh, bypass TTL cache")
@pass_config
def update(app_context, symbols, universe, force):
    """Update price statistics (52w high/low, avg volume, etc)"""
    pass

@stats.command()
@click.argument("symbol")
@pass_config
def info(app_context, symbol):
    """Show price statistics for a symbol"""
    pass
```

**Refactor market_commands.py:**

```python
@market.command()
@click.option("--force", is_flag=True, help="Force refresh all data")
@pass_config
def update(app_context, force):
    """Update all market data (orchestrates prices, ratios, indicators, stats)"""

    console.print("[bold cyan]🌍 Complete Market Update[/bold cyan]\n")

    ctx = click.get_current_context()

    # 1. Update asset prices
    console.print("[blue]Step 1/4: Updating asset prices...[/blue]")
    ctx.invoke(assets_prices_update, force=force)

    # 2. Update asset ratios
    console.print("\n[blue]Step 2/4: Updating asset ratios...[/blue]")
    ctx.invoke(assets_ratios_update, universe="default", force=force)

    # 3. Update asset indicators
    console.print("\n[blue]Step 3/4: Updating asset indicators...[/blue]")
    ctx.invoke(assets_indicators_update, universe="default", force=force)

    # 4. Update asset statistics
    console.print("\n[blue]Step 4/4: Updating asset statistics...[/blue]")
    ctx.invoke(assets_stats_update, universe="default", force=force)

    console.print("\n[green]✓ Complete market update finished[/green]")
```

**Register in main.py:**

```python
from cli.assets_commands import assets

# ... existing imports ...

cli.add_command(assets)  # Add new assets command group
```

---

### Phase 7: Integration (Week 4)

**Gap Analysis Integration:**

```bash
# Enrich gap candidates with fundamental/technical context
./tradescout gap analyze --with-ratios
./tradescout gap analyze --with-indicators
./tradescout gap analyze --with-all  # Both ratios and indicators
```

**Screener Integration:**

Update screener YAML configs to support new fields:

```yaml
name: value_momentum_screener
description: "Value stocks with improving fundamentals and technical momentum"
enabled: true
valid_sessions: ["regular"]

filters:
  # Fundamental filters (from asset_ratios)
  - field: "pe_ratio"
    operator: "<"
    value: 20
  - field: "roe"
    operator: ">"
    value: 0.15
  - field: "current_ratio"
    operator: ">"
    value: 1.5

  # Technical filters (from asset_indicators)
  - field: "rsi_14"
    operator: "<"
    value: 30
  - field: "price_vs_sma_50"
    operator: "="
    value: "above"

  # Price statistics (from asset_price_statistics)
  - field: "range_52w_pct"
    operator: ">"
    value: 0.8
  - field: "avg_volume_30d"
    operator: ">"
    value: 1000000
```

---

## Success Criteria

### Command Functionality
- [ ] `./tradescout asset AAPL` still works unchanged (singular)
- [ ] `./tradescout assets prices update` updates snapshot data
- [ ] `./tradescout assets prices update --date 2025-10-15` backfills historical
- [ ] `./tradescout assets ratios update` fetches quarterly fundamentals
- [ ] `./tradescout assets indicators update` fetches technical signals
- [ ] `./tradescout assets stats update` calculates price statistics
- [ ] `./tradescout market update` orchestrates all four updates

### Data Quality
- [ ] Ratios update quarterly with proper fiscal period tracking
- [ ] Indicators update daily/intraday with configurable timespans
- [ ] Statistics calculated correctly from historical aggregates
- [ ] TTL respected for each data type independently

### Screening Capabilities
- [ ] Can screen by: `pe_ratio < 20 AND rsi_14 < 30`
- [ ] Can screen by: `high_52w_pct > 0.8 AND avg_volume_30d > 1M`
- [ ] Can screen by: `roe > 15% AND macd_crossover = 'bullish'`
- [ ] View `asset_latest_statistics` performs well (indexed joins)

### Integration
- [ ] Gap analysis enriches candidates with ratios/indicators
- [ ] Asset info command shows all statistics
- [ ] Screeners support new filter fields
- [ ] Web API exposes new endpoints

---

## Future Enhancements

### Historical Trending
- [ ] Chart ratio trends over last 8 quarters
- [ ] Chart indicator trends over last 30 days
- [ ] Detect improving/declining metrics

### Advanced Screening
- [ ] Combo filters: "RSI < 30 AND improving ROE"
- [ ] Percentile rankings: "Top 10% by ROE"
- [ ] Sector-relative filters: "RSI < sector average"

### Alerts
- [ ] Alert when RSI crosses thresholds
- [ ] Alert when ratios improve quarter-over-quarter
- [ ] Alert when price breaks 52w high

### Backtesting
- [ ] Historical indicator performance
- [ ] Strategy validation using historical ratios/indicators

---

## References

- **Related Planning Docs:**
  - `docs/planning/RATIOS_PLANNING.md`
  - `docs/planning/INDICATORS_PLANNING.md`
  - `docs/planning/PRICE_STATISTICS_PLANNING.md` (to be created)

- **Current Implementation:**
  - `src/cli/market_commands.py` (market update)
  - `src/cli/asset_commands.py` (singular asset info)
  - `src/services/data_service_v2.py`

- **Polygon API Docs:**
  - Financials: https://polygon.io/docs/rest/stocks/fundamentals/ratios
  - Indicators: https://polygon.io/docs/rest/stocks/technical-indicators
  - Aggregates: https://polygon.io/docs/rest/stocks/aggregates

---

**Status:** Planning complete, awaiting implementation
**Next Steps:** Begin Phase 1 (Planning docs) when ready to implement
