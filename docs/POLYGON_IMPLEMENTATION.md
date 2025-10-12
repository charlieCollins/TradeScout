# Polygon.io Integration - TradeScout Implementation Details

**Last Updated:** October 7, 2025
**Purpose:** Document how TradeScout uses Polygon APIs, including implementation details, testing results, and discovered limitations

**See Also:**
- [POLYGON.md](POLYGON.md) - General Polygon API reference
- [POLYGON_VOLUME_FIELDS.md](POLYGON_VOLUME_FIELDS.md) - Volume field structure and session-specific usage

---

## Overview

TradeScout uses multiple Polygon.io APIs for market data:

**Primary Data Sources:**
1. **Snapshot API** - Real-time market snapshots (bulk and single ticker)
2. **Aggregates API** - Minute-level bars for extended hours volume calculation
3. **Market Status API** - Current trading session detection
4. **Reference Data API** - Ticker universe bootstrapping

**Implementation:**
- `src/api/providers/polygon_snapshot_provider.py` - Snapshot data fetching
- `src/api/providers/polygon_aggregates_provider.py` - Extended hours volume
- `src/api/providers/polygon_market_status_provider.py` - Session detection
- `src/api/providers/polygon_tickers_provider.py` - Universe bootstrapping

**Database Storage:**
- `asset_prices` table - Stores snapshot data with provider timestamps
- `assets` table - Ticker symbols and metadata
- `market_holidays` table - Trading calendar

---

## 🚨 CRITICAL LIMITATIONS

### ⚠️ min.av (Accumulated Volume) Showing Inconsistent Data During Extended Hours

**Discovered:** October 7, 2025 during after-hours gap analysis

**Volume Field Structure:**
- `prevDay.v` = Previous session total volume
- `day.v` = Regular session volume (9:30am-4pm)
- `min.v` = Individual minute bar volume (just that minute)
- `min.av` = Accumulated volume (cumulative from session start)

**Key:** Only `min` has both `v` and `av`. Completed sessions (prevDay, day) only have `v`.

**The Problem:**
During after-hours, `min.av` can be LESS than `day.v`, which is impossible if truly accumulated.

**Test Evidence (AAPL at 5:45 PM ET on Oct 7, 2025):**
```
day.v:  31,906,059 shares (regular session 9:30am-4pm)
min.av: 31,905,871 shares (at 5:45 PM, 1hr 45min into after-hours)
min.v:  156 shares (that specific minute only)

min.av < day.v = DATA INCONSISTENCY
```

**What This Means:**
- `min.av` field has unreliable/inconsistent data during extended hours
- Cannot trust `min.av - day.v` calculation for after-hours volume
- May be a Polygon API data quality issue or timing/update lag

**Impact & Session-Specific Behavior:**
- ❌ **After-hours**: `min.av` UNRELIABLE (can be < day.v, cannot calculate AH volume)
- ✅ **Premarket**: `min.av` RELIABLE (day.v is zero, so min.av = total PM volume accumulated)
- ✅ **Regular hours**: Use `day.v` for accurate volume
- ✅ **Closed**: Use `prevDay.v` for previous session's volume

**Summary:**
- Premarket: `min.av` works ✅
- Regular: `day.v` works ✅
- After-hours: `min.av` broken ❌ - must use Aggregates API
- Closed: `prevDay.v` works ✅

**Workaround:**
Use Polygon's **Aggregates API** instead for accurate extended hours volume:
```
GET /v2/aggs/ticker/{symbol}/range/1/minute/{from}/{to}
```

Example for after-hours volume (4pm-8pm ET):
```
GET /v2/aggs/ticker/AAPL/range/1/minute/2025-10-07T16:00:00/2025-10-07T20:00:00
```

Sum the `v` (volume) field from all returned minute bars to get total after-hours volume.

**Documentation Reference:** https://polygon.io/docs/rest/stocks/aggregates/custom-bars

---

## API Implementation Details

### Snapshot API Usage

