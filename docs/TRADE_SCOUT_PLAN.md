# TradeScout - Personal Market Research Assistant

**Version:** 1.0  
**Date:** July 20, 2025  
**Platform:** Linux/WSL + IntelliJ IDEA  
**Budget:** $0-50/month maximum

---

## Mission Statement

TradeScout is a personal market research assistant that analyzes overnight market activity and provides morning trade suggestions with performance tracking. The system suggests trades based on analysis but leaves all execution decisions to the user.

**Key Principle:** TradeScout suggests, you decide. All trades are manually executed after your own verification.

---

## Core Features

### 1. Overnight Market Analysis
- **After-hours monitoring** (4:00 PM - 8:00 PM ET)
- **Pre-market analysis** (4:00 AM - 9:30 AM ET)
- **Volume surge detection** and price movement analysis
- **Gap identification** and momentum confirmation
- **News and sentiment analysis** during extended hours

### 2. Morning Trade Suggestions
- **Daily reports** with top 3-5 trade recommendations
- **Clear entry/exit points** with stop losses and profit targets
- **Risk assessment** and position sizing suggestions
- **Detailed rationale** with supporting data for each suggestion

### 3. Performance Tracking System
- **Suggestion Performance**: Track all recommendations (whether taken or not)
- **Actual Trade Log**: Manual entry for trades you execute
- **Comparative Analysis**: Side-by-side performance tracking
- **Strategy Refinement**: Win rate analysis and improvement insights

### 4. Research Dashboard
- **Real-time scanner** with customizable alerts
- **News sentiment analysis** and event detection
- **Technical analysis** with momentum indicators
- **Performance analytics** and pattern recognition

---

## Architecture & Technology

### Interface-First Design
```
External APIs → Adapter Layer → Internal Interfaces → Analysis Engine → Suggestions
```

- **No vendor lock-in**: All external data sources adapted to internal models
- **Easy testing**: Mock interfaces instead of external APIs
- **Flexible providers**: Switch data sources without changing business logic
- **Cloud-ready**: Seamless migration from local to cloud deployment

### Technology Stack
| Component | Local | Cloud Migration | Pattern |
|-----------|-------|-----------------|---------|
| **Database** | SQLite | PostgreSQL | Repository Pattern |
| **Data Sources** | yfinance + Polygon.io | Same APIs | Adapter Pattern |
| **Analysis** | Python algorithms | Same code | Strategy Pattern |
| **Scheduling** | Linux cron | Cloud Scheduler | Factory Pattern |
| **Web Interface** | Flask localhost | Cloud Run | Same codebase |

### Project Structure
```
TradeScout/
├── data_collection/    # External API adapters
├── analysis/          # Momentum detection & suggestion engine
├── storage/           # Repository pattern for data persistence
├── interface/         # Web dashboard & CLI tools
├── config/            # Environment & API key management
├── docs/              # Documentation & planning
└── scripts/           # Automation & cron jobs
```

---

## Data Sources Strategy

### Free Tier Foundation (Phase 1)
| Provider | Data Type | Cost | Rate Limit | Purpose |
|----------|-----------|------|------------|---------|
| **yfinance** | Real-time quotes, after-hours | FREE | Unlimited* | Primary market data |
| **Polygon.io FREE** | Fundamentals, historical | FREE | 5 calls/min | Enhanced analysis |
| **NewsAPI** | Global news aggregation | FREE | 1000/day | News catalyst detection |
| **Reddit API** | Social sentiment | FREE | 60/min | Retail sentiment analysis |

*Rate-limited by being respectful to Yahoo's servers

### Upgrade Path (Optional)
- **Month 3+**: Polygon.io Professional ($29/month)
- **Benefits**: Unlimited API calls + 15-minute delayed real-time data
- **Total Budget**: Still under $50/month

---

## Development Phases

### Phase 1: MVP Foundation (3-4 weeks) ✅ DESIGN COMPLETE
**Architecture & Interfaces**
- [x] Interface-first design completed
- [x] Data models and abstractions defined
- [x] Configuration and environment setup
- [x] Documentation structure established

**Next: Core Implementation**
- [ ] YFinance and Polygon.io adapters
- [ ] Basic momentum detection algorithm
- [ ] SQLite repository implementations
- [ ] Simple CLI interface
- [ ] Morning suggestion generation

### Phase 2: Enhanced Analysis (2-3 weeks)
**Advanced Features**
- [ ] News and sentiment integration
- [ ] Technical indicators (RSI, MACD, volume analysis)
- [ ] Historical pattern recognition
- [ ] Web dashboard with charts
- [ ] Email notification system

### Phase 3: Production Features (Ongoing)
**Optimization & Scaling**
- [ ] Performance optimization
- [ ] Machine learning integration
- [ ] Cloud migration capabilities
- [ ] Advanced risk management
- [ ] Mobile-responsive interface

