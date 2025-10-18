"""CLI output adapter for database results using Rich formatting.

Formats database operation results for terminal display with Rich tables and styling.
"""

from typing import Optional

from rich.console import Console
from rich.table import Table

from models.result.database_result import DatabaseStats


class CLIDatabaseOutputAdapter:
    """Format and display database results for CLI using Rich."""

    def __init__(self, console: Optional[Console] = None):
        """Initialize CLI database output adapter.

        Args:
            console: Optional Rich console (creates new one if not provided)
        """
        self.console = console or Console()

    def display_database_stats(self, result: DatabaseStats):
        """Display database statistics.

        Args:
            result: DatabaseStats containing database information
        """
        # Create main info table
        info_table = Table(title="Database Information", show_header=True)
        info_table.add_column("Property", style="cyan")
        info_table.add_column("Value", style="white")

        info_table.add_row("Path", result.database_path)

        # Status with color
        if result.is_healthy:
            status_str = f"[green]{result.status}[/green]"
        else:
            status_str = f"[red]{result.status}[/red]"
        info_table.add_row("Status", status_str)

        if result.error_message:
            info_table.add_row("Error", f"[red]{result.error_message}[/red]")

        self.console.print(info_table)

        # Create table statistics table
        if result.table_counts:
            stats_table = Table(title="\nTable Statistics", show_header=True)
            stats_table.add_column("Table", style="cyan")
            stats_table.add_column("Records", justify="right", style="white")

            for table_name, count in sorted(result.table_counts.items()):
                stats_table.add_row(table_name, f"{count:,}")

            self.console.print(stats_table)

            # Show total
            if result.total_records > 0:
                self.console.print(f"\n[bold]Total records:[/bold] {result.total_records:,}")

        # Show last updated time
        if result.last_updated:
            from datetime import datetime
            age = datetime.now() - result.last_updated
            if age.total_seconds() < 3600:
                age_str = f"{age.total_seconds() / 60:.0f} minutes ago"
            elif age.total_seconds() < 86400:
                age_str = f"{age.total_seconds() / 3600:.1f} hours ago"
            else:
                age_str = f"{age.total_seconds() / 86400:.1f} days ago"

            self.console.print(f"[dim]Last updated: {age_str}[/dim]")
