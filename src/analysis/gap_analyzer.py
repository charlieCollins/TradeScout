"""Gap analysis for TradeScout trading system.

Implements the gap trading workflow from docs/GAP_ANALYSIS_MANUAL_WORKFLOW.md:
1. Find gap candidates (price + market cap filters)
2. Calculate volume ratios using Aggregates API
3. Calculate quality scores (0-100)
4. Filter exhaustion gaps
5. Assess weekend/holiday risks
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import date

from models.dataclass.gap import GapCandidate, GapDirection, GapSignificance, RiskLevel
from models.dataclass.market_context import MarketContext, MarketSession
from utils.config_loader import get_config_loader

logger = logging.getLogger(__name__)


class GapAnalyzer:
    """Analyzes gaps for trading opportunities using new architecture.

    Uses DataService pattern:
    - All database queries and API calls via DataService
    - Session-aware gap calculations (premarket vs after-hours)
    - Quality scoring from academic gap trading strategy
    """

    def __init__(self, data_service):
        """Initialize gap analyzer with data service.

        Args:
            data_service: DataService instance for database access and API calls
        """
        self.data_service = data_service

        # Load gap trading configuration
        config_loader = get_config_loader()
        self.config = config_loader.load_gap_trading_config()

    def find_gap_candidates(
        self,
        universe_symbols: List[str],
        market_context: MarketContext,
        min_gap_pct: Optional[float] = None,
        min_market_cap: Optional[float] = None
    ) -> List[GapCandidate]:
        """Find gap candidates from active universe (Steps 2-3 of workflow).

        Queries database for symbols with:
        - Gap ≥ min_gap_pct (session-aware calculation)
        - Market cap ≥ min_market_cap
        - Volume data available

        Uses ONLY the latest asset_price record per symbol (MAX(id) filter).

        Args:
            universe_symbols: List of symbols in active universe
            market_context: Market context for session detection
            min_gap_pct: Minimum gap percentage (default: from config)
            min_market_cap: Minimum market cap (default: from config)

        Returns:
            List of gap candidates meeting criteria, sorted by gap size

        Raises:
            ValueError: If session is not premarket or afterhours
        """
        # Use config defaults if not provided
        if min_gap_pct is None:
            min_gap_pct = self.config['minimum_criteria']['gap_percent']
        if min_market_cap is None:
            min_market_cap = self.config['minimum_criteria']['market_cap']

        session = market_context.session_name

        if session not in ["premarket", "afterhours"]:
            raise ValueError(
                f"Gap analysis only works during premarket/afterhours. "
                f"Current session: {session}"
            )

        logger.info(
            f"Finding gap candidates: {len(universe_symbols)} symbols, "
            f"session={session}, min_gap={min_gap_pct}%, min_mcap=${min_market_cap/1e9:.1f}B"
        )

        # Query database for gap candidates
        # Uses session-aware gap calculation:
        # - Premarket: (min.c - prevDay.c) / prevDay.c
        # - After-hours: (min.c - day.c) / day.c

        if session == "premarket":
            # Premarket gap: current vs yesterday's close
            query = """
                SELECT
                    ap.symbol,
                    a.name,
                    ap.min_close as current_price,
                    ap.prevday_close as reference_price,
                    ap.prevday_volume,
                    af.market_cap,
                    ((ap.min_close - ap.prevday_close) / ap.prevday_close * 100) as gap_pct,
                    ap.prevday_high,
                    ap.prevday_low
                FROM asset_prices ap
                JOIN assets a ON ap.symbol = a.symbol
                LEFT JOIN asset_fundamentals af ON a.id = af.asset_id
                JOIN universe_memberships um ON a.id = um.asset_id
                JOIN universes u ON um.universe_id = u.id
                WHERE u.is_active = 1
                    AND ap.symbol IN ({})
                    AND ap.prevday_close IS NOT NULL
                    AND ap.prevday_close > 0
                    AND ap.min_close IS NOT NULL
                    AND ap.min_close > 0
                    AND ap.prevday_volume IS NOT NULL
                    AND ap.prevday_volume > 0
                    AND af.market_cap >= ?
                    AND ABS((ap.min_close - ap.prevday_close) / ap.prevday_close * 100) >= ?
                    AND ap.id IN (
                        SELECT MAX(id)
                        FROM asset_prices
                        GROUP BY symbol
                    )
                ORDER BY ABS((ap.min_close - ap.prevday_close) / ap.prevday_close * 100) DESC
            """.format(','.join('?' * len(universe_symbols)))

            params = universe_symbols + [min_market_cap, min_gap_pct]

        else:  # afterhours
            # After-hours gap: current vs today's 4PM close
            query = """
                SELECT
                    ap.symbol,
                    a.name,
                    ap.min_close as current_price,
                    ap.day_close as reference_price,
                    ap.prevday_volume,
                    af.market_cap,
                    ((ap.min_close - ap.day_close) / ap.day_close * 100) as gap_pct,
                    ap.day_high,
                    ap.day_low,
                    ap.day_volume
                FROM asset_prices ap
                JOIN assets a ON ap.symbol = a.symbol
                LEFT JOIN asset_fundamentals af ON a.id = af.asset_id
                JOIN universe_memberships um ON a.id = um.asset_id
                JOIN universes u ON um.universe_id = u.id
                WHERE u.is_active = 1
                    AND ap.symbol IN ({})
                    AND ap.day_close IS NOT NULL
                    AND ap.day_close > 0
                    AND ap.min_close IS NOT NULL
                    AND ap.min_close > 0
                    AND ap.prevday_volume IS NOT NULL
                    AND ap.prevday_volume > 0
                    AND af.market_cap >= ?
                    AND ABS((ap.min_close - ap.day_close) / ap.day_close * 100) >= ?
                    AND ap.id IN (
                        SELECT MAX(id)
                        FROM asset_prices
                        GROUP BY symbol
                    )
                ORDER BY ABS((ap.min_close - ap.day_close) / ap.day_close * 100) DESC
            """.format(','.join('?' * len(universe_symbols)))

            params = universe_symbols + [min_market_cap, min_gap_pct]

        rows = self.data_service.execute_query(query, params)

        # Convert rows to GapCandidate objects
        candidates = []
        for row in rows:
            symbol = row[0]
            name = row[1]
            current_price = float(row[2])
            reference_price = float(row[3])
            prevday_volume = int(row[4])
            market_cap = float(row[5])
            gap_pct = float(row[6])
            ref_high = float(row[7]) if row[7] else None
            ref_low = float(row[8]) if row[8] else None

            # After-hours queries include day_volume as row[9]
            day_volume = int(row[9]) if session == "afterhours" and len(row) > 9 and row[9] else None

            gap_amount = current_price - reference_price
            direction = GapDirection.UP if gap_amount > 0 else GapDirection.DOWN
            significance = self._determine_significance(abs(gap_pct))

            candidate = GapCandidate(
                symbol=symbol,
                name=name,
                current_price=current_price,
                reference_price=reference_price,
                gap_amount=gap_amount,
                gap_percent=gap_pct,
                direction=direction,
                significance=significance,
                market_cap=market_cap,
                prevday_volume=prevday_volume,
                day_volume=day_volume,
                session=session,
                prevday_close=reference_price,  # For premarket: prevday.close, for afterhours: day.close
                prevday_high=ref_high,
                prevday_low=ref_low
            )
            candidates.append(candidate)

        logger.info(f"Found {len(candidates)} gap candidates meeting criteria")
        return candidates

    def calculate_volume_ratio(
        self,
        candidate: GapCandidate,
        trading_date: date,
        analysis_time=None
    ) -> Optional[float]:
        """Calculate volume ratio using Aggregates API (Step 4 of workflow).

        Uses data service to get accurate extended hours volume (trade-eligible only),
        then calculates ratio vs recent hourly average using ELAPSED session time.

        IMPORTANT: Uses elapsed session time, not full session. If analyzing at 5:30 PM
        during after-hours, only 1.5 hours have elapsed (4:00-5:30), not the full 4 hours.

        Baseline selection:
        - Premarket: Uses prevday_volume (yesterday's regular hours pace)
        - After-hours: Uses day_volume (today's regular hours pace - more recent)

        Args:
            candidate: Gap candidate with volume data
            trading_date: Trading date for volume query
            analysis_time: Time of analysis (defaults to now)

        Returns:
            Volume ratio (e.g., 2.5 = 2.5x hourly average for elapsed time)
            Or None if volume data unavailable
        """
        from datetime import datetime, time

        try:
            # Query for extended hours volume via data service
            agg_volume = self.data_service.calculate_extended_hours_volume(
                symbol=candidate.symbol,
                trading_date=trading_date,
                session=candidate.session
            )

            if agg_volume is None:
                logger.warning(f"{candidate.symbol}: No aggregates volume data")
                return None

            # Determine baseline volume (session-aware)
            if candidate.session == "premarket":
                baseline_volume = candidate.prevday_volume
            else:  # afterhours
                baseline_volume = candidate.day_volume if candidate.day_volume else candidate.prevday_volume
                if not candidate.day_volume:
                    logger.warning(f"{candidate.symbol}: No day_volume available, falling back to prevday_volume")

            if not baseline_volume or baseline_volume <= 0:
                logger.warning(f"{candidate.symbol}: Invalid baseline volume")
                return None

            # Calculate elapsed session time
            if analysis_time is None:
                analysis_time = datetime.now()

            current_time = analysis_time.time()

            # Determine session start/end times
            if candidate.session == "premarket":
                # Premarket: 4:00 AM - 9:30 AM
                session_start = time(4, 0)
                session_end = time(9, 30)
            else:  # afterhours
                # After-hours: 4:00 PM - 8:00 PM
                session_start = time(16, 0)
                session_end = time(20, 0)

            # Calculate elapsed time since session start
            start_minutes = session_start.hour * 60 + session_start.minute
            current_minutes = current_time.hour * 60 + current_time.minute
            end_minutes = session_end.hour * 60 + session_end.minute

            elapsed_minutes = current_minutes - start_minutes

            # Cap at full session length
            max_session_minutes = end_minutes - start_minutes
            elapsed_minutes = min(elapsed_minutes, max_session_minutes)

            # If negative or zero, something is wrong
            if elapsed_minutes <= 0:
                logger.warning(
                    f"{candidate.symbol}: Invalid elapsed time ({elapsed_minutes} minutes) - "
                    f"current={current_time}, session_start={session_start}"
                )
                return None

            elapsed_hours = elapsed_minutes / 60.0

            # Calculate volume ratio vs hourly average for elapsed time
            regular_hours = self.config['session_hours']['regular']
            hourly_avg = baseline_volume / regular_hours
            expected_volume = hourly_avg * elapsed_hours
            volume_ratio = agg_volume / expected_volume if expected_volume > 0 else 0

            # Update candidate
            candidate.volume_ratio = volume_ratio
            candidate.extended_hours_volume = agg_volume

            logger.debug(
                f"{candidate.symbol}: Volume ratio - session={candidate.session}, "
                f"elapsed={elapsed_hours:.1f}h, baseline={baseline_volume:,}, "
                f"hourly_avg={hourly_avg:,.0f}, expected={expected_volume:,.0f}, "
                f"actual={agg_volume:,}, ratio={volume_ratio:.2f}x"
            )

            return volume_ratio

        except Exception as e:
            logger.error(f"Error calculating volume ratio for {candidate.symbol}: {e}")
            return None

    def calculate_quality_score(
        self,
        candidate: GapCandidate,
        market_aligned: bool = False,
        sector_aligned: bool = False
    ) -> int:
        """Calculate quality score (0-100) from gap trading strategy (Step 7 of workflow).

        Scoring formula (from config):
        - Gap size: Configurable max points
        - Volume: Configurable max points with thresholds
        - Catalyst: Configurable max points
        - Sector alignment: Configurable points
        - Market alignment: Configurable points

        Args:
            candidate: Gap candidate with volume_ratio and catalyst_score populated
            market_aligned: Whether gap aligns with overall market direction
            sector_aligned: Whether gap aligns with sector trend

        Returns:
            Quality score 0-100
        """
        score = 0
        scoring = self.config['quality_scoring']

        # Gap size (max points from config)
        gap_max = scoring['gap_size']['max_points']
        gap_mult = scoring['gap_size']['multiplier']
        score += min(gap_max, abs(candidate.gap_percent) * gap_mult)

        # Volume (max points from config)
        if candidate.volume_ratio:
            vol_max = scoring['volume']['max_points']
            vol_strong = scoring['volume']['thresholds']['strong']
            vol_min = scoring['volume']['thresholds']['minimum']
            mult_strong = scoring['volume']['multipliers']['strong']
            mult_min = scoring['volume']['multipliers']['minimum']

            if candidate.volume_ratio >= vol_strong:
                score += min(vol_max, (candidate.volume_ratio - 1) * mult_strong)
            elif candidate.volume_ratio >= vol_min:
                score += (candidate.volume_ratio - vol_min) * mult_min

        # Catalyst quality (max points from config)
        if candidate.catalyst_score:
            cat_max = scoring['catalyst']['max_points']
            cat_mult = scoring['catalyst']['multiplier']
            score += min(cat_max, candidate.catalyst_score * cat_mult)

        # Sector alignment (points from config)
        if sector_aligned:
            score += scoring['sector_alignment']['points']

        # Market alignment (points from config)
        if market_aligned:
            score += scoring['market_alignment']['points']

        # Determine risk level based on config thresholds
        risk_thresholds = self.config['risk_levels']
        if score >= risk_thresholds['low']:
            risk_level = RiskLevel.LOW
        elif score >= risk_thresholds['medium']:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.HIGH

        # Update candidate
        candidate.quality_score = int(min(100, score))
        candidate.risk_level = risk_level

        return candidate.quality_score

    def is_exhaustion_gap(self, candidate: GapCandidate) -> bool:
        """Check if gap is an exhaustion gap (Step 6 of workflow).

        Exhaustion gap criteria (from config and academic research):
        - Gap ≥ configured threshold
        - Recent trend ≥ 20 days (requires historical data - not implemented yet)
        - Volume ratio ≥ configured threshold

        Note: Currently only checks gap and volume. Historical trend check
        requires additional data not available in snapshot API.

        Args:
            candidate: Gap candidate with volume_ratio

        Returns:
            True if exhaustion gap (should be rejected), False otherwise
        """
        exhaustion = self.config['exhaustion_gap']
        min_gap = exhaustion['min_gap_percent']
        min_vol = exhaustion['min_volume_ratio']

        if abs(candidate.gap_percent) >= min_gap and candidate.volume_ratio and candidate.volume_ratio >= min_vol:
            logger.warning(
                f"{candidate.symbol}: Possible exhaustion gap "
                f"(gap={candidate.gap_percent:.1f}%, vol_ratio={candidate.volume_ratio:.1f}x)"
            )
            return True

        return False

    def is_friday_gap(self, trading_date: date) -> bool:
        """Check if gap occurs on Friday (weekend risk filter).

        Academic research shows Friday gaps have higher risk due to:
        - 2-3 day gap until next trading session
        - Weekend news can invalidate thesis
        - Lower fill rates on Monday

        Args:
            trading_date: Date of the gap

        Returns:
            True if Friday (should be rejected), False otherwise
        """
        # 4 = Friday (Monday=0, Sunday=6)
        return trading_date.weekday() == 4

    def classify_academic_gap_type(self, candidate: GapCandidate) -> str:
        """Classify gap using academic taxonomy (simplified version).

        Academic gap types from research (full classification requires trend analysis):
        - Common: <2.0% (noise, low probability)
        - Breakaway: ≥2.0%, breaking consolidation (requires trend data)
        - Continuation: ≥2.0%, within trend (requires trend data)
        - Exhaustion: ≥5.0%, end of extended trend (requires trend age data)

        Current simplified classification (based on gap size only):
        - 'common': <2.0%
        - 'breakaway_continuation': 2.0-4.9% (can't differentiate without trend)
        - 'exhaustion_candidate': ≥5.0% (possible exhaustion, pending trend confirmation)

        Args:
            candidate: Gap candidate with gap_percent

        Returns:
            Academic gap type classification string
        """
        gap_size = abs(candidate.gap_percent)

        if gap_size < 2.0:
            return "common"
        elif gap_size < 5.0:
            return "breakaway_continuation"
        else:
            return "exhaustion_candidate"

    def _determine_significance(self, gap_percent: float) -> GapSignificance:
        """Determine gap significance level from config thresholds."""
        thresholds = self.config['gap_significance']

        if gap_percent >= thresholds['major']:
            return GapSignificance.MAJOR
        elif gap_percent >= thresholds['significant']:
            return GapSignificance.SIGNIFICANT
        elif gap_percent >= thresholds['moderate']:
            return GapSignificance.MODERATE
        else:
            return GapSignificance.MINOR
