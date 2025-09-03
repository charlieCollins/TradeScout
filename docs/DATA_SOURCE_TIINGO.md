# Tiingo API Data Source Documentation

## Overview
Tiingo provides financial market data through multiple API endpoints including real-time IEX data, historical prices, news, and market fundamentals. This document covers our implementation and findings for TradeScout.

**Plan ends on**: 2025-10-02

## Authentication
- **API Key Required**: Set via `TIINGO_API_KEY` environment variable
- **Headers**: 
  ```python
  headers = {
      'Content-Type': 'application/json',
      'Authorization': f'Token {api_key}'
  }
  ```

## Real-Time IEX Data (Critical for Gap Detection)

### Endpoints
- **Single Ticker**: `https://api.tiingo.com/iex/{symbol}`
- **All Tickers**: `https://api.tiingo.com/iex`
- **IEX API Documentation**: `https://www.tiingo.com/products/iex-api`
- **Eligible Symbols List**: `https://iextrading.com/trading/eligible-symbols/`

### Data Fields
```json
{
  "ticker": "AAPL",
  "timestamp": "2025-02-01T20:15:00.000Z",
  "tngoLast": 225.50,          // Current/last price
  "prevClose": 227.85,         // Previous session close
  "bidPrice": 225.45,          // Current bid
  "askPrice": 225.55,          // Current ask
  "mid": 225.50,               // Mid price
  "volume": 45623789,          // Current volume
  "lastSaleTimestamp": "2025-02-01T20:14:58.000Z"
}
```

### IEX Market Data Policy Changes (Feb 2025)
**Critical Implementation Detail**: Tiingo uses IEX Exchange threshold levels for data access.

#### Threshold Level 6 (What We Use)
- **No IEX Agreement Required**: We can use this without signing a market data agreement with IEX
- **Data Type**: Derived reference price calculated in real-time by Tiingo
- **Coverage**: Fulfills needs of 95% of customer base according to Tiingo
- **Cost**: No additional cost from IEX Exchange
- **Compliance**: "Compliant-friendly reference price"

#### Other Threshold Levels (Not Available to Us)
- **Threshold Level 0/5**: Requires signed IEX market data agreement
- **Data Type**: Full TOPS feed in real-time
- **Status**: Not accessible without IEX agreement

### Real-Time Gap Calculation
```python
def calculate_real_time_gap(symbol):
    """
    Calculate gap percentage for extended hours trading
    Gap = (Current Price - Previous Close) / Previous Close * 100
    """
    response = requests.get(f'https://api.tiingo.com/iex/{symbol}', headers=headers)
    data = response.json()[0]
    
    current_price = data.get('tngoLast') or data.get('mid') or data.get('bidPrice')
    prev_close = data.get('prevClose')
    
    if current_price and prev_close and prev_close > 0:
        gap_pct = ((current_price - prev_close) / prev_close) * 100
        return gap_pct
    return None
```

### Extended Hours Coverage
- **Premarket**: 4:00 AM - 9:30 AM EST
- **After Hours**: 4:00 PM - 8:00 PM EST
- **Real-time Updates**: Available during extended hours sessions
- **Data Freshness**: Updates reflect current extended hours trading

## Market Movers/Screeners

### Endpoints
- **Gainers**: `https://api.tiingo.com/tiingo/utilities/screener?gainers=true`
- **Losers**: `https://api.tiingo.com/tiingo/utilities/screener?gainers=false`
- **Screener Documentation**: `https://www.tiingo.com/documentation/general/overview`

### Response Format
```json
[
  {
    "ticker": "TSLA",
    "name": "Tesla Inc",
    "priceData": {
      "date": "2025-02-01",
      "close": 234.56,
      "open": 228.90,
      "high": 236.78,
      "low": 227.45,
      "volume": 34567890,
      "adjClose": 234.56
    },
    "stats": {
      "changePercent": 2.47,
      "changeAbsolute": 5.66
    }
  }
]
```

### Implementation Notes
- Returns top movers by percentage change
- Includes both price data and statistical metrics
- Updates during regular trading hours
- Can be filtered by various criteria

## Historical Data

### Daily Prices Endpoint
`https://api.tiingo.com/tiingo/daily/{symbol}/prices`

