# Gap Trading Strategy - Machine Implementation Rules

**Document Purpose:** Machine-readable rules and parameters for automated gap trading strategy execution  
**Strategy Reference:** [Gap Trading Strategy Guide](./GAP_TRADING_STRATEGY.md)  
**Last Updated:** 2025-08-31  
**Academic Basis:** Plastun et al. (2019), Caporale & Plastun (2016), Van Rensburg & Van Zyl (2025)

---

## Core Strategy Parameters

### Gap Identification Criteria
```yaml
gap_detection:
  minimum_gap_size: 2.0%                    # Academic threshold from research
  dynamic_threshold_range: [0.01%, 1.20%]   # Plastun volatility-adjusted range
  calculation_method: "(open - prev_close) / prev_close * 100"
  
volume_confirmation:
  minimum_volume_ratio: 2.0                 # 2x average daily volume
  lookback_period: 20                       # Days for volume average calculation
  premarket_volume_threshold: 1.5           # 1.5x for pre-market confirmation
  
time_constraints:
  entry_window_start: "09:30:00"           # Market open
  entry_window_end: "10:30:00"             # First hour maximum
  mandatory_exit_time: "16:00:00"          # Market close - no overnight holds
  weekend_gap_handling: "separate_rules"   # Different criteria per research
```

### Market Conditions Filter
```yaml
market_filters:
  minimum_market_cap: 1_000_000_000        # $1B minimum (reduce manipulation risk)
  maximum_market_cap: null                 # No upper limit
  minimum_daily_volume: 500_000            # 500k shares minimum liquidity
  maximum_bid_ask_spread: 1.0%             # 1% maximum spread
  
sector_alignment:
  check_sector_momentum: true              # Verify sector direction alignment
  sector_etf_correlation_min: 0.3          # Minimum correlation with sector
  
market_regime:
  vix_threshold_high: 30                   # Reduce exposure above VIX 30
  vix_threshold_low: 15                    # Normal operation below VIX 30
  market_trend_lookback: 10                # Days to assess market direction
```

---

## Binary Gap Classification Rules

### ✅ GOOD CANDIDATE (TRADE IT)
**A gap is GOOD if ALL of these conditions are TRUE:**

```yaml
good_candidate_requirements:
  # Size Requirements
  gap_size: ">= 2.0%"                      # Must be 2% or larger
  
  # Volume Requirements  
  volume_ratio: ">= 2.0"                   # Must be 2x normal volume or higher
  
  # Liquidity Requirements
  market_cap: ">= 1_000_000_000"           # Must be $1B+ market cap
  bid_ask_spread: "<= 1.0%"                # Spread must be 1% or less
  
  # Timing Requirements
  gap_occurs: "market_open"                # Gap from close to open (not intraday)
  time_of_day: "between 9:30 AM - 10:30 AM" # Entry window only
  
  # Exclusion Requirements
  gap_size: "< 5.0% OR trend_age < 20_days" # NOT an exhaustion gap (trend_age check: future)
  volume_ratio: "> 0.5"                    # NOT a thin volume gap

  # NOTE: trend_age check not yet implemented - requires 20 days historical data
  # Currently only checking gap_size >= 5.0% AND volume >= 3.0x for exhaustion detection
  # Full implementation coming when historical data pipeline is built
  
# LOGIC: If all conditions above = TRUE, then TRADE
# LOGIC: If any condition above = FALSE, then REJECT
```

### ❌ BAD CANDIDATE (REJECT IT)
**A gap is BAD if ANY of these conditions are TRUE:**

```yaml
bad_candidate_triggers:
  # Size Problems
  gap_too_small: "< 2.0%"                  # Below academic threshold
  
  # Volume Problems
  volume_too_low: "< 2.0x average"         # Insufficient institutional interest
  thin_volume: "< 0.5x average"            # Manipulation risk
  
  # Liquidity Problems  
  market_cap_too_small: "< 1_000_000_000"  # Below $1B
  spread_too_wide: "> 1.0%"                # Poor liquidity
  
  # Pattern Problems
  exhaustion_gap: "gap >= 5.0% AND trend_age >= 20_days AND volume >= 3.0x" # Trend ending
  # NOTE: Currently only checks gap >= 5.0% AND volume >= 3.0x (trend_age check pending)
  counter_trend: "stock_direction != market_direction" # Swimming upstream
  
  # Timing Problems
  friday_gap: "day_of_week == Friday"      # Weekend risk
  late_entry: "time > 10:30 AM"           # Missed optimal window
  
# LOGIC: If any condition above = TRUE, then REJECT  
# LOGIC: All conditions above must = FALSE to consider trading
```

