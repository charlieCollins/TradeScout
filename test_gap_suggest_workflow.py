#!/usr/bin/env python3
"""
Test Gap Trading Suggest Workflow

Tests the end-to-end gap trading suggestion system with synthetic data
to validate the implementation works correctly.
"""

import sys
import os
from datetime import datetime
from decimal import Decimal

# Add project root to path
sys.path.insert(0, '/home/ccollins/projects/TradeScout')

from src.tradescout.data_models.domain_models_core import Asset, AssetType, MarketQuote, PriceData
from src.tradescout.data_models.factories import MarketFactory
from src.tradescout.analysis.gap_market_scanner import GapMarketScanner
from src.tradescout.analysis.gap_rules_engine import GapRulesEngine
from src.tradescout.analysis.academic_gap_analyzer import AcademicGapTypeAnalyzer
from src.tradescout.analysis.gap_suggestion_engine import GapTradeSuggestionEngine

def create_test_quote(symbol: str, price: float, gap_percent: float, volume_ratio: float = 2.5):
    """Create a test market quote with gap information"""
    
    nasdaq_market = MarketFactory().create_nasdaq_market()
    asset = Asset(
        symbol=symbol,
        name=f"{symbol} Corp",
        asset_type=AssetType.COMMON_STOCK,
        market=nasdaq_market,
        currency="USD"
    )
    
    price_data = PriceData(
        asset=asset,
        timestamp=datetime.now(),
        price=Decimal(str(price)),
        volume=int(1_000_000 * volume_ratio)  # Synthetic volume
    )
    
    # Calculate previous close from gap percentage
    previous_close = Decimal(str(price / (1 + gap_percent / 100)))
    
    quote = MarketQuote(
        asset=asset,
        price_data=price_data,
        previous_close=previous_close,
        average_volume=int(1_000_000 * 2.0)  # Base volume for ratio calculation
    )
    
    # Add gap-specific attributes
    quote.gap_size = Decimal(str(abs(gap_percent)))
    quote.gap_direction = "up" if gap_percent > 0 else "down"
    quote.volume_ratio = Decimal(str(volume_ratio))
    quote.market_cap = 50_000_000_000  # $50B market cap
    
    return quote

