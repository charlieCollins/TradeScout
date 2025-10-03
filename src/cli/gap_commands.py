"""
Gap Analysis CLI Commands

Provides CLI commands for gap trading analysis, combining screener results
with sophisticated gap and catalyst analysis.
"""

import click
import sys
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from .main import pass_config
from .asset_commands import display_market_context

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from screener.screener_engine import ScreenerEngine
from screener.screener_config import ScreenerConfig
from analysis.gap_analyzer import GapAnalyzer, GapCandidate, GapAssessment
from analysis.catalyst_analyzer import CatalystAnalyzer
from models.asset import Asset
from models.price import AssetPrice


console = Console()


@click.group()
def gap():
    """Gap trading analysis commands"""
    pass


@gap.command()
@click.option('--direction', type=click.Choice(['up', 'down', 'both']),
              default='both', help='Gap direction to analyze')
@click.option('--limit', default=20, help='Maximum number of candidates to show')
@pass_config
def candidates(config, direction, limit):
    """Find gap candidates using basic screeners"""

    # Display market context at the top
    display_market_context(config)

    # Just run the existing screeners - they already find gap candidates!
    console.print(f"🔍 Finding gap candidates using existing screeners...")

    if direction in ['up', 'both']:
        console.print("Running gapupcandidates screener...")
        console.print("Use: ./tradescout screener gapupcandidates")

    if direction in ['down', 'both']:
        console.print("Running gapdowncandidates screener...")
        console.print("Use: ./tradescout screener gapdowncandidates")

    console.print("\n💡 Gap candidates are found by running the gap screeners!")
    console.print("The screeners filter the universe and find stocks with ≥2% gaps")


@gap.command()
@click.argument('symbols', nargs=-1, required=True)
@pass_config
def analyze(config, symbols):
    """Analyze specific symbols for gap information"""

    # Display market context at the top
    display_market_context(config)

    try:
        data_service = config.get_data_service()

        console.print(f"🔍 Analyzing {len(symbols)} symbols for gap information...")

        for symbol in symbols:
            try:
                # Get current snapshot data
                snapshot = data_service.get_ticker_snapshot(symbol.upper())
                if not snapshot:
                    console.print(f"❌ No snapshot data available for {symbol}")
                    continue

                # Use typed snapshot data directly
                day_close = snapshot.close_price  # Day close price
                current_price = snapshot.last_price  # Current/last price

                if day_close and current_price:
                    gap_size = current_price - day_close
                    gap_percent = (gap_size / day_close) * 100

                    console.print(f"📊 {symbol.upper()}:")
                    console.print(f"   Current: ${current_price:.2f}")
                    console.print(f"   Day Close: ${day_close:.2f}")
                    console.print(f"   Gap: ${gap_size:+.2f} ({gap_percent:+.2f}%)")

                    if abs(gap_percent) >= 2.0:
                        console.print(f"   🎯 Significant gap candidate!")
                    console.print()
                else:
                    console.print(f"❌ Incomplete price data for {symbol}")

            except Exception as e:
                console.print(f"❌ Error analyzing {symbol}: {e}")

    except Exception as e:
        console.print(f"❌ Error in gap analysis: {e}")


@gap.command()
@pass_config
def setup(config):
    """Setup catalyst database with academic research-based scoring"""

    # Display market context at the top
    display_market_context(config)

    try:
        console.print("🔧 Setting up catalyst database...")
        console.print("📊 Academic research-based catalyst types will be configured:")
        console.print("   • FDA Approval (95 points)")
        console.print("   • Earnings Beat >10% (85 points)")
        console.print("   • M&A Announcement (75 points)")
        console.print("   • Earnings Beat 5-10% (70 points)")
        console.print("   • Analyst Upgrade (60 points)")
        console.print("   • And more...")
        console.print("✅ Setup placeholder complete!")
        console.print("💡 Full catalyst analysis will be implemented in future version")

    except Exception as e:
        console.print(f"❌ Error in setup: {e}")


def _display_basic_gap_results(results: List[dict], screener_name: str):
    """Display basic gap screening results in a formatted table"""

    if not results:
        console.print("📭 No results to display")
        return

    # Create table
    direction = "Up" if "up" in screener_name else "Down" if "down" in screener_name else "Gap"
    table = Table(title=f"🎯 Gap {direction} Candidates", show_header=True, header_style="bold magenta")

    table.add_column("Symbol", style="cyan", width=8)
    table.add_column("Current", justify="right", style="white", width=10)
    table.add_column("Day Close", justify="right", style="dim", width=10)
    table.add_column("Gap %", justify="right", style="green", width=8)
    table.add_column("Volume", justify="right", style="blue", width=10)
    table.add_column("Time", justify="right", style="dim", width=8)

    for result in results:
        # Calculate gap percentage for display
        gap_percent = 0
        if result.get('day_close') and result.get('min_close'):
            gap_percent = ((result['min_close'] - result['day_close']) / result['day_close']) * 100

        # Format gap percentage with color
        gap_text = f"{gap_percent:+.1f}%"
        gap_style = "bright_green" if gap_percent > 0 else "bright_red"

        # Format volume
        volume = result.get('min_volume', 0)
        if volume >= 1000000:
            volume_text = f"{volume/1000000:.1f}M"
        elif volume >= 1000:
            volume_text = f"{volume/1000:.0f}K"
        else:
            volume_text = str(volume)

        # Format time
        time_text = "N/A"
        if result.get('min_timestamp'):
            try:
                timestamp = datetime.fromtimestamp(result['min_timestamp'] / 1000)
                time_text = timestamp.strftime("%H:%M")
            except:
                time_text = "N/A"

        table.add_row(
            result.get('symbol', 'N/A'),
            f"${result.get('min_close', 0):.2f}",
            f"${result.get('day_close', 0):.2f}",
            Text(gap_text, style=gap_style),
            volume_text,
            time_text
        )

    console.print(table)

    # Add summary
    significant_gaps = sum(1 for r in results if abs(((r.get('min_close', 0) - r.get('day_close', 0)) / r.get('day_close', 1)) * 100) >= 2.0)
    console.print(f"\n📊 Found {len(results)} candidates, {significant_gaps} with ≥2% gaps")