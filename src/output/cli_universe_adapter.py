"""CLI output adapter for universe command displays.

This adapter handles all universe-related formatted output for the CLI interface.
For web/JSON output, a different adapter would be injected via PresentationContext.
"""

from rich.console import Console
from rich.table import Table
from rich import box

from models.result.universe_result import UniverseListResult, UniverseInfoResult


console = Console()


class CLIUniverseOutputAdapter:
    """Adapter for displaying universe results in CLI format using Rich."""

    def display_universe_list(self, result: UniverseListResult) -> None:
        """Display list of all universes.

        Args:
            result: UniverseListResult containing list of universes
        """
        if not result.universes:
            console.print("[yellow]No universes found[/yellow]")
            return

        # Display table
        table = Table(
            title="📊 Available Universes",
            box=box.ROUNDED,
            header_style="bold blue"
        )
        table.add_column("Universe", style="cyan")
        table.add_column("Description", style="white")
        table.add_column("Assets", justify="right", style="white")
        table.add_column("Status", style="white")

        for item in result.universes:
            # Mark the active universe
            if item.universe.is_active:
                name_display = f"➤ {item.universe.name}"
                status = "[green]ACTIVE[/green]"
            else:
                name_display = f"  {item.universe.name}"
                status = ""

            table.add_row(
                name_display,
                item.universe.description or "",
                f"{item.asset_count:,}",
                status
            )

        console.print(table)

    def display_universe_info(self, result: UniverseInfoResult) -> None:
        """Display detailed information about a universe.

        Args:
            result: UniverseInfoResult containing universe details
        """
        # Display header
        console.print(f"\n[bold]Universe: {result.universe.name}[/bold]")
        if result.universe.is_active:
            console.print("[green]➤ Currently Active[/green]")

        if result.universe.description:
            console.print(f"[dim]{result.universe.description}[/dim]")

        # Basic info table
        info_table = Table(box=box.ROUNDED, show_header=False)
        info_table.add_column("Property", style="cyan")
        info_table.add_column("Value", style="white")

        info_table.add_row("Status", "✅ Active" if result.universe.is_active else "❌ Inactive")
        info_table.add_row("Total Assets", f"{result.stats.total_members:,}")
        info_table.add_row("Active Assets", f"{result.stats.active_members:,}")
        info_table.add_row("Inactive Assets", f"{result.stats.inactive_members:,}")

        if result.universe.min_market_cap:
            info_table.add_row("Min Market Cap", f"${result.universe.min_market_cap:,}")
        if result.universe.min_volume:
            info_table.add_row("Min Volume", f"{result.universe.min_volume:,}")
        if result.universe.max_assets:
            info_table.add_row("Max Assets", f"{result.universe.max_assets:,}")

        info_table.add_row("Created", result.universe.created_at.strftime("%Y-%m-%d %H:%M:%S"))
        info_table.add_row("Updated", result.universe.updated_at.strftime("%Y-%m-%d %H:%M:%S") if result.universe.updated_at else "Never")

        console.print(info_table)

        # Market breakdown
        if result.stats.by_market:
            console.print("\n[bold]Market Distribution:[/bold]")
            market_table = Table(box=box.SIMPLE, show_header=True)
            market_table.add_column("Market", style="cyan")
            market_table.add_column("Assets", justify="right", style="white")
            market_table.add_column("Percentage", justify="right", style="white")

            for market_name, count in result.stats.by_market.items():
                pct = (count / result.stats.total_members * 100) if result.stats.total_members > 0 else 0
                market_table.add_row(market_name, f"{count:,}", f"{pct:.1f}%")

            console.print(market_table)

        # Asset type breakdown
        if result.stats.by_asset_type:
            console.print("\n[bold]Asset Type Distribution:[/bold]")
            type_table = Table(box=box.SIMPLE, show_header=True)
            type_table.add_column("Type", style="cyan")
            type_table.add_column("Assets", justify="right", style="white")
            type_table.add_column("Percentage", justify="right", style="white")

            for asset_type, count in result.stats.by_asset_type.items():
                pct = (count / result.stats.total_members * 100) if result.stats.total_members > 0 else 0
                type_table.add_row(asset_type, f"{count:,}", f"{pct:.1f}%")

            console.print(type_table)

    def display_universe_not_found(self, universe_name: str) -> None:
        """Display message when universe is not found.

        Args:
            universe_name: Name of universe that wasn't found
        """
        console.print(f"[red]Universe '{universe_name}' not found[/red]")
