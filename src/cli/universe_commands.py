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
def universe(config):
    """Manage asset universes for trading."""
    pass


@universe.command('list')
@pass_config
def universe_list(config):
    """List all available universes."""
    try:
        data_service = config.get_data_service()
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


@universe.command('info')
@click.argument('universe_name', required=False)
@pass_config
def universe_info(config, universe_name):
    """Show detailed information about a universe."""
    # Use active universe if not specified
    if not universe_name:
        universe_name = config.get_active_universe()

    try:
        data_service = config.get_data_service()

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


@universe.command('activate')
@click.argument('universe_name')
@pass_config
def universe_activate(config, universe_name):
    """Set a universe as the active trading universe."""
    if config.set_active_universe(universe_name):
        console.print(f"[green]✅ Activated universe: {universe_name}[/green]")

        # Show brief info about the activated universe
        data_service = config.get_data_service()
        stats = data_service.get_universe_stats(universe_name)
        count = stats.total_members if stats else 0
        console.print(f"[dim]This universe contains {count:,} assets[/dim]")
    else:
        console.print(f"[red]❌ Failed to activate universe '{universe_name}'[/red]")
        console.print("[yellow]Use 'tradescout universe list' to see available universes[/yellow]")
        sys.exit(1)


@universe.command('current')
@pass_config
def universe_current(config):
    """Show the currently active universe."""
    active = config.get_active_universe()
    console.print(f"Active universe: [bold cyan]{active}[/bold cyan]")


@universe.command('create')
@click.argument('name')
@click.option('--description', '-d', help='Description of the universe')
@click.option('--min-market-cap', type=int, help='Minimum market cap filter')
@click.option('--min-volume', type=int, help='Minimum volume filter')
@click.option('--max-assets', type=int, help='Maximum number of assets')
@pass_config
def universe_create(config, name, description, min_market_cap, min_volume, max_assets):
    """Create a new empty universe."""
    try:
        data_service = config.get_data_service()

        if data_service.create_universe(name, description, min_market_cap, min_volume, max_assets):
            console.print(f"[green]✅ Created universe: {name}[/green]")

            if description:
                console.print(f"[dim]{description}[/dim]")

            console.print("[yellow]Note: Universe created empty. Use 'tradescout database bootstrap-universes' to populate it.[/yellow]")
        else:
            console.print(f"[red]Universe '{name}' already exists[/red]")
            sys.exit(1)

    except Exception as e:
        console.print(f"[red]❌ Failed to create universe: {e}[/red]")
        sys.exit(1)


@universe.command('delete')
@click.argument('name')
@click.option('--force', '-f', is_flag=True, help='Skip confirmation')
@pass_config
def universe_delete(config, name, force):
    """Delete a universe and all its memberships."""
    if name == "default_universe":
        console.print("[red]❌ Cannot delete default_universe[/red]")
        sys.exit(1)

    if name == config.get_active_universe():
        console.print("[red]❌ Cannot delete the currently active universe[/red]")
        console.print("[yellow]Activate a different universe first[/yellow]")
        sys.exit(1)

    try:
        data_service = config.get_data_service()

        # Get current member count for confirmation
        stats = data_service.get_universe_stats(name)
        if not stats:
            console.print(f"[red]Universe '{name}' not found[/red]")
            sys.exit(1)

        member_count = stats.total_members

        # Confirm deletion
        if not force:
            console.print(f"[yellow]⚠️  This will delete universe '{name}' and {member_count:,} memberships[/yellow]")
            if not click.confirm("Are you sure?"):
                console.print("Deletion cancelled")
                return

        # Delete the universe
        success, deleted_count = data_service.delete_universe(name)
        if success:
            console.print(f"[green]✅ Deleted universe '{name}' and {deleted_count:,} memberships[/green]")
        else:
            console.print(f"[red]❌ Failed to delete universe '{name}'[/red]")
            sys.exit(1)

    except Exception as e:
        console.print(f"[red]❌ Failed to delete universe: {e}[/red]")
        sys.exit(1)