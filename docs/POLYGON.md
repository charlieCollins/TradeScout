# Polygon.io (Massive) API Integration

**Last Updated:** November 18, 2025
**Current Status:** Stocks Starter plan (active until Dec 2, 2025)
**Future Plan:** Stocks Basic (free tier, starting Dec 2, 2025)

> **Note:** Polygon.io has rebranded to Massive.com, but APIs and integrations continue to work without interruption.

---

## What We Use Polygon For

TradeScout relies on Polygon.io for comprehensive market data across several key areas:

1. **Real-Time Market Snapshots** - Current prices, volume, and OHLCV data for all US stocks
2. **Historical Price Data** - Minute-level and daily bars for backtesting and analysis
3. **Market Context** - Trading session detection (premarket, regular, afterhours, closed)
4. **Universe Management** - Ticker reference data for bootstrapping our tradable assets
5. **News & Sentiment** - Financial news articles with AI-powered sentiment analysis
6. **Economic Data** - Federal Reserve inflation, treasury yields, and inflation expectations
7. **Extended Hours Volume** - Accurate premarket and afterhours volume calculation

---

## API Calls We Make: Basic vs Starter Availability

| API Endpoint | Provider File | Method(s) | Use Case | Basic | Starter | Impact if Lost |
|-------------|---------------|-----------|----------|-------|---------|----------------|
| **SNAPSHOTS** |
| `/v2/snapshot/locale/us/markets/stocks/tickers` | `polygon_snapshot_provider.py` | `fetch_bulk_market_snapshot()` | Bulk market updates, screeners, gap analysis | ❌ | ✅ | **CRITICAL** - Core feature loss |
| `/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}` | `polygon_snapshot_provider.py` | `fetch_single_ticker_snapshot()` | Single asset info, force refresh | ❌ | ✅ | **CRITICAL** - Core feature loss |
| **AGGREGATES** |
| `/v2/aggs/ticker/{symbol}/range/1/minute/{from}/{to}` | `polygon_aggregates_provider.py` | `fetch_minute_bars()` | Extended hours volume, gap validation | ⚠️ | ✅ | **HIGH** - Gap trading compromised |
| `/v2/aggs/ticker/{symbol}/range/1/day/{from}/{to}` | `polygon_aggregates_provider.py` | `get_daily_aggregates()` | Historical daily bars | ⚠️ | ✅ | **MEDIUM** - Backfill affected |
| `/v2/aggs/grouped/locale/us/market/stocks/{date}` | `polygon_aggregates_provider.py` | `fetch_grouped_daily_bars()` | Historical date backfill | ⚠️ | ✅ | **MEDIUM** - Backfill affected |
| **MARKET STATUS** |
| `/v1/marketstatus/now` | `polygon_market_status_provider.py` | `fetch_market_status()` | Session detection (PM/Regular/AH/Closed) | ✅ | ✅ | **MEDIUM** - Screener logic affected |
| `/v1/marketstatus/upcoming` | `polygon_market_status_provider.py` | `fetch_upcoming_holidays()` | Market holidays calendar | ✅ | ✅ | **LOW** - Trading calendar affected |
| **REFERENCE DATA** |
| `/v3/reference/tickers` | `polygon_tickers_provider.py` | `fetch_all_tickers()` | Universe bootstrapping | ✅ | ✅ | **LOW** - One-time bootstrap only |
| `/v3/reference/tickers/{symbol}` | `polygon_tickers_provider.py` | `fetch_ticker_details()` | Ticker metadata + fundamentals | ✅ | ✅ | **LOW** - One-time bootstrap only |
| `/v3/reference/exchanges` | `polygon_markets_provider.py` | `fetch_all_exchanges()` | Market/exchange data | ✅ | ✅ | **LOW** - One-time bootstrap only |
| **NEWS & SENTIMENT** |
| `/v2/reference/news` | `polygon_news_provider.py` | `fetch_news_for_ticker()` | News articles with AI sentiment | ❌ | ✅ | **MEDIUM** - Sentiment analysis lost |
| **FEDERAL RESERVE DATA** |
| `/fed/v1/inflation` | `polygon_fed_provider.py` | `fetch_inflation()` | CPI, inflation metrics | ✅ | ✅ | **LOW** - Alternative sources exist |
| `/fed/v1/inflation-expectations` | `polygon_fed_provider.py` | `fetch_inflation_expectations()` | Cleveland Fed models | ✅ | ✅ | **LOW** - Alternative sources exist |
| `/fed/v1/treasury-yields` | `polygon_fed_provider.py` | `fetch_treasury_yields()` | Treasury yield curves | ✅ | ✅ | **LOW** - Alternative sources exist |

