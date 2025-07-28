# Web Scrapers Documentation

## Overview
Comprehensive documentation of web scrapers for market data collection including after-hours, pre-market, news, sentiment analysis, and regular trading session data.

## Table of Contents
- [After-Hours Scrapers](#after-hours-scrapers)
- [Pre-Market Scrapers](#pre-market-scrapers) *(Coming Soon)*
- [News & Sentiment Scrapers](#news--sentiment-scrapers) *(Coming Soon)*
- [Regular Session Scrapers](#regular-session-scrapers) *(Coming Soon)*
- [Scraper Capabilities Matrix](#scraper-capabilities-matrix)
- [Technical Architecture](#technical-architecture)

---

## After-Hours Scrapers

After-hours trading occurs from 4:00 PM to 8:00 PM ET. These scrapers collect data on stocks with significant price movements during extended trading hours.

### 1. CNN Markets After-Hours Scraper ✅ WORKING - PRIMARY SOURCE

**Source**: https://www.cnn.com/markets/after-hours  
**Status**: Fully operational  
**Data Quality**: High quality, curated mashup  

#### Data Characteristics:
- **Volume Coverage**: Nasdaq, NYSE, and NYSE American exchanges
- **Price Filter**: Stocks with prior close of $2 or higher 
- **Data Type**: Curated mashup (not raw exchange data)
- **Update Frequency**: Real-time during after-hours session
- **Typical Count**: ~11 gainers/losers displayed
- **Exchange Selection**: ❌ No - CNN's proprietary mix
- **Methodology Transparency**: ✅ Yes - documented filtering criteria

#### CNN's Stated Methodology:
*"Trade volume is from Nasdaq, NYSE, and NYSE American and includes stocks with a prior close of $2 or higher"*

#### Data Format:
```python
{
    "symbol": "INMB",
    "company_name": "INmune Bio, Inc.",
    "regular_close": 2.71,
    "after_hours_price": 3.43,
    "after_hours_change": 0.72,
    "after_hours_change_percent": 26.55,
    "after_hours_volume": 325000,
    "source": "cnn_markets_after_hours",
    "timestamp": datetime.now(),
    "session": "after_hours"
}
```

#### Technical Implementation:
- **Method**: Selenium WebDriver with persistent Chrome session
- **Popup Handling**: Persistent session bypasses Legal Terms popup after first run
- **Session Storage**: `/home/ccollins/projects/TradeScout/data/chrome_session/CNN_Scraper/`
- **Parsing**: BeautifulSoup on rendered HTML
- **Reliability**: High - consistent data structure

#### Strengths & Limitations:
- ✅ Consistent, clean data format
- ✅ Good filtering (removes penny stocks)
- ✅ Reliable source with persistent session
- ✅ Real company names included
- ✅ Volume data available
- ❌ Limited to ~11 stocks (not customizable)
- ❌ No market/index selection
- ❌ No access to raw exchange data

---

### 2. MarketWatch After-Hours Scraper ✅ WORKING - SECONDARY SOURCE

**Source**: https://www.marketwatch.com/tools/screener/after-hours  
**Status**: Functional with structured table data  
**Data Quality**: Good but filtering criteria not documented  

#### Data Characteristics:
- **Market Coverage**: Unknown - no indication of which exchanges or indices
- **Price Filter**: Unknown - no documented thresholds
- **Data Type**: Unclear filtering methodology 
- **Update Frequency**: Real-time during after-hours
- **Typical Count**: Variable (10-20+ stocks displayed)
- **Exchange Selection**: ❌ No
- **Methodology Transparency**: ❌ No - criteria not disclosed

#### Data Format:
Table structure includes:
- Symbol (with link)
- Company Name
- Price
- Volume (K/M notation)
- CHG (dollar change)
- CHG % (percentage change)

#### Technical Implementation:
- **Method**: Selenium WebDriver with persistent Chrome session
- **Parsing**: Enhanced table parser with K/M/B volume notation support
- **Reliability**: Medium - stable table structure
- **Session Storage**: `/home/ccollins/projects/TradeScout/data/chrome_session/MarketWatch_Scraper/`

#### Strengths & Limitations:
- ✅ Clean table structure available
- ✅ Company names included
- ✅ Volume data with proper parsing
- ❌ No documented filtering methodology
- ❌ No exchange/index selection
- ⚠️ Volume formatting requires parsing

---

### 3. ADVFN After-Hours Scraper 🔄 PLANNED

**Source**: https://www.advfn.com/markets/{exchange}/afterhours  
**Status**: To be implemented  
**Exchange Selection**: ✅ Yes - Separate URLs for NASDAQ, NYSE, AMEX  
**Methodology Transparency**: 🔍 TBD  

---

### 4. Investing.com After-Hours Scraper 🔄 PLANNED

**Source**: https://www.investing.com/equities/after-hours  
**Status**: To be implemented  
**Exchange Selection**: 🔍 TBD  
**Global Markets**: ✅ Expected  

---

### 5. TipRanks After-Hours Scraper 🔄 PLANNED

**Source**: https://www.tipranks.com/markets/after-hours/gainers  
**Status**: To be implemented  
**Unique Features**: Analyst ratings, Smart scores  
**Exchange Selection**: 🔍 TBD  

---

### 6. TradingView After-Hours Scraper 🔄 PLANNED

**Source**: https://www.tradingview.com/markets/stocks-usa/market-movers-after-hours-gainers/  
**Status**: To be implemented  
**Expected Features**: Professional trading data, Technical indicators  
**Exchange Selection**: 🔍 TBD  

---

## Pre-Market Scrapers

*Coming Soon - Pre-market trading occurs from 4:00 AM to 9:30 AM ET*

---

## News & Sentiment Scrapers

*Coming Soon - Real-time news and social sentiment analysis*

---

## Regular Session Scrapers

*Coming Soon - Regular trading hours 9:30 AM to 4:00 PM ET*

---

## Scraper Capabilities Matrix

| Scraper | Exchange Selection | Methodology Transparent | Price Filters | Volume Data | Company Names | Global Markets |
|---------|-------------------|------------------------|---------------|-------------|---------------|----------------|
| CNN Markets | ❌ | ✅ | $2+ | ✅ | ✅ | ❌ |
| MarketWatch | ❌ | ❌ | Unknown | ✅ | ✅ | ❌ |
| ADVFN | ✅ | 🔍 | 🔍 | 🔍 | 🔍 | ❌ |
| Investing.com | 🔍 | 🔍 | 🔍 | 🔍 | 🔍 | ✅ |
| TipRanks | 🔍 | 🔍 | 🔍 | 🔍 | 🔍 | 🔍 |
| TradingView | 🔍 | 🔍 | 🔍 | 🔍 | 🔍 | 🔍 |

Legend: ✅ Yes | ❌ No | 🔍 To Be Determined | ⚠️ Limited

---

## Technical Architecture

### After-Hours Architecture
```
AfterHoursWebScraper (Interface)
├── CNNAfterHoursScraper ✅
├── MarketWatchAfterHoursScraper ✅
├── ADVFNAfterHoursScraper 🔄
├── InvestingAfterHoursScraper 🔄
├── TipRanksAfterHoursScraper 🔄
├── TradingViewAfterHoursScraper 🔄
└── AfterHoursAggregator 🔄
```

### Data Aggregation Strategy

```python
# Proposed aggregation approach
class ScraperAggregator:
    """
    Intelligent aggregation based on scraper capabilities:
    
    1. Exchange-specific requests → Use ADVFN
    2. Methodology-transparent data → Use CNN
    3. Broadest coverage → Combine all sources
    4. Cross-validation → Compare overlapping symbols
    """
```

### Common Technical Patterns

1. **Selenium WebDriver Setup**
   - Persistent Chrome sessions for cookie/consent management
   - User-agent spoofing for reliability
   - Headless mode for production

2. **Data Parsing**
   - BeautifulSoup for HTML parsing
   - Volume notation parsing (K/M/B)
   - Percentage extraction and normalization

3. **Error Handling**
   - Timeout management
   - Fallback strategies
   - Data validation

---

## Future Enhancements

1. **Capability-Based Routing**
   - Route requests to appropriate scrapers based on requirements
   - Example: NYSE-only requests → ADVFN NYSE scraper

2. **Data Quality Scoring**
   - Rate sources based on reliability, completeness, accuracy
   - Prefer high-quality sources in aggregation

3. **Smart Caching**
   - Cache data based on update frequency
   - Reduce redundant scraping

4. **API Fallbacks**
   - Use web scraping as backup for API failures
   - Seamless failover between data sources