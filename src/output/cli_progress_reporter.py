"""CLI progress reporter using Rich formatting.

Provides CLIProgressReporter for progress bars during long-running operations.
Result display is handled by domain-specific adapters (bootstrap, news, screener, market, etc.).
"""

from typing import Optional

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)


class CLIProgressReporter:
    """Rich-based progress reporter for CLI operations.

    Displays progress bars with spinners, percentages, and elapsed time.
    """

    def __init__(self, console: Optional[Console] = None):
        """Initialize CLI progress reporter.

        Args:
            console: Optional Rich console (creates new one if not provided)
        """
        self.console = console or Console()
        self.progress: Optional[Progress] = None
        self.task_id = None

    def start_operation(self, operation: str, total: int) -> None:
        """Start progress bar for operation.

        Args:
            operation: Operation description
            total: Total items to process
        """
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("•"),
            TextColumn("{task.completed}/{task.total}"),
            TextColumn("•"),
            TimeElapsedColumn(),
            console=self.console,
        )
        self.progress.start()
        self.task_id = self.progress.add_task(operation, total=total)

    def update_progress(self, current: int, message: str = "") -> None:
        """Update progress bar.

        Args:
            current: Current item number (absolute, not increment)
            message: Optional message (not currently displayed)
        """
        if self.progress and self.task_id is not None:
            self.progress.update(self.task_id, completed=current)

    def complete_operation(self, success: bool, message: str = "") -> None:
        """Complete and stop progress bar.

        Args:
            success: Whether operation succeeded
            message: Optional completion message (displayed after progress bar)
        """
        if self.progress:
            self.progress.stop()
            self.progress = None
            self.task_id = None

        if message:
            if success:
                self.console.print(f"[green]✓[/green] {message}")
            else:
                self.console.print(f"[red]✗[/red] {message}")
