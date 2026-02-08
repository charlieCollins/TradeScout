# TradeScout Universe Coverage

## Overview

TradeScout maintains a trading universe sourced from NASDAQ Trader's bulk ticker file, with filtering to focus on high-quality, tradeable US securities.

## Current Universe Statistics

### Actual Coverage (Current Database)
- **Total Assets**: ~12,260 symbols
- **Default Universe**: ~11,758 symbols
- **Asset Types**: Stock + ETF (from NASDAQ Trader ETF flag)
- **Exchanges**: XNYS (NYSE) and XNAS (NASDAQ) only

## Filtering Criteria

Configuration is defined in `src/config/universe_config.py`:

### ✅ **INCLUDED: Default Universe**
- **Ticker Types**: Common Stock (CS), ETFs, REITs *(config allows, but current data is CS only)*
- **Exchanges**:
  - XNYS (New York Stock Exchange)
  - XNAS (NASDAQ)
- **Symbol Format**: 1-5 alphabetic characters only (`^[A-Z]{1,5}$`)
- **Status**: Active trading only
- **Market**: Stock market only

### ❌ **EXCLUDED: Filtered Out**
- Symbols not matching 1-5 character pattern
- Inactive/delisted securities
- Non-NYSE/NASDAQ exchanges
- Non-stock markets

## Universe Configuration

The filtering logic is implemented in `src/config/universe_config.py`:

```python
UNIVERSE_CONFIG = {
    "default_universe": {
        "included": {
            "ticker_types": ["CS", "ETF", "REIT"],
            "markets": ["stocks"],
            "exchanges": ["XNYS", "XNAS"],
            "symbol_pattern": "^[A-Z]{1,5}$",
            "active_only": True
        }
    }
}
```

## Bootstrap Process

1. **Ticker Fetch**: Download NASDAQ Trader bulk file (nasdaqtraded.txt, ~12,000 securities)
2. **Filter Application**: Apply universe_config criteria
3. **Database Storage**: Store in `assets` and `universe_memberships` tables
4. **Universe Creation**: ~95%+ of fetched tickers meet default universe criteria

The high inclusion rate indicates NASDAQ Trader already returns high-quality US exchange listings that meet our criteria.

*Statistics current as of last universe bootstrap. Use `./bootstrap universe info` for real-time stats.*