# Sector Classification in TradeScout

## Overview

TradeScout uses SIC (Standard Industrial Classification) codes to classify companies into broad investment sectors for universe filtering and analysis. This document explains our current approach, limitations, and future enhancement plans.

## Current Implementation

### Classification System: SIC Codes

We use **SIC codes** (not GICS or NAICS) because:
- Available in yfinance ticker details
- Official U.S. government classification system established in 1937
- Simple hierarchical structure enables quick implementation
- Gets universe sector filtering operational immediately

### Mapping Strategy

**SIC Code Structure:**
- 4-digit codes (e.g., `3571` for Electronic Computers)
- First digit = Major division (0-9)
- **First 2 digits = Major group** (what we use for mapping)

**Our Sector Mapping:**
We map the **first 2 digits** of SIC codes to broad investment sectors:

```python
# Example mappings
"35": "Technology"        # Industrial machinery & computer equipment
"36": "Technology"        # Electronic equipment
"60": "Financials"        # Banking
"28": "Healthcare"        # Chemicals (includes pharmaceuticals)
"48": "Communication Services"  # Communications
```

Full mapping is in `src/config/sic_sector_mapping.py`.

## Supported Sectors

Our current sector classifications:

| Sector | SIC Major Groups | Example Companies |
|--------|------------------|-------------------|
| **Technology** | 35, 36, 38, 73 | Apple (3571), Microsoft (7372) |
| **Financials** | 60-64, 67 | JPMorgan (6022), Goldman Sachs (6211) |
| **Healthcare** | 28, 80, 87 | Pfizer (2834), UnitedHealth (8011) |
| **Communication Services** | 27, 48, 78 | Verizon (4813), Netflix (7841) |
| **Consumer Discretionary** | 23, 25, 39, 50, 55-59, 70, 75-76, 79 | Amazon (5961), Tesla (3711) |
| **Consumer Staples** | 20-21, 54 | Coca-Cola (2086), Walmart (5331) |
| **Energy** | 13, 29, 46 | ExxonMobil (1311), Chevron (2911) |
| **Materials** | 10, 12, 14, 24, 26, 30, 32-34 | DuPont (2821), Alcoa (3334) |
| **Industrials** | 15-17, 37, 40-45, 47, 82 | Boeing (3721), Caterpillar (3531) |
| **Real Estate** | 65-66 | American Tower (6512) |
| **Utilities** | 49 | NextEra Energy (4911) |
| **Other** | All unmapped codes | Fallback category |

## Data Source

**yfinance Integration:**
- Source: yfinance ticker details (via `YFinanceReferenceAdapter`)
- Fields used: `sic_code`, `sector`, `industry`, `market_cap`, `name`
- Bootstrap command: `./tradescout database bootstrap-fundamentals`

## Limitations & Known Issues

### Current Limitations

1. **Granularity**: SIC major groups are broader than modern GICS sectors
2. **Age**: SIC system last updated in 1987, doesn't reflect modern tech/services
3. **Manual Mapping**: Our 2-digit mapping may miss industry nuances
4. **Missing Data**: Some companies may lack SIC codes in yfinance data

### Specific Classification Issues

- **SIC 28 (Chemicals)**: Includes both healthcare pharmaceuticals AND materials chemicals
- **SIC 49 (Utilities)**: Overlaps with energy companies (gas distribution)
- **Technology Services**: Some software companies classified under SIC 73 (Business Services)
- **Modern Industries**: Fintech, biotech, cloud computing lack specific SIC categories

### Expected Misclassifications

- Some biotech companies may appear in "Materials" instead of "Healthcare"
- Renewable energy companies might be in "Utilities" vs "Energy"
- Software-as-a-Service companies could be in various service categories

## Usage in Universe Filtering

**Universe Configuration Example:**
```python
"tech": {
    "included": {
        "sectors": ["Technology"],  # Maps to SIC 35, 36, 38, 73
        "min_market_cap": 500000000
    }
}
```

**Filtering Logic:**
1. Get SIC code from fundamentals data
2. Extract first 2 digits: `sic_code[:2]`
3. Look up sector in mapping: `SIC_SECTOR_MAPPING.get(major_group, "Other")`
4. Apply universe filters based on sector

## Future Enhancements

### Short Term
- Add more granular SIC mappings based on usage patterns
- Handle edge cases for common misclassifications
- Add sector validation and reporting tools

### Medium Term
- Integrate commercial SIC→GICS mapping service
- Add manual overrides for specific company classifications
- Implement hybrid classification using multiple data sources

### Long Term
- Migrate to GICS classification system
- Add sub-industry and industry group granularity
- Implement ML-based sector classification using company descriptions

## Testing & Validation

**Validation Commands:**
```bash
# Test single ticker
./tradescout database bootstrap-fundamentals --symbol AAPL

# Check sector assignment
./tradescout universe info tech
```

**Expected Results:**
- Apple (AAPL, SIC 3571) → Technology sector
- tech universe should include major technology companies
- small_cap universe should filter by market cap

## References

- [SEC SIC Code List](https://www.sec.gov/search-filings/standard-industrial-classification-sic-code-list)
- [OSHA SIC Manual](https://www.osha.gov/data/sic-manual)
- [yfinance Documentation](https://github.com/ranaroussi/yfinance)

---

**Last Updated:** 2025-09-28
**Implementation:** `src/config/sic_sector_mapping.py`
**Bootstrap:** `./tradescout database bootstrap-fundamentals`