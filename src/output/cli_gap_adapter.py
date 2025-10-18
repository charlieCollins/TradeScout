"""CLI output adapters for gap analysis and performance results.

Provides CLI-specific display formatting for gap trading operations,
following the PresentationContext adapter pattern. These classes handle
Rich formatting and table generation for gap candidates and performance data.
"""

from typing import List, Optional
from datetime import date

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from models.dataclass.gap import GapCandidate
from models.dataclass.market_context import MarketContext


class CLIGapAnalysisAdapter:
    """CLI output adapter for gap analysis results."""

    def __init__(self):
        """Initialize gap analysis display formatter."""
        self.console = Console()

    def display_candidates_table(
        self,
        candidates: List[GapCandidate],
        market_context: MarketContext
    ):
        """Display gap candidates in formatted table.

        Args:
            candidates: List of gap candidates to display
            market_context: Current market context for session info
        """
        if not candidates:
            return

        session = market_context.session_name

        # Create table
        table = Table(
            title=f"🎯 Gap Candidates - {session.upper()} ({market_context.current_date})",
            show_header=True,
            header_style="bold magenta"
        )

        table.add_column("Symbol", style="cyan", width=8)
        table.add_column("Name", style="white", width=20)
        table.add_column("Gap %", justify="right", style="yellow", width=8)
        table.add_column("Price", justify="right", style="white", width=9)
        table.add_column("Volume", justify="right", style="cyan", width=10)
        table.add_column("Vol Ratio", justify="right", style="green", width=9)
        table.add_column("Sentiment", justify="right", style="white", width=10)
        table.add_column("News", justify="center", style="white", width=6)
        table.add_column("Quality", justify="right", style="magenta", width=8)
        table.add_column("Risk", justify="center", style="white", width=8)
        table.add_column("MCap", justify="right", style="dim", width=10)

        for candidate in candidates:
            # Format gap with color
            gap_style = "bright_green" if candidate.gap_percent > 0 else "bright_red"
            gap_text = Text(f"{candidate.gap_percent:+.1f}%", style=gap_style)

            # Format volume shares
            if candidate.extended_hours_volume:
                volume_text = f"{candidate.extended_hours_volume:,}"
            else:
                volume_text = "N/A"

            # Format volume ratio
            vol_ratio_text = f"{candidate.volume_ratio:.1f}x" if candidate.volume_ratio else "N/A"

            # Format sentiment score
            if candidate.sentiment_score is None:
                sentiment_text = Text("N/A", style="dim")
            elif candidate.sentiment_score >= 0.5:
                sentiment_text = Text(f"+{candidate.sentiment_score:.2f}", style="bright_green")
            elif candidate.sentiment_score >= 0.2:
                sentiment_text = Text(f"+{candidate.sentiment_score:.2f}", style="green")
            elif candidate.sentiment_score >= -0.2:
                sentiment_text = Text(f"{candidate.sentiment_score:+.2f}", style="yellow")
            else:
                sentiment_text = Text(f"{candidate.sentiment_score:+.2f}", style="red")

            # Format news count
            if candidate.news_count and candidate.news_count > 0:
                news_text = Text(f"{candidate.news_count}", style="white")
            else:
                news_text = Text("0", style="dim")

            # Format quality score with color
            if candidate.quality_score is None:
                quality_text = Text("N/A", style="dim")
            elif candidate.quality_score >= 85:
                quality_style = "bright_green bold"
                quality_text = Text(f"{candidate.quality_score}", style=quality_style)
            elif candidate.quality_score >= 70:
                quality_style = "green"
                quality_text = Text(f"{candidate.quality_score}", style=quality_style)
            elif candidate.quality_score >= 60:
                quality_style = "yellow"
                quality_text = Text(f"{candidate.quality_score}", style=quality_style)
            else:
                quality_style = "red"
                quality_text = Text(f"{candidate.quality_score}", style=quality_style)

            # Format risk level
            if candidate.risk_level:
                risk_value = candidate.risk_level.value
                if risk_value == "low":
                    risk_style = "green"
                elif risk_value == "medium":
                    risk_style = "yellow"
                else:
                    risk_style = "red"
                risk_text = Text(risk_value.upper(), style=risk_style)
            else:
                risk_text = Text("N/A", style="dim")

            # Format market cap
            mcap_b = candidate.market_cap / 1e9
            mcap_text = f"${mcap_b:.1f}B"

            table.add_row(
                candidate.symbol,
                candidate.name[:20],  # Truncate long names
                gap_text,
                f"${candidate.current_price:.2f}",
                volume_text,
                vol_ratio_text,
                sentiment_text,
                news_text,
                quality_text,
                risk_text,
                mcap_text
            )

        self.console.print(table)

    def display_failed_candidates(
        self,
        candidates: List[GapCandidate],
        min_ratio: float
    ):
        """Display candidates that failed volume filter.

        Args:
            candidates: List of gap candidates that failed volume validation
            min_ratio: Minimum volume ratio threshold that was required
        """
        if not candidates:
            return

        # Show top 10 by gap size
        top_candidates = candidates[:10]

        table = Table(
            title=f"❌ Top Candidates That Failed Volume Filter (<{min_ratio}x)",
            show_header=True,
            header_style="bold red"
        )

        table.add_column("Symbol", style="cyan", width=8)
        table.add_column("Gap %", justify="right", style="yellow", width=8)
        table.add_column("Vol Ratio", justify="right", style="red", width=9)
        table.add_column("MCap", justify="right", style="dim", width=10)

        for candidate in top_candidates:
            vol_ratio_text = f"{candidate.volume_ratio:.2f}x" if candidate.volume_ratio else "N/A"
            mcap_b = candidate.market_cap / 1e9

            table.add_row(
                candidate.symbol,
                f"{candidate.gap_percent:+.1f}%",
                vol_ratio_text,
                f"${mcap_b:.1f}B"
            )

        self.console.print(table)

    def display_summary(
        self,
        candidates: List[GapCandidate],
        min_volume_ratio: float,
        market_context: MarketContext
    ):
        """Display summary and trading recommendations.

        Args:
            candidates: List of filtered gap candidates
            min_volume_ratio: Minimum volume ratio used for filtering
            market_context: Current market context for risk assessment
        """
        # Count by quality tier
        excellent = [c for c in candidates if c.quality_score >= 85]
        good = [c for c in candidates if 70 <= c.quality_score < 85]
        fair = [c for c in candidates if 60 <= c.quality_score < 70]
        weak = [c for c in candidates if c.quality_score < 60]

        # Summary panel
        summary_text = f"""
[bold]📊 Analysis Summary[/bold]

Total Candidates: {len(candidates)}

Quality Tiers:
  • [bright_green]Excellent (85-100):[/bright_green] {len(excellent)} candidates
  • [green]Good (70-84):[/green] {len(good)} candidates
  • [yellow]Fair (60-69):[/yellow] {len(fair)} candidates
  • [red]Weak (<60):[/red] {len(weak)} candidates

[bold]💡 Recommendations[/bold]
"""

        if excellent:
            summary_text += f"\n[bright_green]✓ {len(excellent)} high-quality candidates for trading[/bright_green]"
            summary_text += f"\n  Symbols: {', '.join(c.symbol for c in excellent[:5])}"

        if good:
            summary_text += f"\n[green]✓ {len(good)} good candidates worth monitoring[/green]"

        if not excellent and not good:
            summary_text += f"\n[yellow]⚠ No high-quality candidates today[/yellow]"
            summary_text += f"\n  Consider waiting for better setups"

        # Weekend/holiday risk check
        if market_context.day_type.value in ["early_close", "holiday"]:
            summary_text += f"\n\n[bold red]⚠️ RISK WARNING: {market_context.day_type.value.upper()}[/bold red]"
            summary_text += f"\n  Consider reducing position sizes or skipping"

        # Friday gap risk check
        if market_context.current_date.weekday() == 4:  # Friday
            summary_text += f"\n\n[bold yellow]⚠️ FRIDAY GAP RISK[/bold yellow]"
            summary_text += f"\n  Weekend gaps have higher risk (2-3 day hold)"
            summary_text += f"\n  Academic research shows lower fill rates on Monday"
            summary_text += f"\n  Consider reducing position sizes by 50%"

        summary_text += f"\n\n[bold]Next Steps:[/bold]"
        summary_text += f"\n1. Monitor volume at market open (9:30 AM)"
        summary_text += f"\n2. Confirm volume continues ≥{min_volume_ratio:.1f}x"
        summary_text += f"\n3. Check bid-ask spreads (≤1.0%)"
        summary_text += f"\n4. Enter per trading plan"
        summary_text += f"\n5. Set stop losses immediately"

        panel = Panel(summary_text, border_style="cyan", padding=(1, 2))
        self.console.print(panel)

    def display_gap_results_list(self, result):
        """Display historical gap analysis results grouped by date.

        Args:
            result: GapResultsListResult containing results grouped by trading date
        """
        from models.dataclass.gap_result import GapResultsListResult

        # Display header
        self.console.print(Panel.fit(
            "[bold cyan]Gap Analysis Results - Historical Data[/bold cyan]",
            border_style="cyan"
        ))

        # Display results for each date
        for date_group in result.results_by_date:
            # Date header
            self.console.print(f"\n[bold blue]═══ {date_group.trading_date} ═══[/bold blue]")
            self.console.print(f"[dim]{date_group.total_count} total results[/dim]")

            # Create table
            table = Table(show_header=True, header_style="bold cyan", show_lines=True)
            table.add_column("Symbol", style="bold", width=8)
            table.add_column("Session", width=10)
            table.add_column("Gap %", justify="right", width=8)
            table.add_column("Type", width=12)
            table.add_column("Vol Ratio", justify="right", width=10)
            table.add_column("MCap", justify="right", width=8)
            table.add_column("Status", width=10)
            table.add_column("Rejection", width=30)

            for row in date_group.results:
                # Format fields
                session_icon = "🌅" if row.session_type == 'premarket' else "🌙"
                session_text = f"{session_icon} {row.session_type[:2].upper()}"

                gap_text = f"{row.gap_percentage:+.1f}%"
                if row.gap_percentage >= 10:
                    gap_style = "bold green"
                elif row.gap_percentage >= 5:
                    gap_style = "green"
                else:
                    gap_style = "dim green"

                # Academic gap type with short labels
                gap_type = row.academic_gap_type or 'unknown'
                if gap_type == 'common':
                    type_text = Text("Common", style="dim")
                elif gap_type == 'breakaway_continuation':
                    type_text = Text("Break/Cont", style="cyan")
                elif gap_type == 'exhaustion_candidate':
                    type_text = Text("Exhaust?", style="yellow")
                else:
                    type_text = Text("—", style="dim")

                vol_ratio = row.volume_ratio if row.volume_ratio else 0
                vol_text = f"{vol_ratio:.2f}x" if vol_ratio > 0 else "N/A"
                vol_style = "green" if vol_ratio >= 1.5 else "red"

                mcap = row.market_cap if row.market_cap else 0
                mcap_text = f"${mcap/1e9:.1f}B" if mcap >= 1e9 else f"${mcap/1e6:.0f}M"

                status_color = "green" if row.status == 'passed' else "red"
                status_text = Text(row.status.upper(), style=status_color)

                rejection = row.rejection_reason if row.rejection_reason else "—"

                table.add_row(
                    row.symbol,
                    session_text,
                    Text(gap_text, style=gap_style),
                    type_text,
                    Text(vol_text, style=vol_style),
                    mcap_text,
                    status_text,
                    rejection[:30]
                )

            self.console.print(table)

            # Show hidden count if any
            hidden_count = date_group.total_count - date_group.shown_count
            if hidden_count > 0:
                self.console.print(f"[dim]  ... and {hidden_count} more results not shown[/dim]")

        # Summary
        self.console.print(f"\n[bold]Summary:[/bold]")
        self.console.print(f"  Days shown: {result.dates_shown}")
        self.console.print(f"  Results displayed: {result.total_results_shown}")
        if result.total_results_hidden > 0:
            self.console.print(f"  Results hidden: {result.total_results_hidden} (use --num-results-per-day to see more)")

        # Statistics
        self.console.print(f"\n[bold]Database Statistics ({result.start_date} to {result.end_date}):[/bold]")
        self.console.print(f"  Total results: {result.total_count}")
        if result.total_count > 0:
            self.console.print(f"  Passed: {result.passed_count} ({100*result.passed_count/result.total_count:.1f}%)")
            self.console.print(f"  Rejected: {result.rejected_count} ({100*result.rejected_count/result.total_count:.1f}%)")
        else:
            self.console.print(f"  Passed: 0")
            self.console.print(f"  Rejected: 0")


