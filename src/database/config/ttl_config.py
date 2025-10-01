"""Time-to-live configuration for cached data and operation staleness detection."""

# Asset price data (real-time market data)
ASSET_PRICE_TTL_MINUTES = 10            # Individual asset prices
TICKER_SNAPSHOT_TTL_MINUTES = 15        # Individual ticker snapshots
MARKET_SNAPSHOT_TTL_MINUTES = 15        # Bulk market snapshots

# Bootstrap operation staleness (hours)
FUNDAMENTALS_TTL_HOURS = 168            # 1 week - fundamentals change rarely
TICKERS_TTL_HOURS = 72                  # 3 days - new listings/delistings are infrequent
ASSETS_TTL_HOURS = 72                   # 3 days - new listings/delistings are infrequent
UNIVERSES_TTL_HOURS = 24                # 1 day - universe membership can change with market cap shifts
MARKETS_TTL_HOURS = 8760                # 1 year - market/exchange reference data is essentially static

# External data sources
NEWS_TTL_MINUTES = 30                   # News data cache

# Service-level caching
MARKET_CONTEXT_TTL_MINUTES = 5          # Market context objects cache
MARKET_HOLIDAYS_TTL_DAYS = 30           # Market holidays rarely change (cache for 30 days)

# Data validation and refresh intervals
MAX_FUNDAMENTALS_AGE_DAYS = 7           # When to warn about stale fundamentals
MAX_TICKERS_AGE_DAYS = 3                # When to warn about stale ticker universe
MARKET_DATA_STALE_HOURS = 4             # When price data is considered too old for trading