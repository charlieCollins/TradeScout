"""Gap Analysis CLI Commands

Implements automated gap trading analysis following docs/GAP_ANALYSIS_MANUAL_WORKFLOW.md.

Command: gap analyze
- Only runs during premarket (4:00-9:30 AM) or after-hours (4:00-8:00 PM)
- Scopes to active universe
- Finds candidates with ≥2% gaps and ≥$1B market cap
- Validates volume using Aggregates API (trade-eligible only)
- Fetches news/sentiment for catalysts
- Calculates quality scores (0-100)
- Filters exhaustion gaps
- Displays comprehensive results table
"""

import click
import sys
import logging
from pathlib import Path
from datetime import date, datetime

from utils.config_loader import ConfigLoader

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from .main import pass_config

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from analysis.gap_analyzer import GapAnalyzer, GapCandidate
# Gap adapters injected via app_context.presentation (no direct imports needed)

console = Console()
logger = logging.getLogger(__name__)


@click.group()
@pass_config
def gap(app_context):
    """Gap trading analysis commands"""
    pass


@gap.command()
@click.option('--min-gap', default=2.0, help='Minimum gap percentage (default: 2.0%)')
@click.option('--min-market-cap', default=1_000_000_000, help='Minimum market cap (default: $1B)')
@click.option('--min-volume-ratio', default=1.5, help='Minimum volume ratio for entry (default: 1.5x)')
@click.option('--limit', default=50, help='Maximum candidates to analyze (default: 50)')
@pass_config
def analyze(app_context, min_gap, min_market_cap, min_volume_ratio, limit):
    """Analyze gap candidates (premarket/after-hours only).

    Automated gap analysis following the manual workflow:
    1. Checks market session (must be premarket or after-hours)
    2. Gets active universe symbols
    3. Finds gap candidates (gap + market cap filters)
    4. Validates volume using Aggregates API
    5. Fetches news/sentiment for catalysts
    6. Calculates quality scores
    7. Filters exhaustion gaps
    8. Displays results with recommendations

    Example:
        ./tradescout gap analyze
        ./tradescout gap analyze --min-gap 3.0 --min-volume-ratio 2.0
    """
    # Suppress verbose logging during gap analysis for cleaner output
    logging.getLogger('analysis.gap_analyzer').setLevel(logging.ERROR)
    logging.getLogger('api.providers').setLevel(logging.ERROR)

    try:
        # Step 1: Get market context and validate session
        console.print("\n[bold cyan]📊 Gap Analysis - Market Context[/bold cyan]")
        market_context = app_context.market_context

        console.print(f"  Session: [yellow]{market_context.session_name}[/yellow]")
        console.print(f"  Market: [yellow]{market_context.market.name}[/yellow]")
        console.print(f"  Date: [yellow]{market_context.current_date}[/yellow]")

        # Validate session
        if market_context.session_name not in ["premarket", "afterhours"]:
            console.print(
                f"\n[bold red]❌ Gap analysis only works during premarket or after-hours[/bold red]"
            )
            console.print(f"   Current session: {market_context.session_name}")
            console.print(f"   Run during: 4:00-9:30 AM (premarket) or 4:00-8:00 PM (after-hours)")
            return

        console.print(f"  [green]✓ Valid session for gap analysis[/green]\n")

        # Always fetch fresh market data for gap analysis
        console.print("[bold cyan]📡 Fetching Fresh Market Data...[/bold cyan]")
        data_service = app_context.get_data_service_v2()

        # Force refresh market snapshot (always gets latest data)
        stats = data_service.update_market_snapshot(
            force_refresh=True,
            market_context=app_context.market_context
        )

        if stats and stats.total_tickers > 0:
            if stats.saved > 0:
                console.print(f"  [green]✓ Market data updated ({stats.total_tickers:,} tickers, {stats.saved:,} new records)[/green]\n")
            else:
                console.print(f"  [green]✓ Market data refreshed ({stats.total_tickers:,} tickers, all current)[/green]\n")
        else:
            console.print(f"  [red]❌ Failed to fetch market data[/red]")
            return

        # Step 2: Get active universe
        active_universe = data_service.get_active_universe()

        if not active_universe:
            console.print("[bold red]❌ No active universe found[/bold red]")
            console.print("   Run: ./tradescout universes activate <name>")
            return

        console.print(f"[bold cyan]🎯 Universe: {active_universe.name}[/bold cyan]")

        universe_symbols = data_service.get_active_universe_symbols()
        console.print(f"  Symbols: {len(universe_symbols):,}")
        console.print(f"  Min gap: {min_gap}%")
        console.print(f"  Min market cap: ${min_market_cap/1e9:.1f}B")
        console.print(f"  Min volume ratio: {min_volume_ratio}x\n")

        # Step 3: Initialize analyzer and find candidates
        console.print("[bold cyan]🔍 Finding Gap Candidates...[/bold cyan]")

        analyzer = GapAnalyzer(data_service)

        candidates = analyzer.find_gap_candidates(
            universe_symbols=universe_symbols,
            market_context=market_context,
            min_gap_pct=min_gap,
            min_market_cap=min_market_cap
        )

        if not candidates:
            console.print("[yellow]📭 No gap candidates found meeting criteria[/yellow]")
            return

        console.print(f"  [green]✓ Found {len(candidates)} candidates[/green]\n")

        # Limit candidates for analysis
        candidates = candidates[:limit]

        # Step 4: Validate volume for each candidate
        console.print("[bold cyan]📈 Validating Volume (Aggregates API)...[/bold cyan]")

        trading_date = market_context.current_date if market_context.is_trading_day else market_context.previous_trading_date
        analysis_timestamp = datetime.now()  # Capture current time for elapsed session calculation
        validated_candidates = []

        for candidate in candidates:
            volume_ratio = analyzer.calculate_volume_ratio(candidate, trading_date, analysis_timestamp)

            if volume_ratio and volume_ratio >= min_volume_ratio:
                validated_candidates.append(candidate)

        console.print(f"  [green]✓ {len(validated_candidates)} passed volume filter (≥{min_volume_ratio}x)[/green]\n")

        if not validated_candidates:
            # Show that sentiment step was skipped
            console.print(f"[bold cyan]📰 Fetching News & Sentiment...[/bold cyan]")
            console.print(f"  [dim]⊘ Skipped (no volume-validated candidates)[/dim]\n")

            # Display results BEFORE asking to save
            console.print("[yellow]📭 No candidates met volume requirements[/yellow]")
            console.print(f"   All {len(candidates)} candidates had volume ratio <{min_volume_ratio}x")
            console.print(f"   Consider lowering --min-volume-ratio threshold\n")

            # Show the candidates table so user can see what was found and why rejected
            gap_display = app_context.presentation.gap_analysis_adapter
            gap_display.display_candidates_table(candidates, market_context)

            # Ask if user wants to save to database
            if click.confirm("\nSave results to database?", default=True):
                console.print("[bold cyan]💾 Saving Results to Database...[/bold cyan]")
                saved_count = _prepare_and_save_candidates(
                    all_candidates=candidates,
                    validated_candidates=[],  # Empty - none passed volume
                    filtered_candidates=[],
                    data_service=data_service,
                    market_context=market_context,
                    analysis_timestamp=datetime.now(),
                    min_volume_ratio=min_volume_ratio,
                    analyzer=analyzer
                )
                if saved_count > 0:
                    console.print(f"  [green]✓ Saved {saved_count} gap results (all rejected)[/green]\n")
            else:
                console.print("  [dim]Skipped database save[/dim]\n")

            return

        # Step 5: Fetch news/sentiment for validated candidates
        console.print(f"[bold cyan]📰 Fetching News & Sentiment...[/bold cyan]")

        # Load catalyst scoring config
        gap_config = ConfigLoader().load_yaml("gap_trading.yaml")
        catalyst_default_score = gap_config["quality_scoring"]["catalyst"]["default_score"]

        for candidate in validated_candidates:
            try:
                # Fetch news and sentiment (stores events automatically)
                result = data_service.fetch_news_and_sentiment(candidate.symbol, limit=10)

                if result and result.success and result.events_stored > 0:
                    # Calculate sentiment from stored events
                    sentiment = data_service.calculate_asset_sentiment(
                        candidate.symbol,
                        limit=10,
                        time_window_days=5
                    )

                    if sentiment:
                        candidate.sentiment_score = sentiment.score
                        candidate.news_count = sentiment.event_count

                        # Simple catalyst scoring (can be enhanced)
                        if sentiment.score >= 0.6:
                            candidate.catalyst_score = 80  # Strong positive
                        elif sentiment.score >= 0.3:
                            candidate.catalyst_score = 60  # Moderate positive
                        elif sentiment.score >= 0:
                            candidate.catalyst_score = 40  # Neutral/weak
                        else:
                            candidate.catalyst_score = 20  # Negative
                    else:
                        candidate.catalyst_score = catalyst_default_score  # No sentiment
                else:
                    candidate.catalyst_score = catalyst_default_score  # No news

            except Exception as e:
                # Silently skip news errors - not critical for analysis
                candidate.catalyst_score = catalyst_default_score

        console.print(f"  [green]✓ News/sentiment analysis complete[/green]\n")

        # Step 6: Filter exhaustion gaps
        console.print("[bold cyan]🚫 Filtering Exhaustion Gaps...[/bold cyan]")

        filtered_candidates = []
        exhaustion_count = 0

        for candidate in validated_candidates:
            if analyzer.is_exhaustion_gap(candidate):
                exhaustion_count += 1
            else:
                filtered_candidates.append(candidate)

        console.print(f"  [green]✓ Filtered out {exhaustion_count} exhaustion gaps[/green]\n")

        # Step 6b: Check for Friday gaps (weekend risk)
        if analyzer.is_friday_gap(trading_date):
            console.print("[yellow]⚠️  FRIDAY GAP WARNING[/yellow]")
            console.print("   Academic research shows Friday gaps have higher weekend risk")
            console.print("   Consider reducing position sizes or skipping today\n")

        if not filtered_candidates:
            console.print("[yellow]📭 All candidates were exhaustion gaps (gap≥5% + vol≥3x)[/yellow]")
            console.print("   Exhaustion gaps have high reversal risk\n")

            # Display the exhaustion gaps BEFORE asking to save
            gap_display = app_context.presentation.gap_analysis_adapter
            gap_display.display_candidates_table(validated_candidates, market_context)

            # Ask if user wants to save to database
            if click.confirm("\nSave results to database?", default=True):
                console.print("[bold cyan]💾 Saving Results to Database...[/bold cyan]")
                saved_count = _prepare_and_save_candidates(
                    all_candidates=candidates,
                    validated_candidates=validated_candidates,
                    filtered_candidates=[],  # Empty - all failed exhaustion filter
                    data_service=data_service,
                    market_context=market_context,
                    analysis_timestamp=datetime.now(),
                    min_volume_ratio=min_volume_ratio,
                    analyzer=analyzer
                )
                if saved_count > 0:
                    console.print(f"  [green]✓ Saved {saved_count} gap results (all rejected - exhaustion)[/green]\n")
            else:
                console.print("  [dim]Skipped database save[/dim]\n")

            # Generate report even with no viable candidates
            report_path = _generate_text_report(
                candidates=candidates,
                validated_candidates=validated_candidates,
                filtered_candidates=filtered_candidates,
                market_context=market_context,
                config={
                    'min_gap': min_gap,
                    'min_market_cap': min_market_cap,
                    'min_volume_ratio': min_volume_ratio
                }
            )
            console.print(f"\n[dim]📄 Report saved: {report_path}[/dim]")
            return

        # Step 7: Calculate quality scores
        console.print("[bold cyan]⭐ Calculating Quality Scores...[/bold cyan]")

        for candidate in filtered_candidates:
            # TODO: Add market/sector alignment checks
            analyzer.calculate_quality_score(
                candidate,
                market_aligned=False,  # Not implemented yet
                sector_aligned=False   # Not implemented yet
            )

        # Sort by quality score
        filtered_candidates.sort(key=lambda c: c.quality_score, reverse=True)

        console.print(f"  [green]✓ Quality scores calculated[/green]\n")

        # Step 8: Display results BEFORE asking to save
        gap_display = app_context.presentation.gap_analysis_adapter
        gap_display.display_candidates_table(filtered_candidates, market_context)

        # Display summary and recommendations
        gap_display.display_summary(filtered_candidates, min_volume_ratio, market_context)

        # Step 9: Save results to database
        if click.confirm("\nSave results to database?", default=True):
            console.print("[bold cyan]💾 Saving Results to Database...[/bold cyan]")

            saved_count = _prepare_and_save_candidates(
                all_candidates=candidates,
                validated_candidates=validated_candidates,
                filtered_candidates=filtered_candidates,
                data_service=data_service,
                market_context=market_context,
                analysis_timestamp=datetime.now(),
                min_volume_ratio=min_volume_ratio,
                analyzer=analyzer
            )

            if saved_count > 0:
                console.print(f"  [green]✓ Saved {saved_count} gap results to database[/green]\n")
            else:
                console.print(f"  [yellow]⚠ No results saved to database[/yellow]\n")
        else:
            console.print("  [dim]Skipped database save[/dim]\n")

        # Step 10: Generate text report
        report_path = _generate_text_report(
            candidates=candidates,
            validated_candidates=validated_candidates,
            filtered_candidates=filtered_candidates,
            market_context=market_context,
            config={
                'min_gap': min_gap,
                'min_market_cap': min_market_cap,
                'min_volume_ratio': min_volume_ratio
            }
        )
        console.print(f"\n[dim]📄 Report saved: {report_path}[/dim]")

    except ValueError as e:
        console.print(f"[bold red]❌ {e}[/bold red]")
    except Exception as e:
        console.print(f"[bold red]❌ Error during gap analysis: {e}[/bold red]")
        logger.exception("Gap analysis error")