class CLIGapPerformanceAdapter:
    """CLI output adapter for gap performance results."""

    def __init__(self):
        """Initialize gap performance display formatter."""
        self.console = Console()

    def display_date_performance(
        self,
        trading_date: date,
        results: List[dict]
    ):
        """Display performance results for a specific trading date.

        Args:
            trading_date: The trading date for these results
            results: List of performance result dictionaries containing:
                - status: 'success', 'skipped', or 'failed'
                - symbol: Stock symbol
                - performance: GapCandidateResult object (if status == 'success')
                - reason: Error/skip reason (if status != 'success')
        """
        if not results:
            return

        # Create table
        table = Table(show_header=True, header_style="bold magenta", box=None)
        table.add_column("Symbol", style="cyan")
        table.add_column("Entry", justify="right", style="white")
        table.add_column("Exit", justify="right", style="white")
        table.add_column("Return", justify="right")
        table.add_column("High", justify="right", style="dim")
        table.add_column("Low", justify="right", style="dim")
        table.add_column("Gap Fill", justify="center")

        has_rows = False

        for result in results:
            if result['status'] == 'skipped':
                self.console.print(f"  [yellow]{result['symbol']}: {result['reason']}[/yellow]")
                continue

            if result['status'] == 'failed':
                self.console.print(f"  [red]{result['symbol']}: {result['reason']}[/red]")
                continue

            perf = result['performance']

            # Format return with color
            ret_pct = perf.realized_return_pct
            if ret_pct >= 2.0:
                ret_style = "bright_green bold"
                ret_text = f"+{ret_pct:.1f}% (winner)"
            elif ret_pct <= -1.0:
                ret_style = "bright_red bold"
                ret_text = f"{ret_pct:.1f}% (loser)"
            else:
                ret_style = "yellow"
                ret_text = f"{ret_pct:+.1f}% (breakeven)"

            # Gap fill status
            gap_fill_text = "Yes" if perf.gap_filled else "No"
            gap_fill_style = "red" if perf.gap_filled else "green"

            # Format time if gap filled
            if perf.gap_fill_timestamp:
                fill_time = perf.gap_fill_timestamp.strftime("%I:%M %p")
                gap_fill_text = f"Yes ({fill_time})"

            table.add_row(
                result['symbol'],
                f"${perf.entry_price:.2f}",
                f"${perf.exit_price:.2f}",
                Text(ret_text, style=ret_style),
                f"${perf.max_intraday_price:.2f}",
                f"${perf.min_intraday_price:.2f}",
                Text(gap_fill_text, style=gap_fill_style)
            )
            has_rows = True

        # Only print table if it has data rows
        if has_rows:
            self.console.print(table)

    def display_performance_statistics(
        self,
        performance_data: List[dict]
    ):
        """Display performance statistics summary.

        Args:
            performance_data: List of dicts with 'session_type', 'gap_direction', and 'performance' keys
        """
        if not performance_data:
            return

        # Overall statistics
        total = len(performance_data)
        winners = sum(1 for p in performance_data if p['performance'].get('realized_return_pct', 0) >= 2.0)
        losers = sum(1 for p in performance_data if p['performance'].get('realized_return_pct', 0) <= -1.0)
        breakeven = total - winners - losers

        total_return = sum(p['performance'].get('realized_return_pct', 0) for p in performance_data)
        avg_return = total_return / total if total > 0 else 0

        winner_returns = [p['performance'].get('realized_return_pct', 0) for p in performance_data
                          if p['performance'].get('realized_return_pct', 0) >= 2.0]
        loser_returns = [p['performance'].get('realized_return_pct', 0) for p in performance_data
                         if p['performance'].get('realized_return_pct', 0) <= -1.0]

        avg_winner = sum(winner_returns) / len(winner_returns) if winner_returns else 0
        avg_loser = sum(loser_returns) / len(loser_returns) if loser_returns else 0

        gap_filled = sum(1 for p in performance_data if p['performance'].get('gap_filled', False))
        gap_fill_rate = (gap_filled / total * 100) if total > 0 else 0

        # By gap direction
        gap_ups = [p for p in performance_data if p.get('gap_direction') == 'up']
        gap_downs = [p for p in performance_data if p.get('gap_direction') == 'down']

        gap_ups_avg = sum(p['performance'].get('realized_return_pct', 0) for p in gap_ups) / len(gap_ups) if gap_ups else 0
        gap_downs_avg = sum(p['performance'].get('realized_return_pct', 0) for p in gap_downs) / len(gap_downs) if gap_downs else 0

        gap_ups_winners = sum(1 for p in gap_ups if p['performance'].get('realized_return_pct', 0) >= 2.0)
        gap_downs_winners = sum(1 for p in gap_downs if p['performance'].get('realized_return_pct', 0) >= 2.0)

        # By session type
        premarket = [p for p in performance_data if p['session_type'] == 'premarket']
        afterhours = [p for p in performance_data if p['session_type'] == 'afterhours']

        premarket_avg = sum(p['performance'].get('realized_return_pct', 0) for p in premarket) / len(premarket) if premarket else 0
        afterhours_avg = sum(p['performance'].get('realized_return_pct', 0) for p in afterhours) / len(afterhours) if afterhours else 0

        # By academic gap type (from stored classification)
        common = [p for p in performance_data if p.get('academic_gap_type') == 'common']
        breakaway_cont = [p for p in performance_data if p.get('academic_gap_type') == 'breakaway_continuation']
        exhaustion = [p for p in performance_data if p.get('academic_gap_type') == 'exhaustion_candidate']

        common_avg = sum(p['performance'].get('realized_return_pct', 0) for p in common) / len(common) if common else 0
        breakaway_cont_avg = sum(p['performance'].get('realized_return_pct', 0) for p in breakaway_cont) / len(breakaway_cont) if breakaway_cont else 0
        exhaustion_avg = sum(p['performance'].get('realized_return_pct', 0) for p in exhaustion) / len(exhaustion) if exhaustion else 0

        common_winners = sum(1 for p in common if p['performance'].get('realized_return_pct', 0) >= 2.0)
        breakaway_cont_winners = sum(1 for p in breakaway_cont if p['performance'].get('realized_return_pct', 0) >= 2.0)
        exhaustion_winners = sum(1 for p in exhaustion if p['performance'].get('realized_return_pct', 0) >= 2.0)

        # Create statistics panel
        stats_text = f"""
[bold]📊 Backtest Results - Overall Statistics[/bold]

Total Gaps Backtested: {total}

[bold]Outcome Distribution:[/bold]
  • Winners (≥2%):      {winners:3d} ({100*winners/total:.1f}%)
  • Losers (≤-1%):      {losers:3d} ({100*losers/total:.1f}%)
  • Breakeven (-1-2%):  {breakeven:3d} ({100*breakeven/total:.1f}%)

[bold]Return Metrics:[/bold]
  • Average Return:     {avg_return:+.1f}%
  • Average Winner:     {avg_winner:+.1f}%
  • Average Loser:      {avg_loser:+.1f}%

[bold]Gap Fill Analysis:[/bold]
  • Gap Fill Rate:      {gap_fill_rate:.1f}% ({gap_filled}/{total} filled)

[bold]By Gap Direction:[/bold]
  • Gap Ups:            {len(gap_ups):3d} gaps ({100*len(gap_ups)/total:.1f}%) | Avg: {gap_ups_avg:+.1f}% | Winners: {gap_ups_winners}
  • Gap Downs:          {len(gap_downs):3d} gaps ({100*len(gap_downs)/total:.1f}%) | Avg: {gap_downs_avg:+.1f}% | Winners: {gap_downs_winners}

[bold]By Session Type:[/bold]
  • Premarket Gaps:     {len(premarket):3d} gaps ({100*len(premarket)/total:.1f}%) | Avg: {premarket_avg:+.1f}%
  • After-Hours Gaps:   {len(afterhours):3d} gaps ({100*len(afterhours)/total:.1f}%) | Avg: {afterhours_avg:+.1f}%

[bold]By Academic Gap Type:[/bold]
  • Common (<2%):           {len(common):3d} gaps ({100*len(common)/total:.1f}%) | Avg: {common_avg:+.1f}% | Winners: {common_winners}
  • Breakaway/Cont (2-5%):  {len(breakaway_cont):3d} gaps ({100*len(breakaway_cont)/total:.1f}%) | Avg: {breakaway_cont_avg:+.1f}% | Winners: {breakaway_cont_winners}
  • Exhaustion (≥5%):       {len(exhaustion):3d} gaps ({100*len(exhaustion)/total:.1f}%) | Avg: {exhaustion_avg:+.1f}% | Winners: {exhaustion_winners}
"""

        panel = Panel(stats_text, border_style="cyan", padding=(1, 2))
        self.console.print(panel)
