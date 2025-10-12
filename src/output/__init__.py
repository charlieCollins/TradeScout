"""Output adapters for different display contexts (CLI, Web, Reports)."""

from .cli_adapter import CLIOutputAdapter, CLIProgressReporter
from .gap_display import GapAnalysisDisplay, GapPerformanceDisplay

__all__ = [
    "CLIOutputAdapter",
    "CLIProgressReporter",
    "GapAnalysisDisplay",
    "GapPerformanceDisplay"
]