### Legend
- ✅ **Available** - Fully accessible on this tier
- ❌ **Not Available** - Requires higher tier
- ⚠️ **Limited** - Available but restricted (end-of-day only, 2 years historical max, 5 API calls/min)

---

## Plan Comparison

| Feature | Stocks Basic (Free) | Stocks Starter ($29/mo) |
|---------|---------------------|------------------------|
| **API Rate Limit** | 5 calls/minute | Unlimited |
| **Historical Data** | 2 years | 5 years |
| **Data Timeliness** | End of day only | 15-minute delayed |
| **Snapshot API** | ❌ No | ✅ Yes |
| **WebSockets** | ❌ No | ✅ Yes |
| **Second Aggregates** | ❌ No | ✅ Yes |
| **Minute Aggregates** | ✅ Yes (historical/EOD) | ✅ Yes (intraday) |
| **Reference Data** | ✅ Yes | ✅ Yes |
| **Market Status** | ✅ Yes | ✅ Yes |
| **News API** | ❌ No | ✅ Yes (likely) |
| **Fed Data** | ✅ Yes | ✅ Yes |
| **File Downloads** | ❌ No | ✅ Unlimited |

---

## Critical Issues After Downgrade (Dec 2, 2025)

### 🚨 BREAKING: Snapshot API Loss
**Affected Endpoints:**
- `/v2/snapshot/locale/us/markets/stocks/tickers` (bulk)
- `/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}` (single)

**Impact:**
- ❌ `./tradescout market update` - Cannot refresh current market data
- ❌ `./tradescout asset info {symbol}` - Cannot fetch latest prices
- ❌ All screeners (gainers, losers, gaps) - No data source
- ❌ Gap analysis - Cannot detect gaps without current prices
- ❌ Real-time portfolio tracking - No price updates

**Why This Hurts:**
The Snapshot API is our **PRIMARY** data source. It provides:
- Current/last traded price (`min.c`)
- Previous day close (`prevDay.c`) for change calculations
- Day session data (`day.*`) for regular hours
- Volume data (`prevDay.v`, `day.v`, `min.v`, `min.av`)
- Provider timestamp (`updated`) for staleness detection

Without it, TradeScout loses 90% of its functionality.

### ⚠️ DEGRADED: Aggregates API Restrictions
**Affected Endpoints:**
- `/v2/aggs/ticker/{symbol}/range/1/minute/{from}/{to}`
- `/v2/aggs/ticker/{symbol}/range/1/day/{from}/{to}`
- `/v2/aggs/grouped/locale/us/market/stocks/{date}`

**Limitations on Basic:**
- ✅ Can fetch historical minute/daily bars (but only up to 2 years)
- ❌ Cannot fetch intraday/recent bars (end-of-day data only)
- ⚠️ Rate limited to 5 calls/minute (slow for batch operations)

**Impact:**
- ❌ Extended hours volume calculation - No intraday minute bars
- ⚠️ Historical backfill - Limited to 2 years, slow with rate limits
- ⚠️ Gap backtesting - Historical analysis works, but slower

