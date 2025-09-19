"""Universe configuration for TradeScout asset filtering."""

# Based on docs/SUPPORTED_UNIVERSE.md filtering criteria

UNIVERSE_CONFIG = {
    "default_universe": {
        "name": "default_universe",
        "description": "Primary universe for gap analysis - US stocks, ETFs, and REITs",

        # Included criteria
        "included": {
            "ticker_types": ["CS", "ETF", "REIT"],  # Common Stock, ETFs, REITs
            "markets": ["stocks"],   # Stock market only
            "exchanges": [
                "XNYS",  # New York Stock Exchange
                "XNAS"   # NASDAQ
            ],
            "symbol_pattern": "^[A-Z]{1,5}$",  # 1-5 alphabetic characters only
            "active_only": True
        },

        # Excluded criteria
        "excluded": {
            "non_us_securities": True,
            "preferred_stocks": True,    # Symbols ending in -P, -PR, -A, etc.
            "investment_vehicles": {
                "etns": True,
                "mutual_funds": True,
                "closed_end_funds": True
            },
            "minor_exchanges": {
                "otc_markets": True,
                "regional_exchanges": True
            },
            "invalid_symbols": {
                "test_symbols": True,
                "inactive_delisted": True,
                "special_characters": True,
                "duplicate_classes": True
            }
        }
    }
}

# Expected results based on documentation
EXPECTED_UNIVERSE_SIZE = {
    "polygon_total": 11698,
    "filtered_us_common": "4800-5000",
    "current_tradescout": 1019,
    "available_expansion": "3800+"
}