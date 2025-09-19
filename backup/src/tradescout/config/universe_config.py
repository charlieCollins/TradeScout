"""
Asset Universe Configuration

Simple configuration for asset universe filtering based on SUPPORTED_UNIVERSE.md criteria.
Used to define what assets should be included in the default trading universe.
"""

from typing import Dict, List, Optional
from datetime import time

# Exchange definitions - centralized to avoid hardcoding throughout codebase
SUPPORTED_EXCHANGES = {
    # Polygon API codes -> Market definitions
    "XNYS": {
        "id": "NYSE",
        "name": "New York Stock Exchange",
        "timezone": "America/New_York",
        "currency": "USD",
        "regular_open": time(9, 30),
        "regular_close": time(16, 0),
        "pre_market_start": time(4, 0),
        "after_hours_end": time(20, 0),
    },
    "XNAS": {
        "id": "NASDAQ",
        "name": "NASDAQ Global Market",
        "timezone": "America/New_York",
        "currency": "USD",
        "regular_open": time(9, 30),
        "regular_close": time(16, 0),
        "pre_market_start": time(4, 0),
        "after_hours_end": time(20, 0),
    },
    "BATS": {
        "id": "NASDAQ",  # Maps to NASDAQ for simplicity
        "name": "Cboe BZX Exchange",
        "timezone": "America/New_York",
        "currency": "USD",
        "regular_open": time(9, 30),
        "regular_close": time(16, 0),
        "pre_market_start": time(4, 0),
        "after_hours_end": time(20, 0),
    },
    "ARCX": {
        "id": "NYSE",  # Maps to NYSE
        "name": "NYSE Arca",
        "timezone": "America/New_York",
        "currency": "USD",
        "regular_open": time(9, 30),
        "regular_close": time(16, 0),
        "pre_market_start": time(4, 0),
        "after_hours_end": time(20, 0),
    },
    "AMEX": {
        "id": "AMEX",
        "name": "American Stock Exchange",
        "timezone": "America/New_York",
        "currency": "USD",
        "regular_open": time(9, 30),
        "regular_close": time(16, 0),
        "pre_market_start": time(4, 0),
        "after_hours_end": time(20, 0),
    },
}

# Major US exchanges for filtering (from SUPPORTED_UNIVERSE.md)
MAJOR_US_EXCHANGES = ["XNYS", "XNAS", "BATS"]

# Default universe based on SUPPORTED_UNIVERSE.md filtering criteria
DEFAULT_UNIVERSE = {
    "name": "default_universe",
    "description": "US Common Stocks from major exchanges with standard filtering criteria",
    "filtering_criteria": {
        # Asset type filtering
        "ticker_types": ["CS"],  # Common Stock only (from Polygon API)
        "market": ["stocks"],  # Stock market only
        # Exchange filtering - Major US exchanges only
        "exchanges": MAJOR_US_EXCHANGES,
        # Symbol format requirements
        "symbol_format": {
            "min_length": 1,
            "max_length": 5,
            "pattern": "alphabetic_only",  # Letters only, no numbers/special chars
        },
        # Status requirements
        "status": ["active"],  # Active trading only
        # No arbitrary market cap, volume, or asset count restrictions
        # Quality is ensured by exchange and type filtering
    },
}


def get_default_universe_config() -> Dict:
    """Get the default universe configuration"""
    return DEFAULT_UNIVERSE.copy()


def should_include_in_default_universe(ticker_data: Dict) -> bool:
    """
    Check if a ticker should be included in the default universe
    based on SUPPORTED_UNIVERSE.md filtering criteria.

    Args:
        ticker_data: Dictionary with ticker info from Polygon API

    Returns:
        True if ticker should be included in default universe
    """
    criteria = DEFAULT_UNIVERSE["filtering_criteria"]

    # Check ticker type (Common Stock only)
    ticker_type = ticker_data.get("type", "").upper()
    if ticker_type not in criteria["ticker_types"]:
        return False

    # Check market (stocks only)
    market = ticker_data.get("market", "")
    if market not in criteria["market"]:
        return False

    # Check exchange (major US exchanges only)
    primary_exchange = ticker_data.get("primary_exchange", "")
    if primary_exchange not in criteria["exchanges"]:
        return False

    # Check symbol format
    symbol = ticker_data.get("ticker", "").upper()
    symbol_format = criteria["symbol_format"]

    if not (symbol_format["min_length"] <= len(symbol) <= symbol_format["max_length"]):
        return False

    if not symbol.isalpha():  # alphabetic_only pattern
        return False

    # Check active status
    is_active = ticker_data.get("active", False)
    if not is_active:
        return False

    return True


def get_supported_exchanges() -> Dict[str, Dict]:
    """Get all supported exchange definitions"""
    return SUPPORTED_EXCHANGES.copy()


def get_major_us_exchanges() -> List[str]:
    """Get list of major US exchange codes for filtering"""
    return MAJOR_US_EXCHANGES.copy()


def get_exchange_info(exchange_code: str) -> Optional[Dict]:
    """Get exchange information by Polygon exchange code"""
    return SUPPORTED_EXCHANGES.get(exchange_code)
