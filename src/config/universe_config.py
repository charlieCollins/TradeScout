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
    },

    "tech": {
        "name": "tech",
        "description": "Technology sector stocks for high-growth trading",

        # Included criteria
        "included": {
            "ticker_types": ["CS"],  # Common Stock only
            "exchanges": [
                "XNYS",  # New York Stock Exchange
                "XNAS"   # NASDAQ
            ],
            "symbol_pattern": "^[A-Z]{1,5}$",  # 1-5 alphabetic characters only
            "active_only": True,
            "sectors": ["Technology", "Communication Services"],  # Tech sectors
            "min_market_cap": 500000000  # $500M minimum for liquidity
        },

        # Excluded criteria
        "excluded": {
            "non_us_securities": True,
            "preferred_stocks": True,
            "investment_vehicles": {
                "etns": True,
                "mutual_funds": True,
                "closed_end_funds": True
            },
            "invalid_symbols": {
                "test_symbols": True,
                "inactive_delisted": True,
                "special_characters": True,
                "duplicate_classes": True
            }
        }
    },

    "small_cap": {
        "name": "small_cap",
        "description": "Small cap stocks under $2B market cap",

        # Included criteria
        "included": {
            "ticker_types": ["CS"],  # Common Stock only
            "exchanges": [
                "XNYS",  # New York Stock Exchange
                "XNAS"   # NASDAQ
            ],
            "symbol_pattern": "^[A-Z]{1,5}$",  # 1-5 alphabetic characters only
            "active_only": True,
            "min_market_cap": 300000000,    # $300M minimum
            "max_market_cap": 2000000000,   # $2B maximum (small cap definition)
            "min_volume": 100000            # Minimum daily volume for liquidity
        },

        # Excluded criteria
        "excluded": {
            "non_us_securities": True,
            "preferred_stocks": True,
            "investment_vehicles": {
                "etns": True,
                "mutual_funds": True,
                "closed_end_funds": True
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
}