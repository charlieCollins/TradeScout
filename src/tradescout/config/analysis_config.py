"""
Analysis Configuration

Configuration for trading analysis strategies including gap trading, momentum detection, 
and other analytical criteria used by TradeScout's analysis modules.
"""

from typing import Dict, List, Optional, Tuple

# Gap Trading Configuration
GAP_TRADING_CRITERIA = {
    "min_gap_percent": 2.0,      # Minimum 2% gap to trade
    "max_gap_percent": 20.0,     # Maximum 20% gap (too risky above)
    "min_price_for_gaps": 5.00,  # Don't trade gaps below $5
    "max_price_for_gaps": 300.00, # Don't trade gaps above $300
    "min_volume_ratio": 1.5,     # Volume must be 1.5x average
    "blackout_conditions": {
        "earnings_days": True,    # Skip gaps on earnings days
        "ex_dividend_days": True, # Skip gaps on ex-dividend days
        "major_events": True      # Skip during major market events
    }
}

# Market Mover Detection Criteria
MARKET_MOVER_CRITERIA = {
    "min_change_percent": 5.0,   # Minimum 5% change to be considered a mover
    "min_volume_ratio": 2.0,     # Volume must be 2x average
    "min_price": 1.00,           # Minimum price to avoid penny stocks
    "lookback_days": 1           # Compare to N days back
}

# Momentum Analysis Settings
MOMENTUM_CRITERIA = {
    "short_period": 5,           # Short-term momentum period (days)
    "long_period": 20,           # Long-term momentum period (days)
    "volume_confirmation": True,  # Require volume confirmation
    "min_volume_ratio": 1.2,     # Minimum volume increase for confirmation
    "trend_threshold": 0.15      # 15% change threshold for trend detection
}


def get_gap_trading_criteria() -> Dict:
    """Get gap trading specific criteria"""
    return GAP_TRADING_CRITERIA.copy()


def get_market_mover_criteria() -> Dict:
    """Get market mover detection criteria"""
    return MARKET_MOVER_CRITERIA.copy()


def get_momentum_criteria() -> Dict:
    """Get momentum analysis criteria"""
    return MOMENTUM_CRITERIA.copy()


def is_valid_gap_candidate(price: float, gap_percent: float, volume_ratio: float = 1.0) -> bool:
    """
    Check if a stock meets gap trading criteria
    
    Args:
        price: Current stock price
        gap_percent: Gap percentage (absolute value)
        volume_ratio: Volume compared to average (optional)
        
    Returns:
        True if stock is a valid gap trading candidate
    """
    criteria = GAP_TRADING_CRITERIA
    
    # Check price range
    if price < criteria["min_price_for_gaps"] or price > criteria["max_price_for_gaps"]:
        return False
    
    # Check gap size
    if gap_percent < criteria["min_gap_percent"] or gap_percent > criteria["max_gap_percent"]:
        return False
    
    # Check volume ratio if provided
    if volume_ratio < criteria["min_volume_ratio"]:
        return False
    
    return True


def is_significant_mover(change_percent: float, volume_ratio: float, price: float) -> bool:
    """
    Check if a stock qualifies as a significant market mover
    
    Args:
        change_percent: Price change percentage (absolute value)
        volume_ratio: Volume compared to average
        price: Current stock price
        
    Returns:
        True if stock is a significant mover
    """
    criteria = MARKET_MOVER_CRITERIA
    
    return (
        change_percent >= criteria["min_change_percent"] and
        volume_ratio >= criteria["min_volume_ratio"] and
        price >= criteria["min_price"]
    )


def has_momentum_signal(short_momentum: float, long_momentum: float, volume_ratio: float = 1.0) -> bool:
    """
    Check if a stock has a momentum signal
    
    Args:
        short_momentum: Short-term momentum percentage
        long_momentum: Long-term momentum percentage
        volume_ratio: Volume confirmation ratio
        
    Returns:
        True if stock has momentum signal
    """
    criteria = MOMENTUM_CRITERIA
    
    # Check trend threshold
    if abs(short_momentum) < criteria["trend_threshold"]:
        return False
    
    # Check momentum divergence (short-term stronger than long-term)
    if short_momentum * long_momentum < 0:  # Different directions
        return False
        
    if abs(short_momentum) <= abs(long_momentum):  # Short-term not stronger
        return False
    
    # Check volume confirmation if required
    if criteria["volume_confirmation"] and volume_ratio < criteria["min_volume_ratio"]:
        return False
    
    return True