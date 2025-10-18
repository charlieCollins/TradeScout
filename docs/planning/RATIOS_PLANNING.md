# Financial Ratios & Indicators Planning

**Status:** Planning Phase
**API Source:** Polygon.io Stock Financials API
**Endpoint:** https://polygon.io/docs/rest/stocks/fundamentals/ratios

---

## Overview

Polygon.io provides comprehensive financial ratio and indicator data that could enhance TradeScout's fundamental analysis capabilities. This data complements our existing fundamentals but requires careful planning for storage and integration.

## Available Data from Polygon Ratios API

The `/vX/reference/financials` endpoint provides quarterly and annual ratios including:

### Liquidity Ratios
- Current Ratio
- Quick Ratio
- Cash Ratio
- Working Capital

### Profitability Ratios
- Return on Equity (ROE)
- Return on Assets (ROA)
- Return on Invested Capital (ROIC)
- Profit Margin
- Operating Margin
- Gross Margin

### Leverage Ratios
- Debt to Equity
- Debt to Assets
- Interest Coverage Ratio

### Efficiency Ratios
- Asset Turnover
- Inventory Turnover
- Receivables Turnover
- Days Sales Outstanding

### Valuation Ratios
- Price to Earnings (P/E)
- Price to Book (P/B)
- Price to Sales (P/S)
- EV/EBITDA
- Dividend Yield
- Payout Ratio

### Growth Metrics
- Revenue Growth
- Earnings Growth
- Book Value Growth

---

## Current State

**What we have now:**
- `fundamentals` table with basic data:
  - Market cap
  - Shares outstanding
  - Sector/Industry
  - Some basic ratios (P/E, beta, dividend yield)

**What we're missing:**
- Comprehensive ratio data
- Historical ratio trends (quarterly/annual)
- Efficiency and leverage metrics
- Growth rate calculations

---

## Proposed Architecture

### Option 1: Separate Ratios Table
Create a new `asset_ratios` table for time-series ratio data:

```sql
CREATE TABLE asset_ratios (
    id INTEGER PRIMARY KEY,
    asset_id INTEGER NOT NULL,
    provider_id INTEGER NOT NULL,

    -- Time period
    period_type TEXT NOT NULL,  -- 'quarterly', 'annual', 'ttm'
    fiscal_period TEXT,          -- 'Q1', 'Q2', 'Q3', 'Q4'
    fiscal_year INTEGER,
    period_end_date DATE,

    -- Liquidity
    current_ratio REAL,
    quick_ratio REAL,
    cash_ratio REAL,

    -- Profitability
    roe REAL,
    roa REAL,
    roic REAL,
    profit_margin REAL,
    operating_margin REAL,
    gross_margin REAL,

    -- Leverage
    debt_to_equity REAL,
    debt_to_assets REAL,
    interest_coverage REAL,

    -- Efficiency
    asset_turnover REAL,
    inventory_turnover REAL,
    receivables_turnover REAL,

    -- Valuation
    pe_ratio REAL,
    pb_ratio REAL,
    ps_ratio REAL,
    ev_ebitda REAL,
    dividend_yield REAL,

    -- Growth (YoY)
    revenue_growth REAL,
    earnings_growth REAL,

    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (asset_id) REFERENCES assets(id),
    FOREIGN KEY (provider_id) REFERENCES providers(id),
    UNIQUE(asset_id, period_type, fiscal_year, fiscal_period)
);
```

**Pros:**
- Time-series data for trend analysis
- Historical comparison (current quarter vs previous quarters)
- Supports quarterly/annual/TTM views
- Clean separation of concerns

**Cons:**
- More complex queries (need latest period)
- Additional table to maintain
- More API calls to keep updated

### Option 2: Extend Fundamentals Table
Add ratio columns to existing `fundamentals` table (latest only):

**Pros:**
- Simple to query (all data in one place)
- Easy to display in asset info
- Fewer tables

**Cons:**
- Loses historical ratio data
- Fundamentals table becomes very wide
- Can't track trends over time

### Option 3: JSON Column Approach
Store ratios as JSON in fundamentals table:

```sql
ALTER TABLE fundamentals ADD COLUMN ratios_json TEXT;
```

**Pros:**
- Flexible schema
- Easy to add new ratios

**Cons:**
- Harder to query
- Can't index individual ratios
- Not type-safe

---

