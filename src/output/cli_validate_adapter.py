"""CLI output adapter for validate command displays.

This adapter handles all validation-related formatted output for the CLI interface.
For web/JSON output, a different adapter would be injected via PresentationContext.
"""

from rich.console import Console
from rich.table import Table

from models.dataclass.validate_result import VolumeValidationResult


console = Console()


class CLIValidateOutputAdapter:
    """Adapter for displaying validation results in CLI format using Rich."""

    def display_volume_validation_result(self, result: VolumeValidationResult) -> None:
        """Display volume validation results.

        Args:
            result: VolumeValidationResult containing validation data
        """
        # Display session info
        console.print(f"\n[bold]📊 Volume Validation - {result.session.upper()} Session[/bold]")
        console.print(f"Trading Date: {result.trading_date}")
        console.print(f"Extended Hours: {result.is_extended_hours}\n")

        # Build results table
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Symbol", style="bold")
        table.add_column("Snap Vol", justify="right")

        if result.is_extended_hours:
            table.add_column("Snap Time", justify="right")
            table.add_column("Agg Vol", justify="right")
            table.add_column("Agg Time", justify="right")
            table.add_column("Diff %", justify="right")
            table.add_column("Status")

        # Add rows
        for row in result.rows:
            # Format snapshot volume
            snap_vol_display = f"{row.snapshot_volume:,}" if row.snapshot_volume is not None else "N/A"

            # For regular/closed sessions (no extended hours columns)
            if not result.is_extended_hours:
                table.add_row(row.symbol, snap_vol_display)
                continue

            # For extended hours sessions (with comparison columns)
            snap_time_display = row.snapshot_time.strftime("%H:%M:%S") if row.snapshot_time else "N/A"
            agg_vol_display = f"{row.aggregates_volume:,}" if row.aggregates_volume is not None else "N/A"
            agg_time_display = row.aggregates_time.strftime("%H:%M:%S") if row.aggregates_time else "N/A"

            # Format difference percentage
            if row.diff_percent is not None:
                diff_pct_display = f"{row.diff_percent:+.1f}%"
            else:
                diff_pct_display = "N/A"

            # Format status with color
            if row.status == "good":
                status_display = "[green]✅ Good[/green]"
            elif row.status == "ok":
                status_display = "[yellow]⚠️ OK[/yellow]"
            elif row.status == "high":
                status_display = "[red]❌ High[/red]"
            elif row.status == "snap_na":
                status_display = "[yellow]⚠️ Snap N/A[/yellow]"
            else:
                status_display = "N/A"

            table.add_row(
                row.symbol,
                snap_vol_display,
                snap_time_display,
                agg_vol_display,
                agg_time_display,
                diff_pct_display,
                status_display,
            )

        console.print(table)

        # Summary
        console.print("\n[bold]Legend:[/bold]")
        console.print("  [green]✅ Good[/green]  - Within ±25% (acceptable for screening)")
        console.print("  [yellow]⚠️ OK[/yellow]    - Within ±50% (monitor)")
        console.print("  [red]❌ High[/red]  - Over ±50% (investigate)")

        # Session-specific notes
        if result.session == "premarket":
            console.print(
                f"\n[dim]Note: Premarket uses snapshot (min.av) for screening, "
                "Aggregates API for final validation.[/dim]"
            )
        elif result.session == "afterhours":
            console.print(
                f"\n[yellow]⚠️  Note: Snapshot volume NOT available for after-hours (min.av frozen at 4 PM).[/yellow]"
            )
            console.print(
                f"[dim]   After-hours MUST use Aggregates API for volume (no snapshot alternative).[/dim]"
            )
