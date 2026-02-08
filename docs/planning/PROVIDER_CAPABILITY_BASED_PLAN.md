# Capability-Based Provider Architecture

**Created:** December 4, 2025
**Updated:** January 17, 2026
**Status:** 🚧 Partially Implemented

---

## Current State Summary

### What's Implemented ✅
| Provider | Protocol | Status |
|----------|----------|--------|
| `pandas_market_calendars` | Market Status | ✅ Working - local, no API calls |
| `finnhub` | News | ✅ Working - 60 req/min free |
| `yfinance` | Snapshot (bulk) | ✅ Working - free, 500 sym/23sec |
| `alpaca` | Snapshot (single) | ✅ Wired up - needs testing |
| Polygon/Massive adapters | All | ✅ Working but PAID |

### What's NOT Implemented ❌
| Need | Current Solution | Problem |
|------|------------------|---------|
| Real-time streaming quotes | Polygon/Massive | Requires $199/mo Advanced tier |
| Intraday minute bars | Polygon/Massive | Free tier = EOD only |
| Tiingo adapter | Not built | Could be useful fallback |

### Recently Implemented ✅ (Jan 2026)
| Feature | Provider | Notes |
|---------|----------|-------|
| Bulk market snapshots | yfinance | 500 symbols in ~23 sec, 93% success rate |
| Yahoo Finance adapter | yfinance | YFinanceSnapshotAdapter implementing SnapshotProvider |

---

## Massive.com (formerly Polygon.io) Pricing Reality

**Rebranded October 30, 2025** - Same API, new name. Both domains work.

### Free Tier ($0/month) - "Stocks Basic"
- ❌ **End-of-day data ONLY** (not real-time)
- ❌ 5 API calls/minute limit
- ✅ 2 years historical data
- ✅ US equities, forex, crypto

### What We Use That's NOT Free
| Feature | Our Usage | Free? | Required Tier |
|---------|-----------|-------|---------------|
| **Real-time snapshots** | Screeners, gap analysis | ❌ NO | Advanced ($199/mo) |
| **Intraday/minute bars** | Volume analysis | ❌ NO | Starter ($29/mo) |
| **News API** | Sentiment | ❌ NO | Unknown |
| **Reference data** | Tickers, fundamentals | ⚠️ Maybe | Unknown |
| **Market status API** | Session detection | ⚠️ Maybe | Unknown |
| **Fed/Economic data** | Fed info command | ⚠️ Maybe | Unknown |

### Massive Pricing Tiers
| Tier | Price | Rate Limit | Historical | Real-time |
|------|-------|------------|------------|-----------|
| **Basic (Free)** | $0/mo | 5/min | 2 years EOD | ❌ No |
| **Starter** | $29/mo | Unlimited | 5 years | ❌ No |
| **Developer** | $79/mo | Unlimited | 10 years | ❌ No |
| **Advanced** | $199/mo | Unlimited | 20+ years | ✅ Yes |

**Bottom line:** Real-time data requires $199/month. We need alternatives.

---

## Available Free Alternatives

| Provider | API Key | Free Limits | Best For | Status |
|----------|---------|-------------|----------|--------|
| **Yahoo Finance** | N/A | Unlimited (unofficial) | Bulk snapshots, quotes | ✅ Working |
| **Alpaca** | ✅ Have | 200 calls/min | Single ticker snapshots | ✅ Wired up |
| **Finnhub** | ✅ Have | 60 calls/min | News + sentiment | ✅ Working |
| **pandas_market_calendars** | N/A | Unlimited (local) | Market hours, holidays | ✅ Working |
| **Tiingo** | ⏳ Can get | 50 symbols/hour EOD | Historical backup | ❌ Not built |
| **Alpha Vantage** | ✅ Have | 25 calls/DAY | Too limited - skip | ❌ Skip |

---

## The Core Problem ✅ SOLVED

**Our screeners need bulk market snapshots** - querying ALL tickers at once to find gainers/losers.

| Solution | Feasibility | Notes |
|----------|-------------|-------|
| **Yahoo Finance (yfinance)** | ✅ **IMPLEMENTED** | 500 sym/23sec, 93% success |
| Massive Advanced ($199/mo) | Works but expensive | Fallback option |
| Alpaca bulk snapshot | ❌ Not supported | Needs symbol list upfront |
| Pre-filter + single queries | ⚠️ Slow | Query universe one-by-one |
| EOD-only screeners | ⚠️ Limited | Run after market close |

---

## Yahoo Finance (yfinance) - Research Findings

**Library:** `yfinance` - Unofficial Yahoo Finance API wrapper
**PyPI:** https://pypi.org/project/yfinance/
**GitHub:** https://github.com/ranaroussi/yfinance

### Capabilities

