# Polygon Data Source Documentation

**Date:** 2025-09-18
**Status:** Tested and Confirmed
**Plan:** Stocks Starter (~$50/month)

---

## **Plan Limitations & Capabilities**

### **What We Have:**
- **Stocks Starter Plan** - Paid subscription (~$50/month)
- **15-minute delayed data** - All prices are delayed by 15 minutes
- **NO real-time quotes or trades** - We get aggregated bars only (OHLCV)
- **Extended hours data** - Pre-market and after-hours data is available

### **What We've Confirmed We DON'T Get in API Responses:**
- `lastQuote` and `lastTrade` fields are missing from snapshot responses
- This is what we've actually observed, not a plan limitation assumption

---

## **Snapshot API Strategy**

### **Core Concept:**
We base our entire data strategy on Polygon's **Snapshot APIs**. These provide everything we need for gap analysis in a simple, efficient manner.

### **Two Snapshot Endpoints:**

#### **1. Market Snapshot (Bulk)**
```
GET /v2/snapshot/locale/us/markets/stocks/tickers
```
- **Purpose:** Get current state of ALL stocks in one call
- **Returns:** ~10,000 stocks with current price data
- **When to use:** Bulk screening, market-wide gap analysis

#### **2. Single Ticker Snapshot**
```
GET /v2/snapshot/locale/us/markets/stocks/tickers/{ticker}
```
- **Purpose:** Get detailed data for one specific stock
- **When to use:** Individual stock analysis, detailed gap investigation

---

## **Critical Field Mapping**

### **Snapshot Response Structure:**
```json
{
  "ticker": {
    "ticker": "AAPL",
    "todaysChangePerc": 2.5,
    "todaysChange": 5.50,
    "updated": 1758235860000000000,
    "day": {
      "o": 239.97,    // Regular session open
      "h": 240.50,    // Regular session high
      "l": 237.85,    // Regular session low
      "c": 237.88,    // REGULAR SESSION CLOSE (4:00 PM)
      "v": 44221987,  // Regular session volume
      "vw": 239.12    // Regular session VWAP
    },
    "min": {
      "t": 1758235800000,  // Timestamp (tells you session)
      "o": 238.10,         // Last minute open
      "h": 238.11,         // Last minute high
      "l": 238.10,         // Last minute low
      "c": 238.10,         // CURRENT PRICE (any session)
      "v": 247,            // Last minute volume
      "vw": 238.10         // Last minute VWAP
    },
    "prevDay": {
      "c": 238.99     // PREVIOUS DAY'S CLOSE
    }
  }
}
```

### **Key Price Fields for Gap Analysis (CONFIRMED):**

| **Field** | **Meaning** | **Gap Analysis Use** | **Behavior** |
|-----------|-------------|---------------------|--------------|
| `prevDay.c` | **Previous completed session close** | **THE reference price for premarket gaps** | Always last trading day (handles weekends/holidays) |
| `min.c` | Current real-time price | Current price in ANY session | Live data with 15-min delay |
| `day.*` | Current regular session data | OHLCV for today's regular session | **CONFIRMED: All zeros during premarket** (will populate during regular session) |
| `min.t` | Timestamp of current price | Determines which session | Unix timestamp in milliseconds |

**Premarket Behavior (CONFIRMED):**
- `day.*` fields are ALL ZEROS during premarket hours
- This is expected and correct - they only populate once regular session starts
- Use `prevDay.c` as reference price for premarket gaps

**Afterhours Behavior (TO BE TESTED):**
- Need to confirm whether `day.c` or `prevDay.c` is the correct reference
- Will test after 4:00 PM ET to see if `day.*` fields are populated with completed session data

---

## **Session Detection Logic**

### **Determining Current Session:**
**DON'T hardcode session times!** Use Polygon's Market Status API:

```
GET /v1/marketstatus/now
```

This API returns:
- Current market status (open/closed)
- Which session is active (premarket/regular/afterhours)
- Exact session times for today (including holidays/half days)

```python
def get_current_market_status():
    """Get actual market status from Polygon API"""
    url = f"https://api.polygon.io/v1/marketstatus/now"
    params = {"apiKey": api_key}
    response = requests.get(url, params=params)

    if response.status_code == 200:
        data = response.json()
        return data["market"]  # Returns current session info
    return None


```

### **Gap Calculation Logic (CONFIRMED):**

#### **EXTENDED HOURS GAP FORMULA:**
```python
# For overnight/premarket/afterhours gaps
gap = min.c - prevDay.c
gap_percent = (gap / prevDay.c) * 100
```

