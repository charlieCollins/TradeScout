#!/usr/bin/env python3
"""
TradeScout CLI Interface

Command-line interface for TradeScout market research assistant.
Provides commands for data collection, analysis, and market research.
"""

import click
import logging
import json
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import track
from rich import box

from ..storage.sqlite_repository import create_sqlite_database_manager
from ..data_models.domain_models_core import Asset, AssetType
from ..data_models.factories import MarketFactory
from ..config.local_config import DATABASE_CONFIG
from ..data_sources.smart_coordinator import create_smart_coordinator
from ..config.data_sources_manager import get_data_sources_manager
from ..market_wide import create_market_movers_provider

# Setup rich console for beautiful output
console = Console()
logger = logging.getLogger(__name__)


@click.group()
@click.version_option()
@click.option(
    "--db-path",
    default=None,
    help="Path to SQLite database file (default: from config)",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.pass_context
def main(ctx, db_path: Optional[str], verbose: bool):
    """
    TradeScout - Personal Market Research Assistant

    Analyze overnight market activity and generate trade suggestions.
    """
    # Setup logging
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Initialize database manager
    if db_path:
        db_manager = create_sqlite_database_manager(db_path)
    else:
        default_path = DATABASE_CONFIG["path"]
        db_manager = create_sqlite_database_manager(str(default_path))

    # Initialize database if needed
    if not db_manager.initialize_database():
        console.print("[red]❌ Failed to initialize database[/red]")
        ctx.exit(1)

    # Create smart coordinator
    try:
        coordinator = create_smart_coordinator()
        provider_count = len(coordinator._provider_instances)
        console.print(f"[green]✅ Initialized Smart Coordinator with {provider_count} data providers[/green]")
        
        # Show provider status if verbose
        if verbose:
            data_manager = get_data_sources_manager()
            status = data_manager.get_provider_status()
            console.print(f"[dim]Available providers: {status['summary']['available']}/{status['summary']['total_configured']}[/dim]")
            console.print(f"[dim]Data types configured: {len(coordinator.get_available_data_types())}[/dim]")
    except Exception as e:
        console.print(f"[red]❌ Failed to initialize Smart Coordinator: {e}[/red]")
        ctx.exit(1)

    # Store in context for subcommands
    ctx.ensure_object(dict)
    ctx.obj["db_manager"] = db_manager
    ctx.obj["coordinator"] = coordinator
    ctx.obj["verbose"] = verbose


@main.command()
@click.argument("symbols", nargs=-1, required=True)
@click.option("--save", is_flag=True, help="Save quotes to database")
@click.pass_context
def quote(ctx, symbols: tuple, save: bool):
    """
    Get current market quotes for one or more symbols.

    Examples:
        tradescout quote AAPL
        tradescout quote AAPL MSFT GOOGL --save
    """
    db_manager = ctx.obj["db_manager"]
    coordinator = ctx.obj["coordinator"]

    console.print(f"[blue]📈 Getting quotes for: {', '.join(symbols)}[/blue]")

    # Create table for results
    table = Table(title="Market Quotes", box=box.ROUNDED)
    table.add_column("Symbol", style="cyan", no_wrap=True)
    table.add_column("Price", style="green", justify="right")
    table.add_column("Change", justify="right")
    table.add_column("Change %", justify="right")
    table.add_column("Volume", justify="right")
    table.add_column("Time", style="dim")

    nasdaq = MarketFactory().create_nasdaq_market()
    quotes_to_save = []

    for symbol in track(symbols, description="Fetching quotes..."):
        try:
            # Create asset
            asset = Asset(
                symbol=symbol.upper(),
                name=f"{symbol.upper()} Corp",
                asset_type=AssetType.COMMON_STOCK,
                market=nasdaq,
                currency="USD",
            )

            # Get quote using smart coordinator
            quote = coordinator.get_current_quote(asset.symbol)

            if quote:
                # Format data
                price = f"${quote.price_data.price:.2f}"
                change = f"${quote.price_change:.2f}" if quote.price_change else "N/A"
                change_pct = (
                    f"{quote.price_change_percent:.2f}%"
                    if quote.price_change_percent
                    else "N/A"
                )
                volume = (
                    f"{quote.price_data.volume:,}" if quote.price_data.volume else "0"
                )
                timestamp = quote.price_data.timestamp.strftime("%H:%M:%S")

                # Color change based on positive/negative
                if quote.price_change and quote.price_change > 0:
                    change = f"[green]+{change}[/green]"
                    change_pct = f"[green]+{change_pct}[/green]"
                elif quote.price_change and quote.price_change < 0:
                    change = f"[red]{change}[/red]"
                    change_pct = f"[red]{change_pct}[/red]"

                table.add_row(
                    symbol.upper(), price, change, change_pct, volume, timestamp
                )

                if save:
                    quotes_to_save.append(quote)
            else:
                table.add_row(
                    symbol.upper(), "[red]Error[/red]", "N/A", "N/A", "N/A", "N/A"
                )

        except Exception as e:
            logger.error(f"Error getting quote for {symbol}: {e}")
            table.add_row(
                symbol.upper(), "[red]Error[/red]", "N/A", "N/A", "N/A", "N/A"
            )

    console.print(table)

    # Save to database if requested
    if save and quotes_to_save:
        console.print(
            f"\n[blue]💾 Saving {len(quotes_to_save)} quotes to database...[/blue]"
        )
        saved_count = db_manager.quotes.bulk_save_quotes(quotes_to_save)
        console.print(f"[green]✅ Saved {saved_count} quotes successfully[/green]")


@main.command()
@click.argument("symbol")
@click.option("--days", "-d", default=7, help="Number of days to look back")
@click.pass_context
def history(ctx, symbol: str, days: int):
    """
    Show historical quotes for a symbol from the database.

    Example:
        tradescout history AAPL --days 7
    """
    db_manager = ctx.obj["db_manager"]

    console.print(
        f"[blue]📊 Historical quotes for {symbol.upper()} (last {days} days)[/blue]"
    )

    # Get historical quotes
    quotes = db_manager.quotes.get_historical_quotes(symbol.upper(), days)

    if not quotes:
        console.print(
            f"[yellow]⚠️  No historical data found for {symbol.upper()}[/yellow]"
        )
        return

    # Create table
    table = Table(title=f"{symbol.upper()} Historical Data", box=box.ROUNDED)
    table.add_column("Date", style="cyan")
    table.add_column("Time", style="dim")
    table.add_column("Price", style="green", justify="right")
    table.add_column("Volume", justify="right")
    table.add_column("Change %", justify="right")

    for quote in sorted(quotes, key=lambda q: q.price_data.timestamp, reverse=True):
        date = quote.price_data.timestamp.strftime("%Y-%m-%d")
        time = quote.price_data.timestamp.strftime("%H:%M:%S")
        price = f"${quote.price_data.price:.2f}"
        volume = f"{quote.price_data.volume:,}" if quote.price_data.volume else "0"

        change_pct = "N/A"
        if quote.price_change_percent:
            pct = f"{quote.price_change_percent:.2f}%"
            if quote.price_change_percent > 0:
                change_pct = f"[green]+{pct}[/green]"
            elif quote.price_change_percent < 0:
                change_pct = f"[red]{pct}[/red]"
            else:
                change_pct = pct

        table.add_row(date, time, price, volume, change_pct)

    console.print(table)


@main.command()
@click.option(
    "--min-volume-ratio", "-r", default=2.0, help="Minimum volume ratio (default: 2.0)"
)
@click.option(
    "--symbols",
    "-s",
    default="AAPL,MSFT,GOOGL,TSLA,NVDA,AMZN",
    help="Comma-separated symbols to scan",
)
@click.pass_context
def volume_leaders(ctx, min_volume_ratio: float, symbols: str):
    """
    Scan for stocks with unusual volume activity.

    Example:
        tradescout volume-leaders --min-volume-ratio 3.0
    """
    coordinator = ctx.obj["coordinator"]

    symbol_list = [s.strip().upper() for s in symbols.split(",")]
    console.print(
        f"[blue]🔍 Scanning for volume leaders (min ratio: {min_volume_ratio}x)[/blue]"
    )

    # Create assets
    nasdaq = MarketFactory().create_nasdaq_market()
    assets = []
    for symbol in symbol_list:
        assets.append(
            Asset(
                symbol=symbol,
                name=f"{symbol} Corp",
                asset_type=AssetType.COMMON_STOCK,
                market=nasdaq,
                currency="USD",
            )
        )

    # Scan for volume leaders using smart coordinator
    symbol_list = [asset.symbol for asset in assets]
    volume_leaders = coordinator.get_volume_leaders(symbol_list, min_volume_ratio=Decimal(str(min_volume_ratio)))

    if not volume_leaders:
        console.print("[yellow]⚠️  No volume leaders found[/yellow]")
        return

    # Create table
    table = Table(title="Volume Leaders", box=box.ROUNDED)
    table.add_column("Symbol", style="cyan", no_wrap=True)
    table.add_column("Price", style="green", justify="right")
    table.add_column("Volume", justify="right")
    table.add_column("Avg Volume", justify="right")
    table.add_column("Ratio", style="yellow", justify="right")
    table.add_column("Change %", justify="right")

    for quote in volume_leaders:
        symbol = quote.asset.symbol
        price = f"${quote.price_data.price:.2f}"
        volume = f"{quote.price_data.volume:,}"
        avg_volume = f"{quote.average_volume:,}" if quote.average_volume else "N/A"
        ratio = f"{quote.volume_ratio:.1f}x" if quote.volume_ratio else "N/A"

        change_pct = "N/A"
        if quote.price_change_percent:
            pct = f"{quote.price_change_percent:.2f}%"
            if quote.price_change_percent > 0:
                change_pct = f"[green]+{pct}[/green]"
            elif quote.price_change_percent < 0:
                change_pct = f"[red]{pct}[/red]"
            else:
                change_pct = pct

        table.add_row(symbol, price, volume, avg_volume, ratio, change_pct)

    console.print(table)


@main.command()
@click.argument("symbol")
@click.pass_context
def fundamentals(ctx, symbol: str):
    """
    Show fundamental data for a symbol.

    Example:
        tradescout fundamentals AAPL
    """
    coordinator = ctx.obj["coordinator"]

    console.print(f"[blue]📋 Fundamental data for {symbol.upper()}[/blue]")

    # Create asset
    nasdaq = MarketFactory().create_nasdaq_market()
    asset = Asset(
        symbol=symbol.upper(),
        name=f"{symbol.upper()} Corp",
        asset_type=AssetType.COMMON_STOCK,
        market=nasdaq,
        currency="USD",
    )

    # Get fundamentals using smart coordinator
    fundamentals_data = coordinator.get_company_fundamentals(asset.symbol)

    if not fundamentals_data:
        console.print(f"[red]❌ No fundamental data found for {symbol.upper()}[/red]")
        return

    # Create info panel
    info_text = []

    # Company info
    if fundamentals_data.get("company_name"):
        info_text.append(f"[bold]Company:[/bold] {fundamentals_data['company_name']}")
    if fundamentals_data.get("sector"):
        info_text.append(f"[bold]Sector:[/bold] {fundamentals_data['sector']}")
    if fundamentals_data.get("industry"):
        info_text.append(f"[bold]Industry:[/bold] {fundamentals_data['industry']}")

    # Financial metrics
    if fundamentals_data.get("market_cap"):
        market_cap = f"${fundamentals_data['market_cap']:,}"
        info_text.append(f"[bold]Market Cap:[/bold] {market_cap}")

    if fundamentals_data.get("pe_ratio"):
        info_text.append(f"[bold]P/E Ratio:[/bold] {fundamentals_data['pe_ratio']:.2f}")

    if fundamentals_data.get("price_to_book"):
        info_text.append(
            f"[bold]P/B Ratio:[/bold] {fundamentals_data['price_to_book']:.2f}"
        )

    if fundamentals_data.get("dividend_yield"):
        div_yield = f"{fundamentals_data['dividend_yield']*100:.2f}%"
        info_text.append(f"[bold]Dividend Yield:[/bold] {div_yield}")

    if fundamentals_data.get("beta"):
        info_text.append(f"[bold]Beta:[/bold] {fundamentals_data['beta']:.2f}")

    # 52-week range
    if fundamentals_data.get("52_week_high") and fundamentals_data.get("52_week_low"):
        high = fundamentals_data["52_week_high"]
        low = fundamentals_data["52_week_low"]
        info_text.append(f"[bold]52-Week Range:[/bold] ${low:.2f} - ${high:.2f}")

    if info_text:
        console.print(
            Panel(
                "\n".join(info_text),
                title=f"{symbol.upper()} Fundamentals",
                border_style="blue",
            )
        )
    else:
        console.print(
            f"[yellow]⚠️  Limited fundamental data available for {symbol.upper()}[/yellow]"
        )


@main.command()
@click.pass_context
def status(ctx):
    """
    Show TradeScout system status and database statistics.
    """
    db_manager = ctx.obj["db_manager"]
    coordinator = ctx.obj["coordinator"]

    console.print("[blue]📊 TradeScout System Status[/blue]")

    # Show provider status
    provider_status = coordinator.get_provider_status()
    
    provider_table = Table(title="Smart Coordinator - Data Providers", box=box.ROUNDED)
    provider_table.add_column("Provider", style="cyan")
    provider_table.add_column("Type", justify="center")
    provider_table.add_column("Priority", justify="center")
    provider_table.add_column("Quality", justify="center")
    provider_table.add_column("Rate Limit", justify="right")
    provider_table.add_column("Status", style="green")

    for provider_id, provider_info in provider_status["providers"].items():
        name = provider_info["name"]
        provider_type = provider_info["type"].title()
        priority = str(provider_info["priority"])
        quality = str(provider_info["quality_weight"])
        rate_limit = f"{provider_info['rate_limit_per_minute']}/min"
        
        # Format status with colors
        if provider_info["available"]:
            status_text = "[green]✅ Available[/green]"
        elif provider_info["temporarily_disabled"]:
            status_text = "[yellow]⚠️ Disabled[/yellow]"
        elif not provider_info["api_key_available"]:
            status_text = "[red]❌ No API Key[/red]"
        elif not provider_info["enabled"]:
            status_text = "[dim]⚪ Disabled[/dim]"
        else:
            status_text = "[red]❌ Error[/red]"
        
        provider_table.add_row(name, provider_type, priority, quality, rate_limit, status_text)

    console.print(provider_table)
    
    # Show data type configurations
    data_types_table = Table(title="Data Type Configurations", box=box.ROUNDED)
    data_types_table.add_column("Data Type", style="cyan")
    data_types_table.add_column("Strategy", justify="center")
    data_types_table.add_column("Providers", style="dim")
    data_types_table.add_column("Cache TTL", justify="right")
    
    data_manager = get_data_sources_manager()
    for data_type in sorted(coordinator.get_available_data_types())[:8]:  # Show first 8
        config = data_manager.get_data_type_config(data_type)
        if config:
            providers = data_manager.get_providers_for_data_type(data_type)
            provider_names = [p[0] for p in providers]
            
            strategy = config.fallback_strategy.value.replace('_', ' ').title()
            providers_str = ', '.join(provider_names) if provider_names else "None"
            
            # Format cache TTL
            if config.cache_ttl_minutes:
                cache_ttl = f"{config.cache_ttl_minutes}m"
            elif config.cache_ttl_hours:
                cache_ttl = f"{config.cache_ttl_hours}h"
            elif config.cache_ttl_days:
                cache_ttl = f"{config.cache_ttl_days}d"
            else:
                cache_ttl = "5m"
            
            data_types_table.add_row(
                data_type.replace('_', ' ').title(),
                strategy,
                providers_str,
                cache_ttl
            )
    
    console.print(data_types_table)
    console.print()

    # Get database stats
    stats = db_manager.get_database_stats()

    # Create status table
    table = Table(title="Database Statistics", box=box.ROUNDED)
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Database Path", stats.get("database_path", "N/A"))
    table.add_row("Database Size", f"{stats.get('database_size_bytes', 0):,} bytes")
    table.add_row("Total Quotes", str(stats.get("quotes_count", 0)))

    console.print(table)

    # Show recent activity
    try:
        # Get a sample of recent quotes
        recent_quotes = db_manager.execute_raw_query(
            """
            SELECT symbol, timestamp, price, volume 
            FROM quotes 
            ORDER BY timestamp DESC 
            LIMIT 5
        """
        )

        if recent_quotes:
            recent_table = Table(title="Recent Activity", box=box.ROUNDED)
            recent_table.add_column("Symbol", style="cyan")
            recent_table.add_column("Time", style="dim")
            recent_table.add_column("Price", style="green", justify="right")
            recent_table.add_column("Volume", justify="right")

            for quote in recent_quotes:
                timestamp = datetime.fromisoformat(quote["timestamp"])
                time_str = timestamp.strftime("%Y-%m-%d %H:%M:%S")
                price = f"${float(quote['price']):.2f}"
                volume = f"{quote['volume']:,}"

                recent_table.add_row(quote["symbol"], time_str, price, volume)

            console.print(recent_table)

    except Exception as e:
        logger.error(f"Error getting recent activity: {e}")


@main.command()
@click.option(
    "--days", "-d", default=90, help="Delete quotes older than N days (default: 90)"
)
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def cleanup(ctx, days: int, confirm: bool):
    """
    Clean up old data from the database.

    Example:
        tradescout cleanup --days 90 --confirm
    """
    db_manager = ctx.obj["db_manager"]

    if not confirm:
        if not click.confirm(f"Delete quotes older than {days} days?"):
            console.print("[yellow]❌ Cleanup cancelled[/yellow]")
            return

    console.print(f"[blue]🧹 Cleaning up data older than {days} days...[/blue]")

    # Perform cleanup
    deleted_count = db_manager.cleanup_old_data(days)

    if deleted_count > 0:
        console.print(f"[green]✅ Deleted {deleted_count} old records[/green]")
    else:
        console.print("[blue]ℹ️  No old data to clean up[/blue]")


@main.command()
@click.argument("backup_path")
@click.pass_context
def backup(ctx, backup_path: str):
    """
    Create a backup of the database.

    Example:
        tradescout backup backup/tradescout_2025-07-21.db
    """
    db_manager = ctx.obj["db_manager"]

    console.print(f"[blue]💾 Creating backup at: {backup_path}[/blue]")

    success = db_manager.backup_database(backup_path)

    if success:
        console.print(f"[green]✅ Backup created successfully[/green]")

        # Show backup info
        backup_size = Path(backup_path).stat().st_size
        console.print(f"[dim]Backup size: {backup_size:,} bytes[/dim]")
    else:
        console.print(f"[red]❌ Backup failed[/red]")


@main.command()
@click.option("--limit", default=10, help="Number of gainers to show (default: 10)")
@click.option("--force-refresh", "--force", is_flag=True, help="Force refresh cache")
@click.pass_context
def gainers(ctx, limit: int, force_refresh: bool):
    """
    Show top market gainers.
    
    Uses Alpha Vantage TOP_GAINERS_LOSERS API with 1-hour caching.
    Falls back to YFinance S&P 500 processing if Alpha Vantage unavailable.
    
    Example:
        tradescout gainers --limit 20
    """
    console.print("[green]🟢 Top Market Gainers[/green]")
    
    try:
        # Create market movers provider
        movers_provider = create_market_movers_provider()
        
        # Get gainers
        with console.status("[bold green]Fetching market gainers...", spinner="dots"):
            gainers_list = movers_provider.get_market_gainers(limit, force_refresh)
        
        if not gainers_list:
            console.print("[yellow]⚠️  No gainers data available[/yellow]")
            return
        
        # Create table
        table = Table(title=f"Top {len(gainers_list)} Market Gainers", box=box.ROUNDED)
        table.add_column("Rank", justify="center", style="dim", width=4)
        table.add_column("Symbol", style="cyan", no_wrap=True)
        table.add_column("Price", style="green", justify="right")
        table.add_column("Change", justify="right")
        table.add_column("Change %", justify="right", style="bold green")
        table.add_column("Volume", justify="right", style="dim")
        
        # Add rows
        for gainer in gainers_list:
            change_color = "green" if gainer.price_change >= 0 else "red"
            price_change_str = f"+{gainer.price_change:.2f}" if gainer.price_change >= 0 else f"{gainer.price_change:.2f}"
            
            table.add_row(
                str(gainer.rank),
                gainer.asset.symbol,
                f"${gainer.current_price:.2f}",
                f"[{change_color}]{price_change_str}[/{change_color}]",
                f"+{gainer.price_change_percent:.2f}%",
                f"{gainer.volume:,}" if gainer.volume > 0 else "N/A"
            )
        
        console.print(table)
        
        # Show cache status more prominently
        if force_refresh:
            console.print(f"[yellow]🔄 Fresh data retrieved (cache bypassed)[/yellow]")
        else:
            console.print(f"[blue]💾 Data cached for 1 hour. Use --force-refresh to get fresh data.[/blue]")
        
    except Exception as e:
        console.print(f"[red]❌ Error fetching gainers: {e}[/red]")


@main.command()
@click.option("--limit", default=10, help="Number of losers to show (default: 10)")
@click.option("--force-refresh", "--force", is_flag=True, help="Force refresh cache")
@click.pass_context  
def losers(ctx, limit: int, force_refresh: bool):
    """
    Show top market losers.
    
    Uses Alpha Vantage TOP_GAINERS_LOSERS API with 1-hour caching.
    Falls back to YFinance S&P 500 processing if Alpha Vantage unavailable.
    
    Example:
        tradescout losers --limit 20
    """
    console.print("[red]🔴 Top Market Losers[/red]")
    
    try:
        # Create market movers provider
        movers_provider = create_market_movers_provider()
        
        # Get losers
        with console.status("[bold red]Fetching market losers...", spinner="dots"):
            losers_list = movers_provider.get_market_losers(limit, force_refresh)
        
        if not losers_list:
            console.print("[yellow]⚠️  No losers data available[/yellow]")
            return
        
        # Create table
        table = Table(title=f"Top {len(losers_list)} Market Losers", box=box.ROUNDED)
        table.add_column("Rank", justify="center", style="dim", width=4)
        table.add_column("Symbol", style="cyan", no_wrap=True)
        table.add_column("Price", style="red", justify="right")
        table.add_column("Change", justify="right")
        table.add_column("Change %", justify="right", style="bold red")
        table.add_column("Volume", justify="right", style="dim")
        
        # Add rows
        for loser in losers_list:
            change_color = "green" if loser.price_change >= 0 else "red"
            price_change_str = f"+{loser.price_change:.2f}" if loser.price_change >= 0 else f"{loser.price_change:.2f}"
            
            table.add_row(
                str(loser.rank),
                loser.asset.symbol,
                f"${loser.current_price:.2f}",
                f"[{change_color}]{price_change_str}[/{change_color}]",
                f"{loser.price_change_percent:.2f}%",
                f"{loser.volume:,}" if loser.volume > 0 else "N/A"
            )
        
        console.print(table)
        
        # Show cache status more prominently
        if force_refresh:
            console.print(f"[yellow]🔄 Fresh data retrieved (cache bypassed)[/yellow]")
        else:
            console.print(f"[blue]💾 Data cached for 1 hour. Use --force-refresh to get fresh data.[/blue]")
        
    except Exception as e:
        console.print(f"[red]❌ Error fetching losers: {e}[/red]")


@main.command()
@click.option("--limit", default=10, help="Number of stocks to show (default: 10)")
@click.option("--force-refresh", "--force", is_flag=True, help="Force refresh cache")
@click.pass_context
def active(ctx, limit: int, force_refresh: bool):
    """
    Show most active stocks by volume.
    
    Uses Alpha Vantage TOP_GAINERS_LOSERS API with 1-hour caching.
    Falls back to YFinance S&P 500 processing if Alpha Vantage unavailable.
    
    Example:
        tradescout active --limit 20
    """
    console.print("[blue]📊 Most Active Stocks[/blue]")
    
    try:
        # Create market movers provider
        movers_provider = create_market_movers_provider()
        
        # Get most active
        with console.status("[bold blue]Fetching most active stocks...", spinner="dots"):
            active_list = movers_provider.get_most_active(limit, force_refresh)
        
        if not active_list:
            console.print("[yellow]⚠️  No active stocks data available[/yellow]")
            return
        
        # Create table
        table = Table(title=f"Top {len(active_list)} Most Active Stocks", box=box.ROUNDED)
        table.add_column("Rank", justify="center", style="dim", width=4)
        table.add_column("Symbol", style="cyan", no_wrap=True)
        table.add_column("Price", justify="right")
        table.add_column("Change %", justify="right")
        table.add_column("Volume", justify="right", style="bold blue")
        
        # Add rows
        for active_stock in active_list:
            change_color = "green" if active_stock.price_change_percent >= 0 else "red"
            change_prefix = "+" if active_stock.price_change_percent >= 0 else ""
            
            table.add_row(
                str(active_stock.rank),
                active_stock.asset.symbol,
                f"${active_stock.current_price:.2f}",
                f"[{change_color}]{change_prefix}{active_stock.price_change_percent:.2f}%[/{change_color}]",
                f"{active_stock.volume:,}" if active_stock.volume > 0 else "N/A"
            )
        
        console.print(table)
        
        # Show cache status more prominently
        if force_refresh:
            console.print(f"[yellow]🔄 Fresh data retrieved (cache bypassed)[/yellow]")
        else:
            console.print(f"[blue]💾 Data cached for 1 hour. Use --force-refresh to get fresh data.[/blue]")
        
    except Exception as e:
        console.print(f"[red]❌ Error fetching most active: {e}[/red]")


@main.command()
@click.option("--limit", default=5, help="Number of stocks per category (default: 5)")
@click.option("--force-refresh", "--force", is_flag=True, help="Force refresh cache")
@click.pass_context
def movers(ctx, limit: int, force_refresh: bool):
    """
    Show comprehensive market movers report (gainers, losers, most active).
    
    Uses Alpha Vantage TOP_GAINERS_LOSERS API with 1-hour caching.
    Falls back to YFinance S&P 500 processing if Alpha Vantage unavailable.
    
    Example:
        tradescout movers --limit 10
    """
    console.print("[bold]📈 Market Movers Report[/bold]")
    
    try:
        # Create market movers provider
        movers_provider = create_market_movers_provider()
        
        # Get complete report
        with console.status("[bold]Fetching complete market movers report...", spinner="dots"):
            report = movers_provider.get_market_movers_report(limit, force_refresh)
        
        # Show report header
        console.print(Panel(
            f"[bold]Market Status:[/bold] {report.market_status.value}\n"
            f"[bold]Report Time:[/bold] {report.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"[bold]Data Source:[/bold] {'Alpha Vantage' if len(report.gainers) >= limit else 'YFinance Fallback'}",
            title="📊 Report Info",
            box=box.ROUNDED
        ))
        
        # Gainers table
        if report.gainers:
            console.print("\n[green]🟢 Top Gainers[/green]")
            gainers_table = Table(box=box.SIMPLE)
            gainers_table.add_column("Symbol", style="cyan")
            gainers_table.add_column("Price", justify="right")
            gainers_table.add_column("Change %", justify="right", style="bold green")
            
            for gainer in report.gainers:
                gainers_table.add_row(
                    gainer.asset.symbol,
                    f"${gainer.current_price:.2f}",
                    f"+{gainer.price_change_percent:.2f}%"
                )
            console.print(gainers_table)
        
        # Losers table
        if report.losers:
            console.print("\n[red]🔴 Top Losers[/red]")
            losers_table = Table(box=box.SIMPLE)
            losers_table.add_column("Symbol", style="cyan")
            losers_table.add_column("Price", justify="right")
            losers_table.add_column("Change %", justify="right", style="bold red")
            
            for loser in report.losers:
                losers_table.add_row(
                    loser.asset.symbol,
                    f"${loser.current_price:.2f}",
                    f"{loser.price_change_percent:.2f}%"
                )
            console.print(losers_table)
        
        # Most active table
        if report.most_active:
            console.print("\n[blue]📊 Most Active[/blue]")
            active_table = Table(box=box.SIMPLE)
            active_table.add_column("Symbol", style="cyan")
            active_table.add_column("Price", justify="right")
            active_table.add_column("Volume", justify="right", style="bold blue")
            
            for active_stock in report.most_active:
                active_table.add_row(
                    active_stock.asset.symbol,
                    f"${active_stock.current_price:.2f}",
                    f"{active_stock.volume:,}" if active_stock.volume > 0 else "N/A"
                )
            console.print(active_table)
        
        # Show cache status more prominently  
        if force_refresh:
            console.print(f"\n[yellow]🔄 Fresh data retrieved (cache bypassed)[/yellow]")
        else:
            console.print(f"\n[blue]💾 Data cached for 1 hour. Use --force-refresh to get fresh data.[/blue]")
        
    except Exception as e:
        console.print(f"[red]❌ Error fetching market movers report: {e}[/red]")


if __name__ == "__main__":
    main()