def _prepare_and_save_candidates(
    all_candidates: list,
    validated_candidates: list,
    filtered_candidates: list,
    data_service,
    market_context,
    analysis_timestamp: datetime,
    min_volume_ratio: float,
    analyzer
) -> int:
    """Prepare candidates for database storage and save them.

    Args:
        all_candidates: All gap candidates (passed gap % and market cap filters)
        validated_candidates: Candidates that passed volume filter
        filtered_candidates: Final candidates (passed exhaustion filter)
        data_service: DataService instance for asset lookups
        market_context: Current market context
        analysis_timestamp: Timestamp when analysis was performed
        min_volume_ratio: Minimum volume ratio threshold used
        analyzer: GapAnalyzer instance for gap classification

    Returns:
        Number of candidates saved to database
    """
    try:
        from models.sqlmodel.gap_candidate_sqlmodel import GapCandidateSQLModel

        trading_date = market_context.current_date if market_context.is_trading_day else market_context.previous_trading_date
        is_friday = trading_date.weekday() == 4

        saved_count = 0

        # Process each candidate and determine status
        for candidate in all_candidates:
            # Look up asset_id using DataServiceV2
            asset = data_service.get_asset(candidate.symbol)
            if not asset:
                logger.warning(f"Asset {candidate.symbol} not found in database, skipping")
                continue

            # Populate database-specific fields
            candidate.asset_id = asset.id
            candidate.session_type = candidate.session
            candidate.trading_date = trading_date
            candidate.gap_percentage = candidate.gap_percent
            candidate.previous_day_volume = candidate.prevday_volume
            candidate.is_friday_gap = is_friday

            # Classify academic gap type
            candidate.academic_gap_type = analyzer.classify_academic_gap_type(candidate)

            # Set filter flags
            candidate.passed_gap_filter = True  # All candidates passed gap filter
            candidate.passed_market_cap_filter = True  # All candidates passed market cap filter

            # Determine if passed volume filter
            if candidate in validated_candidates:
                candidate.passed_volume_filter = True
            else:
                candidate.passed_volume_filter = False
                candidate.status = "rejected"
                candidate.rejection_reason = f"Volume ratio < {min_volume_ratio}x"

            # Determine if passed exhaustion filter
            if candidate in filtered_candidates:
                candidate.passed_exhaustion_filter = True
                candidate.status = "passed"
                candidate.rejection_reason = None

                # Add Friday warning if applicable
                if is_friday:
                    candidate.status = "warning"
                    candidate.rejection_reason = "Friday gap - weekend risk"
            elif candidate.passed_volume_filter:
                # Passed volume but failed exhaustion filter
                candidate.passed_exhaustion_filter = False
                if not candidate.status:  # Don't override if already set
                    candidate.status = "rejected"
                    candidate.rejection_reason = "Exhaustion gap (gap≥5% + vol≥3x)"
            else:
                # Failed volume filter - never checked exhaustion filter
                candidate.passed_exhaustion_filter = False

            # Derive quality tier from quality score
            if candidate.quality_score is not None:
                if candidate.quality_score >= 85:
                    candidate.quality_tier = "excellent"
                elif candidate.quality_score >= 70:
                    candidate.quality_tier = "good"
                elif candidate.quality_score >= 60:
                    candidate.quality_tier = "fair"
                else:
                    candidate.quality_tier = "poor"

            # Determine if has tier-1 catalyst (strong sentiment)
            if candidate.catalyst_score is not None:
                candidate.has_tier1_catalyst = candidate.catalyst_score >= 80

            # Convert GapCandidate to GapCandidateSQLModel
            gap_result_sql = GapCandidateSQLModel(
                asset_id=candidate.asset_id,
                analysis_timestamp=analysis_timestamp,
                session_type=candidate.session_type,
                trading_date=candidate.trading_date,
                gap_percentage=candidate.gap_percentage,
                gap_direction=candidate.direction.value if candidate.direction else None,
                gap_type=candidate.gap_type,
                academic_gap_type=candidate.academic_gap_type,
                reference_price=candidate.reference_price,
                current_price=candidate.current_price,
                day_open=candidate.day_open,
                day_high=candidate.day_high,
                day_low=candidate.day_low,
                day_close=candidate.day_close,
                prevday_close=candidate.prevday_close,
                prevday_high=candidate.prevday_high,
                prevday_low=candidate.prevday_low,
                extended_hours_volume=candidate.extended_hours_volume,
                previous_day_volume=candidate.previous_day_volume,
                day_volume=candidate.day_volume,
                volume_ratio=candidate.volume_ratio,
                market_cap=candidate.market_cap,
                sector=candidate.sector,
                quality_score=candidate.quality_score,
                quality_tier=candidate.quality_tier,
                catalyst_score=candidate.catalyst_score,
                volume_score=candidate.volume_score,
                gap_size_score=candidate.gap_size_score,
                sector_alignment_score=candidate.sector_alignment_score,
                market_alignment_score=candidate.market_alignment_score,
                passed_gap_filter=candidate.passed_gap_filter,
                passed_volume_filter=candidate.passed_volume_filter,
                passed_market_cap_filter=candidate.passed_market_cap_filter,
                passed_exhaustion_filter=candidate.passed_exhaustion_filter,
                is_friday_gap=candidate.is_friday_gap,
                status=candidate.status,
                rejection_reason=candidate.rejection_reason,
                news_count=candidate.news_count,
                sentiment_score=candidate.sentiment_score,
                has_tier1_catalyst=candidate.has_tier1_catalyst,
                catalyst_description=candidate.catalyst_description,
                min_timestamp=candidate.min_timestamp,
                data_freshness_hours=candidate.data_freshness_hours
            )

            # Save to database using new repository
            gap_result = data_service.gap_candidate_repository.save(gap_result_sql)
            gap_result_id = gap_result.id

            if gap_result_id:
                saved_count += 1
            else:
                logger.warning(f"Failed to save gap result for {candidate.symbol}")

        return saved_count

    except Exception as e:
        logger.error(f"Error preparing and saving candidates: {e}")
        logger.exception("Candidate save error")
        return 0