def test_gap_trading_workflow():
    """Test the complete gap trading suggestion workflow"""
    
    print("🧪 Testing Gap Trading Suggestion Workflow")
    print("=" * 50)
    
    # Create synthetic gap candidates
    test_candidates = [
        # Good candidates that should pass rules
        create_test_quote("AAPL", 150.0, 3.2, 3.1),    # Gap up 3.2%, volume 3.1x
        create_test_quote("NVDA", 420.0, -2.8, 2.9),   # Gap down 2.8%, volume 2.9x
        create_test_quote("TSLA", 250.0, 4.1, 2.4),    # Gap up 4.1%, volume 2.4x
        
        # Candidates that should be rejected
        create_test_quote("XYZ", 10.0, 1.5, 1.2),      # Gap too small, volume too low
        create_test_quote("ABC", 5.0, 8.0, 4.5),       # Potential exhaustion gap
    ]
    
    print(f"📊 Created {len(test_candidates)} test gap candidates:")
    for quote in test_candidates:
        gap_size = getattr(quote, 'gap_size', 0)
        volume_ratio = getattr(quote, 'volume_ratio', 0)
        print(f"  • {quote.asset.symbol}: {gap_size:.1f}% gap, {volume_ratio:.1f}x volume")
    
    print("\n" + "="*50)
    
    # Test 1: Gap Rules Engine
    print("🔍 Step 1: Testing Gap Rules Engine")
    rules_engine = GapRulesEngine()
    
    approved_candidates = []
    for quote in test_candidates:
        evaluation = rules_engine.evaluate_gap_candidate(quote)
        decision = evaluation["decision"]
        print(f"  • {quote.asset.symbol}: {decision}")
        
        if decision == "TRADE":
            approved_candidates.append(quote)
    
    print(f"✅ {len(approved_candidates)}/{len(test_candidates)} candidates approved")
    
    # Test 2: Academic Gap Analyzer
    print(f"\n🎓 Step 2: Testing Academic Gap Type Analyzer")
    gap_analyzer = AcademicGapTypeAnalyzer()
    
    if approved_candidates:
        gap_assessments = gap_analyzer.batch_analyze_candidates(approved_candidates)
        
        for i, assessment in enumerate(gap_assessments):
            if i < len(approved_candidates):
                symbol = approved_candidates[i].asset.symbol
                tradeable = "✅ TRADEABLE" if assessment.is_tradeable else "❌ NOT TRADEABLE"
                strategy = assessment.recommended_strategy
                quality = assessment.overall_quality_score
                print(f"  • {symbol}: {tradeable} | Strategy: {strategy} | Quality: {quality:.1f}")
    else:
        print("  • No approved candidates to analyze")
        gap_assessments = []
    
    # Test 3: Suggestion Engine
    print(f"\n💡 Step 3: Testing Gap Suggestion Engine")
    suggestion_engine = GapTradeSuggestionEngine()
    
    suggestions = []
    for i, assessment in enumerate(gap_assessments):
        if i < len(approved_candidates) and assessment.is_tradeable:
            analysis_data = {
                "quote": approved_candidates[i],
                "gap_assessment": assessment
            }
            
            suggestion = suggestion_engine.generate_suggestion(
                approved_candidates[i].asset.symbol, 
                analysis_data
            )
            
            if suggestion and suggestion_engine.validate_suggestion(suggestion):
                suggestions.append(suggestion)
                
                symbol = suggestion.asset.symbol
                entry = suggestion.entry_price
                stop = suggestion.stop_loss
                target = suggestion.take_profit_1
                rr_ratio = suggestion.risk_reward_ratio
                confidence = suggestion.confidence.value
                
                print(f"  • {symbol}: Entry ${entry:.2f} | Stop ${stop:.2f} | Target ${target:.2f} | R:R {rr_ratio:.1f}:1 | {confidence}")
    
    print(f"✅ Generated {len(suggestions)} valid trade suggestions")
    
    # Test 4: Final Ranking and Filtering
    print(f"\n🏆 Step 4: Testing Suggestion Ranking")
    
    if suggestions:
        final_suggestions = suggestion_engine.filter_suggestions(suggestions, max_suggestions=3)
        
        print("📋 Final Ranked Suggestions:")
        for rank, suggestion in enumerate(final_suggestions, 1):
            symbol = suggestion.asset.symbol
            gap_size = getattr(suggestion, 'gap_size', 0)
            volume_ratio = getattr(suggestion, 'volume_ratio', 0)
            confidence = suggestion.confidence.value.upper()
            
            print(f"  {rank}. {symbol} - {gap_size:.1f}% gap, {volume_ratio:.1f}x vol, {confidence} confidence")
    else:
        print("  • No suggestions generated for ranking")
        final_suggestions = []
    
    # Summary
    print("\n" + "="*50)
    print("📈 Gap Trading Workflow Test Summary:")
    print(f"  • Initial Candidates: {len(test_candidates)}")
    print(f"  • Rules Engine Approved: {len(approved_candidates)}")
    print(f"  • Academic Analysis: {len(gap_assessments)} assessments")
    print(f"  • Valid Suggestions: {len(suggestions)}")
    print(f"  • Final Recommendations: {len(final_suggestions)}")
    
    if final_suggestions:
        print(f"✅ Workflow completed successfully!")
        print(f"🎯 Top recommendation: {final_suggestions[0].asset.symbol}")
        return True
    else:
        print(f"⚠️  No final recommendations generated")
        return False

if __name__ == "__main__":
    success = test_gap_trading_workflow()
    sys.exit(0 if success else 1)