"""CLI output adapter for asset command displays.

This adapter handles all asset-related formatted output for the CLI interface.
For web/JSON output, a different adapter would be injected via PresentationContext.
"""

from datetime import datetime
from typing import List

from rich.console import Console
from rich.table import Table
from rich import box

from models.dataclass.asset_result import MarketContextResult, AssetInfoResult, PriceDataResult, SentimentEventsResult


console = Console()


class CLIAssetOutputAdapter:
    """Adapter for displaying asset results in CLI format using Rich."""

    def display_market_context(self, result: MarketContextResult) -> None:
        """Display market context table.

        Args:
            result: MarketContextResult containing market status for all configured exchanges
        """
        if not result.markets:
            console.print(f"[dim]⚠️ No configured markets found[/dim]")
            return

        # Create markets context table
        context_table = Table(box=box.ROUNDED, show_header=True, title="📊 Markets Context")
        context_table.add_column("Market", style="bold", width=8)
        context_table.add_column("Session", width=12)
        context_table.add_column("Status", width=8)
        context_table.add_column("Trading Day", width=12)
        context_table.add_column("Extended Hours", width=15)

        # Add row for each market
        for market_code, session, status, trading_day, extended in result.markets:
            context_table.add_row(market_code, session, status, trading_day, extended)

        console.print(context_table)
        console.print()

    def display_asset_info(self, result: AssetInfoResult) -> None:
        """Display asset information table.

        Args:
            result: AssetInfoResult containing symbol details
        """
        title = result.asset.symbol

        # Create asset info table
        asset_table = Table(box=box.ROUNDED, show_header=False, title=title)
        asset_table.add_column("", style="bold", width=12)
        asset_table.add_column("", width=30)

        asset_table.add_row("Name", result.asset.name or "N/A")

        if result.market:
            asset_table.add_row("Market", f"{result.market.name} ({result.market.code})")
        else:
            asset_table.add_row("Market", "N/A")

        # Handle asset_type (could be enum or string)
        asset_type_str = result.asset.asset_type.value if hasattr(result.asset.asset_type, 'value') else str(result.asset.asset_type) if result.asset.asset_type else "N/A"
        asset_table.add_row("Type", asset_type_str)

        # Handle asset_class (could be enum or string)
        asset_class_str = result.asset.asset_class.value if hasattr(result.asset.asset_class, 'value') else str(result.asset.asset_class) if result.asset.asset_class else "N/A"
        asset_table.add_row("Class", asset_class_str)
        asset_table.add_row("Currency", result.asset.currency or "N/A")
        asset_table.add_row("Status", "✅ Active" if result.asset.is_active else "❌ Inactive")
        asset_table.add_row("Asset ID", str(result.asset.id))
        asset_table.add_row("Provider ID", str(result.asset.provider_id))

        if result.universes:
            asset_table.add_row("Universes", ", ".join(result.universes))
        else:
            asset_table.add_row("Universes", "[dim]none[/dim]")

        console.print(asset_table)

    def display_price_data(self, result: PriceDataResult) -> None:
        """Display price data table with prevday/day/minute columns.

        Args:
            result: PriceDataResult containing OHLCV data for all timeframes
        """
        console.print()

        # Provider timestamp header
        provider_time = datetime.fromtimestamp(result.asset_price.provider_updated_at / 1_000_000_000).strftime("%Y-%m-%d %H:%M:%S ET")

        # Show status based on whether data is new/cached
        if result.is_new_data:
            console.print(f"[green]✅ New data fetched[/green] | {result.asset_price.symbol} | Provider Updated: {provider_time}")
        else:
            if result.forced_fetch:
                console.print(f"[yellow]📋 No new data from provider[/yellow] | {result.asset_price.symbol} | Provider Updated: {provider_time}")
            else:
                console.print(f"[yellow]📋 Using cached data[/yellow] | {result.asset_price.symbol} | Provider Updated: {provider_time}")

        # If this is local-only display, show capture time instead
        if not result.forced_fetch and not result.is_new_data:
            our_capture_time = result.asset_price.updated_at.strftime("%Y-%m-%d %H:%M:%S")
            console.print(f"{result.asset_price.symbol} | Provider Updated: {provider_time} | Captured: {our_capture_time}")

        # Price data table
        price_table = Table(box=box.ROUNDED, show_header=True)
        price_table.add_column("PrevDay", style="", width=8)
        price_table.add_column("", style="", width=9)
        price_table.add_column("Day", style="", width=8)
        price_table.add_column("", style="", width=9)
        price_table.add_column("Min", style="", width=8)
        price_table.add_column("", style="", width=19)

        def format_price(value):
            return f"${value:.2f}" if value else "N/A"

        def format_volume(value):
            if not value:
                return "N/A"
            if value >= 1_000_000:
                return f"{value/1_000_000:.1f}M"
            elif value >= 1_000:
                return f"{value/1_000:.1f}K"
            return f"{value:,}"

        def format_timestamp(timestamp_ms):
            if not timestamp_ms:
                return "N/A"
            dt = datetime.fromtimestamp(timestamp_ms / 1000)
            return dt.strftime("%Y-%m-%d %H:%M:%S")

        # Add rows
        price_table.add_row(
            "Open", format_price(result.asset_price.prevday_open),
            "Open", format_price(result.asset_price.day_open),
            "Open", format_price(result.asset_price.min_open)
        )
        price_table.add_row(
            "High", format_price(result.asset_price.prevday_high),
            "High", format_price(result.asset_price.day_high),
            "High", format_price(result.asset_price.min_high)
        )
        price_table.add_row(
            "Low", format_price(result.asset_price.prevday_low),
            "Low", format_price(result.asset_price.day_low),
            "Low", format_price(result.asset_price.min_low)
        )
        price_table.add_row(
            "Close", format_price(result.asset_price.prevday_close),
            "Close", format_price(result.asset_price.day_close),
            "Close", format_price(result.asset_price.min_close)
        )
        price_table.add_row(
            "Volume", format_volume(result.asset_price.prevday_volume),
            "Volume", format_volume(result.asset_price.day_volume),
            "Volume", format_volume(result.asset_price.min_volume)
        )
        price_table.add_row(
            "", "",
            "", "",
            "TS", format_timestamp(result.asset_price.min_timestamp)
        )

        console.print(price_table)

    def display_no_price_data(self, symbol: str) -> None:
        """Display message when no price data is available.

        Args:
            symbol: Asset symbol
        """
        console.print(f"[yellow]⚠️  No price data available for {symbol}[/yellow]")

    def display_asset_not_found(self, symbol: str) -> None:
        """Display message when asset is not found.

        Args:
            symbol: Asset symbol
        """
        console.print(f"[red]❌ Asset {symbol} not found[/red]")

    def display_sentiment_events(self, result: SentimentEventsResult) -> None:
        """Display sentiment events table with overall score.

        Args:
            result: SentimentEventsResult containing events and sentiment score
        """
        if not result.sentiment_events:
            console.print()
            console.print(f"[dim]📰 No sentiment events found for {result.symbol}[/dim]")
            return

        console.print()
        console.print(f"[cyan]📰 Recent News Sentiment[/cyan] (Latest {len(result.sentiment_events[:5])} of {len(result.sentiment_events)})")

        # Create sentiment table
        sentiment_table = Table(box=box.ROUNDED, show_header=True, show_footer=True)
        sentiment_table.add_column("Date", style="", no_wrap=True)
        sentiment_table.add_column("Time", style="", no_wrap=True)
        sentiment_table.add_column("Type", style="")
        sentiment_table.add_column("Article", style="dim")

        # Show only 5 most recent
        for event in result.sentiment_events[:5]:
            # Format date and time
            event_date = event.event_date.strftime("%Y-%m-%d")
            event_time = event.event_time.strftime("%H:%M") if event.event_time else "N/A"

            # Get type name
            type_name = result.type_id_to_name.get(event.sentiment_type_id, "unknown")
            # Clean up type name (remove "news_" prefix if present)
            if type_name.startswith("news_"):
                type_name = type_name[5:]  # Remove "news_" prefix

            # Get article title from details
            article_title = event.get_detail("title", "N/A")
            # Truncate if too long
            if len(article_title) > 47:
                article_title = article_title[:44] + "..."

            sentiment_table.add_row(
                event_date,
                event_time,
                type_name.capitalize(),
                article_title
            )

        # Add overall sentiment score as footer
        if result.sentiment_score is not None:
            score_value = result.sentiment_score.overall_score

            # Format score with color coding
            if score_value > 0.3:
                score_str = f"[green]+{score_value:.2f}[/green]"
            elif score_value < -0.3:
                score_str = f"[red]{score_value:.2f}[/red]"
            else:
                score_str = f"[yellow]{score_value:.2f}[/yellow]"

            sentiment_table.columns[0].footer = "[bold]Overall:[/bold]"
            sentiment_table.columns[1].footer = ""
            sentiment_table.columns[2].footer = f"[bold]{score_str} ({result.sentiment_score.sentiment_label})[/bold]"
            sentiment_table.columns[3].footer = f"[dim]{result.sentiment_score.articles_analyzed} articles within {result.time_window_days}-day window, {result.sentiment_score.confidence_level} confidence[/dim]"

        console.print(sentiment_table)
