#!/usr/bin/env python3
"""
Universe Management CLI

Commands to manage asset universe in the database.
"""

import click
from rich.console import Console
from rich.table import Table
from rich import box
from ..storage.asset_universe_manager import AssetUniverseManager
import logging

console = Console()
logger = logging.getLogger(__name__)


@click.group()
def universe():
    """Manage asset universe database"""
    pass


@universe.command()
@click.argument('universe_name')
@click.option('--limit', default=50, help='Number of symbols to show')
def list(universe_name: str, limit: int):
    """List symbols in a universe"""
    manager = AssetUniverseManager()
    
    try:
        symbols = manager.get_universe_symbols(universe_name)
        
        if not symbols:
            console.print(f"[yellow]No symbols found in universe '{universe_name}'[/yellow]")
            return
        
        # Create table
        table = Table(
            title=f"Universe: {universe_name} ({len(symbols)} symbols)",
            box=box.ROUNDED
        )
        table.add_column("Index", justify="right", style="dim")
        table.add_column("Symbol", style="cyan")
        
        # Show limited symbols
        for i, symbol in enumerate(symbols[:limit], 1):
            table.add_row(str(i), symbol)
        
        if len(symbols) > limit:
            table.add_row("...", f"[dim]({len(symbols) - limit} more)[/dim]")
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@universe.command()
def show():
    """Show all universes"""
    manager = AssetUniverseManager()
    conn = manager._get_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT u.name, u.description, 
                   COUNT(DISTINCT um.asset_id) as asset_count,
                   u.min_market_cap_millions, u.min_avg_volume
            FROM universes u
            LEFT JOIN universe_membership um ON u.name = um.universe_name AND um.is_active = 1
            WHERE u.is_active = 1
            GROUP BY u.name
            ORDER BY asset_count DESC
        """)
        
        universes = cursor.fetchall()
        
        # Create table
        table = Table(title="Asset Universes", box=box.ROUNDED)
        table.add_column("Universe", style="cyan")
        table.add_column("Assets", justify="right")
        table.add_column("Min Market Cap", justify="right")
        table.add_column("Min Volume", justify="right")
        table.add_column("Description", max_width=40)
        
        for univ in universes:
            market_cap = f"${univ['min_market_cap_millions']:.0f}M" if univ['min_market_cap_millions'] else "-"
            volume = f"{univ['min_avg_volume']:,.0f}" if univ['min_avg_volume'] else "-"
            
            table.add_row(
                univ['name'],
                str(univ['asset_count']),
                market_cap,
                volume,
                univ['description'] or ""
            )
        
        console.print(table)
        
    finally:
        conn.close()


@universe.command()
@click.argument('symbol')
@click.argument('universe_name')
@click.option('--reason', help='Reason for adding')
def add(symbol: str, universe_name: str, reason: str):
    """Add a symbol to a universe"""
    manager = AssetUniverseManager()
    
    try:
        if manager.add_to_universe(symbol, universe_name, reason):
            console.print(f"[green]✅ Added {symbol} to {universe_name}[/green]")
        else:
            console.print(f"[red]Failed to add {symbol} to {universe_name}[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@universe.command()
@click.argument('symbol')
@click.argument('universe_name')
@click.option('--reason', help='Reason for removal')
def remove(symbol: str, universe_name: str, reason: str):
    """Remove a symbol from a universe"""
    manager = AssetUniverseManager()
    
    try:
        if manager.remove_from_universe(symbol, universe_name, reason):
            console.print(f"[green]✅ Removed {symbol} from {universe_name}[/green]")
        else:
            console.print(f"[red]Failed to remove {symbol} from {universe_name}[/red]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@universe.command()
@click.argument('symbol')
def info(symbol: str):
    """Show information about an asset"""
    manager = AssetUniverseManager()
    
    try:
        asset = manager.get_asset(symbol)
        
        if not asset:
            console.print(f"[yellow]Asset {symbol} not found[/yellow]")
            return
        
        # Get performance stats
        performance = manager.get_asset_performance(symbol)
        
        # Create info panel
        from rich.panel import Panel
        from rich.text import Text
        
        info_text = Text()
        info_text.append(f"Symbol: ", style="bold")
        info_text.append(f"{asset['symbol']}\n", style="cyan")
        
        if asset['name']:
            info_text.append(f"Name: ", style="bold")
            info_text.append(f"{asset['name']}\n")
        
        if asset['exchange']:
            info_text.append(f"Exchange: ", style="bold")
            info_text.append(f"{asset['exchange']}\n")
        
        if asset['sector']:
            info_text.append(f"Sector: ", style="bold")
            info_text.append(f"{asset['sector']}\n")
        
        if performance:
            info_text.append(f"\nPerformance:\n", style="bold yellow")
            info_text.append(f"  Total Gaps: {performance.get('total_gaps', 0)}\n")
            info_text.append(f"  Gaps Filled: {performance.get('gaps_filled', 0)}\n")
            if performance.get('avg_gap_size'):
                info_text.append(f"  Avg Gap Size: {performance['avg_gap_size']:.2f}%\n")
            if performance.get('avg_volume'):
                info_text.append(f"  Avg Volume: {performance['avg_volume']:,.0f}\n")
        
        panel = Panel(info_text, title=f"Asset Information: {symbol}", border_style="cyan")
        console.print(panel)
        
        # Show universe memberships
        conn = manager._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT universe_name, added_date, is_active
            FROM universe_membership
            WHERE asset_id = ?
            ORDER BY is_active DESC, universe_name
        """, (asset['id'],))
        
        memberships = cursor.fetchall()
        conn.close()
        
        if memberships:
            table = Table(title="Universe Memberships", box=box.ROUNDED)
            table.add_column("Universe", style="cyan")
            table.add_column("Added Date")
            table.add_column("Status")
            
            for m in memberships:
                status = "[green]Active[/green]" if m['is_active'] else "[dim]Inactive[/dim]"
                table.add_row(m['universe_name'], str(m['added_date']), status)
            
            console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


@universe.command()
@click.argument('symbol')
def gaps(symbol: str):
    """Show gap history for a symbol"""
    manager = AssetUniverseManager()
    
    try:
        gap_history = manager.get_gap_history(symbol, days_back=90)
        
        if not gap_history:
            console.print(f"[yellow]No gap history found for {symbol}[/yellow]")
            return
        
        # Create table
        table = Table(title=f"Gap History: {symbol}", box=box.ROUNDED)
        table.add_column("Date")
        table.add_column("Type", justify="center")
        table.add_column("Size", justify="right")
        table.add_column("Previous Close", justify="right")
        table.add_column("Open", justify="right")
        table.add_column("Filled", justify="center")
        
        for gap in gap_history:
            gap_type_color = "green" if gap['gap_type'] == 'up' else "red"
            filled_status = "✓" if gap['filled'] else "-"
            
            table.add_row(
                str(gap['gap_date']),
                f"[{gap_type_color}]{gap['gap_type'].upper()}[/{gap_type_color}]",
                f"{gap['gap_size_percent']:.2f}%",
                f"${gap['previous_close']:.2f}" if gap['previous_close'] else "-",
                f"${gap['open_price']:.2f}" if gap['open_price'] else "-",
                filled_status
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")


if __name__ == "__main__":
    universe()