### Simple Decision Logic
```
Step 1: Is gap >= 2.0%?
        NO → REJECT (too small)
        YES → Go to Step 2

Step 2: Is volume >= 2.0x average?  
        NO → REJECT (insufficient volume)
        YES → Go to Step 3

Step 3: Is market cap >= $1B?
        NO → REJECT (too risky)  
        YES → Go to Step 4

Step 4: Is spread <= 1.0%?
        NO → REJECT (poor liquidity)
        YES → Go to Step 5

Step 5: Is it an exhaustion gap? (gap >= 5% AND volume >= 3x)
        YES → REJECT (trend ending)
        NO → Go to Step 6
        NOTE: Full check should include "trend >= 20 days" but not yet implemented

Step 6: Is it Friday?
        YES → REJECT (weekend risk)
        NO → TRADE IT ✅

RESULT: Only gaps that pass ALL 6 steps are tradeable
```

---

## Position Management Rules

### Entry Rules
```yaml
entry_criteria:
  timing_rule: "day_0_only"                # Academic requirement
  confirmation_wait: 5                     # Minutes after market open
  volume_confirmation_check: true         # Must maintain volume
  sector_alignment_check: true            # Verify sector momentum
  max_positions_per_day: 3                # Risk management limit
  
entry_validation:
  - gap_size >= minimum_threshold
  - volume_ratio >= required_minimum  
  - market_cap >= minimum_required
  - bid_ask_spread <= maximum_allowed
  - catalyst_score >= minimum_score (if news-driven)
  - sector_momentum_aligned == true
```

### Position Sizing Rules
```yaml
position_sizing:
  max_position_risk: 2.0%                 # 2% of account maximum
  base_position_size: 1.0%                # Standard size
  high_conviction_multiplier: 1.5         # For best setups only
  
  size_adjustments:
    gap_size_2_3_percent: 1.0             # Base size
    gap_size_3_5_percent: 1.2             # 20% increase
    gap_size_above_5_percent: 0.8         # 20% decrease (higher volatility)
    
    volume_2x_3x: 1.0                     # Base size
    volume_above_3x: 1.2                  # 20% increase
    volume_below_2x: 0.8                  # 20% decrease
    
    vix_below_20: 1.0                     # Normal sizing
    vix_20_30: 0.8                        # Reduce 20%
    vix_above_30: 0.5                     # Reduce 50%
```

### Risk Management Rules
```yaml
stop_loss:
  maximum_loss_percent: 2.0               # 2% max loss from entry
  stop_type: "percentage"                 # Not price-based
  adjust_stops: false                     # Never move against position
  
  placement_options:
    - "gap_fill_level"                    # At previous close
    - "premarket_extreme"                 # Pre-market high/low
    - "technical_level"                   # Nearest support/resistance
    
take_profit:
  strategy: "scale_out"                   # Partial profit taking
  first_target: 1.0                      # 1:1 risk/reward (50% position)
  second_target: 2.0                     # 2:1 risk/reward (remaining 50%)
  maximum_hold_time: "16:00:00"          # Market close mandatory exit
```

### Exit Rules (Mandatory)
```yaml
exit_conditions:
  mandatory_exit_time: "16:00:00"         # No overnight holds (academic rule)
  maximum_hold_hours: 6.5                # Market hours only
  
  exit_triggers:
    - time_limit_reached: "mandatory_close"
    - stop_loss_hit: "immediate_close"
    - take_profit_1_hit: "close_50_percent"
    - take_profit_2_hit: "close_remaining"
    - volume_dries_up: "close_if_no_progress"  # <1.5x avg volume for 30min
    
  volume_exit_rule:
    volume_threshold: 1.5                 # 1.5x average minimum
    time_period: 30                       # Minutes below threshold
    action: "close_position"              # Exit if volume disappears
```

---

## Automated Screening Workflow

### Daily Morning Process
```yaml
daily_workflow:
  timing: "06:00:00"                      # 6 AM EST daily execution
  
  step_1_scan:
    - identify_gaps_above_2_percent
    - filter_by_market_cap_minimum
    - filter_by_volume_requirements
    - filter_by_bid_ask_spread
    
  step_2_classify:
    - determine_gap_type
    - calculate_catalyst_score
    - assess_sector_alignment
    - check_market_conditions
    
  step_3_rank:
    - sort_by_quality_score
    - apply_position_sizing_rules
    - generate_trade_recommendations
    - output_daily_gap_report
    
  step_4_monitor:
    - track_premarket_volume
    - monitor_news_developments
    - update_gap_sizes
    - alert_on_significant_changes
```

