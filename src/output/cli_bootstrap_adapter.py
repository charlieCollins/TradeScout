"""CLI output adapter for bootstrap results using Rich formatting.

Formats bootstrap operation results for terminal display with Rich tables and styling.
"""

from typing import Optional

from rich.console import Console

from models.result.bootstrap_result import BootstrapResult


class CLIBootstrapOutputAdapter:
    """Format and display bootstrap results for CLI using Rich."""

    def __init__(self, console: Optional[Console] = None):
        """Initialize CLI bootstrap output adapter.

        Args:
            console: Optional Rich console (creates new one if not provided)
        """
        self.console = console or Console()

    def display_bootstrap_result(self, result: BootstrapResult) -> None:
        """Display bootstrap result with Rich formatting.

        Args:
            result: Bootstrap operation result
        """
        # Display summary
        self.console.print(
            f"\n[bold green]✅ {result.operation.title()} Bootstrap Complete[/]"
        )

        # Show delta information if available (new, updated, deprecated)
        if result.new_items > 0 or result.updated_items > 0 or result.deprecated_items > 0:
            self.console.print(f"  • Total from API: {result.total_items:,}")
            self.console.print(f"  • New: {result.new_items:,}")
            self.console.print(f"  • Updated: {result.updated_items:,}")
            if result.deprecated_items > 0:
                self.console.print(
                    f"  • [yellow]Deprecated (in DB but not in API): {result.deprecated_items:,}[/]"
                )
        # Show fetch/insert breakdown if both phases exist
        elif result.fetch_errors or result.insert_errors:
            # Two-phase operation (fetch + insert)
            fetch_count = result.total_items - len(result.fetch_errors)
            self.console.print(
                f"  • API Fetches: {fetch_count}/{result.total_items} succeeded"
            )
            self.console.print(
                f"  • Database Inserts: {result.successful}/{fetch_count} succeeded"
            )
        else:
            # Single-phase operation
            self.console.print(f"  • Total: {result.total_items}")
            self.console.print(f"  • Successful: {result.successful}")
            self.console.print(f"  • Failed: {result.failed}")

        self.console.print(f"  • Total Errors: {result.total_errors}")

        # Display cache statistics if available (fundamentals bootstrap)
        if result.from_database > 0 or result.from_cache > 0 or result.from_api > 0:
            self.console.print(f"\n[cyan]Data Sources:[/cyan]")
            self.console.print(f"  • From database (fresh): {result.from_database:,}")
            self.console.print(f"  • From cache files: {result.from_cache:,}")
            self.console.print(f"  • From Polygon API: {result.from_api:,}")
            self.console.print(f"  • Cache hit rate: {result.cache_hit_rate:.1f}%")

        # Display fetch errors if any
        if result.fetch_errors:
            self.console.print(
                f"\n[yellow]⚠️  API Fetch Errors ({len(result.fetch_errors)}):[/]"
            )
            for error in result.fetch_errors[:10]:
                self.console.print(f"  • {error}")
            if len(result.fetch_errors) > 10:
                self.console.print(
                    f"  • ... and {len(result.fetch_errors) - 10} more"
                )

        # Display insert errors if any
        if result.insert_errors:
            self.console.print(
                f"\n[yellow]⚠️  Database Insert Errors ({len(result.insert_errors)}):[/]"
            )
            for error in result.insert_errors[:10]:
                self.console.print(f"  • {error}")
            if len(result.insert_errors) > 10:
                self.console.print(
                    f"  • ... and {len(result.insert_errors) - 10} more"
                )
