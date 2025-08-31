# Market Hours Documentation

## Overview

This document defines the standard market hours terminology used throughout TradeScout, ensuring consistent understanding of trading sessions and extended hours data collection.

## Market Hours Breakdown

### Regular Trading Hours
- **Time**: 9:30 AM - 4:00 PM ET (Eastern Time)
- **Description**: Main trading session when all markets are fully active
- **Volume**: Highest liquidity and trading volume
- **Data Sources**: All API providers and most financial data sources

### Extended Hours Trading

Extended hours trading is a **superset** that includes both pre-market and after-hours sessions:

#### Extended Hours = Pre-Market + After-Hours

### Pre-Market Trading
- **Time**: 4:00 AM - 9:30 AM ET
- **Description**: Trading session before the market officially opens
- **Volume**: Lower liquidity, typically institutional and news-driven
- **Gap Implications**: Price movements here contribute to opening gaps
- **Current Support**: Stub implementations in web scrapers, planned for future development

### After-Hours Trading
- **Time**: 4:00 PM - 8:00 PM ET  
- **Description**: Trading session after the market officially closes
- **Volume**: Lower liquidity, earnings and news-driven movements
- **Gap Implications**: Price movements here contribute to next-day opening gaps
- **Current Support**: Fully implemented in web scrapers and some API providers

## TradeScout Implementation

### Data Collection Strategy

#### Regular Hours
- **Primary**: API providers (yfinance, polygon, finnhub, alpha_vantage)
- **Methods**: Real-time quotes, historical data, volume analysis
- **Update Frequency**: Real-time to 15-minute delays depending on provider

#### Extended Hours (Unified)
- **Configuration**: `extended_hours` data type in `data_sources_config.yaml`
- **API Providers**: `polygon`, `yfinance` (limited extended hours support)
- **Web Scrapers**: `marketwatch_scraper`, `investing_com_scraper`, `cnn_scraper`, `tipranks_scraper`
- **Routing**: SmartCoordinator intelligently routes requests based on data type and provider capabilities

#### Current Implementation Status
```yaml
# From data_sources_config.yaml
extended_hours:
  description: "Extended hours trading data (pre-market and after-hours) from both APIs and web scrapers"
  providers: ["polygon", "yfinance", "marketwatch_scraper", "investing_com_scraper", "cnn_scraper", "tipranks_scraper"]
  fallback_strategy: "first_success"
  cache_ttl_minutes: 5
```

### Session Detection

#### Market Status Enumeration
```python
class MarketStatus(Enum):
    OPEN = "open"                    # 9:30 AM - 4:00 PM ET
    CLOSED = "closed"                # Outside all trading hours  
    PRE_MARKET = "pre_market"        # 4:00 AM - 9:30 AM ET
    AFTER_HOURS = "after_hours"      # 4:00 PM - 8:00 PM ET
```

#### Session-Aware Data Collection
- **Regular Hours**: Route to primary API providers for best data quality
- **Extended Hours**: Route to providers that support extended hours (polygon, yfinance) or web scrapers
- **Pre-Market**: Currently stub implementations, will be developed when needed
- **After-Hours**: Fully implemented with multiple provider fallbacks

### Web Scraper Capabilities

#### After-Hours Support (Current)
All web scrapers implement `AfterHoursWebScraper` interface:
- `get_after_hours_gainers(limit: int) -> List[Dict]`
- `get_after_hours_losers(limit: int) -> List[Dict]`
- `is_after_hours_session() -> bool`
- `get_session_info() -> Dict`

#### Pre-Market Support (Planned)  
All web scrapers implement `PreMarketWebScraper` interface with stub methods:
- `get_premarket_gainers(limit: int) -> List[Dict]` *(stub)*
- `get_premarket_losers(limit: int) -> List[Dict]` *(stub)*
- `is_premarket_session() -> bool` *(stub)*
- `get_premarket_session_info() -> Dict` *(stub)*

## Time Zone Considerations

### Standard Time Zone
- **All times**: Eastern Time (ET) 
- **Daylight Saving**: Automatically adjusts with ET (EST/EDT)
- **Internal Storage**: UTC timestamps with ET display formatting

### Holiday Handling
- **Market Holidays**: No regular or extended hours trading
- **Early Closes**: Some holidays have modified hours (e.g., 1:00 PM close)
- **Extended Hours Impact**: After-hours and pre-market may also be affected

## Gap Trading Context

### Gap Formation
- **Overnight Gap**: Difference between previous close and current open
- **Contributing Factors**: 
  - Pre-market trading (4:00 AM - 9:30 AM ET)
  - After-hours trading (previous 4:00 PM - 8:00 PM ET)
  - Overseas market movements
  - News and earnings releases

### Data Collection for Gap Analysis
1. **Previous Close**: Last regular hours price (4:00 PM ET)
2. **Extended Hours Activity**: Monitor after-hours and pre-market movements
3. **Opening Price**: First regular hours price (9:30 AM ET)
4. **Gap Calculation**: Opening price vs. previous close difference

## Configuration Reference

### Data Sources Config
```yaml
# Extended hours providers with their capabilities
extended_hours:
  providers: 
    - "polygon"              # API: Both pre-market and after-hours
    - "yfinance"             # API: Limited extended hours
    - "marketwatch_scraper"  # Web: After-hours only (pre-market planned)
    - "investing_com_scraper"  # Web: After-hours only (pre-market planned)
    - "cnn_scraper"          # Web: After-hours only (pre-market planned)
    - "tipranks_scraper"     # Web: After-hours only (pre-market planned)
```

### Provider Selection Logic
1. **Regular Hours**: Prefer API providers for reliability
2. **Extended Hours**: Use API providers if available, fallback to web scrapers  
3. **After-Hours**: Web scrapers provide good market mover data
4. **Pre-Market**: Will prefer API providers when implemented

## Future Development

### Planned Enhancements
1. **Pre-Market Web Scrapers**: Implement real pre-market data collection
2. **Session-Aware Routing**: Smarter provider selection based on current session
3. **Holiday Calendar**: Integrate market holiday awareness
4. **Time Zone Expansion**: Support for other major market time zones

### Reliability Considerations
- **Web Scrapers**: Subject to website changes, rate limiting
- **API Providers**: More reliable but may have usage limits
- **Fallback Strategy**: Multiple providers ensure data availability

---

This documentation ensures consistent understanding of market hours across TradeScout's data collection, analysis, and gap trading functionality.