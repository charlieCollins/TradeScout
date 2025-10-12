"""Progress reporting protocol for long-running operations.

This protocol allows DataService to report progress without knowing the output format.
Different implementations can provide CLI progress bars, web socket updates, log entries, etc.
"""

from typing import Protocol


class ProgressReporter(Protocol):
    """Protocol for progress reporting (CLI, Web sockets, logs, etc.).

    Example implementations:
    - CLIProgressReporter: Rich progress bars for terminal
    - WebSocketProgressReporter: Real-time updates to web UI
    - LogProgressReporter: Log file entries
    - SilentProgressReporter: No-op for batch jobs
    """

    def start_operation(self, operation: str, total: int) -> None:
        """Called when operation starts.

        Args:
            operation: Operation name/description (e.g., "Fetching fundamentals")
            total: Total number of items to process
        """
        ...

    def update_progress(self, current: int, message: str = "") -> None:
        """Called as operation progresses.

        Args:
            current: Current item number (1-based)
            message: Optional progress message
        """
        ...

    def complete_operation(self, success: bool, message: str = "") -> None:
        """Called when operation completes.

        Args:
            success: Whether operation completed successfully
            message: Optional completion message
        """
        ...
