# TradeScout Universe Coverage

## Overview

TradeScout maintains a trading universe sourced from Polygon.io's reference tickers API, with filtering to focus on high-quality, tradeable US securities.

## Current Universe Statistics

### Actual Coverage (Current Database)
- **Total Assets**: 11,765 symbols
- **Default Universe**: 7,521 symbols (64.0% of total)
- **Asset Types**: All stock (CS) - no ETFs or REITs currently included
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

1. **Ticker Fetch**: Get all tickers from Polygon `/v3/reference/tickers`
2. **Filter Application**: Apply universe_config criteria
3. **Database Storage**: Store in `assets` and `universe_memberships` tables
4. **Universe Creation**: ~95.8% of fetched tickers meet criteria

The high inclusion rate (11,249 of 11,745) indicates Polygon's reference API already returns mostly high-quality US exchange listings that meet our criteria.

*Statistics current as of last universe bootstrap. Use `./bootstrap universe info` for real-time stats.*