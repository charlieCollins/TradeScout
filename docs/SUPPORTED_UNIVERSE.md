# TradeScout Universe Coverage

## Overview

TradeScout maintains a comprehensive trading universe sourced from Polygon.io's all-tickers API, with intelligent filtering to focus on high-quality, tradeable US securities. The universe expansion system provides access to thousands of symbols while maintaining data quality standards.

## Universe Statistics

### Total Coverage
- **Polygon.io Total Tickers**: ~11,698 (all markets, all types)
- **Filtered US Common Stocks**: ~4,800-5,000 symbols
- **Current TradeScout Universe**: 1,019 symbols (expandable to full coverage)
- **Available for Addition**: ~3,800+ additional symbols

## Filtering Criteria

TradeScout applies rigorous filtering to ensure only high-quality, tradeable securities:

### ✅ **INCLUDED: US Tradeable Securities**
- **Ticker Types**: Common Stock (CS), ETFs, REITs
- **Market**: Stock market only
- **Exchanges**: Major US exchanges only
  - XNYS (New York Stock Exchange)
  - XNAS (NASDAQ)
- **Symbol Format**: 1-5 alphabetic characters only
- **Status**: Active trading only

### ❌ **EXCLUDED: Filtered Categories**

#### Non-US Securities (~2,000-3,000 tickers)
- International stocks
- Canadian exchanges  
- Foreign ADRs on minor exchanges
- Cross-listings on non-major exchanges

#### Non-Common Stock Types (~1,500-2,000 tickers)
- Preferred stocks (symbols ending in -P, -PR, -A, etc.)
- Rights and warrants
- Units and tracking stocks
- Convertible securities

#### Investment Vehicles (~1,000-1,500 tickers)
- ETNs (Exchange Traded Notes)
- Mutual funds
- Closed-end funds

#### Minor/Alternative Exchanges (~500-1,000 tickers)
- BATS (Cboe BZX Exchange)
- OTC Markets (Pink Sheets)
- OTCQB/OTCQX
- Regional exchanges
- Dark pools

#### Invalid/Unusable Symbols (~500 tickers)
- Test symbols
- Inactive/delisted symbols
- Symbols with numbers or special characters
- Symbols longer than 5 characters
- Duplicate class shares

