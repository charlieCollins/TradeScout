# Polygon.io API Integration Documentation

## Overview

TradeScout integrates with Polygon.io as the primary data provider using a **hybrid data architecture**. This document details the Polygon.io integration and API usage patterns.


**API Base URL**: `https://api.polygon.io`  
**Subscription**: **Stocks Starter Plan** (NOT Premium - see limitations below)
**Implementation**: `AssetDataProviderPolygon` class in `/src/tradescout/data_sources_api/asset_data_provider_polygon.py`

---

## Critical Data Rules - PRICE COMPARISONS

**ALWAYS:**
1. **Previous SESSION close** = Last regular trading session close (could be today, yesterday, 3 days ago - doesn't matter)
   - Get from bulk snapshot: `prevDay.c`
   - API: `/v2/snapshot/locale/us/markets/stocks/tickers` (bulk snapshot)
   
2. **Current REAL-TIME price** = The price RIGHT NOW (pre-market, regular, after-hours - doesn't matter)
   - Get from minute bar in bulk snapshot: `min.c`
   - API: `/v2/snapshot/locale/us/markets/stocks/tickers` (bulk snapshot)

**The calculation is ALWAYS:**
- Change = Current real-time price - Previous session close
- Change % = (Change / Previous session close) × 100

**PERIOD. That's it.**

No special handling for different sessions. No using today's close for after-hours. Just:
- Previous session close (from bulk)
- Current real-time price (from minute bar in bulk snapshot)
- Calculate the difference

This gives you the movement from the last regular session close to right now, which is what matters for trading.

---

## 🚀 API Method Mapping

### **Polygon API Endpoints → TradeScout Methods**

| **Polygon API Endpoint** | **TradeScout Method** | **Purpose** | **Cache TTL** |
|---|---|---|---|
| `/v2/snapshot/locale/us/markets/stocks/tickers` | `_get_full_market_snapshot()` | Complete market data including extended hours | 10 minutes |
| `/v3/reference/tickers/{symbol}` | `_fetch_ticker_details()` | Company info & fundamentals | 24 hours |
| `/vX/reference/financials` | `_fetch_financial_data()` | Financial statements & ratios | 24 hours |

### **TradeScout Command → API Usage**

| **CLI Command** | **Primary API** | **Data Used** | **Purpose** |
|---|---|---|---|
| `asset quote AAPL` | Market snapshot | `min.c` (current price) | Extended hours pricing |
| `market gainers` | Market snapshot | `day` vs `prevDay` comparison | Session-level movers |
| `market suggest` | Market snapshot | `min.c` vs `prevDay.c` | Gap analysis |
| `market suggest-single AAPL` | Market snapshot | `min.c` vs `prevDay.c` | Single symbol gap analysis |
| `asset fundamentals AAPL` | Ticker Details + Financials | Company data | Fundamental analysis |

### **Single Snapshot Architecture**

**All Operations**: Use `/v2/snapshot/locale/us/markets/stocks/tickers` (cached 10 minutes)
- **Session data**: `day` object for regular hours OHLC
- **Extended hours pricing**: `min` object for current minute bar pricing  
- **Previous close**: `prevDay.c` for gap calculations
- **Market scanning**: All symbols available for gainers/losers analysis

**Key Fields**:
- `day.c` = Regular session close price
- `min.c` = Current extended hours price (real-time minute bar) 
- `prevDay.c` = Previous session close (gap reference)

---

## **Core API Endpoint**

### **Market Snapshot API**
**Endpoint**: `/v2/snapshot/locale/us/markets/stocks/tickers`  
**Purpose**: Complete market data including extended hours pricing
**Contains**: 
- `day` object: Regular session OHLC data
- `min` object: Current minute bar (extended hours pricing)  
- `prevDay` object: Previous session reference data
**Caching**: 10 minutes TTL, stored in database

---

## **Extended Hours Coverage** ✅ STOCKS STARTER PLAN

**TradeScout Subscription**: **Stocks Starter Plan**
- ❌ Cannot access Stocks Developer level APIs (Trades `/v3/trades`, Quotes `/v3/quotes`)
- ✅ Can access Basic APIs (Snapshots, Aggregates)

### **Extended Hours Solution: Market Snapshot**

The **Market Snapshot** endpoint (`/v2/snapshot/locale/us/markets/stocks/tickers`) is **included with Stocks Starter plan** and provides extended hours data via the `min` field:

**Endpoint**: `/v2/snapshot/locale/us/markets/stocks/tickers`

**Extended Hours Data Available**:
- `min.c` = Current minute bar close price (includes extended hours)
- `min.t` = Minute bar timestamp  
- `min.v` = Minute bar volume

This single API call provides extended hours pricing for **all symbols** simultaneously, eliminating the need for individual ticker calls.

### **Trading Sessions Covered**
- **Pre-market**: 4:00 AM - 9:30 AM EST ✅
- **Regular Hours**: 9:30 AM - 4:00 PM EST ✅  
- **After-hours**: 4:00 PM - 8:00 PM EST ✅

### **Data Quality with Starter Plan**
- **Current Price**: Latest minute bar close (`c` field) ✅
- **Volume**: Extended hours volume (`v` field) ✅
- **Timestamp**: Unix timestamp (`t` field) ✅  
- **Real-time Updates**: Minute-level granularity ✅
- **Limitation**: No tick-level trades (requires Developer plan)

### **Gap Calculations**

Gap analysis compares current real-time price to previous session close:

```python
# Previous session close from bulk snapshot
reference_close = ticker_data['prevDay']['c'] 

# Current real-time price from minute bar in bulk snapshot
current_price = ticker_data['min']['c']

# Gap calculation  
gap_percent = ((current_price - reference_close) / reference_close) * 100
```


---

## **Additional API Endpoints**

### **Company Data**
- **Ticker Details**: `/v3/reference/tickers/{symbol}` → `_fetch_ticker_details()`
- **Financial Data**: `/vX/reference/financials` → `_fetch_financial_data()`

### **Universe Management**  
- **All Tickers**: `/v3/reference/tickers` → Used by `universe-update` command

---

## **Configuration**

### **API Key Setup**
```bash
# .env file
POLYGON_API_KEY=your_api_key_here
```

### **Caching Configuration**
```python
# Market snapshot: 10 minutes TTL (configurable)
# Company data: 24 hours TTL  
# Real-time quotes: 15 minutes TTL
```

---

**Last Updated**: September 8, 2025  
**Subscription**: Stocks Starter Plan  
**Architecture**: Single API - bulk snapshot provides both session data and real-time pricing via minute bars