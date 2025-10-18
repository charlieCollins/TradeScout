"""Presentation context for TradeScout.

This module provides PresentationContext - manages output/display adapters.
Keeps presentation layer concerns separate from application state (AppContext).

Used to inject different output adapters (CLI, Web, JSON) into commands,
making commands output-agnostic.
"""


class PresentationContext:
    """Presentation layer context - manages output adapters.

    This is separate from AppContext which handles application state.
    PresentationContext is about HOW to display results, not application logic.

    Attributes:
        screener_adapter: Adapter for screener results
        gap_analysis_adapter: Adapter for gap analysis results
        gap_performance_adapter: Adapter for gap performance/backtest results
        bootstrap_adapter: Adapter for bootstrap operation results
        fetch_adapter: Adapter for fetch operation results
        update_adapter: Adapter for update operation results
        news_adapter: Adapter for news/sentiment results
        asset_adapter: Adapter for asset information
        market_adapter: Adapter for market information
        universe_adapter: Adapter for universe listings
        validate_adapter: Adapter for validation results
        fed_adapter: Adapter for federal reserve data
    """

    def __init__(
        self,
        screener_adapter=None,
        gap_analysis_adapter=None,
        gap_performance_adapter=None,
        bootstrap_adapter=None,
        fetch_adapter=None,
        update_adapter=None,
        news_adapter=None,
        asset_adapter=None,
        market_adapter=None,
        universe_adapter=None,
        validate_adapter=None,
        fed_adapter=None
    ):
        """Initialize presentation context with output adapters.

        Args:
            screener_adapter: Adapter for screener output (CLI/Web/JSON)
            gap_analysis_adapter: Adapter for gap analysis output
            gap_performance_adapter: Adapter for gap performance/backtest output
            bootstrap_adapter: Adapter for bootstrap operations
            fetch_adapter: Adapter for fetch operations
            update_adapter: Adapter for update operations
            news_adapter: Adapter for news/sentiment output
            asset_adapter: Adapter for asset info output
            market_adapter: Adapter for market info output
            universe_adapter: Adapter for universe listings
            validate_adapter: Adapter for validation results
            fed_adapter: Adapter for federal reserve data
        """
        self.screener_adapter = screener_adapter
        self.gap_analysis_adapter = gap_analysis_adapter
        self.gap_performance_adapter = gap_performance_adapter
        self.bootstrap_adapter = bootstrap_adapter
        self.fetch_adapter = fetch_adapter
        self.update_adapter = update_adapter
        self.news_adapter = news_adapter
        self.asset_adapter = asset_adapter
        self.market_adapter = market_adapter
        self.universe_adapter = universe_adapter
        self.validate_adapter = validate_adapter
        self.fed_adapter = fed_adapter
