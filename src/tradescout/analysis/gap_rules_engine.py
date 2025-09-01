"""
Gap Rules Engine Implementation

Implements the six-step binary classification rules from GAP_TRADING_STRATEGY_RULES.md
Based on academic research for systematic gap trading decisions.
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional

from ..data_models.domain_models_core import MarketQuote
from ..data_models.domain_models_analysis import GapType

logger = logging.getLogger(__name__)


class GapRulesEngine:
    """
    Binary classification engine for gap trading decisions

    Implements the six-step academic research-based decision tree:
    1. Gap size >= 2.0%
    2. Volume ratio >= 2.0x
    3. Market cap >= $1B
    4. Bid-ask spread <= 1.0%
    5. NOT exhaustion gap
    6. NOT Friday gap
    """

    def __init__(self):
        """Initialize gap rules engine with academic thresholds"""
        # Academic research thresholds
        self.min_gap_size = Decimal("2.0")  # 2% minimum gap
        self.min_volume_ratio = Decimal("2.0")  # 2x average volume
        self.min_market_cap = 1_000_000_000  # $1B minimum market cap
        self.max_bid_ask_spread = Decimal("1.0")  # 1% maximum spread
        self.exhaustion_gap_size = Decimal("5.0")  # 5% exhaustion threshold
        self.exhaustion_trend_days = 20  # 20-day trend age threshold
        self.exhaustion_volume_ratio = Decimal("3.0")  # 3x volume for exhaustion

    def evaluate_gap_candidate(
        self,
        quote: MarketQuote,
        volume_data: Optional[Dict[str, Decimal]] = None,
        market_context: Optional[Dict[str, any]] = None,
    ) -> Dict[str, any]:
        """
        Evaluate gap candidate through six-step binary decision tree

        Args:
            quote: Market quote with gap information
            volume_data: Volume analysis data
            market_context: Additional market context

        Returns:
            Dictionary with evaluation results and reasoning
        """
        logger.debug(f"Evaluating gap candidate: {quote.asset.symbol}")

        result = {
            "symbol": quote.asset.symbol,
            "decision": "REJECT",  # Default to reject
            "reasons": [],
            "step_results": {},
            "final_score": 0,
            "trade_recommendation": None,
        }

        # Extract gap information
        gap_size = getattr(quote, "gap_size", None)
        if gap_size is None:
            # Try to calculate from price change
            gap_size = abs(quote.price_change_percent or Decimal(0))

        volume_ratio = self._get_volume_ratio(quote, volume_data)

        # Step 1: Is gap >= 2.0%?
        step1_pass = self._step1_gap_size_check(gap_size, result)
        if not step1_pass:
            return result

        # Step 2: Is volume >= 2.0x average?
        step2_pass = self._step2_volume_check(volume_ratio, result)
        if not step2_pass:
            return result

        # Step 3: Is market cap >= $1B?
        step3_pass = self._step3_market_cap_check(quote, market_context, result)
        if not step3_pass:
            return result

        # Step 4: Is spread <= 1.0%?
        step4_pass = self._step4_spread_check(quote, result)
        if not step4_pass:
            return result

        # Step 5: Is it NOT an exhaustion gap?
        step5_pass = self._step5_exhaustion_check(quote, gap_size, volume_ratio, result)
        if not step5_pass:
            return result

        # Step 6: Is it NOT Friday?
        step6_pass = self._step6_friday_check(result)
        if not step6_pass:
            return result

        # All steps passed - TRADE IT!
        result["decision"] = "TRADE"
        result["reasons"].append("✅ Passed all 6 decision criteria")
        result["final_score"] = self._calculate_quality_score(
            quote, gap_size, volume_ratio
        )
        result["trade_recommendation"] = self._generate_trade_recommendation(
            quote, gap_size
        )

        logger.info(
            f"Gap candidate {quote.asset.symbol} APPROVED for trading "
            f"(score: {result['final_score']:.1f})"
        )

        return result

    def _step1_gap_size_check(self, gap_size: Decimal, result: Dict) -> bool:
        """Step 1: Is gap >= 2.0%?"""
        step_name = "Step 1: Gap Size >= 2.0%"

        if gap_size >= self.min_gap_size:
            result["step_results"][step_name] = "✅ PASS"
            result["reasons"].append(f"✅ Gap size {gap_size:.2f}% meets minimum 2.0%")
            return True
        else:
            result["step_results"][step_name] = "❌ FAIL"
            result["reasons"].append(f"❌ Gap size {gap_size:.2f}% below minimum 2.0%")
            result["decision"] = "REJECT"
            return False

    def _step2_volume_check(
        self, volume_ratio: Optional[Decimal], result: Dict
    ) -> bool:
        """Step 2: Is volume >= 2.0x average?"""
        step_name = "Step 2: Volume Ratio >= 2.0x"

        if volume_ratio is None:
            result["step_results"][step_name] = "❌ FAIL"
            result["reasons"].append("❌ Volume ratio data not available")
            result["decision"] = "REJECT"
            return False

        if volume_ratio >= self.min_volume_ratio:
            result["step_results"][step_name] = "✅ PASS"
            result["reasons"].append(
                f"✅ Volume ratio {volume_ratio:.1f}x meets minimum 2.0x"
            )
            return True
        else:
            result["step_results"][step_name] = "❌ FAIL"
            result["reasons"].append(
                f"❌ Volume ratio {volume_ratio:.1f}x below minimum 2.0x"
            )
            result["decision"] = "REJECT"
            return False

    def _step3_market_cap_check(
        self, quote: MarketQuote, market_context: Optional[Dict], result: Dict
    ) -> bool:
        """Step 3: Is market cap >= $1B?"""
        step_name = "Step 3: Market Cap >= $1B"

        # Try to get market cap from various sources
        market_cap = None

        if hasattr(quote, "market_cap") and quote.market_cap:
            market_cap = quote.market_cap
        elif market_context and "market_cap" in market_context:
            market_cap = market_context["market_cap"]

        if market_cap is None:
            # If we can't determine market cap, we'll allow it but note the limitation
            result["step_results"][step_name] = "⚠️ UNKNOWN"
            result["reasons"].append(
                "⚠️ Market cap data not available - proceeding with caution"
            )
            return True

        if market_cap >= self.min_market_cap:
            market_cap_str = f"${market_cap/1_000_000_000:.1f}B"
            result["step_results"][step_name] = "✅ PASS"
            result["reasons"].append(
                f"✅ Market cap {market_cap_str} meets minimum $1B"
            )
            return True
        else:
            market_cap_str = f"${market_cap/1_000_000:.0f}M"
            result["step_results"][step_name] = "❌ FAIL"
            result["reasons"].append(
                f"❌ Market cap {market_cap_str} below minimum $1B"
            )
            result["decision"] = "REJECT"
            return False

    def _step4_spread_check(self, quote: MarketQuote, result: Dict) -> bool:
        """Step 4: Is spread <= 1.0%?"""
        step_name = "Step 4: Bid-Ask Spread <= 1.0%"

        # Calculate spread if we have bid/ask data
        bid_ask_spread = None

        if hasattr(quote, "bid") and hasattr(quote, "ask") and quote.bid and quote.ask:
            spread_dollars = float(quote.ask - quote.bid)
            spread_percent = (spread_dollars / float(quote.price_data.price)) * 100
            bid_ask_spread = Decimal(spread_percent)

        if bid_ask_spread is None:
            # If we can't determine spread, assume it's reasonable for now
            result["step_results"][step_name] = "⚠️ UNKNOWN"
            result["reasons"].append(
                "⚠️ Bid-ask spread data not available - assuming reasonable"
            )
            return True

        if bid_ask_spread <= self.max_bid_ask_spread:
            result["step_results"][step_name] = "✅ PASS"
            result["reasons"].append(
                f"✅ Bid-ask spread {bid_ask_spread:.2f}% within 1.0% limit"
            )
            return True
        else:
            result["step_results"][step_name] = "❌ FAIL"
            result["reasons"].append(
                f"❌ Bid-ask spread {bid_ask_spread:.2f}% exceeds 1.0% limit"
            )
            result["decision"] = "REJECT"
            return False

    def _step5_exhaustion_check(
        self,
        quote: MarketQuote,
        gap_size: Decimal,
        volume_ratio: Optional[Decimal],
        result: Dict,
    ) -> bool:
        """Step 5: Is it NOT an exhaustion gap?"""
        step_name = "Step 5: NOT Exhaustion Gap"

        # Exhaustion gap criteria: gap >= 5% AND trend >= 20 days AND volume >= 3x
        is_exhaustion = False
        exhaustion_reasons = []

        # Check gap size component
        if gap_size >= self.exhaustion_gap_size:
            exhaustion_reasons.append(f"Large gap size {gap_size:.2f}% >= 5%")

            # Check volume component
            if volume_ratio and volume_ratio >= self.exhaustion_volume_ratio:
                exhaustion_reasons.append(f"High volume {volume_ratio:.1f}x >= 3x")

                # Note: We would need trend analysis to check 20-day trend age
                # For now, we'll be conservative with large gaps + high volume
                if gap_size >= 5.0 and volume_ratio >= 3.0:
                    is_exhaustion = True
                    exhaustion_reasons.append(
                        "Conservative exhaustion pattern detected"
                    )

        if is_exhaustion:
            result["step_results"][step_name] = "❌ FAIL"
            result["reasons"].append(
                f"❌ Exhaustion gap detected: {', '.join(exhaustion_reasons)}"
            )
            result["decision"] = "REJECT"
            return False
        else:
            result["step_results"][step_name] = "✅ PASS"
            result["reasons"].append("✅ Not classified as exhaustion gap")
            return True

    def _step6_friday_check(self, result: Dict) -> bool:
        """Step 6: Is it NOT Friday?"""
        step_name = "Step 6: NOT Friday"

        current_day = datetime.now().weekday()  # 0=Monday, 6=Sunday
        is_friday = current_day == 4  # Friday = 4

        if is_friday:
            result["step_results"][step_name] = "❌ FAIL"
            result["reasons"].append("❌ Friday gaps avoided due to weekend risk")
            result["decision"] = "REJECT"
            return False
        else:
            day_names = [
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            ]
            result["step_results"][step_name] = "✅ PASS"
            result["reasons"].append(f"✅ {day_names[current_day]} trading allowed")
            return True

    def _get_volume_ratio(
        self, quote: MarketQuote, volume_data: Optional[Dict[str, Decimal]]
    ) -> Optional[Decimal]:
        """Extract volume ratio from various data sources"""

        # Try to get from quote attributes first
        if hasattr(quote, "volume_ratio") and quote.volume_ratio:
            return quote.volume_ratio

        # Try to get from volume_data parameter
        if volume_data and "volume_ratio" in volume_data:
            return volume_data["volume_ratio"]

        # Try to calculate from quote if we have average volume
        if hasattr(quote, "average_volume") and quote.average_volume:
            if quote.price_data.volume and quote.average_volume > 0:
                return Decimal(quote.price_data.volume) / Decimal(quote.average_volume)

        return None

    def _calculate_quality_score(
        self, quote: MarketQuote, gap_size: Decimal, volume_ratio: Optional[Decimal]
    ) -> float:
        """
        Calculate gap quality score (0-100) based on academic research

        Score components:
        - Gap size: 40 points max
        - Volume ratio: 25 points max
        - Catalyst strength: 20 points max (placeholder)
        - Sector alignment: 10 points max (placeholder)
        - Market alignment: 5 points max (placeholder)
        """
        score = 0.0

        # Gap size component (40 points max)
        if gap_size >= Decimal("2.0"):
            score += min(40, float(gap_size) * 8)  # 8 points per percent

        # Volume component (25 points max)
        if volume_ratio and volume_ratio >= Decimal("2.0"):
            score += min(25, (float(volume_ratio) - 1) * 12.5)

        # Placeholder for catalyst scoring (20 points)
        score += 10  # Assume moderate catalyst for now

        # Placeholder for sector alignment (10 points)
        score += 5  # Assume some sector alignment

        # Placeholder for market alignment (5 points)
        score += 3  # Assume reasonable market conditions

        return min(100.0, score)

    def _generate_trade_recommendation(
        self, quote: MarketQuote, gap_size: Decimal
    ) -> Dict[str, any]:
        """Generate basic trade recommendation"""

        gap_direction = getattr(quote, "gap_direction", "up")
        current_price = float(quote.price_data.price)

        # Basic position sizing (2% max risk)
        risk_percent = 0.02  # 2% max account risk

        # Basic stop loss (gap fill level or 2% below entry)
        if gap_direction == "up":
            # For gap up, stop at gap fill (previous close) or 2% below
            stop_loss_price = current_price * 0.98  # 2% below entry
        else:
            # For gap down, stop at gap fill or 2% above
            stop_loss_price = current_price * 1.02  # 2% above entry

        # Basic take profit targets (1:1 and 2:1 risk/reward)
        risk_amount = abs(current_price - stop_loss_price)
        take_profit_1 = current_price + risk_amount  # 1:1
        take_profit_2 = current_price + (risk_amount * 2)  # 2:1

        return {
            "entry_price": current_price,
            "stop_loss": stop_loss_price,
            "take_profit_1": take_profit_1,
            "take_profit_2": take_profit_2,
            "risk_reward_ratio_1": 1.0,
            "risk_reward_ratio_2": 2.0,
            "position_sizing": risk_percent,
            "trade_direction": "long" if gap_direction == "up" else "short",
            "holding_period": "intraday",  # Academic requirement
            "mandatory_exit": "16:00 ET",  # No overnight holds
        }

    def batch_evaluate_candidates(
        self, candidates: List[MarketQuote]
    ) -> List[Dict[str, any]]:
        """
        Evaluate multiple gap candidates efficiently

        Args:
            candidates: List of gap candidate quotes

        Returns:
            List of evaluation results sorted by quality score
        """
        logger.info(f"Batch evaluating {len(candidates)} gap candidates")

        results = []

        for quote in candidates:
            try:
                evaluation = self.evaluate_gap_candidate(quote)
                results.append(evaluation)

            except Exception as e:
                logger.error(f"Error evaluating candidate {quote.asset.symbol}: {e}")
                continue

        # Sort by quality score (highest first)
        approved_results = [r for r in results if r["decision"] == "TRADE"]
        approved_results.sort(key=lambda x: x["final_score"], reverse=True)

        # Add rejected results at the end
        rejected_results = [r for r in results if r["decision"] == "REJECT"]
        final_results = approved_results + rejected_results

        logger.info(
            f"Batch evaluation complete: {len(approved_results)} approved, "
            f"{len(rejected_results)} rejected"
        )

        return final_results
