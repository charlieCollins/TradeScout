"""Time-to-live configuration for cached data and operation staleness detection."""

# Asset price data (real-time market data)
ASSET_PRICE_TTL_MINUTES = 10            # Price snapshots and market data

# Bootstrap operation staleness (hours)
FUNDAMENTALS_TTL_HOURS = 168            # 1 week - fundamentals change rarely
TICKERS_TTL_HOURS = 72                  # 3 days - new listings/delistings are infrequent
UNIVERSE_TTL_HOURS = 24                 # 1 day - universe membership can change with market cap shifts
SNAPSHOT_TTL_MINUTES = 60               # 1 hour - market snapshots for real-time trading

# External data sources
NEWS_TTL_MINUTES = 30                   # News data cache

# Service-level caching
MARKET_CONTEXT_TTL_MINUTES = 5          # Market context service cache

# Data validation and refresh intervals
MAX_FUNDAMENTALS_AGE_DAYS = 7           # When to warn about stale fundamentals
MAX_TICKERS_AGE_DAYS = 3                # When to warn about stale ticker universe
MARKET_DATA_STALE_HOURS = 4             # When price data is considered too old for trading