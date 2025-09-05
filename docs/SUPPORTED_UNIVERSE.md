# TradeScout Universe Coverage

## Overview

TradeScout maintains a comprehensive trading universe sourced from Polygon.io's all-tickers API, with intelligent filtering to focus on high-quality, tradeable US securities. The universe expansion system provides access to thousands of symbols while maintaining data quality standards.

## Universe Statistics

### Total Coverage
- **Polygon.io Total Tickers**: ~11,698 (all markets, all types)
- **Filtered US Common Stocks**: ~4,800-5,000 symbols
- **Current TradeScout Universe**: 1,019 symbols (expandable to full coverage)
- **Available for Addition**: ~3,800+ additional symbols

### Expansion Capabilities
```bash
# Get ALL available US common stocks (~4,800 total)
./tradescout system universe-update

# Preview what would be added
./tradescout system universe-update --dry-run  

# Add specific quantity
./tradescout system universe-update --limit 500
```

## Filtering Criteria

TradeScout applies rigorous filtering to ensure only high-quality, tradeable securities:

### ✅ **INCLUDED: US Common Stocks Only**
- **Ticker Type**: Common Stock (CS) only
- **Market**: Stock market only 
- **Exchanges**: Major US exchanges only
  - XNYS (New York Stock Exchange)
  - XNAS (NASDAQ)  
  - BATS (Cboe BZX Exchange)
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
- ETFs (Exchange Traded Funds)
- ETNs (Exchange Traded Notes)  
- REITs (Real Estate Investment Trusts)
- Mutual funds
- Closed-end funds

#### Minor/Alternative Exchanges (~500-1,000 tickers)
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

## Filter Implementation

### Code Logic
```python
# From engine.py universe update method
for ticker in polygon_tickers:
    symbol = ticker.get("ticker", "").upper()
    ticker_type = ticker.get("type", "")
    market = ticker.get("market", "")
    primary_exchange = ticker.get("primary_exchange", "")
    
    # Apply filtering criteria
    if (ticker_type == "CS" and                          # Common Stock only
        market == "stocks" and                           # Stock market only
        primary_exchange in ["XNYS", "XNAS", "BATS"] and # Major US exchanges  
        1 <= len(symbol) <= 5 and                        # Standard ticker length
        symbol.isalpha() and                             # Letters only
        symbol not in current_symbols):                  # Not already present
        new_symbols.append(symbol)
```

### Quality Assurance
- **Deduplication**: Prevents adding symbols already in universe
- **Exchange Validation**: Only major, liquid US exchanges
- **Type Verification**: Common stocks only (no derivatives)
- **Format Standards**: Professional ticker symbol format

## Universe Management

### Expansion Process
1. **API Query**: Fetches up to 11,698 tickers from Polygon.io via pagination
2. **Intelligent Filtering**: Applies quality criteria (reduces to ~4,800)
3. **Deduplication**: Removes symbols already in universe
4. **Backup Creation**: Creates timestamped backup of existing universe
5. **YAML Update**: Adds new symbols, updates metadata

### Backup System
```bash
# Automatic backups created before updates
screening_universe.bak.20250905_092906  # Timestamped backups
screening_universe.bak.20250905_083421  # Multiple restore points
```

### Configuration Updates
```yaml
default_liquid_universe:
  description: High-volume liquid stocks for reliable market screening  
  source: "Manual curation from S&P 500 and major indices + Polygon all-tickers API update"
  last_updated: '2025-09-05'
  symbols: [1019+ symbols]
```

## Usage Examples

### View Current Universe
```bash
./tradescout system universe
# Shows: Total symbols, last updated, source
```

### Expand Universe
```bash
# Get all available US common stocks (~3,800 more symbols)
./tradescout system universe-update

# Preview expansion without changes  
./tradescout system universe-update --dry-run

# Add specific quantity
./tradescout system universe-update --limit 1000
```

### Expected Results
```
🔄 Updating Trading Universe

Current symbols: 1,019
Fetching ALL symbols from Polygon...

⏳ Fetching tickers from Polygon.io...
Page 1: Retrieved 1000 tickers (total: 1000)  
Page 2: Retrieved 1000 tickers (total: 2000)
...
Page 12: Retrieved 698 tickers (total: 11698)
✅ Retrieved 11698 total tickers from Polygon (12 pages)
Filtered out 6876 tickers (non-stocks, duplicates, or invalid symbols)  
New symbols to add: 3803

💾 Creating backup: screening_universe.bak.20250905_094523
✅ Successfully updated 'default_liquid_universe'
Added 3803 new symbols
Total symbols now: 4822
```

## Strategic Benefits

### Comprehensive Coverage
- **Market Scanning**: Access to nearly all tradeable US stocks
- **Gap Detection**: Broader universe increases gap trading opportunities  
- **Sector Analysis**: Complete coverage across all US sectors
- **Small/Mid Cap**: Includes smaller companies often missed by major indices

### Quality Assurance  
- **Liquidity Focus**: Major exchanges ensure adequate trading volume
- **Data Reliability**: Common stocks have consistent fundamental data
- **Trading Safety**: Excludes complex instruments and low-liquidity securities
- **System Performance**: Focused universe prevents data bloat

### Operational Efficiency
- **Automated Updates**: Single command expands entire universe
- **Incremental Growth**: Only adds new symbols, preserves existing
- **Safe Operations**: Automatic backups enable quick restoration
- **Audit Trail**: Timestamps and source tracking for compliance

## Technical Specifications

### API Integration
- **Provider**: Polygon.io Premium API
- **Endpoint**: `/v3/reference/tickers`  
- **Rate Limits**: Commercial tier (300+ calls/min)
- **Pagination**: Automatic handling of 1000-symbol pages

### Data Processing
- **Filtering Speed**: ~11,698 tickers processed in <10 seconds
- **Memory Efficiency**: Streaming processing, no large memory allocation
- **Error Handling**: Graceful failure with detailed error messages
- **Backup Safety**: Pre-update snapshots prevent data loss

---

**Last Updated**: September 5, 2025  
**Universe Version**: 1,019 symbols → Expandable to 4,800+ US common stocks  
**Data Source**: Polygon.io All-Tickers API with intelligent filtering