## Recommendation: Option 1 (Separate Table)

Create `asset_ratios` table for historical ratio tracking. This enables:

1. **Trend Analysis:** "Show me P/E ratio trend over last 4 quarters"
2. **Comparative Analysis:** "Find stocks where ROE is improving quarter-over-quarter"
3. **Screeners:** "Find stocks with current ratio > 2.0 and improving margins"
4. **Gap Trading:** "Verify fundamental health before trading gaps"

---

## Implementation Plan

### Phase 1: Database Schema
- [ ] Create `asset_ratios` SQLModel
- [ ] Create migration script
- [ ] Add indexes (asset_id, period_type, fiscal_year)

### Phase 2: Data Provider
- [ ] Create `PolygonRatiosProvider` class
- [ ] Implement data fetching from `/vX/reference/financials`
- [ ] Handle quarterly vs annual data
- [ ] Parse and transform API response

### Phase 3: Repository Layer
- [ ] Create `RatiosRepository`
- [ ] Implement CRUD operations
- [ ] Add queries:
  - Get latest ratios for asset
  - Get ratios for specific period
  - Get ratio trend over N periods
  - Find assets by ratio criteria

### Phase 4: Service Layer
- [ ] Add ratio methods to `DataServiceV2`
- [ ] Implement caching strategy (similar to fundamentals)
- [ ] Add TTL management for ratio data

### Phase 5: CLI Commands
- [ ] Add `tradescout asset ratios <SYMBOL>` command
- [ ] Display current ratios with historical comparison
- [ ] Add `--period` flag for specific quarters/years
- [ ] Add ratio filtering to screeners

### Phase 6: Web API
- [ ] Add `/api/assets/{symbol}/ratios` endpoint
- [ ] Add ratio display to asset info modal
- [ ] Create ratio trend charts

---

## Data Freshness Strategy

**Ratios update frequency:**
- **Quarterly data:** Updates after earnings releases (4x per year)
- **Annual data:** Updates after fiscal year end (1x per year)
- **TTM (Trailing 12 Months):** Can update quarterly

**TTL Strategy:**
- Cache ratios for 7-14 days
- Refresh after known earnings dates
- Allow manual refresh with `--force`

---

## Use Cases

### For Screeners
```yaml
# Example screener criteria
criteria:
  fundamentals:
    min_market_cap: 1B
    max_pe: 20
  ratios:
    min_current_ratio: 1.5        # Liquidity screen
    min_roe: 0.15                 # 15% return on equity
    max_debt_to_equity: 1.0       # Conservative leverage
    min_revenue_growth: 0.10      # 10% growth
```

### For Gap Analysis
Before trading a gap, verify:
- Current ratio > 1.5 (can meet obligations)
- ROE improving (company is efficient)
- Debt to equity < 2.0 (not over-leveraged)

### For Asset Info Display
```
📊 Financial Ratios (Q3 2025)

Profitability          Liquidity           Leverage
ROE:        18.5%     Current:    2.1     D/E:     0.45
ROA:        12.3%     Quick:      1.8     Coverage: 8.2x
Margins:    25.5%     Cash:       0.9

Efficiency             Valuation
Asset TO:   1.2x      P/E:        18.5
Inv TO:     6.5x      P/B:        3.2
DSO:        45 days   P/S:        2.8
```

---

## Questions to Answer

1. **Storage strategy:** Latest only vs full history?
   - **Recommendation:** Store last 8 quarters + last 3 annual periods per asset

2. **Update frequency:** How often to fetch ratios?
   - **Recommendation:** Weekly background job + on-demand with force refresh

3. **API quota:** How many calls for universe bootstrap?
   - ~7,000 assets × 1 call = 7,000 calls for initial load
   - Quarterly updates = ~7,000 calls every 3 months

4. **Display priorities:** Which ratios are most important?
   - **Recommendation:** P/E, ROE, Current Ratio, Debt/Equity (show first)

---

## Next Steps

1. Review Polygon API response format
2. Design SQLModel schema
3. Create migration script
4. Implement provider class
5. Test with sample assets
6. Integrate into screeners

---

**References:**
- Polygon Financials API: https://polygon.io/docs/rest/stocks/fundamentals/ratios
- Current fundamentals implementation: `src/models/sqlmodel/fundamentals_sqlmodel.py`
- Provider pattern: `src/api/providers/`
