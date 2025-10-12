# Polygon.io API Reference

**Subscription:** Stocks Starter Plan (~$50/month)
**Website:** https://polygon.io

**For TradeScout-specific usage and testing:** See [POLYGON_IMPLEMENTATION.md](POLYGON_IMPLEMENTATION.md)

---

## Plan Capabilities

**Stocks Starter Plan:**
- 15-minute delayed market data
- Extended hours data (pre-market and after-hours)
- Unlimited API calls
- Snapshot aggregates (no tick-by-tick data)
- Historical data access

---

## API Endpoints

### Snapshot APIs

**Bulk Snapshot:**
```
GET /v2/snapshot/locale/us/markets/stocks/tickers
```
Returns snapshot data for all US stocks at once.

**Single Ticker Snapshot:**
```
GET /v2/snapshot/locale/us/markets/stocks/tickers/{symbol}
```
Returns snapshot data for a specific ticker.

**Response Structure:**
```json
{
  "ticker": "AAPL",
  "updated": 1758931200000000000,
  "prevDay": {
    "o": 253.205,
    "h": 257.17,
    "l": 251.712,
    "c": 256.87,
    "v": 55202075,
    "vw": 254.8219
  },
  "day": {
    "o": 254.095,
    "h": 257.6,
    "l": 253.78,
    "c": 255.46,
    "v": 46293856,
    "vw": 255.4635
  },
  "min": {
    "av": 46293856,
    "t": 1758931140000,
    "n": 322,
    "o": 255.5325,
    "h": 255.5325,
    "l": 255.49,
    "c": 255.49,
    "v": 322,
    "vw": 255.5
  }
}
```

**Field Definitions:**
- `prevDay.*` - Previous completed trading session
- `day.*` - Current trading day regular session (9:30am-4pm ET)
- `min.*` - Most recent minute bar (any session)
- `updated` - Timestamp in nanoseconds

**Volume Fields:**
- `prevDay.v` - Previous session total volume
- `day.v` - Regular session volume
- `min.v` - Individual minute bar volume
- `min.av` - Accumulated volume (cumulative)

See [POLYGON_VOLUME_FIELDS.md](POLYGON_VOLUME_FIELDS.md) for complete volume field documentation.

### Aggregates API

**Minute Bars:**
```
GET /v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{from}/{to}
```

**Parameters:**
- `symbol` - Ticker symbol
- `multiplier` - Size of timespan multiplier (e.g., 1)
- `timespan` - Timespan unit (minute, hour, day, etc.)
- `from` - Start timestamp (milliseconds)
- `to` - End timestamp (milliseconds)
- `adjusted` - Adjust for splits (true/false)
- `sort` - Sort order (asc/desc)
- `limit` - Max results (50000 max)

**Example:**
```
GET /v2/aggs/ticker/AAPL/range/1/minute/1759872000000/1759886400000?apiKey=XXX
```

**Response:**
```json
{
  "results": [
    {
      "o": 74.50,
      "h": 74.55,
      "l": 74.48,
      "c": 74.52,
      "v": 12450,
      "vw": 74.5125,
      "t": 1759872060000,
      "n": 145
    }
  ],
  "status": "OK",
  "count": 240
}
```

### Market Status API

**Current Market Status:**
```
GET /v1/marketstatus/now
```

**Response:**
```json
{
  "market": "open",
  "serverTime": "2025-10-07T14:30:00-04:00",
  "earlyHours": false,
  "afterHours": false
}
```

**Market Status Values:**
- `open` - Regular trading hours
- `closed` - Market closed
- `extended-hours` - Pre-market or after-hours

**Flags:**
- `earlyHours` - True during pre-market (4-9:30 AM ET)
- `afterHours` - True during after-hours (4-8 PM ET)

### Reference Data API

**Tickers List:**
```
GET /v3/reference/tickers
```

**Parameters:**
- `market` - Filter by market (stocks, crypto, fx, etc.)
- `type` - Filter by type (CS for common stock)
- `active` - Only active tickers (true/false)
- `limit` - Results per page (max 1000)
- `cursor` - Pagination cursor

**Response:**
```json
{
  "results": [
    {
      "ticker": "AAPL",
      "name": "Apple Inc.",
      "market": "stocks",
      "locale": "us",
      "primary_exchange": "XNAS",
      "type": "CS",
      "active": true,
      "currency_name": "usd",
      "cik": "0000320193",
      "composite_figi": "BBG000B9XRY4"
    }
  ],
  "status": "OK",
  "count": 1,
  "next_url": "..."
}
```

---

## Authentication

All API calls require an API key as query parameter:
```
?apiKey=YOUR_API_KEY_HERE
```

**Environment Variable:**
```bash
export POLYGON_API_KEY="your_key_here"
```

---

## Rate Limits

| Plan | Rate Limit |
|------|------------|
| Free | 5 calls/minute |
| Stocks Starter | Unlimited |

**Note:** Despite "unlimited", Polygon recommends reasonable usage patterns.

---

## Response Format

All endpoints return JSON with:
- `status` - "OK" or "ERROR"
- `results` - Data payload (array or object)
- `count` - Number of results
- `next_url` - Pagination link (if applicable)

**Error Response:**
```json
{
  "status": "ERROR",
  "error": "Invalid API key",
  "request_id": "abc123"
}
```

---

## Market Hours (US Stocks)

**Eastern Time (ET):**
- Pre-market: 4:00 AM - 9:30 AM
- Regular: 9:30 AM - 4:00 PM
- After-hours: 4:00 PM - 8:00 PM
- Closed: 8:00 PM - 4:00 AM

**Note:** Use `/v1/marketstatus/now` API to detect current session programmatically.

---

## Documentation

**Official Docs:** https://polygon.io/docs

**Key Pages:**
- Snapshot API: https://polygon.io/docs/stocks/get_v2_snapshot_locale_us_markets_stocks_tickers
- Aggregates API: https://polygon.io/docs/stocks/get_v2_aggs_ticker__stocksticker__range__multiplier___timespan___from___to
- Market Status: https://polygon.io/docs/stocks/get_v1_marketstatus_now
- Reference Data: https://polygon.io/docs/stocks/get_v3_reference_tickers
