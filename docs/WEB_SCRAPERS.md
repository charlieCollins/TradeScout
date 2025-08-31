# Web Scrapers Documentation

## Overview
Comprehensive documentation of web scrapers for market data collection. All scrapers support after-hours data and have stub implementations for pre-market data (future development).

**Location**: `src/tradescout/data_sources_scraping/`  
**Integration**: Fully integrated with SmartCoordinator for intelligent routing  
**Configuration**: Centralized in `data_sources_config.yaml`

## Table of Contents
- [Extended Hours Scrapers](#extended-hours-scrapers)
- [Pre-Market Support](#pre-market-support) *(Stub Implementations)*
- [SmartCoordinator Integration](#smartcoordinator-integration)
- [Scraper Capabilities Matrix](#scraper-capabilities-matrix)
- [Technical Architecture](#technical-architecture)

---

## Extended Hours Scrapers

Extended hours trading includes both after-hours (4:00 PM - 8:00 PM ET) and pre-market (4:00 AM - 9:30 AM ET) sessions. Current implementations focus on after-hours data with pre-market support planned.

### 1. CNN Markets Scraper ✅ IMPLEMENTED - PRIMARY SOURCE

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
- **Class**: `CNNScraper` (implements `AfterHoursWebScraper`, `PreMarketWebScraper`)
- **File**: `src/tradescout/data_sources_scraping/cnn_scraper.py`
- **Method**: Selenium WebDriver with persistent Chrome session
- **Popup Handling**: Persistent session bypasses Legal Terms popup after first run
- **Session Storage**: `/home/ccollins/projects/TradeScout/data/chrome_session/CNN_Scraper/`
- **Parsing**: BeautifulSoup on rendered HTML
- **Reliability**: High - consistent data structure
- **SmartCoordinator**: Integrated with `moderately_reliable` rating (priority 5)

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

### 2. MarketWatch Scraper ✅ IMPLEMENTED - SECONDARY SOURCE

**Source**: https://www.marketwatch.com/tools/screener/after-hours  
**Status**: Functional with structured table data  
**Data Quality**: Good but filtering criteria not documented  
**Class**: `MarketWatchScraper` (implements `AfterHoursWebScraper`, `PreMarketWebScraper`)  
**File**: `src/tradescout/data_sources_scraping/marketwatch_scraper.py`  

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
- **SmartCoordinator**: Integrated with `highly_reliable` rating (priority 6)

#### Strengths & Limitations:
- ✅ Clean table structure available
- ✅ Company names included
- ✅ Volume data with proper parsing
- ❌ No documented filtering methodology
- ❌ No exchange/index selection
- ⚠️ Volume formatting requires parsing

---

### 3. ADVFN Scraper ✅ IMPLEMENTED - LESS RELIABLE

**Source**: https://www.advfn.com/markets/{exchange}/afterhours  
**Status**: Implemented (disabled by default due to reliability issues)  
**Class**: `ADVFNScraper` (implements `AfterHoursWebScraper`, `PreMarketWebScraper`)  
**File**: `src/tradescout/data_sources_scraping/advfn_scraper.py`  
**SmartCoordinator**: Integrated with `inconsistent` rating (priority 9, disabled)

---

### 4. Investing.com Scraper ✅ IMPLEMENTED

**Source**: https://www.investing.com/equities/after-hours  
**Status**: Implemented with after-hours support  
**Class**: `InvestingComScraper` (implements `AfterHoursWebScraper`, `PreMarketWebScraper`)  
**File**: `src/tradescout/data_sources_scraping/investing_com_scraper.py`  
**SmartCoordinator**: Integrated with `highly_reliable` rating (priority 8)

---

### 5. TipRanks Scraper ✅ IMPLEMENTED

**Source**: https://www.tipranks.com/markets/after-hours/gainers  
**Status**: Implemented with dynamic content handling  
**Class**: `TipRanksScraper` (implements `AfterHoursWebScraper`, `PreMarketWebScraper`)  
**File**: `src/tradescout/data_sources_scraping/tipranks_scraper.py`  
**SmartCoordinator**: Integrated with `moderately_reliable` rating (priority 7)  

---

### 6. TradingView After-Hours Scraper 🔄 PLANNED

**Source**: https://www.tradingview.com/markets/stocks-usa/market-movers-after-hours-gainers/  
**Status**: To be implemented  
**Expected Features**: Professional trading data, Technical indicators  
**Exchange Selection**: 🔍 TBD  

---

## Pre-Market Support

All web scrapers now implement the `PreMarketWebScraper` interface with **stub methods** for future development. Pre-market trading occurs from 4:00 AM to 9:30 AM ET.

### Current Implementation Status
- **Interface**: `PreMarketWebScraper` (abstract base class)
- **Methods**: `get_premarket_gainers()`, `get_premarket_losers()`, `is_premarket_session()`, `get_premarket_session_info()`
- **Implementation**: All scrapers return empty data and log warnings
- **Future Development**: Real implementations planned when pre-market data collection is prioritized

### Stub Method Behavior
```python
def get_premarket_gainers(self, limit: int = 10) -> List[Dict[str, any]]:
    """Get pre-market gainers - not yet implemented"""
    logger.warning("Pre-market gainers not yet supported by [Scraper] scraper")
    return []

def get_premarket_session_info(self) -> Dict[str, any]:
    """Get pre-market session info - not yet implemented"""
    return {
        "current_session": "not_supported",
        "implementation_status": "stub"
    }
```

---

## SmartCoordinator Integration

All web scrapers are fully integrated with the SmartCoordinator for intelligent data source routing and fallback strategies.

### Configuration-Driven Routing
```yaml
# data_sources_config.yaml
extended_hours:
  providers: ["polygon", "yfinance", "marketwatch_scraper", "investing_com_scraper", "cnn_scraper", "tipranks_scraper"]
  fallback_strategy: "first_success"
```

### Reliability-Based Selection
- **Highly Reliable**: `marketwatch_scraper` (priority 6), `investing_com_scraper` (priority 8)
- **Moderately Reliable**: `cnn_scraper` (priority 5), `tipranks_scraper` (priority 7)
- **Inconsistent**: `advfn_scraper` (priority 9, disabled by default)

### Usage Through SmartCoordinator
```python
from tradescout.data_sources.smart_coordinator import SmartCoordinator

coordinator = SmartCoordinator()

# Get extended hours gainers (uses web scrapers)
gainers = coordinator.get_extended_hours_gainers(limit=20)

# Get extended hours data for specific asset (uses API providers)
extended_data = coordinator.get_extended_hours_data("AAPL")
```

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

### Web Scraper Architecture
```
Extended Hours Web Scrapers (src/tradescout/data_sources_scraping/)

AfterHoursWebScraper (Interface)          PreMarketWebScraper (Interface)
├── CNNScraper ✅                         ├── CNNScraper ✅ (stub)
├── MarketWatchScraper ✅                 ├── MarketWatchScraper ✅ (stub)  
├── InvestingComScraper ✅                ├── InvestingComScraper ✅ (stub)
├── TipRanksScraper ✅                    ├── TipRanksScraper ✅ (stub)
├── ADVFNScraper ✅ (disabled)            ├── ADVFNScraper ✅ (stub)
└── [Future scrapers]                     └── [Future implementations]

SmartCoordinator Integration:
├── API Providers (AssetDataProvider)
│   ├── polygon (extended hours support)
│   └── yfinance (limited extended hours)
└── Web Scrapers (AfterHoursWebScraper + PreMarketWebScraper)  
    ├── Reliability-based routing
    ├── First-success fallback strategy
    └── Configuration-driven selection
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