"""CLI output adapter for market command displays.

This adapter handles all market-related formatted output for the CLI interface.
For web/JSON output, a different adapter would be injected via PresentationContext.
"""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from models.dataclass.market_result import MarketUpdateResult, MarketBackfillResult, MarketContextResult


console = Console()


class CLIMarketOutputAdapter:
    """Adapter for displaying market results in CLI format using Rich."""

    def display_market_update_result(self, result: MarketUpdateResult) -> None:
        """Display market update results.

        Args:
            result: MarketUpdateResult containing update statistics
        """
        console.print("")

        if result.data_was_fresh:
            # Data was fresh - show timing details
            console.print("[green]✅ Data is fresh (within TTL), no update needed[/green]")
            console.print("")

            info_table = Table(show_header=False, box=None, padding=(0, 1))
            info_table.add_column("Info", style="dim")
            info_table.add_column("Value", justify="right")

            if result.last_snapshot_time and result.age_minutes is not None:
                info_table.add_row("Last snapshot", result.last_snapshot_time.strftime("%Y-%m-%d %H:%M:%S"))
                info_table.add_row("Age", f"{result.age_minutes:.1f} minutes")
                info_table.add_row("TTL setting", f"{result.ttl_minutes:.0f} minutes")

            console.print(info_table)
            console.print("")
            console.print("[dim]Use --force to fetch fresh data anyway[/dim]")
            return

        if result.total_tickers == 0:
            console.print("[red]❌ API returned no data[/red]")
            return

        # Show summary
        console.print(f"[green]✅ Received {result.total_tickers:,} tickers from Polygon[/green]")
        console.print("")

        if result.saved > 0:
            console.print(f"[green]✅ Added {result.saved:,} new price records to database[/green]")
            if result.duplicates > 0:
                console.print(f"[dim]   ├─ Skipped {result.duplicates:,} duplicates (already had this data)[/dim]")
        else:
            console.print(f"[yellow]⚠️  No new data - all {result.duplicates:,} records already in database[/yellow]")

        # Show total records if available
        if result.total_historical_records:
            console.print(f"[dim]   Total historical price records in database: {result.total_historical_records:,}[/dim]")

        # Show processing stats
        console.print("")
        console.print("[bold]Market Update Complete[/bold]")

        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Metric", style="dim")
        table.add_column("Value", justify="right")

        table.add_row("Tickers from Polygon", f"{result.total_tickers:,}")
        table.add_row("Matched to our assets", f"{result.matched_symbols:,}")
        table.add_row("Unmatched symbols", f"{result.unmatched_symbols:,}")
        table.add_row("Successfully transformed", f"{result.transformed:,}")
        table.add_row("  ├─ New records added", f"{result.saved:,}")
        table.add_row("  ├─ Duplicates skipped", f"{result.duplicates:,}")
        table.add_row("  └─ Invalid/rejected", f"{result.invalid:,}")
        table.add_row("Update duration", f"{result.duration_seconds:.1f}s")
        table.add_row("Completed at", result.completed_at.strftime("%Y-%m-%d %H:%M:%S"))

        # Add timing information
        if result.last_snapshot_time and result.age_minutes is not None:
            table.add_row("", "")  # Blank line separator
            table.add_row("Last snapshot", result.last_snapshot_time.strftime("%Y-%m-%d %H:%M:%S"))
            table.add_row("Age", f"{result.age_minutes:.1f} minutes")
            table.add_row("TTL setting", f"{result.ttl_minutes:.0f} minutes")

        console.print(table)

    def display_market_backfill_result(self, result: MarketBackfillResult) -> None:
        """Display market backfill results.

        Args:
            result: MarketBackfillResult containing backfill statistics
        """
        console.print("")

        if result.total_tickers == 0:
            console.print("[red]❌ API returned no data[/red]")
            return

        # Show summary
        console.print(f"[green]✅ Received {result.total_tickers:,} tickers from Polygon for {result.target_date}[/green]")
        console.print("")

        if result.force_refresh:
            console.print(f"[green]✅ Force refresh: Updated {result.saved:,} price records in database[/green]")
        else:
            if result.saved > 0:
                console.print(f"[green]✅ Added {result.saved:,} new price records to database[/green]")
                if result.duplicates > 0:
                    console.print(f"[dim]   ├─ Skipped {result.duplicates:,} duplicates (already had this data)[/dim]")
            else:
                console.print(f"[yellow]⚠️  No new data - all {result.duplicates:,} records already in database[/yellow]")

        # Show total records if available
        if result.total_historical_records:
            console.print(f"[dim]   Total historical price records in database: {result.total_historical_records:,}[/dim]")

        console.print("")
        console.print("[bold]Backfill Complete[/bold]")

        # Show detailed stats table
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Metric", style="dim")
        table.add_column("Value", justify="right")

        table.add_row("Tickers from Polygon", f"{result.total_tickers:,}")
        table.add_row("Matched to our assets", f"{result.matched_symbols:,}")
        table.add_row("Unmatched symbols", f"{result.unmatched_symbols:,}")
        table.add_row("Successfully transformed", f"{result.transformed:,}")
        table.add_row("  ├─ New records added", f"{result.saved:,}")
        table.add_row("  ├─ Duplicates skipped", f"{result.duplicates:,}")
        table.add_row("  └─ Invalid/rejected", f"{result.invalid:,}")
        table.add_row("Backfill duration", f"{result.duration_seconds:.1f}s")
        table.add_row("Completed at", result.completed_at.strftime("%Y-%m-%d %H:%M:%S"))

        console.print(table)

    def display_market_context(self, result: MarketContextResult) -> None:
        """Display market context with universe stats and trading status.

        Args:
            result: MarketContextResult containing all market context information
        """
        ctx = result.market_context

        # Create main context table
        table = Table(
            title=f"📊 {result.universe_name.title()} Market Context", show_header=True
        )
        table.add_column("Property", style="cyan", width=25)
        table.add_column("Value", style="white")

        # Show universe composition - use abbreviated names for conciseness
        market_names = []
        for code, name, _ in result.universe_markets:
            if code == "XNYS":
                market_names.append("NYSE")
            elif code == "XNAS":
                market_names.append("NASDAQ")
            else:
                market_names.append(f"{name} ({code})")

        markets_str = ", ".join(market_names)
        table.add_row("Universe Markets", markets_str)

        # Show which market is being used for context (from composed MarketContext)
        if ctx.market.code == "XNYS":
            primary_display = "NYSE (XNYS)"
        elif ctx.market.code == "XNAS":
            primary_display = "NASDAQ (XNAS)"
        else:
            primary_display = f"{ctx.market.name} ({ctx.market.code})"
        table.add_row("Primary Market (Context)", primary_display)

        table.add_row("Total Universe Assets", f"{result.total_universe:,}")

        # Add market distribution with abbreviated names
        for code, name, count in result.universe_markets:
            pct = (count / result.total_universe * 100) if result.total_universe > 0 else 0
            if code == "XNYS":
                display_name = "NYSE"
            elif code == "XNAS":
                display_name = "NASDAQ"
            else:
                display_name = code
            table.add_row(f"  └─ {display_name}", f"{count:,} ({pct:.1f}%)")

        table.add_row("", "")  # Separator

        # Trading status (from composed MarketContext)
        table.add_row("Is Trading Day", "✅ Yes" if ctx.is_trading_day else "❌ No")
        table.add_row("Previous Trading Date", str(ctx.previous_trading_date))
        table.add_row("Current Session", ctx.current_session.value)

        # Add additional context
        table.add_row("Day Type", ctx.day_type.value.replace("_", " ").title())
        table.add_row("Current Date", str(ctx.current_date))
        table.add_row("Current Time", ctx.current_time.strftime("%Y-%m-%d %H:%M:%S %Z"))
        table.add_row("Session Name (for screeners)", ctx.session_name)

        # Market status indicators
        table.add_row("Market Open", "✅ Yes" if ctx.is_market_open else "❌ No")
        table.add_row("Regular Hours", "✅ Yes" if ctx.is_regular_hours else "❌ No")
        table.add_row("Extended Hours", "✅ Yes" if ctx.is_extended_hours else "❌ No")

        if ctx.next_trading_date:
            table.add_row("Next Trading Date", str(ctx.next_trading_date))

        console.print(table)

        # Show session times (from composed MarketContext)
        session_times = ctx.get_session_times()
        if any(session_times.values()):
            console.print()
            times_table = Table(title="🕐 Session Times (Today)", show_header=True)
            times_table.add_column("Session", style="cyan")
            times_table.add_column("Time", style="white")

            for session_name, time_val in session_times.items():
                formatted_name = session_name.replace("_", " ").title()
                if time_val:
                    formatted_time = time_val.strftime("%H:%M")
                else:
                    formatted_time = "N/A"
                times_table.add_row(formatted_name, formatted_time)

            console.print(times_table)

        # Show timezone info (from composed MarketContext's market)
        console.print()
        console.print(
            Panel(
                f"Market Timezone: {ctx.market.timezone}\n"
                f"Currency: {ctx.market.currency}\n"
                f"Extended Hours Support: {'Yes' if ctx.market.has_extended_hours else 'No'}",
                title="Market Details",
            )
        )

        # Show last market snapshot run metadata
        console.print()
        console.print("[bold]Last Market Snapshot Update:[/bold]")

        if result.last_snapshot_time and result.last_snapshot_status:
            status_display = {
                "completed": "[green]✅ Completed[/green]",
                "failed": "[red]❌ Failed[/red]",
                "running": "[blue]🔄 Running[/blue]",
            }.get(result.last_snapshot_status, result.last_snapshot_status)

            snapshot_table = Table(box=box.ROUNDED, show_header=False)
            snapshot_table.add_column("", style="bold", width=20)
            snapshot_table.add_column("", style="", width=40)
            snapshot_table.add_row("Status", status_display)
            snapshot_table.add_row("Last Update", result.last_snapshot_time.strftime("%Y-%m-%d %H:%M:%S"))
            snapshot_table.add_row("Data Age", result.last_snapshot_age_str or "N/A")
            console.print(snapshot_table)
        else:
            console.print("[yellow]No market snapshot data available[/yellow]")
            console.print(
                "[dim]Run 'tradescout market update' to fetch market data[/dim]"
            )
