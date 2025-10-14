"""Universe management commands for TradeScout."""

import sys
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich import box

from .main import pass_config

console = Console()


@click.group()
@pass_config
def universes(app_context):
    """Manage asset universes for trading."""
    pass


@universes.command('list')
@pass_config
def universe_list(app_context):
    """List all available universes."""
    try:
        data_service = app_context.get_data_service_v2()
        universes_list = data_service.get_all_universes()

        if not universes_list:
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

        for universe in universes_list:
            # Get asset count for this universe
            stats = data_service.get_universe_stats(universe.name)
            asset_count = stats.total_members if stats else 0

            # Mark the active universe
            if universe.is_active:
                name_display = f"➤ {universe.name}"
                status = "[green]ACTIVE[/green]"
            else:
                name_display = f"  {universe.name}"
                status = ""

            table.add_row(
                name_display,
                universe.description or "",
                f"{asset_count:,}",
                status
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]❌ Failed to list universes: {e}[/red]")
        sys.exit(1)


@universes.command('info')
@click.argument('universe_name', required=False)
@pass_config
def universe_info(app_context, universe_name):
    """Show detailed information about a universe."""
    # Use active universe if not specified
    if not universe_name:
        universe_name = app_context.get_active_universe()

    try:
        data_service = app_context.get_data_service_v2()

        # Get universe details
        universes_list = data_service.get_all_universes()
        universe = next((u for u in universes_list if u.name == universe_name), None)

        if not universe:
            console.print(f"[red]Universe '{universe_name}' not found[/red]")
            return

        # Get universe statistics
        stats = data_service.get_universe_stats(universe_name)
        if not stats:
            console.print(f"[red]Unable to get stats for universe '{universe_name}'[/red]")
            return

        # Display information
        console.print(f"\n[bold]Universe: {universe.name}[/bold]")
        if universe.is_active:
            console.print("[green]➤ Currently Active[/green]")

        if universe.description:
            console.print(f"[dim]{universe.description}[/dim]")

        # Basic info table
        info_table = Table(box=box.ROUNDED, show_header=False)
        info_table.add_column("Property", style="cyan")
        info_table.add_column("Value", style="white")

        info_table.add_row("Status", "✅ Active" if universe.is_active else "❌ Inactive")
        info_table.add_row("Total Assets", f"{stats.total_members:,}")
        info_table.add_row("Active Assets", f"{stats.active_members:,}")
        info_table.add_row("Inactive Assets", f"{stats.inactive_members:,}")

        if universe.min_market_cap:
            info_table.add_row("Min Market Cap", f"${universe.min_market_cap:,}")
        if universe.min_volume:
            info_table.add_row("Min Volume", f"{universe.min_volume:,}")
        if universe.max_assets:
            info_table.add_row("Max Assets", f"{universe.max_assets:,}")

        info_table.add_row("Created", universe.created_at.strftime("%Y-%m-%d %H:%M:%S"))
        info_table.add_row("Updated", universe.updated_at.strftime("%Y-%m-%d %H:%M:%S") if universe.updated_at else "Never")

        console.print(info_table)

        # Market breakdown
        if stats.by_market:
            console.print("\n[bold]Market Distribution:[/bold]")
            market_table = Table(box=box.SIMPLE, show_header=True)
            market_table.add_column("Market", style="cyan")
            market_table.add_column("Assets", justify="right", style="white")
            market_table.add_column("Percentage", justify="right", style="white")

            for market_name, count in stats.by_market.items():
                pct = (count / stats.total_members * 100) if stats.total_members > 0 else 0
                market_table.add_row(market_name, f"{count:,}", f"{pct:.1f}%")

            console.print(market_table)

        # Asset type breakdown
        if stats.by_asset_type:
            console.print("\n[bold]Asset Type Distribution:[/bold]")
            type_table = Table(box=box.SIMPLE, show_header=True)
            type_table.add_column("Type", style="cyan")
            type_table.add_column("Assets", justify="right", style="white")
            type_table.add_column("Percentage", justify="right", style="white")

            for asset_type, count in stats.by_asset_type.items():
                pct = (count / stats.total_members * 100) if stats.total_members > 0 else 0
                type_table.add_row(asset_type, f"{count:,}", f"{pct:.1f}%")

            console.print(type_table)

    except Exception as e:
        console.print(f"[red]❌ Failed to get universe info: {e}[/red]")
        sys.exit(1)


@universes.command('activate')
@click.argument('universe_name')
@pass_config
def universe_activate(app_context, universe_name):
    """Set a universe as the active trading universe."""
    if app_context.set_active_universe(universe_name):
        console.print(f"[green]✅ Activated universe: {universe_name}[/green]")

        # Show brief info about the activated universe
        data_service = app_context.get_data_service_v2()
        stats = data_service.get_universe_stats(universe_name)
        count = stats.total_members if stats else 0
        console.print(f"[dim]This universe contains {count:,} assets[/dim]")
    else:
        console.print(f"[red]❌ Failed to activate universe '{universe_name}'[/red]")
        console.print("[yellow]Use 'tradescout universes list' to see available universes[/yellow]")
        sys.exit(1)


@universes.command('current')
@pass_config
def universe_current(app_context):
    """Show the currently active universe."""
    active = app_context.get_active_universe()
    console.print(f"Active universe: [bold cyan]{active}[/bold cyan]")


