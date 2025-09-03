# TradeScout Supported Markets

## Overview

TradeScout is designed with a **US-focused equity trading strategy**, specifically targeting liquid securities listed on major US exchanges. Our analysis and candidate identification is currently limited to **NASDAQ and NYSE** listed securities.

## Market Focus Strategy

### Primary Markets (Candidate Identification)

TradeScout identifies trading candidates exclusively from these US exchanges:

- **NASDAQ Stock Market**
  - Technology-heavy exchange
  - High-growth companies
  - Electronic trading platform
  - Extended hours: 4:00 AM - 8:00 PM EST

- **New York Stock Exchange (NYSE)**
  - Traditional blue-chip exchange  
  - Established large-cap companies
  - Hybrid trading system
  - Extended hours: 4:00 AM - 8:00 PM EST

### Geographic Scope

- **Primary Focus**: United States equity markets only
- **Currency**: USD-denominated securities
- **Timezone**: Eastern Time (America/New_York)
- **Regulatory Environment**: SEC-regulated markets

## Trading Sessions

All supported exchanges follow the same trading schedule:

| Session | Time (EST) | Description |
|---------|------------|-------------|
| Pre-Market | 4:00 AM - 9:30 AM | Extended hours before regular session |
| Regular Hours | 9:30 AM - 4:00 PM | Primary trading session |
| After Hours | 4:00 PM - 8:00 PM | Extended hours after regular session |

### Trading Days
- **Active**: Monday through Friday
- **Closed**: Weekends and US federal holidays
- **Early Close**: Some holidays (1:00 PM EST close)

## Supported Asset Types

TradeScout focuses on liquid, actively-traded securities:

### Included Asset Types
- **Common Stock** - Regular equity shares
- **Preferred Stock** - Dividend-paying preferred shares  
- **ETFs** - Exchange-traded funds
- **REITs** - Real estate investment trusts (NYSE)

### Excluded Asset Types
- Pink sheet stocks
- Penny stocks (< $1.00)
- Low-volume securities (< 100K daily volume)
- Foreign ADRs (initially excluded)
- Warrants and rights
- Structured products

## Data Requirements

Securities must meet minimum criteria for TradeScout analysis:

### Minimum Thresholds
- **Price**: $1.00 minimum
- **Daily Volume**: 100,000 shares minimum  
- **Market Cap**: $100 million minimum
- **Exchange Listing**: NASDAQ or NYSE only

### Target Security Categories
- **Large Cap**: > $10B market cap
- **Mid Cap**: $2B - $10B market cap
- **High Volume ETFs**: Major index and sector ETFs
- **Index Constituents**: S&P 500, NASDAQ 100, Russell 2000

## Market Data Coverage

### Real-Time Data
- Current quotes and pricing
- Extended hours trading data
- Volume and liquidity metrics
- News and fundamental data

### Historical Data  
- Multi-year price history
- Volume patterns
- Corporate actions
- Earnings and financial data

## Future Expansion

### Sentiment Indicators (Future)
While we only identify candidates on US exchanges, we may analyze these markets for overall sentiment:

**North American**
- **Toronto Stock Exchange (TSX)** - Canadian market indicator

**European**  
- **London Stock Exchange (LSE)** - European market indicator
- **DAX (Germany)** - German market indicator
- **CAC 40 (France)** - French market indicator
- **FTSE 100 (UK)** - UK market indicator

**Asian-Pacific**
- **Nikkei 225 (Japan)** - Japanese market indicator
- **Hong Kong Exchange (HKEX)** - Hong Kong market indicator
- **Australian Securities Exchange (ASX)** - Australian market indicator

**Chinese Markets** (Key sentiment indicators)
- **Shanghai Stock Exchange (SSE)** - China's primary stock exchange
- **Shenzhen Stock Exchange (SZSE)** - China's second-largest exchange  
- **CSI 300 Index** - Top 300 stocks across both exchanges
- **ChiNext** - Growth board for emerging companies
- **STAR Market** - Science and Technology innovation board

*Note: These markets would be used for directional analysis only, not candidate identification.*

### Expansion Criteria
Future market additions will be evaluated based on:
- Data availability and quality
- Regulatory complexity
- Liquidity and trading volume
- Strategic value for analysis

## Technical Implementation

### Market Configuration
Markets are defined in `src/tradescout/config/markets_config.yaml` with:
- Trading hours and sessions
- Supported asset types  
- Minimum requirements
- Priority and enablement flags

### Market Manager
The `MarketsManager` class provides:
- Current trading session detection
- Market hours validation
- Candidate market filtering
- Requirements checking

### Data Source Integration
- **Primary Provider**: Tiingo Commercial API
- **Coverage**: All NASDAQ and NYSE securities
- **Real-Time**: Extended hours support
- **Rate Limits**: Commercial tier (high frequency)

## Key Principles

1. **Quality Over Quantity**: Focus on liquid, well-traded securities
2. **US Market Expertise**: Deep understanding of US market dynamics
3. **Extended Hours**: Full pre-market and after-hours coverage  
4. **Scalable Architecture**: Ready for future market expansion
5. **Data Integrity**: Strict requirements for analysis inclusion

---

**Last Updated**: 2025-09-02  
**Configuration**: `src/tradescout/config/markets_config.yaml`  
**Manager**: `src/tradescout/config/markets_manager.py`