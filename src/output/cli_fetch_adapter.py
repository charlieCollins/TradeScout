"""CLI output adapter for fetch results using Rich formatting.

Formats fetch operation results for terminal display with Rich styling.
"""

from typing import Optional

from rich.console import Console

from models.dataclass.results import FetchResult


class CLIFetchOutputAdapter:
    """Format and display fetch results for CLI using Rich."""

    def __init__(self, console: Optional[Console] = None):
        """Initialize CLI fetch output adapter.

        Args:
            console: Optional Rich console (creates new one if not provided)
        """
        self.console = console or Console()

    def display_fetch_result(self, result: FetchResult, symbol: str) -> None:
        """Display fetch result for asset info command.

        Args:
            result: Fetch operation result
            symbol: Asset symbol being fetched
        """
        if result.source == "cache":
            self.console.print(f"📋 Using cached data for {symbol}")
        elif result.is_new_data:
            self.console.print(f"✅ New data fetched for {symbol}")
        else:
            self.console.print(f"📋 No new data from provider for {symbol}")

        if not result.success and result.error:
            self.console.print(f"[red]❌ Error: {result.error}[/red]")
