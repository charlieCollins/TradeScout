"""Output adapters for different display contexts (CLI, Web, Reports)."""

from .cli_progress_reporter import CLIProgressReporter
from .cli_screener_adapter import CLIScreenerOutputAdapter
from .cli_bootstrap_adapter import CLIBootstrapOutputAdapter
from .cli_fetch_adapter import CLIFetchOutputAdapter
from .cli_update_adapter import CLIUpdateOutputAdapter
from .cli_news_adapter import CLINewsOutputAdapter
from .cli_gap_adapter import CLIGapAnalysisAdapter, CLIGapPerformanceAdapter
from .cli_asset_adapter import CLIAssetOutputAdapter
from .cli_market_adapter import CLIMarketOutputAdapter
from .cli_universe_adapter import CLIUniverseOutputAdapter
from .cli_validate_adapter import CLIValidateOutputAdapter
from .cli_fed_adapter import CLIFedOutputAdapter

__all__ = [
    "CLIProgressReporter",
    "CLIScreenerOutputAdapter",
    "CLIBootstrapOutputAdapter",
    "CLIFetchOutputAdapter",
    "CLIUpdateOutputAdapter",
    "CLINewsOutputAdapter",
    "CLIGapAnalysisAdapter",
    "CLIGapPerformanceAdapter",
    "CLIAssetOutputAdapter",
    "CLIMarketOutputAdapter",
    "CLIUniverseOutputAdapter",
    "CLIValidateOutputAdapter",
    "CLIFedOutputAdapter"
]
