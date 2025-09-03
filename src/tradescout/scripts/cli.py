#!/usr/bin/env python3
"""
TradeScout CLI Interface

Command-line interface for TradeScout market research assistant.
Provides commands for data collection, analysis, and market research.
"""

import json
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import List, Optional

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.progress import track
from rich.table import Table

from ..config.data_sources_manager import get_data_sources_manager
from ..config.local_config import DATABASE_CONFIG
from ..config.markets_manager import get_markets_manager, TradingSession
from ..data_models.domain_models_core import Asset, AssetType
from ..data_models.domain_models_analysis import ConfidenceLevel
from ..data_models.factories import MarketFactory
from ..data_sources.smart_coordinator import create_smart_coordinator
from ..storage.sqlite_repository import create_sqlite_database_manager

# Setup rich console for beautiful output
console = Console()
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version="0.1.0", package_name="tradescout")
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
        console.print(
            f"[green]✅ Initialized Smart Coordinator with {provider_count} data providers[/green]"
        )

        # Show provider status if verbose
        if verbose:
            data_manager = get_data_sources_manager()
            status = data_manager.get_provider_status()
            console.print(
                f"[dim]Available providers: {status['summary']['available']}/{status['summary']['total_configured']}[/dim]"
            )
            console.print(
                f"[dim]Data types configured: {len(coordinator.get_available_data_types())}[/dim]"
            )
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
    volume_leaders = coordinator.get_volume_leaders(
        symbol_list, min_volume_ratio=Decimal(str(min_volume_ratio))
    )

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

        provider_table.add_row(
            name, provider_type, priority, quality, rate_limit, status_text
        )

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

            strategy = config.fallback_strategy.value.replace("_", " ").title()
            providers_str = ", ".join(provider_names) if provider_names else "None"

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
                data_type.replace("_", " ").title(), strategy, providers_str, cache_ttl
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
    Show top market gainers based on current trading session.
    
    - Regular Hours: Show regular session movers
    - Pre-Market: Show pre-market gaps vs yesterday close  
    - After-Hours: Show after-hours gaps vs today close
    - Closed: Show most recent session data

    Example:
        tradescout gainers --limit 20
    """
    coordinator = ctx.obj["coordinator"]
    markets_manager = get_markets_manager()
    
    # Determine current trading session
    current_session = markets_manager.get_current_trading_session("nasdaq")
    
    # Show session-aware header and data explanation
    now = datetime.now()
    
    if current_session == TradingSession.PREMARKET:
        header = "🌅 PRE-MARKET EXTENDED HOURS GAPS"
        data_explanation = "[dim]Pre-market prices vs yesterday's close[/dim]"
        gap_timing = "PRE-MARKET"
    elif current_session == TradingSession.AFTERHOURS:
        header = "🌆 AFTER-HOURS EXTENDED HOURS GAPS"  
        data_explanation = "[dim]After-hours prices vs today's close[/dim]"
        gap_timing = "AFTER-HOURS"
    elif current_session == TradingSession.REGULAR:
        header = "🟢 DAILY GAPS (Regular Session)"
        data_explanation = "[dim]Showing: Current regular session vs previous session (DAILY GAPS)[/dim]"
        gap_timing = "DAILY"
    else:  # CLOSED
        header = "🟢 DAILY GAPS (Market Closed)"
        data_explanation = "[dim]Showing: Most recent daily session vs previous session (DAILY GAPS)[/dim]"
        gap_timing = "DAILY"
    
    console.print(f"[green]{header}[/green]")
    console.print(f"{data_explanation}")
    console.print(f"[bold green]Current Time: {now.strftime('%Y-%m-%d %H:%M:%S EST')} | Session: {current_session.value.title()}[/bold green]\n")

    try:
        # Get gainers using smart coordinator
        with console.status("[bold green]Fetching market gainers...", spinner="dots"):
            gainers_list = coordinator.get_market_gainers(limit, force_refresh)

        if not gainers_list:
            console.print("[yellow]⚠️  No gainers data available[/yellow]")
            return

        # Create table 
        table = Table(title=f"Top {len(gainers_list)} Market Gainers ({gap_timing} Session)", box=box.ROUNDED)
        table.add_column("Rank", justify="center", style="dim", width=4)
        table.add_column("Symbol", style="cyan", no_wrap=True)
        table.add_column("Price", style="green", justify="right")
        table.add_column("Change", justify="right")
        table.add_column("Change %", justify="right", style="bold green")
        table.add_column("Volume", justify="right", style="dim")
        table.add_column("Session", justify="center", style="yellow", width=10)

        # Add rows
        for gainer in gainers_list:
            change_color = "green" if gainer.price_change >= 0 else "red"
            price_change_str = (
                f"+{gainer.price_change:.2f}"
                if gainer.price_change >= 0
                else f"{gainer.price_change:.2f}"
            )

            table.add_row(
                str(gainer.rank),
                gainer.asset.symbol,
                f"${gainer.current_price:.2f}",
                f"[{change_color}]{price_change_str}[/{change_color}]",
                f"+{gainer.price_change_percent:.2f}%",
                f"{gainer.volume:,}" if gainer.volume > 0 else "N/A",
            )

        console.print(table)

        # Show cache status more prominently
        if force_refresh:
            console.print(f"[yellow]🔄 Fresh data retrieved (cache bypassed)[/yellow]")
        else:
            console.print(
                f"[blue]💾 Data cached for 15 minutes. Use --force-refresh to get fresh data.[/blue]"
            )

    except Exception as e:
        console.print(f"[red]❌ Error fetching gainers: {e}[/red]")


@main.command()
@click.option("--limit", default=10, help="Number of losers to show (default: 10)")
@click.option("--force-refresh", "--force", is_flag=True, help="Force refresh cache")
@click.pass_context
def losers(ctx, limit: int, force_refresh: bool):
    """
    Show top market losers based on current trading session.
    
    - Regular Hours: Show regular session movers
    - Pre-Market: Show pre-market gaps vs yesterday close  
    - After-Hours: Show after-hours gaps vs today close
    - Closed: Show most recent session data

    Example:
        tradescout losers --limit 20
    """
    coordinator = ctx.obj["coordinator"]
    markets_manager = get_markets_manager()
    
    # Determine current trading session
    current_session = markets_manager.get_current_trading_session("nasdaq")
    
    # Show session-aware header and data explanation
    now = datetime.now()
    
    if current_session == TradingSession.PREMARKET:
        header = "🌅 PRE-MARKET EXTENDED HOURS GAPS"
        data_explanation = "[dim]Pre-market prices vs yesterday's close[/dim]"
        gap_timing = "PRE-MARKET"
    elif current_session == TradingSession.AFTERHOURS:
        header = "🌆 AFTER-HOURS EXTENDED HOURS GAPS"  
        data_explanation = "[dim]After-hours prices vs today's close[/dim]"
        gap_timing = "AFTER-HOURS"
    elif current_session == TradingSession.REGULAR:
        header = "🔴 DAILY GAPS (Regular Session)"
        data_explanation = "[dim]Showing: Current regular session vs previous session (DAILY GAPS)[/dim]"
        gap_timing = "DAILY"
    else:  # CLOSED
        header = "🔴 DAILY GAPS (Market Closed)"
        data_explanation = "[dim]Showing: Most recent daily session vs previous session (DAILY GAPS)[/dim]"
        gap_timing = "DAILY"
    
    console.print(f"[red]{header}[/red]")
    console.print(f"{data_explanation}")
    console.print(f"[bold green]Current Time: {now.strftime('%Y-%m-%d %H:%M:%S EST')} | Session: {current_session.value.title()}[/bold green]\n")

    try:
        # Get losers using smart coordinator
        with console.status("[bold red]Fetching market losers...", spinner="dots"):
            losers_list = coordinator.get_market_losers(limit, force_refresh)

        if not losers_list:
            console.print("[yellow]⚠️  No losers data available[/yellow]")
            return

        # Create table 
        table = Table(title=f"Top {len(losers_list)} Market Losers ({gap_timing} Session)", box=box.ROUNDED)
        table.add_column("Rank", justify="center", style="dim", width=4)
        table.add_column("Symbol", style="cyan", no_wrap=True)
        table.add_column("Price", style="red", justify="right")
        table.add_column("Change", justify="right")
        table.add_column("Change %", justify="right", style="bold red")
        table.add_column("Volume", justify="right", style="dim")
        table.add_column("Session", justify="center", style="yellow", width=10)

        # Add rows
        for loser in losers_list:
            change_color = "green" if loser.price_change >= 0 else "red"
            price_change_str = (
                f"+{loser.price_change:.2f}"
                if loser.price_change >= 0
                else f"{loser.price_change:.2f}"
            )

            table.add_row(
                str(loser.rank),
                loser.asset.symbol,
                f"${loser.current_price:.2f}",
                f"[{change_color}]{price_change_str}[/{change_color}]",
                f"{loser.price_change_percent:.2f}%",
                f"{loser.volume:,}" if loser.volume > 0 else "N/A",
            )

        console.print(table)

        # Show cache status more prominently
        if force_refresh:
            console.print(f"[yellow]🔄 Fresh data retrieved (cache bypassed)[/yellow]")
        else:
            console.print(
                f"[blue]💾 Data cached for 15 minutes. Use --force-refresh to get fresh data.[/blue]"
            )

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
    coordinator = ctx.obj["coordinator"]
    console.print("[blue]📊 Most Active Stocks[/blue]")

    try:
        # Get most active using smart coordinator
        with console.status(
            "[bold blue]Fetching most active stocks...", spinner="dots"
        ):
            active_list = coordinator.get_most_active(limit, force_refresh)

        if not active_list:
            console.print("[yellow]⚠️  No active stocks data available[/yellow]")
            return

        # Create table
        table = Table(
            title=f"Top {len(active_list)} Most Active Stocks", box=box.ROUNDED
        )
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
                f"{active_stock.volume:,}" if active_stock.volume > 0 else "N/A",
            )

        console.print(table)

        # Show cache status more prominently
        if force_refresh:
            console.print(f"[yellow]🔄 Fresh data retrieved (cache bypassed)[/yellow]")
        else:
            console.print(
                f"[blue]💾 Data cached for 15 minutes. Use --force-refresh to get fresh data.[/blue]"
            )

    except Exception as e:
        console.print(f"[red]❌ Error fetching most active: {e}[/red]")


@main.command()
@click.option("--limit", default=10, help="Number of stocks per category (default: 10)")
@click.option("--force-refresh", "--force", is_flag=True, help="Force refresh cache")
@click.pass_context
def movers(ctx, limit: int, force_refresh: bool):
    """
    Show comprehensive market movers report (gainers and losers).

    Shows top gainers and losers based on current trading session.

    Example:
        tradescout movers --limit 10
    """
    coordinator = ctx.obj["coordinator"]
    markets_manager = get_markets_manager()
    
    # Determine current trading session
    current_session = markets_manager.get_current_trading_session("nasdaq")
    
    # Show session-aware header
    now = datetime.now()
    
    if current_session == TradingSession.PREMARKET:
        header = "🌅 Market Movers (PRE-MARKET Session)"
        data_explanation = "[dim]Pre-market prices vs yesterday's close[/dim]"
        gap_timing = "PRE-MARKET"
    elif current_session == TradingSession.AFTERHOURS:
        header = "🌆 Market Movers (AFTER-HOURS Session)"  
        data_explanation = "[dim]After-hours prices vs today's close[/dim]"
        gap_timing = "AFTER-HOURS"
    elif current_session == TradingSession.REGULAR:
        header = "🟢 Market Movers (REGULAR Session)"
        data_explanation = "[dim]Showing: Current regular session vs previous session[/dim]"
        gap_timing = "REGULAR"
    else:  # CLOSED
        header = "🟢 Market Movers (Market Closed)"
        data_explanation = "[dim]Showing: Most recent session vs previous session[/dim]"
        gap_timing = "CLOSED"
    
    console.print(f"[bold]{header}[/bold]")
    console.print(f"{data_explanation}")
    console.print(f"[bold green]Current Time: {now.strftime('%Y-%m-%d %H:%M:%S EST')} | Session: {current_session.value.title()}[/bold green]\n")

    try:
        # Get gainers and losers separately
        with console.status("[bold green]Fetching market gainers and losers...", spinner="dots"):
            gainers_list = coordinator.get_market_gainers(limit, force_refresh)
            losers_list = coordinator.get_market_losers(limit, force_refresh)

        # Gainers table
        if gainers_list:
            console.print(f"\n[green]🟢 Top {len(gainers_list)} Market Gainers ({gap_timing} Session)[/green]")
            gainers_table = Table(box=box.ROUNDED)
            gainers_table.add_column("Rank", justify="center", style="dim", width=4)
            gainers_table.add_column("Symbol", style="cyan")
            gainers_table.add_column("Price", justify="right", style="green")
            gainers_table.add_column("Change", justify="right")
            gainers_table.add_column("Change %", justify="right", style="bold green")
            gainers_table.add_column("Volume", justify="right", style="dim")

            for i, gainer in enumerate(gainers_list, 1):
                change_color = "green" if gainer.price_change >= 0 else "red"
                price_change_str = (
                    f"+{gainer.price_change:.2f}"
                    if gainer.price_change >= 0
                    else f"{gainer.price_change:.2f}"
                )
                gainers_table.add_row(
                    str(i),
                    gainer.asset.symbol,
                    f"${gainer.current_price:.2f}",
                    f"[{change_color}]{price_change_str}[/{change_color}]",
                    f"+{gainer.price_change_percent:.2f}%",
                    f"{gainer.volume:,}" if gainer.volume > 0 else "N/A",
                )
            console.print(gainers_table)

        # Losers table
        if losers_list:
            console.print(f"\n[red]🔴 Top {len(losers_list)} Market Losers ({gap_timing} Session)[/red]")
            losers_table = Table(box=box.ROUNDED)
            losers_table.add_column("Rank", justify="center", style="dim", width=4)
            losers_table.add_column("Symbol", style="cyan")
            losers_table.add_column("Price", justify="right", style="red")
            losers_table.add_column("Change", justify="right")
            losers_table.add_column("Change %", justify="right", style="bold red")
            losers_table.add_column("Volume", justify="right", style="dim")

            for i, loser in enumerate(losers_list, 1):
                change_color = "green" if loser.price_change >= 0 else "red"
                price_change_str = (
                    f"+{loser.price_change:.2f}"
                    if loser.price_change >= 0
                    else f"{loser.price_change:.2f}"
                )
                losers_table.add_row(
                    str(i),
                    loser.asset.symbol,
                    f"${loser.current_price:.2f}",
                    f"[{change_color}]{price_change_str}[/{change_color}]",
                    f"{loser.price_change_percent:.2f}%",
                    f"{loser.volume:,}" if loser.volume > 0 else "N/A",
                )
            console.print(losers_table)

        # Show cache status more prominently
        if force_refresh:
            console.print(
                f"\n[yellow]🔄 Fresh data retrieved (cache bypassed)[/yellow]"
            )
        else:
            console.print(
                f"\n[blue]💾 Data cached for 15 minutes. Use --force-refresh to get fresh data.[/blue]"
            )

    except Exception as e:
        console.print(f"[red]❌ Error fetching market movers: {e}[/red]")


@main.command()
@click.option("--limit", default=5, help="Maximum number of suggestions (default: 5)")
@click.option("--force-refresh", "--force", is_flag=True, help="Force refresh data")
@click.option("--min-gap", default=2.0, help="Minimum gap percentage (default: 2.0%)")
@click.pass_context
def suggest(ctx, limit: int, force_refresh: bool, min_gap: float):
    """
    Generate daily gap trading suggestions based on academic research.

    Scans for overnight gaps >= 2.0%, applies six-step binary classification,
    and generates ranked trade recommendations with risk/reward analysis.

    Example:
        tradescout suggest --limit 10 --min-gap 2.5
    """
    coordinator = ctx.obj["coordinator"]
    console.print("[bold]📈 Daily Gap Trading Suggestions[/bold]")

    try:
        # Import gap analysis components
        from ..analysis.gap_market_scanner import GapMarketScanner
        from ..analysis.gap_rules_engine import GapRulesEngine
        from ..analysis.academic_gap_analyzer import AcademicGapTypeAnalyzer
        from ..analysis.gap_suggestion_engine import GapTradeSuggestionEngine
        from decimal import Decimal

        # Initialize gap analysis components
        with console.status("[bold green]Initializing gap analysis system...", spinner="dots"):
            gap_scanner = GapMarketScanner(coordinator)
            rules_engine = GapRulesEngine()
            gap_analyzer = AcademicGapTypeAnalyzer()
            suggestion_engine = GapTradeSuggestionEngine()

        # Step 1: Scan for gap candidates
        with console.status(f"[bold blue]Scanning for gaps >= {min_gap}%...", spinner="dots"):
            gap_candidates = gap_scanner.scan_pre_market_gaps(Decimal(str(min_gap)))

        if not gap_candidates:
            console.print(f"[yellow]⚠️  No gap candidates found >= {min_gap}%[/yellow]")
            return

        console.print(f"[blue]🔍 Found {len(gap_candidates)} gap candidates[/blue]")

        # Step 2: Apply binary classification rules
        with console.status("[bold blue]Applying six-step binary classification...", spinner="dots"):
            rule_evaluations = []
            for quote in gap_candidates:
                evaluation = rules_engine.evaluate_gap_candidate(quote)
                rule_evaluations.append(evaluation)

        # Filter to approved candidates only
        approved_candidates = []
        approved_evaluations = []
        for i, evaluation in enumerate(rule_evaluations):
            if evaluation["decision"] == "TRADE":
                approved_candidates.append(gap_candidates[i])
                approved_evaluations.append(evaluation)

        if not approved_candidates:
            console.print("[yellow]⚠️  No candidates passed binary classification rules[/yellow]")
            
            # Show summary of rejected candidates
            rejection_table = Table(title="Gap Analysis Summary", box=box.ROUNDED)
            rejection_table.add_column("Symbol", style="cyan")
            rejection_table.add_column("Gap Size", justify="right")
            rejection_table.add_column("Decision", justify="center")
            rejection_table.add_column("Primary Reason", style="dim")
            
            for i, evaluation in enumerate(rule_evaluations[:10]):  # Show top 10 rejections
                quote = gap_candidates[i]
                gap_size = getattr(quote, 'gap_size', abs(quote.price_change_percent or Decimal(0)))
                
                decision_color = "green" if evaluation["decision"] == "TRADE" else "red"
                decision_text = f"[{decision_color}]{evaluation['decision']}[/{decision_color}]"
                
                primary_reason = evaluation["reasons"][0] if evaluation["reasons"] else "Unknown"
                if len(primary_reason) > 50:
                    primary_reason = primary_reason[:47] + "..."
                
                rejection_table.add_row(
                    quote.asset.symbol,
                    f"{gap_size:.1f}%",
                    decision_text,
                    primary_reason
                )
            
            console.print(rejection_table)
            return

        console.print(f"[green]✅ {len(approved_candidates)} candidates approved by rules engine[/green]")

        # Step 3: Analyze gap types and generate suggestions
        with console.status("[bold blue]Analyzing gap types and generating suggestions...", spinner="dots"):
            gap_assessments = gap_analyzer.batch_analyze_candidates(approved_candidates)
            
            # Create analysis data for suggestion engine
            analysis_results = []
            for i, assessment in enumerate(gap_assessments):
                if i < len(approved_candidates):
                    analysis_data = {
                        "quote": approved_candidates[i],
                        "gap_assessment": assessment
                    }
                    analysis_results.append(analysis_data)

            # Generate suggestions
            suggestions = []
            for analysis_data in analysis_results:
                suggestion = suggestion_engine.generate_suggestion(
                    analysis_data["quote"].asset.symbol, 
                    analysis_data
                )
                if suggestion and suggestion_engine.validate_suggestion(suggestion):
                    suggestions.append(suggestion)

        # Step 4: Filter and rank suggestions
        final_suggestions = suggestion_engine.filter_suggestions(suggestions, limit)

        if not final_suggestions:
            console.print("[yellow]⚠️  No high-quality trade suggestions generated[/yellow]")
            return

        # Display results
        console.print(f"\n[bold green]🎯 Top {len(final_suggestions)} Gap Trading Opportunities[/bold green]")
        
        # Show report header with current market time
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
        console.print(
            Panel(
                f"[bold]Report Time:[/bold] {current_time}\n"
                f"[bold]Candidates Screened:[/bold] {len(gap_candidates)}\n"
                f"[bold]Rules Approved:[/bold] {len(approved_candidates)}\n"
                f"[bold]Final Suggestions:[/bold] {len(final_suggestions)}\n"
                f"[bold]Entry Window:[/bold] 9:30-10:30 AM ET\n"
                f"[bold]Mandatory Exit:[/bold] 4:00 PM ET",
                title="📊 Analysis Summary",
                border_style="blue",
            )
        )

        # Create suggestions table
        suggestions_table = Table(title=f"Daily Gap Trading Suggestions", box=box.ROUNDED)
        suggestions_table.add_column("Rank", justify="center", style="dim", width=4)
        suggestions_table.add_column("Symbol", style="cyan", no_wrap=True, width=8)
        suggestions_table.add_column("Gap", justify="right", width=8)
        suggestions_table.add_column("Volume", justify="right", width=8)
        suggestions_table.add_column("Type", justify="center", width=10)
        suggestions_table.add_column("Entry", justify="right", width=8)
        suggestions_table.add_column("Stop", justify="right", width=8)
        suggestions_table.add_column("Target", justify="right", width=8)
        suggestions_table.add_column("R:R", justify="center", width=6)
        suggestions_table.add_column("Confidence", justify="center", width=10)

        # Add suggestion rows
        for rank, suggestion in enumerate(final_suggestions, 1):
            # Get suggestion attributes
            gap_size = getattr(suggestion, 'gap_size', 0)
            volume_ratio = getattr(suggestion, 'volume_ratio', Decimal(1))
            gap_type = getattr(suggestion, 'gap_type', 'unknown')
            
            # Format confidence with color
            confidence_colors = {
                ConfidenceLevel.VERY_HIGH: "bright_green",
                ConfidenceLevel.HIGH: "green", 
                ConfidenceLevel.MEDIUM: "yellow",
                ConfidenceLevel.LOW: "red"
            }
            confidence_color = confidence_colors.get(suggestion.confidence, "white")
            confidence_text = f"[{confidence_color}]{suggestion.confidence.value.upper()}[/{confidence_color}]"
            
            # Add confidence emoji
            confidence_emojis = {
                ConfidenceLevel.VERY_HIGH: "✅",
                ConfidenceLevel.HIGH: "✅", 
                ConfidenceLevel.MEDIUM: "⚠️",
                ConfidenceLevel.LOW: "❌"
            }
            emoji = confidence_emojis.get(suggestion.confidence, "")
            confidence_display = f"{confidence_text} {emoji}"
            
            # Format gap direction with color
            gap_direction = "+" if gap_size > 0 else ""
            gap_color = "green" if gap_size > 0 else "red"
            gap_text = f"[{gap_color}]{gap_direction}{gap_size:.1f}%[/{gap_color}]"
            
            suggestions_table.add_row(
                str(rank),
                suggestion.asset.symbol,
                gap_text,
                f"{volume_ratio:.1f}x",
                gap_type.replace("_", " ").title()[:8],
                f"${suggestion.entry_price:.2f}",
                f"${suggestion.stop_loss:.2f}",
                f"${suggestion.take_profit_1:.2f}",
                f"{suggestion.risk_reward_ratio:.1f}:1",
                confidence_display
            )

        console.print(suggestions_table)

        # Show detailed analysis for top suggestion
        if final_suggestions:
            top_suggestion = final_suggestions[0]
            
            console.print(f"\n[bold]💡 Top Recommendation Analysis: {top_suggestion.asset.symbol}[/bold]")
            
            analysis_text = [
                f"[bold]Analysis:[/bold] {top_suggestion.analysis_summary}",
                f"[bold]Position Size:[/bold] {top_suggestion.position_size} shares",
                f"[bold]Risk Amount:[/bold] ${abs(top_suggestion.entry_price - top_suggestion.stop_loss) * top_suggestion.position_size:.0f}"
            ]
            
            if top_suggestion.catalysts:
                analysis_text.append(f"[bold]Key Catalysts:[/bold]")
                for catalyst in top_suggestion.catalysts[:3]:
                    analysis_text.append(f"  • {catalyst}")
            
            if top_suggestion.risk_factors:
                analysis_text.append(f"[bold]Risk Factors:[/bold]")
                for risk in top_suggestion.risk_factors[:3]:
                    analysis_text.append(f"  • {risk}")
            
            console.print(
                Panel(
                    "\n".join(analysis_text),
                    title=f"{top_suggestion.asset.symbol} - Detailed Analysis",
                    border_style="green" if top_suggestion.confidence == ConfidenceLevel.VERY_HIGH else "yellow",
                )
            )

        # Show cache status
        if force_refresh:
            console.print(f"\n[yellow]🔄 Fresh data analysis completed[/yellow]")
        else:
            console.print(
                f"\n[blue]💾 Analysis cached. Market data refreshed at market close.[/blue]"
            )
        
        # Show important disclaimers
        console.print(
            f"\n[dim]⚠️  Academic research-based suggestions • Past performance not indicative of future results[/dim]"
        )
        console.print(
            f"[dim]📋 Entry: 9:30-10:30 AM • Exit: By 4:00 PM • No overnight holds • 2% max risk per trade[/dim]"
        )

    except Exception as e:
        console.print(f"[red]❌ Error generating gap trading suggestions: {e}[/red]")
        logger.error(f"Gap suggestion error: {e}", exc_info=True)


if __name__ == "__main__":
    main()