### Quality Scoring Algorithm
```python
def calculate_gap_quality_score(gap_data):
    """
    Academic research-based gap quality scoring
    Returns score 0-100 for trade prioritization
    """
    score = 0
    
    # Gap size component (40 points max)
    if gap_data.size >= 0.02:  # 2%+
        score += min(40, gap_data.size * 100 * 0.8)
    
    # Volume component (25 points max) 
    if gap_data.volume_ratio >= 2.0:
        score += min(25, (gap_data.volume_ratio - 1) * 12.5)
    
    # Catalyst component (20 points max)
    score += min(20, gap_data.catalyst_score * 2)
    
    # Sector alignment (10 points max)
    if gap_data.sector_aligned:
        score += 10
    
    # Market alignment (5 points max)
    if gap_data.market_aligned:
        score += 5
        
    return min(100, score)
```

---

## Risk Management Framework

### Account-Level Limits
```yaml
account_limits:
  max_daily_risk: 4.0%                    # 4% account risk per day maximum
  max_positions_concurrent: 3             # Maximum simultaneous positions
  max_gap_trades_per_week: 15             # Weekly frequency limit
  
  drawdown_controls:
    daily_loss_limit: 2.0%                # Stop trading if 2% daily loss
    weekly_loss_limit: 5.0%               # Review strategy if 5% weekly loss
    monthly_loss_limit: 10.0%             # Pause strategy if 10% monthly loss
```

### Performance Monitoring
```yaml
performance_tracking:
  required_metrics:
    - win_rate_target: 55.0%              # Minimum acceptable win rate
    - profit_factor_target: 1.3           # Gross profit / Gross loss
    - maximum_drawdown_limit: 8.0%        # Maximum peak-to-trough loss
    - sharpe_ratio_target: 1.0            # Risk-adjusted return target
    
  review_frequency:
    daily: "position_analysis"
    weekly: "strategy_performance" 
    monthly: "parameter_adjustment"
    quarterly: "strategy_overhaul_assessment"
```

---

## Market Data Requirements

### Required Data Feeds
```yaml
data_requirements:
  price_data:
    - open_price: "current_day"
    - close_price: "previous_day"
    - high_low: "current_day_and_premarket"
    - volume: "current_day_and_20_day_average"
    
  market_data:
    - sector_etf_prices: "real_time"
    - vix_level: "current"
    - market_indices: "SPY_QQQ_IWM"
    
  news_data:
    - earnings_announcements: "last_16_hours"
    - fda_approvals: "last_16_hours" 
    - merger_news: "last_16_hours"
    - analyst_ratings: "last_16_hours"
    
  technical_data:
    - support_resistance_levels: "dynamic"
    - trend_direction: "10_day_lookback"
    - consolidation_periods: "pattern_recognition"
```

### Data Validation Rules
```yaml
data_validation:
  price_data:
    - no_zero_values: true
    - logical_price_relationships: true    # open between high/low
    - volume_positive: true
    
  gap_calculation:
    - minimum_decimal_precision: 4
    - exclude_stock_splits: true
    - exclude_dividend_adjustments: true
    
  news_data:
    - source_credibility_check: true
    - timestamp_within_range: true
    - duplicate_news_filter: true
```

---

## Implementation Checklist

### Pre-Trading System Validation
```yaml
system_checks:
  data_feeds:
    - [ ] Real-time price data connected
    - [ ] Volume data accurate and current
    - [ ] News feeds operational
    - [ ] Market hours correctly configured
    
  calculation_engines:
    - [ ] Gap size calculation verified
    - [ ] Volume ratio calculation verified
    - [ ] Position sizing algorithm tested
    - [ ] Stop loss calculation validated
    
  risk_controls:
    - [ ] Account limits properly configured
    - [ ] Position size limits enforced
    - [ ] Stop loss automation functional
    - [ ] Mandatory exit times programmed
    
  reporting:
    - [ ] Daily gap scan report format
    - [ ] Trade execution logging
    - [ ] Performance metrics tracking
    - [ ] Error handling and alerts
```

---

## Academic Research Integration

**Strategy Foundation:** This rule set implements findings from peer-reviewed academic research:

- **Plastun et al. (2019):** Day-0 only momentum effect, 20% gap fill rate reality
- **Caporale & Plastun (2016):** Stock market efficiency limitations, statistical validation requirements  
- **Van Rensburg & Van Zyl (2025):** Volatility-driven gaps, market-specific patterns
- **Baniya (2024):** Volume-gap correlation, catalyst quality framework
- **Avishay et al. (2023):** Size effects, positive gap outperformance patterns

**Statistical Validation:** All automated decisions must demonstrate p < 0.05 significance through backtesting before live implementation.

**Continuous Research Integration:** Rules updated quarterly based on new academic findings and empirical performance data.

---

*For complete strategy context and background, see [Gap Trading Strategy Guide](./GAP_TRADING_STRATEGY.md)*