**Workaround Potential:**
Aggregates API still provides some value on Basic tier:
- Can backfill historical data (up to 2 years back)
- Can use grouped daily endpoint for batch historical updates
- Rate limits are manageable for background jobs

### ⚠️ DEGRADED: News & Sentiment
**Affected Endpoint:**
- `/v2/reference/news`

**Impact:**
- ❌ `./tradescout asset news {symbol}` - No news articles
- ❌ Sentiment analysis - Cannot track market sentiment
- ❌ Gap trading catalyst identification - No news-driven context

**Why It Matters:**
News sentiment helps identify gap trading catalysts:
- Earnings announcements
- Merger/acquisition news
- FDA approvals
- Analyst upgrades/downgrades

Without it, gap trading becomes blind to fundamental catalysts.

### ✅ RETAINED: Reference Data & Economic Data
**Still Available on Basic:**
- `/v3/reference/tickers` - Universe bootstrapping
- `/v3/reference/exchanges` - Market data
- `/v1/marketstatus/now` - Session detection
- `/v1/marketstatus/upcoming` - Market holidays
- `/fed/v1/*` - Inflation, treasury yields, inflation expectations

**Note:** These are mostly one-time or low-frequency operations, so Basic tier is sufficient.

---

## Rate Limiting: 5 Calls/Minute Impact

The Stocks Basic plan limits us to **5 API calls per minute**. Here's how this affects operations:

| Operation | Current (Unlimited) | Basic (5/min) | Estimated Time |
|-----------|---------------------|---------------|----------------|
| Bulk market snapshot | 1 call | N/A (not available) | - |
| Bootstrap 10,000 tickers | 10-20 calls (paginated) | 10-20 calls | 2-4 minutes |
| Fetch fundamentals for 1,000 assets | 1,000 calls | 1,000 calls | 200 minutes (3.3 hours) |
| Historical backfill (1 date) | 1 call (grouped) | 1 call | No impact |
| Extended hours volume (1 symbol) | 1 call (minute bars) | N/A (EOD only) | - |

**Mitigation Strategies:**
1. **Use grouped endpoints** - Fetch all tickers in one call when possible
2. **Cache aggressively** - Store results locally to minimize API calls
3. **Batch operations** - Queue requests and process at 5/min rate
4. **Off-peak processing** - Run expensive operations during nights/weekends

---

## Implementation Details

### Provider Files
All Polygon API interactions are isolated in provider classes:

```
src/api/providers/
├── polygon_snapshot_provider.py      # Snapshot API (bulk & single ticker)
├── polygon_aggregates_provider.py    # Minute bars, daily bars, grouped bars
├── polygon_market_status_provider.py # Market status, holidays
├── polygon_markets_provider.py       # Exchanges/markets reference data
├── polygon_tickers_provider.py       # Ticker reference data, fundamentals
├── polygon_news_provider.py          # News articles, sentiment analysis
└── polygon_fed_provider.py           # Inflation, treasury yields, expectations
```

### Data Flow Architecture
```
CLI Command (e.g., ./tradescout market update)
    ↓
DataServiceV2 (business logic layer)
    ↓
PolygonSnapshotProvider (API calls only)
    ↓
Polygon API /v2/snapshot/locale/us/markets/stocks/tickers
    ↓
MarketSnapshot dataclass (domain model)
    ↓
AssetPrice SQLModel (database persistence)
```

### Database Storage
Polygon data is stored in several tables:

| Table | Polygon Source | Purpose |
|-------|---------------|---------|
| `asset_prices` | Snapshot API | Current/historical OHLCV, volume |
| `assets` | Reference/Tickers API | Ticker symbols, metadata |
| `fundamentals` | Tickers API (via fundamentals) | Market cap, shares outstanding, sector |
| `markets` | Exchanges API | Exchange codes, trading hours |
| `market_holidays` | Market Status API | Trading calendar |
| `sentiment_events` | News API | News articles, AI sentiment scores |
| `fed_data` | Fed APIs | Inflation, yields, expectations |

