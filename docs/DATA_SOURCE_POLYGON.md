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

## **APIs Available**

| **Endpoint** | **Purpose** | **Use Case** |
|--------------|-------------|-------------|
| `/v3/reference/tickers` | Bootstrap asset universe | Get list of all available ticker symbols |
| `/v2/snapshot/locale/us/markets/stocks/tickers` | Bulk market data | Fetch snapshots for multiple/all tickers at once |
| `/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}` | Single ticker snapshot | Fetch real-time snapshot for specific symbol |
| `/v1/marketstatus/now` | Current session detection | Check if market is open/closed/premarket/afterhours |

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

## **Using Polygon APIs**

### **Authentication**

All API calls require an API key passed as query parameter:
```
https://api.polygon.io/v2/snapshot/locale/us/markets/stocks/tickers/AAPL?apiKey=YOUR_KEY_HERE
```

### **Rate Limits**

- **Free Tier**: 5 API calls per minute
- **Stocks Starter Plan** (~$50/month): Unlimited API calls
- **Note**: TradeScout uses Stocks Starter plan for production

### **Response Format**

All endpoints return JSON responses with consistent structure:
- `status`: "OK" or "ERROR"
- `results`: Array or object containing requested data
- `count`: Number of results (for bulk endpoints)

### **Best Practices**

1. **Use bulk endpoints** when fetching multiple symbols (much more efficient)
2. **Cache aggressively** - snapshot data is 15-minute delayed, no need to fetch constantly
3. **Check market status** before making bulk calls to avoid wasted API quota
4. **Handle extended hours** - remember `day.*` fields are zeros during premarket
5. **Always use `prevDay.c`** as reference price for change calculations

---

## **Implementation Note**

For TradeScout's implementation of these APIs, see:
- **Architecture**: `docs/ARCHITECTURE_API_PROVIDERS.md`
- **Provider Code**: `src/api/provider/polygon_snapshot_provider.py`
- **Tests**: `tests/test_polygon_snapshot_provider.py`