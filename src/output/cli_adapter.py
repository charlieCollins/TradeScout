"""CLI output adapters using Rich formatting.

Formats DataService results for terminal display with Rich progress bars and tables.
"""

from typing import Optional

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from models.dataclass.results import BootstrapResult, FetchResult, UpdateResult, NewsResult


class CLIProgressReporter:
    """Rich-based progress reporter for CLI operations.

    Displays progress bars with spinners, percentages, and elapsed time.
    """

    def __init__(self, console: Optional[Console] = None):
        """Initialize CLI progress reporter.

        Args:
            console: Optional Rich console (creates new one if not provided)
        """
        self.console = console or Console()
        self.progress: Optional[Progress] = None
        self.task_id = None

    def start_operation(self, operation: str, total: int) -> None:
        """Start progress bar for operation.

        Args:
            operation: Operation description
            total: Total items to process
        """
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("•"),
            TextColumn("{task.completed}/{task.total}"),
            TextColumn("•"),
            TimeElapsedColumn(),
            console=self.console,
        )
        self.progress.start()
        self.task_id = self.progress.add_task(operation, total=total)

    def update_progress(self, current: int, message: str = "") -> None:
        """Update progress bar.

        Args:
            current: Current item number (absolute, not increment)
            message: Optional message (not currently displayed)
        """
        if self.progress and self.task_id is not None:
            self.progress.update(self.task_id, completed=current)

    def complete_operation(self, success: bool, message: str = "") -> None:
        """Complete and stop progress bar.

        Args:
            success: Whether operation succeeded
            message: Optional completion message (displayed after progress bar)
        """
        if self.progress:
            self.progress.stop()
            self.progress = None
            self.task_id = None

        if message:
            if success:
                self.console.print(f"[green]✓[/green] {message}")
            else:
                self.console.print(f"[red]✗[/red] {message}")