### Critical Dependencies
**Commands that REQUIRE Polygon Snapshot API:**
- `./tradescout market update` - Bulk snapshot
- `./tradescout asset info {symbol}` - Single ticker snapshot
- `./tradescout screener run gainers_combined` - Bulk snapshot
- `./tradescout screener run losers_combined` - Bulk snapshot
- `./tradescout gap analyze` - Bulk snapshot + minute bars

**Commands that use Polygon but have alternatives:**
- `./tradescout database bootstrap-tickers` - Reference API (still works on Basic)
- `./tradescout database bootstrap-fundamentals` - Reference API (still works on Basic)
- `./tradescout market backfill {date}` - Grouped daily bars (limited on Basic)
- `./tradescout fed update` - Fed APIs (still works on Basic)

---

## Known Polygon API Limitations

### ⚠️ min.av (Accumulated Volume) Inconsistency
**Discovered:** October 7, 2025
**Issue:** During after-hours, `min.av` can be LESS than `day.v`, which is impossible if truly accumulated.

**Example (AAPL at 5:45 PM ET):**
```
day.v:  31,906,059 shares (regular session)
min.av: 31,905,871 shares (after 1hr 45min of after-hours)
Result: min.av < day.v = DATA INCONSISTENCY
```

**Impact:**
- ❌ After-hours: `min.av` UNRELIABLE (cannot calculate AH volume)
- ✅ Premarket: `min.av` RELIABLE (day.v is zero, so min.av = total PM volume)

**Workaround:**
Use Aggregates API `/v2/aggs/ticker/{symbol}/range/1/minute/{from}/{to}` for accurate after-hours volume by summing individual minute bars.

**Related Code:**
- `polygon_aggregates_provider.py:calculate_extended_hours_volume()`

### Daily Reset Pattern: `updated` Field
**Discovered:** September 23, 2025
**Issue:** The `updated` field resets to 0 at the start of each trading day for symbols that haven't traded yet.

**Behavior:**
1. Each trading day starts fresh: symbols that haven't traded have `updated = 0`
2. First trade triggers update: once a symbol trades, it gets non-zero `updated` timestamp
3. Timestamp persists through day: continues updating as long as trading occurs

**Impact on Screening:**
- Premarket: ~2,000-2,500 symbols have traded (out of ~7,500 in universe)
- Many legitimate stocks may not trade in premarket and show `updated = 0`
- Cannot rely on `updated > 0` to filter for "active" symbols

### Data Availability by Session

| Session | prevDay.* | day.* | min.* | Formula |
|---------|-----------|-------|-------|---------|
| **Premarket** (4-9:30 AM) | Previous close | All zeros | Premarket price | `min.c - prevDay.c` |
| **Regular** (9:30-4 PM) | Previous close | Live data | Current price | `min.c - prevDay.c` |
| **After-hours** (4-8 PM) | Previous close | Complete session | After-hours price | `min.c - prevDay.c` |
| **Weekend** | Previous close | Friday's session | Last Friday trade | `min.c - prevDay.c` |

**Key Insight:** `prevDay.c` is ALWAYS the reference price for change calculations across all sessions.

---

## Recommendations & Next Steps

### Immediate Actions (Before Dec 2, 2025)
1. ✅ Audit all Polygon API usage (completed via this doc)
2. ⏳ Research alternative data providers (YFinance, Alpha Vantage, IEX Cloud)
3. ⏳ Design provider abstraction layer for easy swapping
4. ⏳ Implement fallback/hybrid strategy (use Basic where possible, supplement with alternatives)

### Short-Term Strategy (Dec 2025 - Jan 2026)
**Option A: Hybrid Approach**
- Keep Polygon Basic for reference data (tickers, exchanges, market status, Fed data)
- Add YFinance for snapshot data (current prices, OHLCV)
- Add Alpha Vantage or IEX for news/sentiment
- Pros: Free, leverages Basic tier for what it does well
- Cons: Multiple providers, complexity, rate limit juggling

