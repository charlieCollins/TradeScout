# Polygon Data Source Documentation

**Date:** 2025-09-18
**Status:** Tested and Confirmed
**Plan:** Stocks Starter (~$50/month)

---

## **Plan Capabilities**

- **15-minute delayed data** - All prices delayed by 15 minutes
- **Extended hours data** - Pre-market and after-hours available
- **Snapshot approach** - No real-time quotes/trades, aggregated bars only

---

## **APIs Used**

| **Endpoint** | **Purpose** | **Implementation** |
|--------------|-------------|-------------------|
| `/v3/reference/tickers` | Bootstrap asset universe | `PolygonDataProvider.fetch_all_tickers()` |
| `/v2/snapshot/locale/us/markets/stocks/tickers` | Bulk market data | `PolygonDataProvider.get_market_snapshot()` |
| `/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}` | Single ticker analysis | `PolygonDataProvider.get_single_ticker_snapshot()` |
| `/v1/marketstatus/now` | Current session detection | `PolygonDataProvider.get_market_status()` |

---

## **Snapshot Field Behavior by Session**

### **Field Definitions:**
- **`prevDay.c`**: Previous completed trading session close
- **`day.*`**: Current trading day regular session data (9:30-4:00 PM)
- **`min.c`**: Most recent price (any session, including extended hours)

### **Expected Behavior by Session:**

| **Session** | **`prevDay.c`** | **`day.*`** | **`min.c`** | **Gap Formula** |
|-------------|-----------------|-------------|-------------|-----------------|
| **Premarket** (4-9:30 AM) | Previous day close | **All zeros** | Premarket price | `min.c - prevDay.c` |
| **Regular** (9:30-4 PM) | Previous day close | Live session data | Current price | `min.c - prevDay.c` |
| **After-hours** (4-8 PM) | Previous day close | Completed session | After-hours price | `min.c - prevDay.c` |
| **Closed** (Weekends/Holidays) | Previous day close | Previous session | Last traded price | `min.c - prevDay.c` |

**Note:** All session behaviors have been tested and confirmed. See `DATA_SOURCE_POLYGON_SNAPSHOT_INFO.md` for detailed test results.

---

## **Key Behavioral Notes**

1. **Session Detection**: Use `/v1/marketstatus/now` API - don't hardcode market hours
2. **Premarket**: `day.*` fields are zeros until regular session starts
3. **Weekends**: All data frozen from Friday 8 PM until Monday premarket
4. **Extended Hours**: `min.c` captures premarket and after-hours pricing
5. **Gap Reference**: Always use `prevDay.c` as the reference price

---

## **Data Processing Architecture**

### **Unified Snapshot Processing Pattern**

TradeScout uses a unified architecture for processing snapshot data regardless of source API:

#### **Single Asset Operations** (Implemented)
- **Commands**: `tradescout analyze asset AAPL`
- **API Call**: `get_single_ticker_snapshot(symbol)` → `/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}`
- **Processing**: Single ticker response → `transform_snapshot_to_asset_price()` → `save_asset_price_data()`
- **TTL**: 10 minutes (checked via `is_price_data_fresh()`)

#### **Bulk Market Operations** (Future Implementation)
- **Commands**: `tradescout screener`, bulk analysis commands
- **API Call**: `get_market_snapshot(symbols)` → `/v2/snapshot/locale/us/markets/stocks/tickers`
- **Processing**: Loop through bulk response → **same methods**: `transform_snapshot_to_asset_price()` + `save_asset_price_data()` for each ticker
- **TTL**: Same 10 minutes for all price data

#### **Key Architecture Benefits**
1. **Single Parsing Logic**: `transform_snapshot_to_asset_price()` handles individual ticker data from either API
2. **Consistent TTL**: `ASSET_PRICE_TTL_MINUTES = 10` for all price data sources
3. **Scalable**: Bulk operations process hundreds of tickers using same transformation methods
4. **Clean Separation**: API call method varies, but data transformation/storage is unified

#### **Configuration**
- **TTL Config**: `src/config/ttl_config.py` - `ASSET_PRICE_TTL_MINUTES = 10`
- **Database**: All price data stored in `asset_prices` table with `updated_at` timestamps
- **Freshness Check**: `is_price_data_fresh(asset_id)` works for all price data regardless of source

*This unified approach ensures consistent data processing across single-asset and bulk market operations.*