"""CLI output adapter for fed command displays.

This adapter handles all federal reserve data-related formatted output for the CLI interface.
For web/JSON output, a different adapter would be injected via PresentationContext.
"""

from rich.console import Console
from rich.table import Table
from rich import box

from models.result.fed_result import FedUpdateResult, FedInfoResult


console = Console()


class CLIFedOutputAdapter:
    """Adapter for displaying fed data results in CLI format using Rich."""

    def display_fed_update_result(self, result: FedUpdateResult) -> None:
        """Display fed update results.

        Args:
            result: FedUpdateResult containing update statistics
        """
        # Show per-type results
        for data_type, stored_count in result.data_by_type.items():
            if stored_count > 0:
                console.print(f"[green]✓[/green] {data_type}: {stored_count} observations stored")
            else:
                console.print(f"[yellow]⚠️[/yellow]  {data_type}: No data fetched")

        # Show summary
        console.print()
        console.print(f"[green]✅ Fed data update complete: {result.total_stored} total observations stored ({result.elapsed_seconds:.2f}s)[/green]")

    def display_fed_info_result(self, result: FedInfoResult) -> None:
        """Display fed info results with recent observations.

        Args:
            result: FedInfoResult containing fed data sections
        """
        console.print()
        console.print("[bold cyan]📊 Federal Reserve Economic Data[/bold cyan]")
        console.print()

        for section in result.sections:
            if section.latest:
                console.print(f"[bold]{section.display_name}[/bold]")
                console.print(f"  Latest: {section.latest.display_value} (as of {section.latest.observation_date})")
                console.print()

                # Display recent history table
                if section.recent:
                    table = Table(box=box.SIMPLE, show_header=True)
                    table.add_column("Date", style="cyan", no_wrap=True)
                    table.add_column("Value", style="bold", justify="right")

                    for fed_data in section.recent:
                        table.add_row(
                            str(fed_data.observation_date),
                            fed_data.display_value
                        )

                    console.print(table)
                    console.print()
            else:
                console.print(f"[yellow]⚠️  {section.display_name}: No data available[/yellow]")
                console.print(f"[dim]   Run 'tradescout fed update' to fetch data[/dim]")
                console.print()