**When We Use It:**
- Market data updates (`./tradescout market update`)
- Single ticker queries (`./tradescout asset info AAPL`)
- Screener data population
- Gap analysis candidate identification

**Endpoints:**
- Bulk: `/v2/snapshot/locale/us/markets/stocks/tickers`
- Single: `/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}`

**Update Strategy:**
- Store `provider_updated_at` (nanosecond timestamp) as version key
- Use `INSERT OR IGNORE` to skip duplicates (same timestamp = same data)
- 10-minute TTL for ticker snapshots
- Bulk snapshots refresh entire universe

**Field Mapping to Database:**
```
prevDay.* → prevday_open, prevday_high, prevday_low, prevday_close, prevday_volume, prevday_vwap
day.*     → day_open, day_high, day_low, day_close, day_volume, day_vwap
min.*     → min_open, min_high, min_low, min_close, min_volume, min_accumulated_volume, min_timestamp
updated   → provider_updated_at
```

### Aggregates API Usage

**When We Use It:**
- After-hours volume calculation (gap trading validation)
- Cannot use snapshot `min.av` due to data inconsistency

**Endpoint:**
```
GET /v2/aggs/ticker/{symbol}/range/1/minute/{from_ts}/{to_ts}
```

**Implementation:**
- `PolygonAggregatesProvider.calculate_extended_hours_volume()`
- Fetches all minute bars for session window
- Sums volume across bars for accurate total
- Session windows:
  - Premarket: 4:00 AM - 9:30 AM ET
  - After-hours: 4:00 PM - 8:00 PM ET

**Example:**
```python
from api.providers.polygon_aggregates_provider import PolygonAggregatesProvider

provider = PolygonAggregatesProvider(api_key)
volume = provider.calculate_extended_hours_volume(
    symbol="AAPL",
    trading_date=date(2025, 10, 7),
    session="afterhours"
)
# Returns total volume summed from minute bars
```

### Market Status API Usage

**When We Use It:**
- Session detection (`market_context_service.py`)
- Determines current session: premarket/regular/afterhours/closed
- Used by screeners for session validation

**Endpoint:**
```
GET /v1/marketstatus/now
```

**Response Processing:**
```python
{
  "market": "extended-hours",  # open | closed | extended-hours
  "earlyHours": false,         # True during premarket
  "afterHours": true           # True during after-hours
}
```

**Session Mapping:**
- `market == "open"` → Regular session
- `market == "extended-hours" + earlyHours` → Premarket
- `market == "extended-hours" + afterHours` → After-hours
- `market == "closed"` → Closed

### Reference Data API Usage

**When We Use It:**
- Universe bootstrapping (`./tradescout database bootstrap-tickers`)
- Builds initial ticker list with metadata

**Endpoint:**
```
GET /v3/reference/tickers
```

**Filters Applied:**
- `market=stocks` - US stocks only
- `type=CS` - Common stock
- `active=true` - Currently trading
- Universe-specific filters (exchange, market cap, volume)

**Pagination:**
- Uses `cursor` for pagination
- Fetches all pages until `next_url` is null

---

## Snapshot API Behavior Testing

### Test Methodology

All sessions tested with real market data to understand field behavior. Tests conducted across multiple market states (premarket, regular, after-hours, weekends).

## Key Findings

### ✅ CONFIRMED: Snapshot API Behavior During Afterhours

