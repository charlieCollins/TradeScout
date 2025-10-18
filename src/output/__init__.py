"""Output adapters for different display contexts (CLI, Web, Reports)."""

# CLI Adapters
from .cli_progress_reporter import CLIProgressReporter
from .cli_screener_adapter import CLIScreenerOutputAdapter
from .cli_bootstrap_adapter import CLIBootstrapOutputAdapter
from .cli_database_adapter import CLIDatabaseOutputAdapter
from .cli_news_adapter import CLINewsOutputAdapter
from .cli_gap_adapter import CLIGapAnalysisAdapter, CLIGapPerformanceAdapter
from .cli_asset_adapter import CLIAssetOutputAdapter
from .cli_market_adapter import CLIMarketOutputAdapter
from .cli_universe_adapter import CLIUniverseOutputAdapter
from .cli_validate_adapter import CLIValidateOutputAdapter
from .cli_fed_adapter import CLIFedOutputAdapter

# Web Adapters
from .web_screener_adapter import WebScreenerOutputAdapter
from .web_market_adapter import WebMarketOutputAdapter
from .web_news_adapter import WebNewsOutputAdapter
from .web_gap_adapter import WebGapOutputAdapter
from .web_fed_adapter import WebFedOutputAdapter
from .web_universe_adapter import WebUniverseOutputAdapter
from .web_validate_adapter import WebValidateOutputAdapter
from .web_asset_adapter import WebAssetOutputAdapter

__all__ = [
    # CLI Adapters
    "CLIProgressReporter",
    "CLIScreenerOutputAdapter",
    "CLIBootstrapOutputAdapter",
    "CLIDatabaseOutputAdapter",
    "CLINewsOutputAdapter",
    "CLIGapAnalysisAdapter",
    "CLIGapPerformanceAdapter",
    "CLIAssetOutputAdapter",
    "CLIMarketOutputAdapter",
    "CLIUniverseOutputAdapter",
    "CLIValidateOutputAdapter",
    "CLIFedOutputAdapter",
    # Web Adapters
    "WebScreenerOutputAdapter",
    "WebMarketOutputAdapter",
    "WebNewsOutputAdapter",
    "WebGapOutputAdapter",
    "WebFedOutputAdapter",
    "WebUniverseOutputAdapter",
    "WebValidateOutputAdapter",
    "WebAssetOutputAdapter",
]