**Why this works for extended hours:**
- `prevDay.c` is ALWAYS the previous completed regular session close
- `min.c` is ALWAYS the current price (premarket, regular, or afterhours)
- This handles weekends/holidays automatically
- Perfect for identifying overnight gaps and extended hours movements

#### **INTRADAY GAP FORMULA (Regular Session):**
```python
# For gaps during regular trading hours
# Could compare to open, previous close, or other reference points
gap_from_open = min.c - day.o  # Gap from today's open
gap_from_prev = min.c - prevDay.c  # Gap from previous close
```

#### **Pre-Market Gap (TESTED & CONFIRMED):**
```python
# Example from 2025-09-19 6:43 AM ET
# AAPL: prevDay.c = $237.88, min.c = $239.52
gap = 239.52 - 237.88  # = $1.64
gap_percent = (1.64 / 237.88) * 100  # = 0.69%
```

#### **After-Hours Gap (TESTED & CONFIRMED):**
```python
# Example from 2025-09-18 after-hours
# AGMH: prevDay.c = $2.23, min.c = $5.42
gap = 5.42 - 2.23  # = $3.19
gap_percent = (3.19 / 2.23) * 100  # = 143.05%
```

**Important Note:** During premarket/afterhours, `day.*` fields are all zeros because the current regular session hasn't completed yet. This is expected behavior.
We have confirmed this for premarket, not yet for afterhours - LLMs like to make stuff up. 

---

## **Data Flow Strategy**

### **Daily Data Collection:**

#### **Step 1: Market Snapshot (Bulk)**
- Call market snapshot API once per day (or multiple times, may be called ad hoc)
- Store regular session OHLCV for ALL stocks

#### **Step 2: Individual Analysis (On-Demand)**
- For interesting stocks, call single ticker snapshot
- Get detailed current pricing and session info
- Calculate precise gaps and session attribution

### **Database Storage:**
- Store `day.*` fields in daily prices table
- Store `min.*` fields in current prices table
- Track session type and timestamp for current prices

---

## **Confirmed Test Results**

### **Test 1: BREA (After-Hours)**
- **Date:** 2025-09-18 18:50
- **Previous Close (`prevDay.c`):** $24.90
- **After-Hours Price (`min.c`):** $22.00
- **Gap:** -$2.90 (-11.65%)
- **Status:** ✅ Confirmed working

### **Test 2: AGMH (After-Hours)**
- **Date:** 2025-09-18 18:53
- **Previous Close (`prevDay.c`):** $2.23
- **After-Hours Price (`min.c`):** $5.42
- **Gap:** +$3.19 (+143.05%)
- **Status:** ✅ Confirmed working

### **Test 3: AAPL (Pre-Market)**
- **Date:** 2025-09-19 6:43 AM ET
- **Previous Close (`prevDay.c`):** $237.88
- **Pre-Market Price (`min.c`):** $239.52
- **Gap:** +$1.64 (+0.69%)
- **Key Finding:** `day.*` fields are zeros during premarket (expected)
- **Status:** ✅ Confirmed working

### **Test 4: MSFT (Pre-Market)**
- **Date:** 2025-09-19 6:44 AM ET
- **Previous Close (`prevDay.c`):** $508.45
- **Pre-Market Price (`min.c`):** $509.00
- **Gap:** +$0.55 (+0.11%)
- **Status:** ✅ Confirmed working


---

## **Complete API List**

### **All Polygon APIs Used:**

| **API Endpoint** | **Purpose** | **When Called** | **Data Stored** |
|------------------|-------------|-----------------|-----------------|
| `/v3/reference/exchanges` | Get exchange metadata | Once at setup | `markets` table |
| `/v3/reference/tickers` | Bootstrap asset universe | Weekly/Monthly | `assets`, `asset_fundamentals` |
| `/v2/snapshot/locale/us/markets/stocks/tickers` | Bulk market data | Multiple times daily | `asset_prices_daily`, `asset_prices_current` |
| `/v2/snapshot/locale/us/markets/stocks/tickers/{ticker}` | Single ticker analysis | On-demand | `asset_prices_current` |
| `/v3/reference/tickers/{ticker}` | Detailed fundamentals | On-demand/Weekly | `asset_fundamentals` |
| `/v2/reference/news` | Market news/sentiment | Hourly | `sentiment_events` |
| **`/v1/marketstatus/now`** | **Current market session** | **As needed** | **No storage - used for logic** |

### **Market Status API Usage:**
- **Critical for session detection** - Don't hardcode market hours
- **Handles holidays and half-days** - Gets actual market schedule
- **Returns current session state** - premarket/regular/afterhours/closed
- **Use before gap calculations** - To know which reference price to use

---

*This documentation is based on actual API testing and confirmed field mappings. The snapshot approach eliminates the need for complex custom bars aggregation.*