1. **day.* fields** = Current regular trading session (9:30 AM - 4:00 PM ET)
   - **Before market open (premarket)**: All zeros - regular session hasn't started yet
   - **During regular hours**: Live session data (9:30 AM - 4:00 PM)
   - **After market close**: Completed regular session data
   - **On weekends**: Previous Friday's completed regular session data
   - day.c = Regular session close at 4:00 PM (or zero if session hasn't started)

2. **prevDay.* fields** = Previous regular trading session
   - On Friday evening: Shows Thursday's regular session data
   - On weekend: Still shows Thursday's data
   - prevDay.c = THE reference price for change calculations

3. **min.* fields** = Last traded minute bar (ANY session)
   - Shows the most recent trading activity
   - During afterhours: Shows afterhours trading
   - On weekend: Shows last afterhours minute from Friday
   - min.c = Current/last traded price

## MSFT Test Results

### How to Determine Which Day is Which

**Starting Point: The `updated` Field**

```json
"updated": 1758326400000000000  // ← This is our anchor
```

**Step 1: Convert `updated` to Human Time**
- 1758326400000000000 nanoseconds ÷ 1,000,000,000 = 1758326400 seconds
- Unix timestamp 1758326400 = **2025-09-19 20:00:00 EDT**
- This is **Friday, September 19, 2025 at 8:00 PM Eastern**

**Step 2: Determine What `day` Represents**
- `updated` = September 19, 2025 (Friday)
- Therefore: **`day.*` = September 19, 2025 regular session**
- This is Friday's 9:30 AM - 4:00 PM trading data
- The 8:00 PM timestamp means afterhours has closed, so day data is complete

**Step 3: Determine What `prevDay` Represents**
- `day` = September 19 (Friday)
- Previous trading day = September 18 (Thursday)
- Therefore: **`prevDay.*` = September 18, 2025 regular session**
- Markets are closed weekends, so previous trading day skips back to Thursday

**Step 4: Understand What `min` Represents**
- `min.t` = 1758326340000 milliseconds = 2025-09-19 19:59:00 EDT
- This is Friday 7:59 PM - during afterhours session
- **`min.*` = Last traded minute bar before snapshot update**
- Could be from premarket, regular, or afterhours depending on when updated

**Summary Table:**
| Field | Represents | Actual Date | How We Know |
|-------|------------|-------------|-------------|
| `updated` | Snapshot timestamp | Sept 19, 8:00 PM | Direct from API |
| `day.*` | Regular session | Sept 19 (Fri) | Same date as `updated` |
| `prevDay.*` | Previous regular session | Sept 18 (Thu) | Prior trading day |
| `min.*` | Last minute bar | Sept 19, 7:59 PM | From `min.t` timestamp |

### Day Fields (Friday September 19, 2025 Regular Session)
- day.o: $510.56 (regular open)
- day.h: $519.30 (regular high)
- day.l: $510.31 (regular low)
- day.c: $517.93 (regular close at 4 PM)
- day.v: 52,697,252 (regular volume)

### PrevDay Fields (Thursday September 18, 2025 Regular Session)
- prevDay.o: $511.49
- prevDay.h: $513.07
- prevDay.l: $507.66
- **prevDay.c: $508.45** ← REFERENCE PRICE
- prevDay.v: 18,913,696

### Min Fields (Last Afterhours Trade - Friday September 19, 2025)
- **min.c: $517.40** ← CURRENT PRICE
- min.t: 2025-09-19 19:59:00 EDT (Friday 7:59 PM)
- min.v: 1,602 (last minute volume)

### Change Calculation
```
Change = min.c - prevDay.c
Change = $517.40 - $508.45
Change = $8.95 (+1.76%)
```

## Important Observations

1. **day.c ≠ Reference Price During Extended Hours**
   - day.c ($517.93) is the 4 PM close
   - But reference price is prevDay.c ($508.45)
   - This is correct - changes are always from previous session close

2. **Min Timestamp Shows Extended Hours**
   - min.t: 19:59:00 EDT (7:59 PM)
   - Confirms min fields update during afterhours trading
   - On weekend, shows last afterhours trade from Friday

3. **Updated Timestamp**
   - Shows 20:00:00 EDT (8:00 PM Friday)
   - Indicates snapshot was last updated at afterhours close

## Formula Summary

### During All Sessions (Premarket, Regular, Afterhours, Weekend):
```
Current Price = min.c
Reference Price = prevDay.c
Change = min.c - prevDay.c
Change % = (Change / prevDay.c) × 100
```

## Empirical Observations and Validation

This section documents real-world testing and observations of Polygon API behavior across different market sessions and conditions. These findings inform our screener logic and field selection.

### Open Questions & Observations to Test

#### ✅ Sunday Closed Session: day.c vs prevDay.c for Afterhours Screeners
**Question:** When markets are closed on Sunday after the last trading day's close, which field should afterhours screeners use?

**Answer:** Use `day.c` - it contains the most recent trading day's 4PM close

**Test Results (AAPL - Sunday October 5, 2025):**
```
prevDay.c: $257.13  (Thursday Oct 2 close)
day.o:     $254.665 (Friday Oct 3 open)
day.c:     $258.02  (Friday Oct 3 4PM close) ← Correct reference
min.c:     $257.90  (Friday Oct 3 7:59 PM afterhours)
min.t:     1759535940000 (Oct 3, 2025 7:59 PM ET)
updated:   1759536000000000000 (Oct 3, 2025 8:00 PM ET)
```

**Calculation validation:**
- **CORRECT:** `(min.c - day.c) / day.c` = (257.90 - 258.02) / 258.02 = -0.046% (afterhours down from 4PM)
- **WRONG:** `(min.c - prevDay.c) / prevDay.c` = (257.90 - 257.13) / 257.13 = +0.30% (would show total move)

**Conclusion:** `gainersafterhours.yaml` using `day_close` is correct. On weekends, `day.*` fields contain Friday's regular session data, allowing afterhours screeners to properly show extended hours movement.

**Status:** ✅ CONFIRMED - Sunday October 5, 2025

---

## All Test Results Summary

### 1. Premarket Test (AAPL - September 19, 2025, 6:43 AM ET)
- **prevDay.c:** $237.88 (Thursday's close - reference price)
- **day.* fields:** All zeros (regular session hasn't started)
- **min.c:** $239.52 (current premarket price)
- **Change:** +$1.64 (+0.69%)
- **✅ Confirmed:** day fields are zeros during premarket

### 2. Afterhours Test (AGMH - September 18, 2025, afterhours)
- **prevDay.c:** $2.23 (previous day close - reference price)
- **min.c:** $5.42 (afterhours price)
- **Change:** +$3.19 (+143.05%)
- **✅ Confirmed:** Large afterhours movement captured correctly

### 3. Weekend Test (AAPL - Saturday September 20, 2025)
- **prevDay.c:** $237.88 (Thursday's close)
- **day.c:** $245.50 (Friday's 4 PM close)
- **min.c:** $245.69 (Friday's afterhours last trade at 7:59 PM)
- **✅ Confirmed:** Data frozen from Friday 8 PM until Monday premarket

### 4. Afterhours Test (MSFT - September 21, 2025, Sunday showing Friday data)
- **prevDay.c:** $508.45 (Thursday's close - reference price)
- **day.o/h/l/c:** $510.56/$519.30/$510.31/$517.93 (Friday regular session)
- **min.c:** $517.40 (Friday afterhours last trade at 7:59 PM)
- **min.t:** 2025-09-19 19:59:00 EDT
- **Change:** +$8.95 (+1.76%)
- **✅ Confirmed:** min fields show afterhours trading, day fields show regular session

## Session Behavior Matrix

| **Session** | **prevDay.c** | **day.*** | **min.c** | **Formula** | **Status** |
|-------------|---------------|-----------|-----------|-------------|------------|
| **Premarket** (4-9:30 AM) | Previous close | All zeros | Premarket price | `min.c - prevDay.c` | ✅ CONFIRMED |
| **Regular** (9:30-4 PM) | Previous close | Live data | Current price | `min.c - prevDay.c` | ✅ CONFIRMED |
| **Afterhours** (4-8 PM) | Previous close | **Complete session data** | Afterhours price | `min.c - prevDay.c` | ✅ CONFIRMED Sept 23 |
| **Weekend** | Previous close | Friday's session | Last Friday trade | `min.c - prevDay.c` | ✅ CONFIRMED |

## Monday Premarket Test (September 22, 2025, 7:56 AM ET)

### Live Production Test Results

**Test Symbols:** AAPL, NVDA, SPY, TSLA

| Symbol | prevDay.c | day.open | day.close | min.c | Gap % | min.timestamp |
|--------|-----------|----------|-----------|-------|-------|---------------|
| AAPL | $245.50 | NULL | NULL | $246.70 | +0.49% | 7:39 AM ET |
| NVDA | $176.67 | NULL | NULL | $175.45 | -0.69% | 7:40 AM ET |
| SPY | $663.70 | NULL | NULL | $661.60 | -0.32% | 7:40 AM ET |
| TSLA | $426.07 | NULL | NULL | $429.25 | +0.75% | 7:40 AM ET |

### Key Validations:
1. **day.* fields are NULL/zero** - ✅ Confirmed, regular session hasn't started
2. **prevDay.c contains Friday's close** - ✅ All symbols show Friday Sept 19 close
3. **min.c shows current premarket price** - ✅ Live premarket prices captured
4. **Gap calculation accurate** - ✅ Formula `(min.c - prevDay.c) / prevDay.c * 100` works
5. **Timestamps correct** - ✅ All show Monday morning premarket times

## Monday After-Hours Test (September 23, 2025, 7:05 PM ET)

### Live Production Test Results - CRITICAL CONFIRMATION

**Test Symbols:** AAPL, NVDA, TSLA during after-hours session

| Symbol | prevDay.c | day.open | day.high | day.low | day.close | min.c | min.timestamp | Updated |
|--------|-----------|----------|----------|---------|-----------|-------|---------------|---------|
| AAPL | $256.08 | $255.88 | $257.34 | $253.58 | **$254.43** | $254.35 | 19:04 ET | 19:05 ET |
| NVDA | $183.61 | $181.97 | $182.42 | $176.21 | **$178.43** | $178.19 | 19:05 ET | 19:06 ET |
| TSLA | $434.21 | $439.88 | $440.97 | $423.72 | **$425.85** | $426.52 | 19:05 ET | 19:06 ET |

### ✅ CRITICAL FINDING: day.* Fields ARE Present During After-Hours

**Confirmed Behavior:**
1. **day.* fields contain COMPLETE regular session data** (9:30 AM - 4:00 PM)
   - day.open = Market open at 9:30 AM
   - day.close = Market close at 4:00 PM (NOT the reference price!)
   - day.high/low/volume = Full regular session statistics
2. **prevDay.c remains the reference price** for all calculations
3. **min.c shows current after-hours price**
4. **Bulk market update confirmed**: 7,255 of 7,499 symbols had trading activity with complete day.* data

This definitively proves that after 4 PM, the day.* fields are populated with the complete regular trading session data, allowing screeners and analysis tools to work correctly during extended hours.

## Critical Discovery: The `updated` Field Behavior (September 23, 2025)

### Daily Reset Pattern
The `updated` field from Polygon API has a daily reset behavior:

1. **Each trading day starts fresh**: At the beginning of each day, symbols that haven't traded yet have `updated = 0`
2. **First trade triggers update**: Once a symbol trades (premarket, regular, or afterhours), it gets a non-zero `updated` timestamp
3. **Timestamp persists through day**: The `updated` value continues to update as long as trading occurs

### Test Evidence
**Symbol: A (Agilent Technologies)**
- Sept 22 record: `updated = 1758564343729855890` (had trading activity)
- Sept 23 premarket: `updated = 0` (no trading yet today)
- No min.* data when `updated = 0`

**Symbol: AAP (Advance Auto Parts)**
- Sept 23 at 7:29 AM: `updated = 0` (hadn't traded yet)
- Sept 23 at 7:43 AM: `updated = 1758626220000000000` (after premarket trading started)
- Has min.* data once trading begins

### Implications for Screening
- **"With recent trading"**: Symbols where `updated > 0` (have traded today)
- **"Without recent trading"**: Symbols where `updated = 0` (haven't traded yet today)
- In premarket, typically ~2,000-2,500 symbols have traded out of ~7,500 in universe
- Many legitimate stocks (like Agilent) may not trade in premarket and show `updated = 0`

### Data Availability Pattern
When `updated = 0`:
- **prevDay.*** fields are still populated (previous session data)
- **day.*** fields are zeros/NULL (no current session yet)
- **min.*** fields are missing/NULL (no recent trading)

When `updated > 0`:
- All fields populated based on trading activity
- min.* shows most recent trade
- day.* updates during regular session

## Min Timestamp Field (`min.t`) - Critical for Gap Trading

### What is `min.t`?
The `min.t` field in Polygon's snapshot API represents the **"Start of the aggregate window"** - the beginning timestamp of the last traded minute bar.

**Key Characteristics:**
- **Format:** Unix timestamp in milliseconds
- **Represents:** When the last minute bar started (not when it ended)
- **Updates:** Every time there's new trading activity in a minute
- **Persists:** Remains frozen when markets are closed

### Example Values
```json
"min": {
  "t": 1759524060000,     // ← Start of aggregate window (milliseconds)
  "c": 16.40,             // Close price for that minute
  "o": 16.39,             // Open price
  "h": 16.40,             // High
  "l": 16.39,             // Low
  "v": 658                // Volume
}
```

Converting timestamp:
```
1759524060000 ms ÷ 1000 = 1759524060 seconds
= 2025-10-03 20:41:00 ET (8:41 PM Friday)
```

### Database Storage
We store `min.t` as `min_timestamp` in the `asset_prices` table:

**Column:** `min_timestamp BIGINT`
**Source:** Polygon `min.t` field (milliseconds)
**Available in:** Screener queries via `ap.min_timestamp`

### Usage in Screeners
The `min_timestamp` field is available for filtering and sorting:

```yaml
# Example: Filter by timestamp
filters:
  - field: "ap.min_timestamp"
    operator: ">="
    value: 1759520000000  # After 8:00 PM

# Display in results
display:
  columns:
    - name: "Time"
      field: "min_timestamp_formatted"  # Automatically formatted by screener engine
      width: 12
```

**Important for Gap Trading:**
- Identifies when the last trade occurred
- Helps determine if afterhours activity is recent or stale
- Can filter for "fresh" afterhours movers vs old data
- Critical for distinguishing premarket gaps from afterhours continuation

### Data Flow
```
Polygon API (min.t in milliseconds)
    ↓
MarketSnapshot.from_polygon_data()
    ↓
MinuteBar.timestamp
    ↓
AssetPrice.min_timestamp
    ↓
Database: asset_prices.min_timestamp (BIGINT)
    ↓
Screeners: ap.min_timestamp (available for queries)
```

### Example Query
```sql
-- Get afterhours gainers with recent activity
SELECT
    a.symbol,
    ap.min_close,
    datetime(ap.min_timestamp/1000, 'unixepoch') as last_trade_time
FROM assets a
JOIN asset_prices ap ON a.id = ap.asset_id
WHERE ap.min_timestamp > 1759520000000  -- After 8 PM
  AND ap.min_close > ap.day_close
ORDER BY ap.min_timestamp DESC
```

## Conclusion

The Polygon snapshot API behaves consistently across ALL trading sessions:
- **prevDay.c** is ALWAYS the reference price for change calculations
- **min.c** is ALWAYS the current/last traded price (when available)
- **min.t** is ALWAYS the start timestamp of the last minute bar (stored as `min_timestamp`)
- **day.*** fields represent the current regular session (9:30-4:00)
  - Zeros during premarket
  - Live during regular hours
  - Complete after 4 PM
- **updated** field resets daily and indicates if symbol has traded today

This behavior is now confirmed for premarket, regular hours, afterhours, and weekend periods with actual test data.