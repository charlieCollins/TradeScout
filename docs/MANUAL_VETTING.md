# Manual Vetting and Comparison Guide

**Purpose:** Manual verification procedures for TradeScout data accuracy and feature validation
**Last Updated:** 2025-09-16

---

## Market Gainers/Losers Validation

### **Current Implementation Behavior**

Our `market gainers` and `market losers` commands return stocks with the largest percentage changes from **previous regular session close to current real-time price**.

**Key Characteristics:**
- **Time Frame**: Previous session close → Current moment (not extended hours only)
- **Data Source**: Polygon market snapshot API
- **Filtering**: Applied gap analysis criteria (≥2% change, ≥500 volume, ≥1.0x volume ratio)
- **Ranking**: By percentage change from previous close
- **Default Limit**: 100 stocks (was 20)

### **Manual Verification Source**

Our results should closely match: **https://stockanalysis.com/markets/gainers/**

**Why This Comparison Works:**
- StockAnalysis.com shows "regular session + extended hours" gainers/losers
- Same calculation: (Current Price - Previous Close) / Previous Close × 100
- Similar time frame: Previous close to current moment
- Both include after-hours and pre-market price movements

**Expected Alignment:**
- ✅ **Top gainers/losers should overlap significantly**
- ✅ **Percentage changes should match closely**
- ✅ **Current prices should be similar** (within market data delay)

### **Key Differences to Note**

| Aspect | TradeScout | StockAnalysis.com |
|--------|------------|-------------------|
| **Filtering** | Gap criteria applied | Minimal filtering |
| **Volume** | ≥500 shares minimum | No minimum |
| **Change** | ≥2% minimum | No minimum |
| **Universe** | Filtered subset | Full market |
| **Count** | Up to 100 | ~100 displayed |

### **What This Means**

**We are NOT showing "extended hours only" movers** - we're showing the **total movement from previous close to now**, which includes:
- Regular session changes
- After-hours changes
- Pre-market changes
- Current real-time changes

This is the **correct behavior** for gap analysis since gaps are measured from previous close to current price regardless of when that movement occurred.

---

## Validation Procedure

### **Daily Verification Steps**

1. **Compare Top 10 Gainers:**
   ```bash
   tradescout market gainers --limit 10
   ```
   - Cross-reference with https://stockanalysis.com/markets/gainers/
   - Verify symbols appear in both lists
   - Check percentage changes are similar (±0.1%)

2. **Compare Top 10 Losers:**
   ```bash
   tradescout market losers --limit 10
   ```
   - Cross-reference with https://stockanalysis.com/markets/losers/
   - Verify symbols appear in both lists
   - Check percentage changes are similar (±0.1%)

3. **Check Edge Cases:**
   - Stocks with gaps exactly at 2% threshold
   - Low volume stocks (should be filtered out in TradeScout)
   - Penny stocks (may differ due to filtering)

### **Expected Discrepancies**

**Normal Differences:**
- TradeScout may show fewer results (due to gap criteria filtering)
- Small differences in percentage (±0.1%) due to data timing
- Some low-volume stocks missing from TradeScout results

**Red Flag Differences:**
- Major percentage differences (>0.5%)
- Completely different top movers
- TradeScout showing stocks not moving significantly
- Current prices significantly different

---

## Data Source Clarification

### **What We're Actually Measuring**

**Gap Analysis Context:**
- **Academic Definition**: Gap = Opening Price - Previous Session Close
- **Our Implementation**: Current Real-Time Price - Previous Session Close
- **Practical Effect**: Captures the "gap" that would exist at market open plus any subsequent movement

**Why This Makes Sense:**
- Real-time data is more actionable than stale opening prices
- Includes extended hours movement that creates the gap
- Shows current opportunity size, not just opening gap size
- Aligns with academic research methodology (Plastun et al.)

### **Not Extended Hours Exclusive**

We are **NOT** filtering for "extended hours only" movement because:
- Gap trading strategies focus on total price displacement from previous close
- Extended hours movement is just one component of the total gap
- Academic research measures gaps from close to current, not close to extended hours only
- Real-time assessment is more valuable for trading decisions

---

## Technical Implementation Notes

### **Data Flow**

```
Polygon Market Snapshot → Filter by Gap Criteria → Rank by % Change → Return Top N
```

**Gap Criteria Applied:**
- Minimum 2% price change from previous close
- Minimum 500 shares volume
- Minimum 1.0x volume ratio vs average
- Maximum 1000% spread (effectively no limit currently)

**Data Quality:**
- Price data: Polygon minute-bar close prices
- Volume data: Current session volume
- Timestamp: Minute-bar timestamp when available
- Market cap: Not currently available (requires fundamentals API)

---

## Troubleshooting Common Issues

### **"No Results" or "Very Few Results"**

**Likely Causes:**
- Gap criteria too strict for current market conditions
- Market in low-volatility period (few stocks moving >2%)
- Extended hours with limited volume
- Configuration changes tightened filters

**Verification Steps:**
1. Check StockAnalysis.com for overall market movement
2. Reduce gap criteria temporarily for testing
3. Verify Polygon API connectivity
4. Check market hours and session status

### **Results Don't Match External Sources**

**Check:**
1. Time synchronization (market data delays)
2. Filter criteria configuration
3. Previous close price calculation
4. Volume data availability
5. Symbol universe differences

---

*This document ensures TradeScout data accuracy through systematic manual verification against trusted external sources.*