class CLIOutputAdapter:
    """Format DataService results for CLI display with Rich formatting."""

    def __init__(self, console: Optional[Console] = None):
        """Initialize CLI output adapter.

        Args:
            console: Optional Rich console (creates new one if not provided)
        """
        self.console = console or Console()

    def display_bootstrap_result(self, result: BootstrapResult) -> None:
        """Display bootstrap result with Rich formatting.

        Args:
            result: Bootstrap operation result
        """
        # Display summary
        self.console.print(
            f"\n[bold green]✅ {result.operation.title()} Bootstrap Complete[/]"
        )

        # Show fetch/insert breakdown if both phases exist
        if result.fetch_errors or result.insert_errors:
            # Two-phase operation (fetch + insert)
            fetch_count = result.total_items - len(result.fetch_errors)
            self.console.print(
                f"  • API Fetches: {fetch_count}/{result.total_items} succeeded"
            )
            self.console.print(
                f"  • Database Inserts: {result.successful}/{fetch_count} succeeded"
            )
        else:
            # Single-phase operation
            self.console.print(f"  • Total: {result.total_items}")
            self.console.print(f"  • Successful: {result.successful}")
            self.console.print(f"  • Failed: {result.failed}")

        self.console.print(f"  • Total Errors: {result.total_errors}")

        # Display fetch errors if any
        if result.fetch_errors:
            self.console.print(
                f"\n[yellow]⚠️  API Fetch Errors ({len(result.fetch_errors)}):[/]"
            )
            for error in result.fetch_errors[:10]:
                self.console.print(f"  • {error}")
            if len(result.fetch_errors) > 10:
                self.console.print(
                    f"  • ... and {len(result.fetch_errors) - 10} more"
                )

        # Display insert errors if any
        if result.insert_errors:
            self.console.print(
                f"\n[yellow]⚠️  Database Insert Errors ({len(result.insert_errors)}):[/]"
            )
            for error in result.insert_errors[:10]:
                self.console.print(f"  • {error}")
            if len(result.insert_errors) > 10:
                self.console.print(
                    f"  • ... and {len(result.insert_errors) - 10} more"
                )

    def display_fetch_result(self, result: FetchResult, symbol: str) -> None:
        """Display fetch result for asset info command.

        Args:
            result: Fetch operation result
            symbol: Asset symbol being fetched
        """
        if result.source == "cache":
            self.console.print(f"📋 Using cached data for {symbol}")
        elif result.is_new_data:
            self.console.print(f"✅ New data fetched for {symbol}")
        else:
            self.console.print(f"📋 No new data from provider for {symbol}")

        if not result.success and result.error:
            self.console.print(f"[red]❌ Error: {result.error}[/red]")

    def display_update_result(self, result: UpdateResult) -> None:
        """Display update result for bulk operations.

        Args:
            result: Update operation result
        """
        self.console.print(
            f"\n[bold green]✅ {result.operation.title()} Complete[/]"
        )
        self.console.print(f"  • New Records: {result.new_records}")
        self.console.print(f"  • Duplicate Records: {result.duplicate_records}")

        if result.updated_records > 0:
            self.console.print(f"  • Updated Records: {result.updated_records}")

        if result.errors:
            self.console.print(f"\n[yellow]⚠️  Errors ({len(result.errors)}):[/]")
            for error in result.errors[:10]:
                self.console.print(f"  • {error}")
            if len(result.errors) > 10:
                self.console.print(f"  • ... and {len(result.errors) - 10} more")

    @staticmethod
    def format_news_result(result: NewsResult, sentiment_score=None) -> None:
        """Display news and sentiment result with Rich formatting.

        Args:
            result: News fetch and sentiment operation result
            sentiment_score: Optional SentimentScore from sentiment analyzer
        """
        from rich.table import Table
        from rich import box
        from datetime import datetime

        console = Console()

        # Summary section
        console.print(f"[bold cyan]📰 News for {result.symbol}[/]")
        console.print(f"  • Articles Fetched: {result.articles_found}")
        console.print(f"  • [green]New Events Stored: {result.sentiment_events_stored}[/green]")

        if result.sentiment_events_duplicates > 0:
            console.print(f"  • [dim]Already Have (Skipped): {result.sentiment_events_duplicates}[/dim]")

        if result.errors:
            console.print(f"  • [red]Errors: {len(result.errors)}[/red]")

        console.print()

        # Display overall sentiment score if available
        if sentiment_score:
            # Color code based on sentiment
            score_val = sentiment_score.overall_score
            if score_val >= 0.2:
                score_color = "green"
            elif score_val <= -0.2:
                score_color = "red"
            else:
                score_color = "yellow"

            console.print(f"[bold]📊 Overall Sentiment Analysis[/]")
            console.print(f"  • Score: [{score_color}]{score_val:+.3f}[/{score_color}] ({sentiment_score.sentiment_label})")
            console.print(f"  • Confidence: {sentiment_score.confidence_level}")
            console.print(f"  • Articles Analyzed: {sentiment_score.articles_analyzed} (last {sentiment_score.time_window_days} days)")

            # Show breakdown
            breakdown_parts = []
            for sentiment_type, count in sentiment_score.sentiment_breakdown.items():
                if count > 0:
                    breakdown_parts.append(f"{count} {sentiment_type}")
            if breakdown_parts:
                console.print(f"  • Breakdown: {', '.join(breakdown_parts)}")

            console.print()

        # Display articles in a table
        if result.has_articles:
            news_table = Table(
                box=box.ROUNDED,
                show_header=True,
                title=f"Recent News Articles - {result.symbol}",
            )
            news_table.add_column("Published", style="dim", no_wrap=True)
            news_table.add_column("Sentiment", no_wrap=True)
            news_table.add_column("Title", ratio=2)
            news_table.add_column("Publisher", style="dim", ratio=1)

            for event in result.sentiment_events:
                # Format published time
                event_datetime = datetime.combine(event.event_date, event.event_time or datetime.min.time())
                pub_str = event_datetime.strftime("%Y-%m-%d %H:%M")

                # Format sentiment from details JSON
                sentiment = event.get_detail("sentiment", "neutral").title()

                # Color code sentiment
                if sentiment.lower() == "positive":
                    sentiment_display = f"[green]{sentiment}[/green]"
                elif sentiment.lower() == "negative":
                    sentiment_display = f"[red]{sentiment}[/red]"
                elif sentiment.lower() == "mixed":
                    sentiment_display = f"[yellow]{sentiment}[/yellow]"
                else:
                    sentiment_display = f"[dim]{sentiment}[/dim]"

                # Format title and publisher from details
                title = event.get_detail("title", "No title")
                if len(title) > 57:
                    title = title[:57] + "..."
                publisher_name = event.get_detail("publisher", "Unknown")

                news_table.add_row(pub_str, sentiment_display, title, publisher_name)

            console.print(news_table)
        else:
            console.print("[yellow]No articles found for this symbol[/yellow]")

        # Display errors if any
        if result.errors:
            console.print()
            console.print(f"[yellow]⚠️  Errors ({len(result.errors)}):[/]")
            for error in result.errors[:5]:
                console.print(f"  • {error}")
            if len(result.errors) > 5:
                console.print(f"  • ... and {len(result.errors) - 5} more")

        console.print()
