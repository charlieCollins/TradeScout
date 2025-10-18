"""CLI output adapter for update results using Rich formatting.

Formats update operation results for terminal display with Rich styling.
"""

from typing import Optional

from rich.console import Console

from models.dataclass.results import UpdateResult


class CLIUpdateOutputAdapter:
    """Format and display update results for CLI using Rich."""

    def __init__(self, console: Optional[Console] = None):
        """Initialize CLI update output adapter.

        Args:
            console: Optional Rich console (creates new one if not provided)
        """
        self.console = console or Console()

    def display_update_result(self, result: UpdateResult) -> None:
        """Display update result for bulk operations.

        Args:
            result: Update operation result
        """
        self.console.print(
            f"\n[bold green]✅ {result.operation.title()} Complete[/]"
        )
        self.console.print(f"  • New Records: {result.new_records}")
        self.console.print(f"  • Duplicate Records: {result.duplicate_records}")

        if result.updated_records > 0:
            self.console.print(f"  • Updated Records: {result.updated_records}")

        if result.errors:
            self.console.print(f"\n[yellow]⚠️  Errors ({len(result.errors)}):[/]")
            for error in result.errors[:10]:
                self.console.print(f"  • {error}")
            if len(result.errors) > 10:
                self.console.print(f"  • ... and {len(result.errors) - 10} more")
