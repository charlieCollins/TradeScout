"""CLI output adapter for news results using Rich formatting.

Formats news and sentiment results for terminal display with Rich tables and styling.
"""

from typing import Optional
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich import box

from models.result.news_result import NewsResult


class CLINewsOutputAdapter:
    """Format and display news results for CLI using Rich."""

    def __init__(self, console: Optional[Console] = None):
        """Initialize CLI news output adapter.

        Args:
            console: Optional Rich console (creates new one if not provided)
        """
        self.console = console or Console()

    def display_news_result(self, result: NewsResult, sentiment_score=None) -> None:
        """Display news and sentiment result with Rich formatting.

        Args:
            result: News fetch and sentiment operation result
            sentiment_score: Optional SentimentScore from sentiment analyzer
        """
        # Summary section
        self.console.print(f"[bold cyan]📰 News for {result.symbol}[/]")
        self.console.print(f"  • Articles Fetched: {result.articles_found}")
        self.console.print(f"  • [green]New Events Stored: {result.sentiment_events_stored}[/green]")

        if result.sentiment_events_duplicates > 0:
            self.console.print(f"  • [dim]Already Have (Skipped): {result.sentiment_events_duplicates}[/dim]")

        if result.errors:
            self.console.print(f"  • [red]Errors: {len(result.errors)}[/red]")

        self.console.print()

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

            self.console.print(f"[bold]📊 Overall Sentiment Analysis[/]")
            self.console.print(f"  • Score: [{score_color}]{score_val:+.3f}[/{score_color}] ({sentiment_score.sentiment_label})")
            self.console.print(f"  • Confidence: {sentiment_score.confidence_level}")
            self.console.print(f"  • Articles Analyzed: {sentiment_score.articles_analyzed} (last {sentiment_score.time_window_days} days)")

            # Show breakdown
            breakdown_parts = []
            for sentiment_type, count in sentiment_score.sentiment_breakdown.items():
                if count > 0:
                    breakdown_parts.append(f"{count} {sentiment_type}")
            if breakdown_parts:
                self.console.print(f"  • Breakdown: {', '.join(breakdown_parts)}")

            self.console.print()

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

            self.console.print(news_table)
        else:
            self.console.print("[yellow]No articles found for this symbol[/yellow]")

        # Display errors if any
        if result.errors:
            self.console.print()
            self.console.print(f"[yellow]⚠️  Errors ({len(result.errors)}):[/]")
            for error in result.errors[:5]:
                self.console.print(f"  • {error}")
            if len(result.errors) > 5:
                self.console.print(f"  • ... and {len(result.errors) - 5} more")

        self.console.print()