| Feature | Supported | Example |
|---------|-----------|---------|
| **Bulk ticker download** | ✅ Yes | `yf.download(["AAPL", "MSFT", ...], period="1d")` |
| **Multithreaded** | ✅ Yes | `threads=True` parameter for parallel downloads |
| **Real-time websocket** | ✅ Yes | `ticker.live()` or `tickers.live()` |
| **Historical data** | ✅ Yes | Minutes to decades of history |
| **Fundamentals** | ✅ Yes | `ticker.info`, `ticker.financials` |
| **No API key needed** | ✅ Yes | Free, unlimited (unofficial) |

### Bulk Download Example
```python
import yfinance as yf

# Download multiple tickers at once
data = yf.download(
    ["AAPL", "MSFT", "GOOGL", "AMZN"],
    period="1d",
    interval="1m",
    threads=True,
    group_by="ticker"
)

# Access individual ticker data
aapl_close = data['AAPL']['Close']
```

### Real-Time Websocket
```python
ticker = yf.Ticker("AAPL")
ticker.live()  # Real-time streaming quotes
```

### Risks
- **Unofficial API** - Not endorsed by Yahoo, could break
- **Rate limiting** - Too many requests can get IP blocked
- **Data quality** - May have delays or inaccuracies

### Recommendation
**yfinance is our best free option for bulk snapshots.** We should:
1. Build `YahooSnapshotAdapter` implementing our `SnapshotProvider` protocol
2. Test bulk download with our full universe (~500 tickers)
3. Implement rate limiting and caching
4. Keep Alpaca as fallback for single-ticker queries

---

## Recommended Provider Routing

### Already Implemented
```yaml
market_status: pandas_market_calendars  # ✅ Local, unlimited
news: finnhub                            # ✅ 60/min free
```

### Still Using Massive (need alternatives)
```yaml
snapshot: polygon      # ❌ Needs real-time for screeners
aggregates: polygon    # ⚠️ EOD might be OK, intraday needs paid
reference: polygon     # ⚠️ Might be free? Need to test
economic: polygon      # ⚠️ Might be free? Need to test
```

### Proposed Changes
```yaml
# Phase 1: Test what's actually free on Massive
reference: polygon     # Test if free tier works
economic: polygon      # Test if free tier works

# Phase 2: Build Yahoo Finance adapter for real-time
snapshot:
  default: yfinance    # Unofficial but free
  fallback: [alpaca]   # Single ticker backup

# Phase 3: Build Tiingo adapter for historical
aggregates:
  daily: polygon       # Free tier EOD works
  intraday: yfinance   # If we need it
```

---

## Implementation Phases

### Phase 1: Test Massive Free Tier Boundaries
- [ ] Test reference data API on free tier
- [ ] Test economic data API on free tier
- [ ] Test what exactly returns 403 vs works
- [ ] Document actual free tier capabilities

### Phase 2: Build Yahoo Finance Adapter ✅ COMPLETE (Jan 2026)
- [x] Research yfinance library capabilities
- [x] Implement `YFinanceSnapshotAdapter`
- [x] Implement bulk ticker query - 500 symbols in ~23 sec
- [x] Test data quality - 93% success rate
- [x] Wire up in provider_factory.py
- [x] Set as default in providers.yaml

### Phase 3: Build Tiingo Adapter (optional)
- [ ] Get Tiingo API key
- [ ] Implement `TiingoSnapshotAdapter`
- [ ] Implement `TiingoAggregatesAdapter`
- [ ] Test as fallback provider

### Phase 4: Reduce Massive Dependency
- [ ] Move snapshot to Yahoo/Alpaca
- [ ] Keep aggregates on Massive free (EOD)
- [ ] Keep reference on Massive if free
- [ ] Evaluate if we can drop Massive entirely

---

## Risk Assessment

| Risk | Impact | Mitigation |
|------|--------|------------|
| Yahoo Finance is unofficial | Could break anytime | Have Alpaca as fallback |
| Alpaca can't do bulk | Screeners broken | Need Yahoo or pay Massive |
| Massive free tier too limited | Features broken | Test boundaries first |
| Rate limits on free tiers | Slow performance | Aggressive caching |

---

## Questions to Resolve

1. **What exactly works on Massive free tier?** - Need to test reference, economic APIs
2. **Can Yahoo Finance do bulk queries?** - Critical for screeners
3. **Is Tiingo worth the effort?** - Or just use Yahoo + Alpaca
4. **Do we need real-time at all?** - Could run EOD-only screeners
5. **Budget for Massive?** - $29/mo Starter might be worth it for unlimited calls

---

## Cost Comparison

| Scenario | Monthly Cost | Limitations |
|----------|-------------|-------------|
| **Current (Massive paid)** | $29-199/mo | Full functionality |
| **All free providers** | $0/mo | No real-time bulk, slower |
| **Hybrid (Massive Starter)** | $29/mo | No real-time, but unlimited calls |
| **Hybrid (Yahoo + Massive free)** | $0/mo | Unofficial Yahoo risk |

---

## Next Steps

1. **Test Massive free tier** - What actually works without 403?
2. **Research yfinance** - Can it replace bulk snapshots?
3. **Decide budget** - Is $29/mo acceptable for reliability?
4. **Build adapters** - Yahoo first, then Tiingo if needed