---

## Algorithm Overview

### Overnight Analysis Workflow
```python
def run_overnight_analysis():
    # 1. Scan after-hours activity (4 PM - 8 PM ET)
    after_hours_movers = scan_after_hours_activity()
    
    # 2. Analyze pre-market gaps (4 AM - 9:30 AM ET)
    pre_market_gaps = analyze_pre_market_gaps()
    
    # 3. Process news and sentiment
    overnight_news = analyze_overnight_news()
    sentiment_scores = calculate_sentiment_scores()
    
    # 4. Technical analysis
    technical_setups = identify_technical_patterns()
    
    # 5. Generate and rank suggestions
    suggestions = generate_suggestions(
        after_hours_movers, pre_market_gaps, 
        overnight_news, sentiment_scores, technical_setups
    )
    
    # 6. Create morning report
    top_suggestions = rank_and_filter(suggestions, limit=5)
    send_morning_report(top_suggestions)
    
    return top_suggestions
```

### Suggestion Scoring Framework
```python
momentum_score = (
    volume_surge_factor * 0.30 +      # Volume confirms momentum
    price_movement_factor * 0.25 +    # Strong price action
    sentiment_factor * 0.20 +         # Market sentiment alignment
    technical_factor * 0.15 +         # Technical confirmation
    risk_reward_factor * 0.10         # Favorable risk/reward
)

# Minimum threshold: 0.75 | High confidence: 0.85+
```

---

## Risk Management

### Technical Safeguards
- **Rate limiting** for all API calls
- **Data validation** at adapter boundaries
- **Graceful degradation** when APIs fail
- **Comprehensive logging** for debugging

### Trading Risk Controls
- **Position sizing**: Maximum 2-5% per trade
- **Stop losses**: Required for all suggestions
- **Risk/reward ratios**: Minimum 1:1, target 1:1.5+
- **Confidence thresholds**: Only suggest high-confidence setups

### Personal Risk Guidelines
- **Paper trading first**: 1-2 months validation period
- **Manual verification**: Always confirm before trading
- **Risk tolerance**: Only trade with acceptable loss amounts
- **Performance tracking**: Learn from both wins and losses

---

## Development Environment

### Local Setup (Linux/WSL)
```bash
# System dependencies
sudo apt update && sudo apt install python3 python3-pip python3-venv git curl build-essential

# TA-Lib for technical analysis
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz && cd ta-lib
./configure --prefix=/usr && make && sudo make install

# Project setup
python3 -m venv tradescout_env
source tradescout_env/bin/activate
pip install -r requirements.txt
```

### Automation (Linux Cron)
```bash
# Morning suggestions at 6:30 AM EST
30 6 * * 1-5 cd /home/user/TradeScout && python scripts/morning_analysis.py

# Evening analysis at 11:00 PM EST
0 23 * * 1-5 cd /home/user/TradeScout && python scripts/evening_analysis.py

# Performance tracking at 7:00 PM EST
0 19 * * 1-5 cd /home/user/TradeScout && python scripts/performance_update.py
```

---

## Expected Deliverables

### Phase 1 MVP
- Working momentum detection algorithm
- Daily morning suggestions (3-5 trades)
- Basic performance tracking
- CLI interface for manual analysis
- Email reports (if configured)

### Phase 2 Enhanced
- News and sentiment integration
- Technical analysis indicators
- Web dashboard with charts
- Historical performance insights
- Improved suggestion accuracy

### Phase 3 Production
- Cloud deployment capability
- Advanced analytics and ML
- Mobile-responsive interface
- Portfolio integration
- Strategy backtesting

---

## Success Metrics

### Technical Metrics
- **Suggestion accuracy**: >60% win rate target
- **Response time**: Morning analysis <60 seconds
- **Uptime**: >95% during market hours
- **Data quality**: <5% failed API calls

### Learning Objectives
- **Market analysis skills**: Understanding momentum patterns
- **Risk management**: Position sizing and stop loss discipline
- **Technology skills**: Interface design and system architecture
- **Performance evaluation**: Data-driven strategy improvement

---

## Budget & Cost Structure

### Development Phase (Months 1-3)
- **APIs**: $0/month (free tiers)
- **Infrastructure**: $0/month (local hosting)
- **Tools**: $0-20 one-time (optional)
- **Time Investment**: Personal learning project

### Operational Phase (Month 4+)
- **APIs**: $0-29/month (upgrade optional)
- **Cloud hosting**: $0-20/month (if migrated)
- **Total**: $0-50/month maximum

**ROI**: Educational value + potential trading improvements

---

*This plan provides a clear roadmap for building TradeScout as a sophisticated yet practical market research tool, emphasizing learning, risk management, and systematic improvement over immediate profits.*