**Option B: Single Alternative Provider**
- Migrate entirely to alternative (YFinance, IEX Cloud, Finnhub)
- Drop Polygon completely
- Pros: Simpler, single provider relationship
- Cons: May lose some features, quality may vary

**Option C: Upgrade to Polygon Starter**
- Pay $29/month to keep Starter plan
- Continue using TradeScout as-is
- Pros: No migration work, familiar API, proven quality
- Cons: $29/month ongoing cost

### Long-Term Strategy (2026+)
**Provider Abstraction Layer**
Design a pluggable provider system:
```python
class MarketDataProvider(Protocol):
    def fetch_snapshot(self, symbol: str) -> TickerSnapshot
    def fetch_bulk_snapshot(self) -> MarketSnapshot
    def fetch_news(self, symbol: str) -> List[NewsArticle]
    # ...

class PolygonProvider(MarketDataProvider): ...
class YFinanceProvider(MarketDataProvider): ...
class IEXProvider(MarketDataProvider): ...
```

**Benefits:**
- Easy provider swapping via configuration
- Fallback chains (try Provider A, fall back to Provider B)
- Cost optimization (use free tiers, pay only when needed)
- Reduced vendor lock-in

---

## Alternative Providers Research

### YFinance (Free)
**Pros:**
- Completely free
- Good coverage of US stocks
- Historical data, current prices, fundamentals
- Python library available

**Cons:**
- Unofficial API (scrapes Yahoo Finance)
- Rate limits (unknown, variable)
- No official support or SLA
- Data quality inconsistent
- No news/sentiment API

### Alpha Vantage (Free + Paid)
**Pros:**
- Official API with free tier
- 25 API calls/day (free)
- Stock quotes, fundamentals, economic data
- News sentiment API

**Cons:**
- Very limited free tier (25 calls/day)
- Paid tier expensive ($50-$500/month)
- Slower response times
- Data delays

### IEX Cloud (Paid)
**Pros:**
- High-quality real-time data
- Good API design, well-documented
- News, fundamentals, historical data
- Launch plan: $9/month (limited usage)

**Cons:**
- No truly free tier
- Credit-based pricing (complex)
- US stocks only
- Still costs money

### Finnhub (Free + Paid)
**Pros:**
- Free tier with 60 API calls/minute
- Stock quotes, news, earnings, fundamentals
- WebSocket support
- Good documentation

**Cons:**
- Free tier limited features
- Paid tiers expensive ($20-$300/month)
- Rate limits on free tier
- Some data requires premium

---

## Conclusion

**Current State:**
TradeScout is heavily dependent on Polygon Snapshot API (available on Starter, NOT on Basic).

**Dec 2, 2025 Impact:**
Losing Snapshot API on Basic tier will break 90% of TradeScout's core functionality.

**Decision Required:**
1. **Keep Polygon Starter** - Pay $29/month to maintain current functionality
2. **Hybrid Strategy** - Use Polygon Basic + YFinance/alternative for snapshots
3. **Full Migration** - Switch to alternative provider entirely

**Recommendation:**
Start with **Option 1 (Keep Starter)** short-term while researching/implementing **Option 2 (Hybrid)** for long-term cost optimization.

**Next Document:**
See `POLYGON_DECOUPLING_PLAN.md` (to be created) for detailed migration strategy.

---

## References

- **Official Polygon Docs:** https://polygon.io/docs (now redirects to https://massive.com/docs)
- **Pricing:** https://polygon.io/pricing (now https://massive.com/pricing)
- **Provider Code:** `src/api/providers/polygon_*.py`
- **Data Models:** `src/models/dataclass/snapshot.py`, `src/models/dataclass/price_bar.py`
- **Service Layer:** `src/services/data_service_v2.py`