def _generate_text_report(candidates, validated_candidates, filtered_candidates, market_context, config):
    """Generate comprehensive text report of gap analysis."""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"tradescout_gap_{timestamp}.txt"

    with open(report_path, 'w') as f:
        # Header
        f.write("=" * 80 + "\n")
        f.write("TRADESCOUT GAP ANALYSIS REPORT\n")
        f.write("=" * 80 + "\n\n")

        # Analysis metadata
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Session: {market_context.session_name}\n")
        f.write(f"Market: {market_context.market.name}\n")
        f.write(f"Date: {market_context.current_date}\n")
        f.write(f"Universe: default_universe\n")

        # Risk warnings
        if market_context.current_date.weekday() == 4:  # Friday
            f.write(f"\n⚠️  FRIDAY GAP RISK WARNING\n")
            f.write(f"Academic research shows Friday gaps have higher weekend risk.\n")
            f.write(f"Consider reducing position sizes by 50% or skipping entirely.\n")

        f.write("\n")

        # Configuration
        f.write("Analysis Parameters:\n")
        f.write("-" * 80 + "\n")
        f.write(f"  Minimum Gap: {config['min_gap']}%\n")
        f.write(f"  Minimum Market Cap: ${config['min_market_cap']/1e9:.1f}B\n")
        f.write(f"  Minimum Volume Ratio: {config['min_volume_ratio']}x\n\n")

        # Summary statistics
        f.write("Summary Statistics:\n")
        f.write("-" * 80 + "\n")
        f.write(f"  Total Candidates (Gap + Market Cap): {len(candidates)}\n")
        f.write(f"  Volume Validated (≥{config['min_volume_ratio']}x): {len(validated_candidates)}\n")
        f.write(f"  Final Candidates (After Exhaustion Filter): {len(filtered_candidates)}\n\n")

        if not filtered_candidates:
            f.write("\n" + "=" * 80 + "\n")
            f.write("NO VIABLE CANDIDATES FOUND\n")
            f.write("=" * 80 + "\n\n")

            if len(validated_candidates) > 0:
                f.write("Note: All volume-validated candidates were exhaustion gaps (gap≥5% + vol≥3x)\n")
                f.write("Exhaustion gaps have high reversal risk and were filtered out.\n\n")

            # Show top failed candidates
            f.write("\nTop Candidates That Failed Volume Filter:\n")
            f.write("-" * 80 + "\n\n")

            for i, c in enumerate(candidates[:20], 1):
                f.write(f"{i}. {c.symbol} ({c.name[:40]})\n")
                f.write(f"   Gap: {c.gap_percent:+.2f}%  |  Price: ${c.current_price:.2f}  |  MCap: ${c.market_cap/1e9:.1f}B\n")
                if c.volume_ratio:
                    f.write(f"   Volume Ratio: {c.volume_ratio:.2f}x  |  Extended Hours Vol: {c.extended_hours_volume:,}\n")
                else:
                    f.write(f"   Volume Ratio: N/A (no aggregates data)\n")
                f.write("\n")

        else:
            # Viable candidates section
            f.write("\n" + "=" * 80 + "\n")
            f.write("VIABLE CANDIDATES\n")
            f.write("=" * 80 + "\n\n")

            for i, c in enumerate(filtered_candidates, 1):
                f.write(f"{i}. {c.symbol} - {c.name}\n")
                f.write("-" * 80 + "\n")

                # Price & Gap Info
                f.write(f"  Current Price: ${c.current_price:.2f}\n")
                f.write(f"  Reference Price: ${c.reference_price:.2f}\n")
                f.write(f"  Gap: {c.gap_percent:+.2f}% ({c.direction.value})\n")
                f.write(f"  Significance: {c.significance.value}\n")
                f.write(f"  Market Cap: ${c.market_cap/1e9:.2f}B\n\n")

                # Volume Analysis
                f.write(f"  Volume Analysis:\n")
                f.write(f"    Extended Hours Volume: {c.extended_hours_volume:,} shares\n")
                f.write(f"    Previous Day Volume: {c.prevday_volume:,} shares\n")
                f.write(f"    Volume Ratio: {c.volume_ratio:.2f}x\n")
                if c.volume_ratio >= 2.0:
                    f.write(f"    Volume Status: ✓ STRONG (≥2.0x)\n\n")
                elif c.volume_ratio >= 1.5:
                    f.write(f"    Volume Status: ✓ ADEQUATE (≥1.5x)\n\n")
                else:
                    f.write(f"    Volume Status: ✗ WEAK (<1.5x)\n\n")

                # News & Sentiment
                f.write(f"  News & Sentiment:\n")
                if c.catalyst_score and c.catalyst_score > 0:
                    f.write(f"    Catalyst Score: {c.catalyst_score}/100\n")
                    if c.sentiment_score is not None:
                        f.write(f"    Sentiment Score: {c.sentiment_score:+.2f}\n")
                    if c.news_count:
                        f.write(f"    News Events: {c.news_count} articles\n")

                    if c.catalyst_score >= 70:
                        f.write(f"    Catalyst Quality: ✓ STRONG\n\n")
                    elif c.catalyst_score >= 50:
                        f.write(f"    Catalyst Quality: ✓ MODERATE\n\n")
                    else:
                        f.write(f"    Catalyst Quality: ⚠ WEAK\n\n")
                else:
                    f.write(f"    Catalyst Score: 0/100 (No news found)\n")
                    f.write(f"    Catalyst Quality: ✗ NO CATALYST\n\n")

                # Quality Assessment
                f.write(f"  Overall Quality:\n")
                f.write(f"    Quality Score: {c.quality_score}/100\n")
                if c.risk_level:
                    f.write(f"    Risk Level: {c.risk_level.value.upper()}\n")
                else:
                    f.write(f"    Risk Level: N/A\n")

                if c.quality_score >= 85:
                    f.write(f"    Rating: ✓✓ EXCELLENT (High Conviction)\n")
                elif c.quality_score >= 70:
                    f.write(f"    Rating: ✓ GOOD (Standard Position)\n")
                elif c.quality_score >= 60:
                    f.write(f"    Rating: ⚠ FAIR (Reduced Position)\n")
                else:
                    f.write(f"    Rating: ✗ WEAK (Consider Skipping)\n")

                f.write("\n\n")

            # Quality tiers summary
            excellent = [c for c in filtered_candidates if c.quality_score >= 85]
            good = [c for c in filtered_candidates if 70 <= c.quality_score < 85]
            fair = [c for c in filtered_candidates if 60 <= c.quality_score < 70]

            f.write("=" * 80 + "\n")
            f.write("QUALITY TIER SUMMARY\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"  Excellent (85-100): {len(excellent)} candidates\n")
            if excellent:
                f.write(f"    Symbols: {', '.join(c.symbol for c in excellent)}\n")
            f.write(f"\n  Good (70-84): {len(good)} candidates\n")
            if good:
                f.write(f"    Symbols: {', '.join(c.symbol for c in good)}\n")
            f.write(f"\n  Fair (60-69): {len(fair)} candidates\n")
            if fair:
                f.write(f"    Symbols: {', '.join(c.symbol for c in fair)}\n")
            f.write("\n")

        # Footer
        f.write("\n" + "=" * 80 + "\n")
        f.write("END OF REPORT\n")
        f.write("=" * 80 + "\n")

    return report_path

@gap.command('results')
@click.option('--num-days', default=5, help='Number of recent days to show (default: 5)')
@click.option('--num-results-per-day', default=10, help='Max results per day (default: 10)')
@click.option('--session', type=click.Choice(['premarket', 'afterhours', 'all']), default='all', help='Filter by session type')
@click.option('--status', type=click.Choice(['passed', 'rejected', 'warning', 'all']), default='all', help='Filter by status')
@pass_config
def results_command(app_context, num_days, num_results_per_day, session, status):
    """Query historical gap analysis results from database.

    Shows gap candidates from recent analysis runs, grouped by trading date.
    Default: Last 5 days, top 10 results per day.
    """
    from datetime import date, timedelta
    from collections import defaultdict
    from models.result.gap_result import GapResultRow, GapResultsByDate, GapResultsListResult

    # Get DataServiceV2
    data_service = app_context.get_data_service_v2()

    # Calculate date range
    end_date = date.today()
    start_date = end_date - timedelta(days=30)  # Look back 30 days to find num_days worth of data

    # Query database using repository
    try:
        # Use repository method with filters
        results = data_service.gap_candidate_repository.find_by_date_range_with_symbols(
            start_date=start_date,
            end_date=end_date,
            session_type=session if session != 'all' else None,
            status=status if status != 'all' else None
        )

        # Convert to dict format for compatibility with existing display logic
        all_results = []
        for gap_result, symbol, name in results:
            result_dict = gap_result.model_dump()
            result_dict['symbol'] = symbol
            result_dict['name'] = name
            all_results.append(result_dict)

    except Exception as e:
        console.print(f"[red]Error querying gap results: {e}[/red]")
        return

    if not all_results:
        console.print("\n[yellow]No gap results found matching criteria[/yellow]")
        return

    # Group by trading date
    results_by_date = defaultdict(list)
    for result in all_results:
        results_by_date[result['trading_date']].append(result)

    # Build result model
    dates_shown = 0
    total_results_shown = 0
    total_results_hidden = 0
    results_by_date_list = []

    for trading_date in sorted(results_by_date.keys(), reverse=True):
        if dates_shown >= num_days:
            break

        day_results = results_by_date[trading_date]
        results_to_show = day_results[:num_results_per_day]
        hidden_count = len(day_results) - len(results_to_show)

        # Build GapResultRow objects
        gap_result_rows = []
        for result in results_to_show:
            gap_result_rows.append(GapResultRow(
                symbol=result['symbol'],
                name=result['name'],
                session_type=result['session_type'],
                gap_percentage=result['gap_percentage'],
                academic_gap_type=result.get('academic_gap_type', 'unknown'),
                volume_ratio=result['volume_ratio'] if result['volume_ratio'] else 0,
                market_cap=result['market_cap'] if result['market_cap'] else 0,
                status=result['status'],
                rejection_reason=result['rejection_reason'] if result['rejection_reason'] else ""
            ))

        # Build GapResultsByDate
        results_by_date_list.append(GapResultsByDate(
            trading_date=trading_date,
            results=gap_result_rows,
            total_count=len(day_results),
            shown_count=len(results_to_show)
        ))

        dates_shown += 1
        total_results_shown += len(results_to_show)
        total_results_hidden += hidden_count

    # Statistics
    total_count = len(all_results)
    passed_count = sum(1 for r in all_results if r['status'] == 'passed')
    rejected_count = sum(1 for r in all_results if r['status'] == 'rejected')

    # Build final result and display
    result = GapResultsListResult(
        results_by_date=results_by_date_list,
        dates_shown=dates_shown,
        total_results_shown=total_results_shown,
        total_results_hidden=total_results_hidden,
        start_date=start_date,
        end_date=end_date,
        total_count=total_count,
        passed_count=passed_count,
        rejected_count=rejected_count
    )

    app_context.presentation.gap_analysis_adapter.display_gap_results_list(result)


@gap.command('backtest')
@click.option('--date', help='Specific date to backtest (YYYY-MM-DD)')
@click.option('--num-days', default=10, help='Number of recent days to show (default: 10)')
@click.option('--force', is_flag=True, help='Force refresh existing backtest data')
@click.option('--dry-run', is_flag=True, help='Show what would be updated without saving')
@pass_config
def backtest_command(app_context, date, num_days, force, dry_run):
    """Backtest gap candidates against actual market data.

    Validates gap trading strategy by fetching historical intraday data and
    calculating theoretical performance as if gaps were traded according to
    academic strategy rules (entry at open, exit at close).

    For premarket gaps: Uses same day's regular hours (9:30 AM - 4:00 PM)
    For afterhours gaps: Uses next trading day's regular hours

    Default: Shows most recent 10 days of results with all candidates per day.

    Examples:
        ./tradescout gap backtest                 # Show last 10 days
        ./tradescout gap backtest --num-days 30   # Show last 30 days
        ./tradescout gap backtest --force         # Reprocess all gaps
        ./tradescout gap backtest --date 2025-10-09
        ./tradescout gap backtest --dry-run       # Preview updates
    """
    from analysis.gap_performance_calculator import GapCandidateResultCalculator
    from datetime import date as date_type, datetime

    console.print(Panel.fit(
        "[bold cyan]Gap Strategy Backtest[/bold cyan]",
        border_style="cyan"
    ))

    console.print("\n[bold]Backtesting gap candidates against actual market data...[/bold]\n")

    # Get DataServiceV2
    data_service = app_context.get_data_service_v2()

    calculator = GapCandidateResultCalculator(data_service)

    # Get gap results to process
    try:
        # Use repository method
        if date:
            # Specific date
            target_date = date_type.fromisoformat(date)
            results = data_service.gap_candidate_repository.find_recent_with_symbols(
                num_days=1,
                specific_date=target_date
            )
        else:
            # Most recent N days (all candidates per day)
            results = data_service.gap_candidate_repository.find_recent_with_symbols(
                num_days=num_days
            )

        # Convert to dict format
        gap_results = []
        for gap_result, symbol in results:
            result_dict = gap_result.model_dump()
            result_dict['symbol'] = symbol
            gap_results.append(result_dict)

    except Exception as e:
        console.print(f"[red]Error querying gap results: {e}[/red]")
        return

    if not gap_results:
        console.print("[yellow]No gap results found[/yellow]")
        return

    # Count distinct dates
    distinct_dates = len(set(gr['trading_date'] for gr in gap_results))
    total_results = len(gap_results)

    console.print(f"\n[dim]Showing {distinct_dates} days with {total_results} total gap candidates[/dim]\n")

    # Show statistics if we have a lot of results
    show_statistics = total_results > 50

    if show_statistics:
        # Collect all performance data for statistics
        all_performance_data = []
        for gr in gap_results:
            existing = data_service.gap_candidate_result_repository.get_by_gap_candidate_id(gr['id'])
            if existing:
                existing_dict = existing.model_dump()
                all_performance_data.append({
                    'session_type': gr['session_type'],
                    'performance': existing_dict
                })

        if all_performance_data:
            perf_display = app_context.presentation.gap_performance_adapter
            perf_display.display_performance_statistics(all_performance_data)
            console.print("")  # Extra spacing

    # Process each gap result
    updated_count = 0
    skipped_incomplete = 0
    skipped_exists = 0
    failed_count = 0

    current_date = None
    date_results = []
    all_performance_for_stats = []  # Collect all performance data for final stats

    for gap_result in gap_results:
        trading_date = gap_result['trading_date']
        if isinstance(trading_date, str):
            trading_date = date_type.fromisoformat(trading_date)

        symbol = gap_result['symbol']
        session_type = gap_result['session_type']

        # Group by date for display
        if current_date != trading_date:
            if current_date and date_results:
                # Display previous date results
                perf_display = app_context.presentation.gap_performance_adapter
                perf_display.display_date_performance(current_date, date_results)
                date_results = []
            current_date = trading_date
            console.print(f"[bold cyan]{'=' * 60}[/bold cyan]")
            console.print(f"[bold]{trading_date} {session_type}:[/bold]")

        # Check if should update
        should_update = force

        if not should_update:
            existing = data_service.gap_candidate_result_repository.get_by_gap_candidate_id(gap_result['id'])
            if not existing:
                should_update = True
            elif existing.entry_price is None or existing.exit_price is None:
                should_update = True

        if not should_update:
            # Already has performance data - read and display it
            existing_sql = data_service.gap_candidate_result_repository.get_by_gap_candidate_id(gap_result['id'])
            if existing_sql:
                existing_dict = existing_sql.model_dump()
                # Convert dict to GapPerformance object for display
                from models.dataclass.gap_performance import GapCandidateResult, PerformanceOutcome
                from datetime import datetime as dt

                existing_perf = GapCandidateResult(
                    gap_result_id=existing_dict['gap_result_id'],
                    entry_price=existing_dict['entry_price'],
                    exit_price=existing_dict['exit_price'],
                    max_intraday_price=existing_dict['max_intraday_price'],
                    min_intraday_price=existing_dict['min_intraday_price'],
                    gap_filled=bool(existing_dict['gap_filled']),
                    gap_fill_timestamp=existing_dict.get('gap_fill_timestamp')
                )

                result_info = {
                    'symbol': symbol,
                    'status': 'success',
                    'performance': existing_perf
                }
                date_results.append(result_info)

                # Collect for overall statistics
                all_performance_for_stats.append({
                    'session_type': session_type,
                    'gap_direction': gap_result.get('gap_direction', 'unknown'),
                    'gap_percentage': gap_result.get('gap_percentage', 0),
                    'academic_gap_type': gap_result.get('academic_gap_type'),
                    'performance': existing_dict
                })
            skipped_exists += 1
            continue

        # Determine performance trading date
        try:
            performance_date = calculator.get_performance_trading_date(gap_result)
        except Exception as e:
            console.print(f"  [red]{symbol}: Error determining performance date - {e}[/red]")
            failed_count += 1
            continue

        # Check if trading day is complete
        if not calculator.is_trading_day_complete(performance_date):
            result_info = {
                'symbol': symbol,
                'status': 'skipped',
                'reason': f"Trading day not complete (need data for {performance_date})"
            }
            date_results.append(result_info)
            skipped_incomplete += 1
            continue

        # Calculate performance
        console.print(f"  {symbol}: Fetching performance data...", end=" ")

        try:
            performance = calculator.calculate_performance(
                gap_result=gap_result,
                symbol=symbol,
                performance_date=performance_date
            )

            if not performance:
                console.print("[red]✗ No data available[/red]")
                result_info = {
                    'symbol': symbol,
                    'status': 'failed',
                    'reason': 'No data available'
                }
                date_results.append(result_info)
                failed_count += 1
                continue

            # Save to database (unless dry-run)
            if not dry_run:
                # Convert GapPerformance domain model to SQLModel
                from models.sqlmodel.gap_candidate_result_sqlmodel import GapCandidateResultSQLModel
                from datetime import datetime

                performance_sql = GapCandidateResultSQLModel(
                    gap_result_id=performance.gap_result_id,
                    entry_price=performance.entry_price,
                    exit_price=performance.exit_price,
                    max_intraday_price=performance.max_intraday_price,
                    min_intraday_price=performance.min_intraday_price,
                    realized_return_pct=performance.realized_return_pct,
                    max_drawdown_pct=performance.max_drawdown_pct,
                    max_upside_pct=performance.max_upside_pct,
                    gap_filled=performance.gap_filled,
                    gap_fill_timestamp=performance.gap_fill_timestamp,
                    outcome=performance.outcome.value if performance.outcome else None,
                    trade_taken=False,
                    updated_at=datetime.utcnow()
                )

                try:
                    perf_result = data_service.gap_candidate_result_repository.upsert(performance_sql)
                    if not perf_result:
                        console.print("[red]✗ Failed to save[/red]")
                        failed_count += 1
                        continue
                except Exception as e:
                    console.print(f"[red]✗ Failed to save: {e}[/red]")
                    failed_count += 1
                    continue

            console.print("[green]✓[/green]")

            # Store result for summary
            result_info = {
                'symbol': symbol,
                'status': 'updated' if not dry_run else 'dry-run',
                'performance': performance
            }
            date_results.append(result_info)

            # Collect for overall statistics (convert to dict format)
            all_performance_for_stats.append({
                'session_type': session_type,
                'gap_direction': gap_result.get('gap_direction', 'unknown'),
                'gap_percentage': gap_result.get('gap_percentage', 0),
                'academic_gap_type': gap_result.get('academic_gap_type'),
                'performance': {
                    'realized_return_pct': performance.realized_return_pct,
                    'gap_filled': performance.gap_filled
                }
            })
            updated_count += 1

        except Exception as e:
            console.print(f"[red]✗ {e}[/red]")
            result_info = {
                'symbol': symbol,
                'status': 'failed',
                'reason': str(e)
            }
            date_results.append(result_info)
            failed_count += 1

    # Display last date results
    if current_date and date_results:
        perf_display = app_context.presentation.gap_performance_adapter
        perf_display.display_date_performance(current_date, date_results)

    # Display overall statistics
    if all_performance_for_stats:
        console.print("")  # Spacing
        perf_display = app_context.presentation.gap_performance_adapter
        perf_display.display_performance_statistics(all_performance_for_stats)

    # Summary
    console.print("\n" + "=" * 60)
    console.print("\n[bold]Summary:[/bold]")
    if dry_run:
        console.print(f"  [yellow]Dry run - no data saved[/yellow]")
    console.print(f"  Updated: {updated_count} records")
    console.print(f"  Skipped (incomplete day): {skipped_incomplete} records")
    console.print(f"  Skipped (already exists): {skipped_exists} records")
    console.print(f"  Failed (API errors): {failed_count} records")

    # Performance statistics
    if updated_count > 0 and not dry_run:
        stats = data_service.gap_candidate_result_repository.get_statistics()
        if stats:
            console.print(f"\n[bold]Performance Statistics ({stats['total_records']} gaps):[/bold]")

            outcomes = stats.get('by_outcome', {})
            winners = outcomes.get('winner', 0)
            losers = outcomes.get('loser', 0)
            breakeven = outcomes.get('breakeven', 0)
            not_traded = outcomes.get('not_traded', 0)
            total = winners + losers + breakeven

            if total > 0:
                console.print(f"  Winners (≥2%):       {winners} ({100*winners/total:.1f}%)")
                console.print(f"  Losers (≤-1%):       {losers} ({100*losers/total:.1f}%)")
                console.print(f"  Breakeven (-1-2%):   {breakeven} ({100*breakeven/total:.1f}%)")
                if not_traded > 0:
                    console.print(f"  Not traded:          {not_traded}")

                console.print(f"\n  Incomplete records:  {stats.get('incomplete_records', 0)}")


