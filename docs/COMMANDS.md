# TradeScout Commands Reference

## Overview
TradeScout provides a comprehensive CLI for market research and analysis. Commands intelligently select data sources based on availability, rate limits, and data freshness requirements.

## Data Source Architecture

### Smart Coordinator
The Smart Coordinator intelligently routes requests between multiple data providers:
- **Polygon.io**: Primary for fundamentals and historical data (5 calls/min limit)
- **YFinance**: Primary for real-time quotes and backup for all data types (unlimited)
- **Alpha Vantage**: When configured, used for market movers and specialized data

### Market Movers Provider
Specialized provider for gainers/losers/active stocks:
- **Primary**: Alpha Vantage TOP_GAINERS_LOSERS API (1-hour cache)
- **Fallback**: YFinance S&P 500 processing

## Command Reference

### 📈 Market Data Commands

#### `tradescout quote [SYMBOLS...]`
Get current market quotes for one or more symbols.

**Data Source**: Smart Coordinator (Polygon.io/YFinance)  
**Options**:
- `--save`: Save quotes to database

**Examples**:
```bash
tradescout quote AAPL
tradescout quote AAPL MSFT GOOGL --save
```

---

#### `tradescout fundamentals [SYMBOL]`
Show fundamental data for a symbol including P/E ratio, market cap, dividend yield, etc.

**Data Source**: Smart Coordinator (Polygon.io preferred, YFinance fallback)  

**Example**:
```bash
tradescout fundamentals AAPL
```

---

### 📊 Market Movers Commands

#### `tradescout gainers`
Show top market gainers.

**Data Source**: Market Movers Provider  
- Primary: Alpha Vantage TOP_GAINERS_LOSERS API (1-hour cache)
- Fallback: YFinance S&P 500 processing

**Options**:
- `--limit`: Number of gainers to show (default: 10)
- `--force-refresh`: Force refresh cache

**Example**:
```bash
tradescout gainers --limit 20
```

---

#### `tradescout losers`
Show top market losers.

**Data Source**: Market Movers Provider (same as gainers)  

**Options**:
- `--limit`: Number of losers to show (default: 10)
- `--force-refresh`: Force refresh cache

**Example**:
```bash
tradescout losers --limit 20
```

---

#### `tradescout active`
Show most active stocks by volume.

**Data Source**: Market Movers Provider (same as gainers)  

**Options**:
- `--limit`: Number of stocks to show (default: 10)
- `--force-refresh`: Force refresh cache

**Example**:
```bash
tradescout active --limit 20
```

---

#### `tradescout movers`
Show comprehensive market movers report (gainers, losers, most active).

**Data Source**: Market Movers Provider (same as gainers)  

**Options**:
- `--limit`: Number of stocks per category (default: 5)
- `--force-refresh`: Force refresh cache

**Example**:
```bash
tradescout movers --limit 10
```

---

### 🔍 Analysis Commands

#### `tradescout volume-leaders`
Scan for stocks with unusual volume activity.

**Data Source**: Smart Coordinator (real-time data from YFinance/Polygon.io)  

**Options**:
- `--min-volume-ratio`: Minimum volume ratio (default: 2.0)
- `--symbols`: Comma-separated symbols to scan (default: AAPL,MSFT,GOOGL,TSLA,NVDA,AMZN)

**Example**:
```bash
tradescout volume-leaders --min-volume-ratio 3.0
tradescout volume-leaders --symbols "AAPL,MSFT,TSLA"
```

---

### 💾 Database Commands

#### `tradescout history [SYMBOL]`
Show historical quotes for a symbol from the database.

**Data Source**: Local SQLite database only (no external API calls)  

**Options**:
- `--days`: Number of days to look back (default: 7)

**Example**:
```bash
tradescout history AAPL --days 30
```

---

#### `tradescout status`
Show TradeScout system status and database statistics.

**Data Source**: System information only (no external API calls)  

**Example**:
```bash
tradescout status
```

---

#### `tradescout backup [BACKUP_PATH]`
Create a backup of the database.

**Data Source**: Database operation only (no external API calls)  

**Example**:
```bash
tradescout backup backup/tradescout_2025-07-21.db
```

---

#### `tradescout cleanup`
Clean up old data from the database.

**Data Source**: Database operation only (no external API calls)  

**Options**:
- `--days`: Delete quotes older than N days (default: 90)
- `--confirm`: Skip confirmation prompt

**Example**:
```bash
tradescout cleanup --days 90 --confirm
```

---

## Data Caching Strategy

### Cache Policies
- **Real-time quotes**: 5-minute cache
- **Fundamentals**: 24-hour cache  
- **Market movers**: 1-hour cache
- **Historical data**: Stored permanently in database

### Cache Locations
- Polygon.io: `data/cache/polygon/`
- YFinance: `data/cache/yfinance/`
- Alpha Vantage: `data/cache/alphavantage/`

## Rate Limiting

### Provider Limits
- **Polygon.io Free**: 5 calls/minute
- **YFinance**: Unlimited (but respectful usage recommended)
- **Alpha Vantage Free**: 25 calls/day
- **NewsAPI Free**: 1000 articles/day

### Smart Routing
The Smart Coordinator automatically:
1. Routes high-frequency requests to unlimited providers
2. Preserves rate-limited providers for unique data
3. Falls back gracefully when limits are reached
4. Caches aggressively to minimize API calls

## Global Options

All commands support these global options:

- `--db-path`: Override default database path
- `--verbose` or `-v`: Enable verbose logging
- `--help`: Show help for any command

## Examples

### Daily Market Check
```bash
# Get market movers report
tradescout movers --limit 10

# Check specific holdings
tradescout quote AAPL MSFT GOOGL TSLA --save

# Look for volume anomalies
tradescout volume-leaders --min-volume-ratio 3.0
```

### Research Workflow
```bash
# Find top gainers
tradescout gainers --limit 20

# Get fundamentals for interesting stocks
tradescout fundamentals NVDA

# Check historical performance
tradescout history NVDA --days 30
```

### System Maintenance
```bash
# Check system status
tradescout status

# Backup before cleanup
tradescout backup backup/tradescout_$(date +%Y%m%d).db

# Clean old data
tradescout cleanup --days 90 --confirm
```

## Future Commands (Planned)

- `tradescout after-hours`: Fetch after-hours market data (CNN/TipRanks scrapers)
- `tradescout momentum`: Detect momentum patterns
- `tradescout suggest`: Generate trade suggestions
- `tradescout news`: Aggregate market news
- `tradescout sentiment`: Reddit/social sentiment analysis