"""
Gap Analysis Configuration

⚠️  CRITICAL WARNING FOR CLAUDE CODE USERS ⚠️
DO NOT MODIFY THE VALUES IN THIS FILE WITHOUT EXPLICIT HUMAN AUTHORIZATION
These parameters are based on peer-reviewed academic research and documented strategy rules.
If changes are needed, ask the human to review and approve modifications.
NEVER change GAP_TRADING_CRITERIA values autonomously.

Configuration for gap trading analysis based on academic research:
- Plastun et al. (2019): 90-year study showing 61.8% win rate with specific criteria
- Caporale & Plastun (2016): Multi-market gap analysis validation
- Van Rensburg & Van Zyl (2025): Volatility-driven gap behavior confirmation
- Strategy documents: GAP_TRADING_RESEARCH.md, GAP_TRADING_STRATEGY.md, GAP_TRADING_STRATEGY_RULES.md

Last Updated: 2025-09-16 (aligned with documented strategy rules)
"""

from typing import Dict, List, Optional, Tuple

# Gap Trading Configuration - ALIGNED WITH ACADEMIC RESEARCH AND STRATEGY DOCUMENTS
GAP_TRADING_CRITERIA = {
    # Gap Size Criteria (Academic Thresholds)
    ##"min_gap_percent": 2.0,  # Minimum 2% gap (Plastun et al. statistical significance threshold)
    "min_gap_percent": 2.0,
    ##"max_gap_percent": 20.0,  # Maximum 20% gap (too risky above this level)
    "max_gap_percent": 50000.0,

    # Price Range Criteria - REMOVED (not based on academic research)

    # Volume Criteria (Academic Standards)
    ##"min_volume_ratio": 2.0,  # Volume must be 2.0x average (institutional confirmation requirement)
    "min_volume_ratio": 1.0,
    ##"min_volume": 500000,  # Minimum 500K volume (liquidity requirement from strategy rules)
    "min_volume": 500,

    # Market Cap Criteria (Risk Management)
    ## not currently implemented
    "min_market_cap": 1000000000,  # Minimum $1B market cap (strategy rules requirement)

    # Execution Quality Criteria
    ##"max_spread_percent": 2.0,  # Maximum 2% bid-ask spread
    "max_spread_percent": 1000.0,

    # Gap Classification Thresholds (Academic Research Based)
    "exhaustion_threshold": 5.0,  # 5%+ gaps considered exhaustion (academic threshold)
    "breakaway_min": 2.0,  # 2%+ gaps can be breakaway (trend initiation signals)

    # Risk Exclusions
    "blackout_conditions": {
        "earnings_days": True,  # Skip gaps on earnings days (fundamental vs technical)
        "ex_dividend_days": True,  # Skip gaps on ex-dividend days (artificial gaps)
        "major_events": True,  # Skip during major market events (external volatility)
    },
}

# Market Mover Detection Criteria
MARKET_MOVER_CRITERIA = {
    "min_change_percent": 5.0,  # Minimum 5% change to be considered a mover
    "min_volume_ratio": 2.0,  # Volume must be 2x average
    "min_price": 1.00,  # Minimum price to avoid penny stocks
    "lookback_days": 1,  # Compare to N days back
}

# Momentum Analysis Settings
MOMENTUM_CRITERIA = {
    "short_period": 5,  # Short-term momentum period (days)
    "long_period": 20,  # Long-term momentum period (days)
    "volume_confirmation": True,  # Require volume confirmation
    "min_volume_ratio": 1.2,  # Minimum volume increase for confirmation
    "trend_threshold": 0.15,  # 15% change threshold for trend detection
}


def get_gap_rules_config():
    """
    Get GapRules configuration from analysis criteria.

    ⚠️  WARNING: Do not modify this function without updating GapRules model first
    The min_market_cap field must be added to the GapRules dataclass before use.

    Returns:
        GapRules object configured for gap trading analysis
    """
    from ..data_models.models_analysis import GapRules

    criteria = GAP_TRADING_CRITERIA

    return GapRules(
        # Gap size criteria
        min_gap_percent=criteria["min_gap_percent"],
        max_gap_percent=criteria["max_gap_percent"],
        # Volume criteria (UPDATED TO ACADEMIC STANDARDS)
        min_volume=criteria["min_volume"],  # Now 500K (was 50K)
        min_volume_ratio=criteria["min_volume_ratio"],  # Now 2.0x (was 1.5x)
        # Price criteria - REMOVED (not academically based)
        max_spread_percent=criteria["max_spread_percent"],
        # Market cap criteria (NEW - REQUIRES MODEL UPDATE)
        # min_market_cap=criteria["min_market_cap"],  # Uncomment when GapRules model updated
        # Session filtering
        session_types=["premarket", "regular", "afterhours"],
        # Quality filters
        exclude_penny_stocks=True,
        exclude_low_volume=True,
        # Academic research thresholds (UPDATED TO RESEARCH STANDARDS)
        exhaustion_threshold=criteria["exhaustion_threshold"],  # Now 5.0% (was 7.0%)
        breakaway_min=criteria["breakaway_min"],
    )
