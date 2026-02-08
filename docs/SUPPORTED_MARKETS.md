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

## Market Context & Primary Market

### What is MarketContext?

`MarketContext` is a runtime object that provides definitive information about the current market state based on **pandas_market_calendars and rule-based session detection**. It answers three critical questions:

1. **Is today a trading day?** - Checks against market holiday calendar
2. **What was the previous trading day?** - Skips weekends and holidays correctly
3. **What is the current market session?** - Premarket, regular, afterhours, or closed

#### Key Properties

```python
# Dates (from market holiday calendar)
market_context.current_date              # Today's date
market_context.previous_trading_date     # Last trading day (skips weekends/holidays)
market_context.next_trading_date         # Next trading day
market_context.expected_data_date        # What date should price data be from?

# Trading Status
market_context.is_trading_day            # True if today is a trading day
market_context.day_type                  # REGULAR_TRADING, EARLY_CLOSE, CLOSED_HOLIDAY, CLOSED_WEEKEND

# Session Information (from market context rules)
market_context.current_session           # PREMARKET, REGULAR, AFTERHOURS, CLOSED_PRE, CLOSED_POST
market_context.session_name              # Simplified: 'premarket', 'regular', 'afterhours', 'closed'
market_context.is_market_open            # True if any trading is happening
market_context.is_regular_hours          # True if regular session (9:30 AM - 4 PM)
market_context.is_extended_hours         # True if premarket or afterhours
```

#### How MarketContext Works

MarketContext uses **pandas_market_calendars + rule-based logic** as the source of truth:

1. **pandas_market_calendars** - Market calendar and holidays
   - Determines trading days, early close days, holidays
   - Used to bootstrap `market_holidays` table

2. **`/v1/marketstatus/upcoming`** - Official holiday calendar
   - Provides all NYSE/NASDAQ holidays
   - Includes both `closed` and `early-close` days
   - Used to skip holidays when finding previous/next trading days

**Example**: On Saturday Oct 18, 2025:
```python
market_context.current_date           # 2025-10-18 (Saturday)
market_context.is_trading_day         # False (weekend)
market_context.previous_trading_date  # 2025-10-17 (Friday - correctly skips Saturday)
market_context.expected_data_date     # 2025-10-17 (data should be from Friday)
market_context.current_session        # CLOSED_POST
```

**Example**: On early-close day (day before Thanksgiving) at 1:05 PM:
```python
market_context.current_date           # 2025-11-26
market_context.day_type               # EARLY_CLOSE
market_context.current_session        # CLOSED_POST (market closed at 1:05 PM)
```

### Primary Market Concept

When a **universe contains assets from multiple markets** (e.g., NYSE + NASDAQ), we need to pick **one market** as the "primary" to determine MarketContext.

#### Why We Need a Primary Market

MarketContext requires:
- A specific market code (e.g., "XNAS" for NASDAQ, "XNYS" for NYSE)
- A timezone for session calculations
- Trading hours and holiday calendar

Since both NYSE and NASDAQ have **identical schedules** (same hours, same holidays), it doesn't matter which we choose. We typically select the market with the **most assets** in the universe.

#### How Primary Market is Selected

```python
# From universe configuration
universe: "default_universe"
  ├─ NASDAQ (XNAS): 4,699 assets (69.2%)  ← Primary market chosen
  └─ NYSE (XNYS):  2,094 assets (30.8%)
```

The primary market is used for:
- Getting MarketContext (session times, trading days, holidays)
- Market status checks (pandas_market_calendars + rules)
- All screeners and commands operating on this universe

You'll see this in logs:
```
INFO - Using primary market 'XNAS' from universe 'default_universe'
INFO - Market Context: MarketContext(XNAS: trading_day=False, session=closed_post, prev_trading=2025-10-17)
```

#### Data Date Validation

MarketContext provides **`expected_data_date`** - the date that price data SHOULD be from:

| Session State | Expected Data Date |
|--------------|-------------------|
| Regular hours on trading day | Today's date |
| Afterhours on trading day | Today's date |
| Premarket | Previous trading day |
| Closed (weekend/holiday) | Previous trading day |

Screeners show data validation:
```
Expected Data Date: 2025-10-17
Actual Data Date:   ⚠️  2025-10-16 (mismatch!)
```

This helps catch:
- Stale data (not refreshed today)
- Mixed dates (some symbols updated, others not)
- Weekend runs with Friday data vs Monday data

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
- **Primary Providers**: yfinance (snapshots/aggregates), NASDAQ Trader (reference), Finnhub (news), FRED (economic), pandas_market_calendars (market status)
- **Coverage**: All NASDAQ and NYSE securities (~12,000)
- **Real-Time**: Extended hours support via yfinance
- **Cost**: Free (no paid subscriptions required)

## Key Principles

1. **Quality Over Quantity**: Focus on liquid, well-traded securities
2. **US Market Expertise**: Deep understanding of US market dynamics
3. **Extended Hours**: Full pre-market and after-hours coverage  
4. **Scalable Architecture**: Ready for future market expansion
5. **Data Integrity**: Strict requirements for analysis inclusion

---

**Last Updated**: 2025-10-18
**Configuration**: `src/tradescout/config/markets_config.yaml`
**Manager**: `src/tradescout/config/markets_manager.py`
**Market Context**: `src/models/dataclass/market_context.py`