### Parameters
- `startDate`: YYYY-MM-DD format
- `endDate`: YYYY-MM-DD format
- `frequency`: daily, weekly, monthly
- `sort`: date (default), -date for descending

## News Data

### Endpoint
`https://api.tiingo.com/tiingo/news`

### Parameters
- `tickers`: Comma-separated list of symbols
- `tags`: News categories
- `startDate`/`endDate`: Date range
- `limit`: Number of articles (default 100, max 1000)

### Documentation
- **News API Documentation**: `https://www.tiingo.com/documentation/general/overview`

### Use Cases
- Gap catalyst identification
- Sentiment analysis for trading decisions
- News-driven momentum validation

## Rate Limits and Usage

### Free Tier Limitations
- **API Calls**: Check current Tiingo documentation for limits
- **Historical Data**: Limited lookback period
- **Real-time Data**: Threshold level 6 only (derived reference prices)

### Optimization Strategies
- Cache responses using our `api_cache` system
- Batch requests where possible
- Use appropriate cache policies for different data types

## Integration with TradeScout

### Configuration
- Settings in `src/tradescout/config/data_sources_config.yaml`
- API key management in `src/tradescout/config/local_config.py`
- Provider selection in coordinator classes
- Screening universe in `src/tradescout/config/screening_universe.yaml`

### Key Configuration URLs
- **Base URL**: `https://api.tiingo.com`
- **General Documentation**: `https://www.tiingo.com/documentation/general/overview`
- **IEX Products**: `https://www.tiingo.com/products/iex-api`

### Key Use Cases
1. **Gap Detection**: Real-time extended hours price vs session close
2. **Market Screening**: Identify high-momentum candidates
3. **Volume Analysis**: Current vs average volume comparisons
4. **News Integration**: Catalyst identification for gap trades

### Advantages
- ✅ Real-time extended hours data available
- ✅ No IEX agreement required (threshold level 6)
- ✅ Comprehensive market coverage
- ✅ Multiple data types in single provider
- ✅ News and fundamental data included

### Limitations
- ❌ Derived reference prices only (not full TOPS feed)
- ❌ Rate limits on free tier
- ❌ Some premium features require paid subscription

## Testing and Validation

### Real-Time Gap Testing
See `test_real_gaps_implementation.py` for current implementation testing real gaps:
- UNH: -0.35% gap (589.90 vs 591.96 close)
- TSLA: -1.35% gap (410.18 vs 415.85 close)
- AAPL: -1.04% gap (223.45 vs 225.79 close)

### Endpoint Validation
See `test_tiingo_iex_correct.py` for comprehensive endpoint testing.

## Academic Research Compliance

### Gap Trading Parameters
- **Minimum Gap**: 2.0% (per Plastun et al. 2019)
- **Volume Requirements**: 2x average volume surge
- **Time Windows**: Extended hours sessions only
- **Market Cap**: Large/mid-cap focus (>$100M)

### Data Requirements Met
- ✅ Real-time extended hours pricing
- ✅ Previous session close reference
- ✅ Volume data for surge detection
- ✅ Timestamp data for session validation

## Implementation Status

### Completed
- [x] Real-time IEX data integration
- [x] Gap calculation implementation
- [x] Market movers functionality
- [x] Configuration integration
- [x] Testing framework

### Pending
- [ ] News sentiment integration
- [ ] Full screening universe expansion (~14K symbols)
- [ ] Advanced filtering capabilities
- [ ] Performance optimization

## Technical Notes

### Error Handling
```python
# Handle various response formats
if response.status_code == 200:
    data = response.json()
    if isinstance(data, list) and data:
        quote = data[0]
    # Process quote data...
elif response.status_code == 401:
    # Handle unauthorized - API key issues
elif response.status_code == 403:
    # Handle forbidden - may need commercial tier
```

### Data Quality Checks
- Validate timestamp freshness during extended hours
- Verify price data completeness
- Handle missing fields gracefully
- Cross-reference with session times

## References
- [Tiingo API Documentation](https://api.tiingo.com/documentation/)
- [IEX Exchange Market Data Policies](https://iexexchange.io/)
- GAP_TRADING_STRATEGY_RULES.md (Internal research documentation)