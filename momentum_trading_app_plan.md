# TradeScout - Personal Market Research Assistant

**Project Name:** TradeScout  
**Version:** 1.0  
**Date:** July 20, 2025  
**Platform:** Linux/Ubuntu  
**Budget:** $0-50/month maximum

---

## Executive Summary

A personal market research assistant that monitors after-hours and pre-market activity, analyzes momentum opportunities, and provides morning trade suggestions with performance tracking. The system suggests trades based on overnight analysis but leaves all execution decisions to the user.

---

## Core Features

### 1. Overnight Market Analysis
- After-hours (4:00 PM - 8:00 PM ET) and pre-market (4:00 AM - 9:30 AM ET) monitoring
- Volume surge detection and price movement analysis
- Gap up/down identification and momentum confirmation
- News and sentiment analysis during extended hours

### 2. Morning Trade Suggestions
- Daily email/dashboard with top 3-5 trade recommendations
- Clear entry points, stop losses, and profit targets
- Risk assessment and position sizing suggestions
- Rationale for each suggested trade with supporting data

### 3. Performance Tracking System
- **Suggested Trades Log:** Track performance of all recommendations (whether taken or not)
- **Actual Trades Log:** Manual entry system for trades you actually execute
- Side-by-side performance comparison between suggestions and actual trades
- Win rate analysis and strategy refinement insights

### 4. Research Dashboard
- Real-time market scanner with customizable alerts
- News sentiment analysis and event detection
- Technical analysis charts with momentum indicators
- Historical performance analytics and pattern recognition

---

## Data Sources & APIs

### Market Data
| **Provider** | **Data Type** | **Cost** | **What We Get** |
|--------------|---------------|----------|-----------------|
| **Polygon.io FREE** | All US stocks, fundamentals | **FREE** (5 calls/min) | End-of-day + 2 years historical |
| **Yahoo Finance (yfinance)** | Real-time quotes, after-hours | **FREE** | Perfect for real-time after-hours analysis |
| **Alpha Vantage** | Market data backup | **FREE** (500 calls/day) | Good fallback option |

### News & Sentiment  
| **Provider** | **Data Type** | **Cost** | **Coverage** |
|--------------|---------------|----------|--------------|
| **NewsAPI** | Global news aggregation | **FREE** (1000 calls/day) | Plenty for daily analysis |
| **Reddit API** | WallStreetBets, investing forums | **FREE** | Excellent retail sentiment |
| **RSS Feeds** | Financial news sites | **FREE** | MarketWatch, Yahoo Finance, etc. |

### Perfect Free Tier Combination
- **Polygon.io FREE:** Fundamentals, historical data, technical indicators
- **yfinance:** Real-time prices, after-hours data, quick market scanning
- **NewsAPI + Reddit:** Sentiment analysis and news impact
- **RSS feeds:** Additional news coverage

### Upgrade Path (Optional)
- **Month 3+:** Polygon.io $29/month for 15-minute delayed real-time data
- **Benefit:** More API calls (unlimited) + faster data updates
- **Total Budget:** Still under $50/month

---

## Technical Architecture

### Cloud-Ready Local Architecture
```
TradeScout/ (Cloud-Migration Friendly)
├── config/
│   ├── local_config.py          # Local settings
│   ├── cloud_config.py          # Future cloud settings
│   └── api_keys.env             # Environment variables (gitignored)
│
├── data_collection/
│   ├── polygon_collector.py      # Fundamentals & historical
│   ├── yfinance_scanner.py       # Real-time & after-hours
│   ├── news_collector.py         # NewsAPI & RSS feeds
│   └── reddit_sentiment.py       # Social sentiment analysis
│
├── analysis/
│   ├── technical_analysis.py     # RSI, MACD, volume analysis
│   ├── gap_scanner.py            # Pre-market gap detection
│   ├── suggestion_engine.py      # Core suggestion generation
│   └── performance_tracker.py    # Track performance
│
├── interface/
│   ├── email_reports.py          # Daily morning emails
│   ├── web_dashboard.py          # Flask app (local + cloud ready)
│   └── api_endpoints.py          # REST API for future expansion
│
├── storage/
│   ├── database_manager.py       # Abstracted DB layer
│   ├── local_sqlite.py           # Local SQLite implementation
│   └── cloud_storage.py          # Future Cloud SQL implementation
│
├── scheduler/
│   ├── local_scheduler.py        # Linux cron jobs
│   ├── cloud_scheduler.py        # Future Cloud Scheduler
│   └── job_definitions.py        # Shared job logic
│
└── deployment/
    ├── requirements.txt           # Python dependencies
    ├── docker/                   # Future containerization
    └── gcp/                      # Future Google Cloud configs
```

### Cloud Migration Strategy
**Phase 1: Local Development (Now)**
- SQLite database (easy to migrate)
- Environment variables for config
- Docker-ready code structure
- REST API endpoints (works locally + cloud)

**Phase 2: Easy Cloud Migration (Later)**
- Container deployment to Google Cloud Run
- Switch from SQLite to Cloud SQL
- Use Cloud Scheduler instead of cron
- Minimal code changes needed

### Technology Choices (Cloud-Ready)
| **Component** | **Local Version** | **Cloud Version** | **Migration Effort** |
|---------------|-------------------|-------------------|----------------------|
| **Database** | SQLite | Cloud SQL/PostgreSQL | Low - same SQLAlchemy ORM |
| **Scheduling** | Linux Cron | Cloud Scheduler | Low - same Python functions |
| **Web Interface** | Flask (localhost) | Cloud Run | None - same Flask app |
| **Storage** | Local files | Cloud Storage | Low - abstracted file operations |
| **Secrets** | .env file | Secret Manager | Low - environment variables |

---

## Trade Suggestion Algorithm

### Overnight Analysis Workflow
```python
def run_overnight_analysis():
    """
    Runs every evening to analyze after-hours activity
    and prepare morning trade suggestions
    """
    
    # 1. After-hours screening (4 PM - 8 PM ET)
    after_hours_movers = scan_after_hours_activity()
    
    # 2. Pre-market analysis (4 AM - 9:30 AM ET)  
    pre_market_gaps = analyze_pre_market_gaps()
    
    # 3. News and sentiment analysis
    overnight_news = analyze_overnight_news()
    sentiment_scores = calculate_sentiment_scores()
    
    # 4. Technical analysis
    technical_setups = identify_technical_patterns()
    
    # 5. Generate trade suggestions
    trade_suggestions = generate_morning_suggestions(
        after_hours_movers,
        pre_market_gaps,
        overnight_news,
        sentiment_scores,
        technical_setups
    )
    
    # 6. Rank and filter top 3-5 suggestions
    top_suggestions = rank_suggestions(trade_suggestions)
    
    # 7. Generate morning report
    create_morning_report(top_suggestions)
    send_morning_email(top_suggestions)
    
    return top_suggestions

def generate_trade_suggestion(symbol, analysis_data):
    """
    Creates a structured trade suggestion
    """
    return {
        'symbol': symbol,
        'direction': 'LONG' or 'SHORT',
        'suggested_entry': price,
        'stop_loss': price,
        'profit_target_1': price,
        'profit_target_2': price,
        'position_size_percent': 2.0,  # % of portfolio
        'confidence_score': 0.85,
        'rationale': "Gap up on earnings beat + high volume + bullish sentiment",
        'risk_reward_ratio': 1.5,
        'max_hold_time': '2 hours',
        'timestamp': datetime.now()
    }
```

---

## Development Phases

### Phase 1: MVP Development (3-4 weeks)
**Core Research Assistant**
- [ ] Set up data collection (Polygon.io FREE + yfinance)
- [ ] Basic overnight analysis algorithm
- [ ] Simple web dashboard for viewing suggestions
- [ ] Daily email reports with top 3 trade ideas
- [ ] Manual trade entry system

**Deliverables:**
- Working research assistant with daily suggestions
- Performance tracking for suggested vs actual trades
- Basic morning email reports

### Phase 2: Enhanced Analysis (2-3 weeks)
**Advanced Features**
- [ ] Sentiment analysis integration (Reddit, NewsAPI)
- [ ] Enhanced technical indicators
- [ ] Historical pattern recognition
- [ ] Improved risk/reward calculations
- [ ] Better dashboard with charts

**Deliverables:**
- More sophisticated trade suggestions
- Better visualization of analysis
- Historical performance insights

### Phase 3: Optimization (Ongoing)
**Enhancement Areas**
- [ ] Machine learning for pattern recognition
- [ ] Advanced charting and analysis tools
- [ ] Mobile-friendly interface
- [ ] Integration with portfolio tracking tools

---

## Linux/Ubuntu Development Environment

### Ubuntu Setup & Scheduling
```bash
# System dependencies for TradeScout
sudo apt update
sudo apt install python3 python3-pip python3-venv git curl

# TA-Lib dependencies (for technical analysis)
sudo apt install build-essential wget
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr
make
sudo make install

# Create TradeScout environment
python3 -m venv tradescout_env
source tradescout_env/bin/activate
pip install -r requirements.txt
```

### Cron Jobs for Automation (Much Better than Windows Task Scheduler)
```bash
# Edit crontab for TradeScout scheduling
crontab -e

# Add these entries for automated trading analysis:
# Evening analysis at 11:00 PM EST (after-hours review)
0 23 * * 1-5 cd /home/user/TradeScout && /home/user/tradescout_env/bin/python evening_analysis.py

# Morning suggestions at 6:30 AM EST (pre-market analysis)  
30 6 * * 1-5 cd /home/user/TradeScout && /home/user/tradescout_env/bin/python morning_suggestions.py

# End-of-day performance tracking at 7:00 PM EST
0 19 * * 1-5 cd /home/user/TradeScout && /home/user/tradescout_env/bin/python performance_tracking.py

# Weekly summary every Sunday at 8:00 AM
0 8 * * 0 cd /home/user/TradeScout && /home/user/tradescout_env/bin/python weekly_summary.py

# Health check every hour during market hours (9 AM - 4 PM EST)
0 9-16 * * 1-5 cd /home/user/TradeScout && /home/user/tradescout_env/bin/python health_check.py
```

### Systemd Service (Even Better - Proper Linux Way)
```bash
# /etc/systemd/system/tradescout.service
[Unit]
Description=TradeScout Market Analysis Service
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/home/your_username/TradeScout
Environment=PATH=/home/your_username/tradescout_env/bin
ExecStart=/home/your_username/tradescout_env/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target

# Enable and start the service
sudo systemctl enable tradescout
sudo systemctl start tradescout
sudo systemctl status tradescout
```

### Linux File Structure (Cloud-Ready)
```
/home/user/TradeScout/
├── config/
│   ├── local_config.py          # Linux-specific settings
│   ├── cloud_config.py          # Future GCP settings
│   └── .env                     # Environment variables
│
├── data_collection/
│   ├── polygon_collector.py      
│   ├── yfinance_scanner.py       
│   ├── news_collector.py         
│   └── reddit_sentiment.py       
│
├── analysis/
│   ├── technical_analysis.py     # Uses TA-Lib compiled for Linux
│   ├── gap_scanner.py            
│   ├── suggestion_engine.py      
│   └── performance_tracker.py    
│
├── interface/
│   ├── email_reports.py          
│   ├── web_dashboard.py          # Flask app
│   └── cli_interface.py          # Command-line interface
│
├── storage/
│   ├── database_manager.py       
│   ├── local_sqlite.py           
│   └── cloud_storage.py          
│
├── scripts/
│   ├── evening_analysis.py       # Cron job scripts
│   ├── morning_suggestions.py    
│   ├── performance_tracking.py   
│   └── health_check.py           
│
├── logs/
│   ├── tradescout.log            # Application logs
│   ├── error.log                 # Error logs
│   └── performance.log           # Performance metrics
│
└── deployment/
    ├── requirements.txt           
    ├── Dockerfile                # For containerization
    ├── docker-compose.yml        # Local development
    └── setup.sh                  # Ubuntu setup script
```

---

## Free Data Sources Strategy

### Primary Stack (100% Free to Start)
```python
# Market Data: Polygon.io Free + yfinance combo
import polygon
from polygon import RESTClient

# Polygon for fundamentals and historical analysis  
polygon_client = RESTClient(api_key="your_free_key")
fundamentals = polygon_client.get_ticker_details("AAPL")
historical = polygon_client.list_aggs("AAPL", 1, "day", "2024-01-01", "2024-12-31")

# yfinance for real-time and after-hours data
import yfinance as yf
ticker = yf.Ticker("AAPL")
hist = ticker.history(period="5d", interval="1m", prepost=True)
current_price = ticker.info['regularMarketPrice']

# News: NewsAPI (1000 free calls/day)
import requests
news_response = requests.get(
    "https://newsapi.org/v2/everything?q=AAPL&apiKey=YOUR_KEY"
)

# Social Sentiment: Reddit API (free)
import praw
reddit = praw.Reddit(client_id="your_id", client_secret="your_secret")
```

### What We Get for Free
- **Polygon.io FREE:** 
  - Fundamentals (P/E, market cap, etc.)
  - 2 years of historical data
  - Technical indicators
  - End-of-day prices
  - 5 API calls/minute (plenty for overnight analysis)

- **yfinance:** 
  - Real-time market prices
  - After-hours and pre-market data
  - Unlimited API calls
  - Quick market scanning

- **NewsAPI + Reddit:**
  - 1000 news articles/day
  - Unlimited social sentiment data
  - RSS feeds for additional coverage

### When to Upgrade to Polygon.io $29/month
- Need faster data updates (15-minute vs end-of-day)
- Want unlimited API calls for real-time scanning
- Need more than 2 years of historical data
- Want to add options or crypto analysis

### Perfect Division of Labor
- **Polygon.io:** Historical analysis, fundamentals, overnight batch processing
- **yfinance:** Real-time scanning, after-hours monitoring, quick checks
- **NewsAPI/Reddit:** Sentiment analysis and news impact assessment

---

## Performance Tracking System

### Suggested Trades Performance
```python
# Track all suggestions whether taken or not
suggested_trade = {
    'date': '2025-07-21',
    'symbol': 'AAPL',
    'suggestion_type': 'LONG',
    'entry_price': 195.50,
    'stop_loss': 190.00,
    'target_1': 202.00,
    'target_2': 208.00,
    'confidence': 0.85,
    'rationale': 'Earnings beat + pre-market gap up',
    
    # Track performance automatically
    'max_price_reached': 201.75,
    'min_price_reached': 194.80,
    'close_price_eod': 199.20,
    'suggestion_result': 'WIN',  # Hit target 1
    'max_gain_percent': 3.2,
    'suggestion_score': 8.5  # 1-10 rating
}

# Actual trades you execute manually
actual_trade = {
    'date': '2025-07-21',
    'symbol': 'AAPL',
    'based_on_suggestion': True,
    'entry_price': 195.75,  # Your actual entry
    'exit_price': 201.50,   # Your actual exit
    'shares': 50,
    'total_profit': 287.50,
    'hold_time': '2.5 hours',
    'notes': 'Exited early due to resistance at $201'
}
```

### Daily Morning Report Format
```
📊 TRADESCOUT MORNING BRIEF - July 21, 2025

🎯 TOP TRADE SUGGESTIONS:

1. NVDA - LONG Setup ⭐⭐⭐⭐⭐
   Entry: $172.50 | Stop: $168.00 | Target: $178.00
   Rationale: Strong pre-market gap on datacenter demand news
   Risk/Reward: 1:1.2 | Confidence: 92%

2. TSLA - SHORT Setup ⭐⭐⭐⭐
   Entry: $385.00 | Stop: $392.00 | Target: $375.00
   Rationale: Rejection at resistance + high put/call ratio
   Risk/Reward: 1:1.4 | Confidence: 78%

3. AAPL - LONG Setup ⭐⭐⭐
   Entry: $195.50 | Stop: $190.00 | Target: $202.00
   Rationale: Earnings beat + analyst upgrades
   Risk/Reward: 1:1.2 | Confidence: 71%

📈 YESTERDAY'S SUGGESTION PERFORMANCE:
   Total Suggestions: 3
   Winners: 2 | Losers: 1
   Avg Gain on Winners: +2.4%
   Avg Loss on Losers: -1.8%

📝 Your Trading Summary:
   Trades Taken: 1/3 suggestions
   Your P&L: +$287.50 (AAPL long)
   
🔍 Click here to view full analysis dashboard
```

---

## Linux Development Advantages

### Linux Development Advantages
```python
# logging_setup.py - Proper Linux logging
import logging
import logging.handlers

def setup_logging():
    """
    Set up Linux-style logging with rotation
    """
    
    # Main application log
    logger = logging.getLogger('tradescout')
    logger.setLevel(logging.INFO)
    
    # Rotating file handler (10MB max, keep 5 files)
    file_handler = logging.handlers.RotatingFileHandler(
        '/home/user/TradeScout/logs/tradescout.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    
    # Console handler for development
    console_handler = logging.StreamHandler()
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# process_manager.py - Linux process management
import psutil
import os
import signal

class TradeScoutManager:
    """Manage TradeScout processes on Linux"""
    
    def __init__(self):
        self.pid_file = '/tmp/tradescout.pid'
    
    def start_daemon(self):
        """Start TradeScout as background daemon"""
        if self.is_running():
            print("TradeScout already running")
            return
        
        # Fork process
        pid = os.fork()
        if pid == 0:
            # Child process - run TradeScout
            self.run_main_loop()
        else:
            # Parent process - save PID and exit
            with open(self.pid_file, 'w') as f:
                f.write(str(pid))
            print(f"TradeScout started with PID {pid}")
    
    def stop_daemon(self):
        """Stop TradeScout daemon"""
        if not self.is_running():
            print("TradeScout not running")
            return
        
        with open(self.pid_file, 'r') as f:
            pid = int(f.read().strip())
        
        os.kill(pid, signal.SIGTERM)
        os.remove(self.pid_file)
        print("TradeScout stopped")
    
    def is_running(self):
        """Check if TradeScout is running"""
        if not os.path.exists(self.pid_file):
            return False
        
        with open(self.pid_file, 'r') as f:
            pid = int(f.read().strip())
        
        return psutil.pid_exists(pid)
```

### SSH Access & Remote Management
```bash
# ssh_interface.py - Remote access commands
#!/usr/bin/env python3

import argparse
import sys
from datetime import datetime

def main():
    parser = argparse.ArgumentParser(description='TradeScout Remote Interface')
    parser.add_argument('command', choices=[
        'status', 'suggestions', 'performance', 'logs', 'scan'
    ])
    
    args = parser.parse_args()
    
    if args.command == 'status':
        show_system_status()
    elif args.command == 'suggestions':
        show_current_suggestions()
    elif args.command == 'performance':
        show_performance_summary()
    elif args.command == 'logs':
        show_recent_logs()
    elif args.command == 'scan':
        run_live_market_scan()

def show_system_status():
    """Show TradeScout system status"""
    print("🔍 TradeScout System Status")
    print("=" * 40)
    
    # Check if daemon is running
    manager = TradeScoutManager()
    status = "RUNNING" if manager.is_running() else "STOPPED"
    print(f"Service Status: {status}")
    
    # Show last analysis time
    from storage.database_manager import DatabaseManager
    db = DatabaseManager()
    last_analysis = db.get_last_analysis_time()
    print(f"Last Analysis: {last_analysis}")
    
    # Show upcoming cron jobs
    import subprocess
    result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
    active_jobs = len([line for line in result.stdout.split('\n') 
                      if 'tradescout' in line.lower()])
    print(f"Scheduled Jobs: {active_jobs}")

# Make script executable from anywhere
if __name__ == "__main__":
    main()

# Usage examples:
# ssh user@home-server "cd TradeScout && python ssh_interface.py status"
# ssh user@home-server "cd TradeScout && python ssh_interface.py suggestions"
# ssh user@home-server "cd TradeScout && python ssh_interface.py performance"
```

### Docker Setup (Cloud Migration Ready)
```dockerfile
# Dockerfile - Linux container for easy cloud deployment
FROM ubuntu:22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    build-essential \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install TA-Lib
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz \
    && tar -xzf ta-lib-0.4.0-src.tar.gz \
    && cd ta-lib \
    && ./configure --prefix=/usr \
    && make && make install \
    && cd .. && rm -rf ta-lib*

# Set working directory
WORKDIR /app

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 tradescout && chown -R tradescout:tradescout /app
USER tradescout

# Expose port for web interface
EXPOSE 5000

# Command to run TradeScout
CMD ["python3", "app.py"]
```

---

## Budget & Cost Analysis

### Development Costs (2-3 months)
- **Your Time Investment:** Personal project - priceless! 🎯
- **Data Subscriptions:** **$0/month** (100% free APIs!)
- **Infrastructure:** **$0/month** (running locally on your home PC)
- **Tools:** $0-20 one-time (optional code editor, etc.)

### Ongoing Operational Costs
- **Data APIs:** **$0/month** (free tiers)
- **Infrastructure:** **$0/month** (local hosting)
- **Electricity:** ~$2-5/month (PC running 24/7)

**Total Initial Investment:** $0-20  
**Monthly Operating Cost:** $0-5 (basically just electricity)

*Can't beat free! Perfect for validating the concept.*

---

## Risk Assessment

### Technical Risks
- **Data Feed Issues:** Start with free APIs, upgrade as needed
- **Algorithm Accuracy:** Track suggested vs actual performance to improve
- **System Downtime:** Personal project - occasional downtime is acceptable

### Personal Trading Risks
- **Following Bad Suggestions:** Always do your own verification before trading
- **Overconfidence:** Remember the system is learning and improving
- **FOMO Trading:** Stick to suggested position sizes and risk management

### Mitigation Strategies
- Start with paper tracking for 1-2 months to validate suggestions
- Only risk money you can afford to lose
- Always maintain stop losses on actual trades
- Keep detailed logs to improve the system over time

---

## Next Steps

1. **Set Up Ubuntu Environment** (Week 1)
2. **Configure Free API Access** (Week 1-2)
3. **Build Basic Data Pipeline** (Week 2-3)
4. **Implement Suggestion Engine** (Week 3-4)
5. **Create Email Reports** (Week 4)
6. **Performance Tracking System** (Week 4-5)

---

*This plan provides a comprehensive roadmap for building TradeScout as a personal market research assistant. The focus is on learning, experimentation, and gradual improvement rather than immediate profitability.*

---

## Data Sources & APIs

### Market Data
| **Provider** | **Data Type** | **Cost** | **What We Get** |
|--------------|---------------|----------|-----------------|
| **Polygon.io FREE** | All US stocks, fundamentals | **FREE** (5 calls/min) | End-of-day + 2 years historical |
| **Yahoo Finance (yfinance)** | Real-time quotes, after-hours | **FREE** | Perfect for real-time after-hours analysis |
| **Alpha Vantage** | Market data backup | **FREE** (500 calls/day) | Good fallback option |

### News & Sentiment  
| **Provider** | **Data Type** | **Cost** | **Coverage** |
|--------------|---------------|----------|--------------|
| **NewsAPI** | Global news aggregation | **FREE** (1000 calls/day) | Plenty for daily analysis |
| **Reddit API** | WallStreetBets, investing forums | **FREE** | Excellent retail sentiment |
| **RSS Feeds** | Financial news sites | **FREE** | MarketWatch, Yahoo Finance, etc. |

### Perfect Free Tier Combination
- **Polygon.io FREE:** Fundamentals, historical data, technical indicators
- **yfinance:** Real-time prices, after-hours data, quick market scanning
- **NewsAPI + Reddit:** Sentiment analysis and news impact
- **RSS feeds:** Additional news coverage

### Upgrade Path (Optional)
- **Month 3+:** Polygon.io $29/month for 15-minute delayed real-time data
- **Benefit:** More API calls (unlimited) + faster data updates
- **Total Budget:** Still under $50/month

---

## Technical Architecture

### Cloud-Ready Local Architecture
```
TradeScout/ (Cloud-Migration Friendly)
├── config/
│   ├── local_config.py          # Local settings
│   ├── cloud_config.py          # Future cloud settings
│   └── api_keys.env             # Environment variables (gitignored)
│
├── data_collection/
│   ├── polygon_collector.py      # Fundamentals & historical
│   ├── yfinance_scanner.py       # Real-time & after-hours
│   ├── news_collector.py         # NewsAPI & RSS feeds
│   └── reddit_sentiment.py       # Social sentiment analysis
│
├── analysis/
│   ├── technical_analysis.py     # RSI, MACD, volume analysis
│   ├── gap_scanner.py            # Pre-market gap detection
│   ├── suggestion_engine.py      # Core suggestion generation
│   └── performance_tracker.py    # Track performance
│
├── interface/
│   ├── email_reports.py          # Daily morning emails
│   ├── web_dashboard.py          # Flask app (local + cloud ready)
│   └── api_endpoints.py          # REST API for future expansion
│
├── storage/
│   ├── database_manager.py       # Abstracted DB layer
│   ├── local_sqlite.py           # Local SQLite implementation
│   └── cloud_storage.py          # Future Cloud SQL implementation
│
├── scheduler/
│   ├── local_scheduler.py        # Windows/Linux cron jobs
│   ├── cloud_scheduler.py        # Future Cloud Scheduler
│   └── job_definitions.py        # Shared job logic
│
└── deployment/
    ├── requirements.txt           # Python dependencies
    ├── docker/                   # Future containerization
    └── gcp/                      # Future Google Cloud configs
```

## Linux/Ubuntu Development Environment

### Ubuntu Setup & Scheduling
```bash
# System dependencies for TradeScout
sudo apt update
sudo apt install python3 python3-pip python3-venv git curl

# TA-Lib dependencies (for technical analysis)
sudo apt install build-essential wget
wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz
tar -xzf ta-lib-0.4.0-src.tar.gz
cd ta-lib/
./configure --prefix=/usr
make
sudo make install

# Create TradeScout environment
python3 -m venv tradescout_env
source tradescout_env/bin/activate
pip install -r requirements.txt
```

### Cron Jobs for Automation (Much Better than Windows Task Scheduler)
```bash
# Edit crontab for TradeScout scheduling
crontab -e

# Add these entries for automated trading analysis:
# Evening analysis at 11:00 PM EST (after-hours review)
0 23 * * 1-5 cd /home/user/TradeScout && /home/user/tradescout_env/bin/python evening_analysis.py

# Morning suggestions at 6:30 AM EST (pre-market analysis)  
30 6 * * 1-5 cd /home/user/TradeScout && /home/user/tradescout_env/bin/python morning_suggestions.py

# End-of-day performance tracking at 7:00 PM EST
0 19 * * 1-5 cd /home/user/TradeScout && /home/user/tradescout_env/bin/python performance_tracking.py

# Weekly summary every Sunday at 8:00 AM
0 8 * * 0 cd /home/user/TradeScout && /home/user/tradescout_env/bin/python weekly_summary.py

# Health check every hour during market hours (9 AM - 4 PM EST)
0 9-16 * * 1-5 cd /home/user/TradeScout && /home/user/tradescout_env/bin/python health_check.py
```

### Systemd Service (Even Better - Proper Linux Way)
```bash
# /etc/systemd/system/tradescout.service
[Unit]
Description=TradeScout Market Analysis Service
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/home/your_username/TradeScout
Environment=PATH=/home/your_username/tradescout_env/bin
ExecStart=/home/your_username/tradescout_env/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target

# Enable and start the service
sudo systemctl enable tradescout
sudo systemctl start tradescout
sudo systemctl status tradescout
```

### Linux File Structure (Cloud-Ready)
```
/home/user/TradeScout/
├── config/
│   ├── local_config.py          # Linux-specific settings
│   ├── cloud_config.py          # Future GCP settings
│   └── .env                     # Environment variables
│
├── data_collection/
│   ├── polygon_collector.py      
│   ├── yfinance_scanner.py       
│   ├── news_collector.py         
│   └── reddit_sentiment.py       
│
├── analysis/
│   ├── technical_analysis.py     # Uses TA-Lib compiled for Linux
│   ├── gap_scanner.py            
│   ├── suggestion_engine.py      
│   └── performance_tracker.py    
│
├── interface/
│   ├── email_reports.py          
│   ├── web_dashboard.py          # Flask app
│   └── cli_interface.py          # Command-line interface
│
├── storage/
│   ├── database_manager.py       
│   ├── local_sqlite.py           
│   └── cloud_storage.py          
│
├── scripts/
│   ├── evening_analysis.py       # Cron job scripts
│   ├── morning_suggestions.py    
│   ├── performance_tracking.py   
│   └── health_check.py           
│
├── logs/
│   ├── tradescout.log            # Application logs
│   ├── error.log                 # Error logs
│   └── performance.log           # Performance metrics
│
└── deployment/
    ├── requirements.txt           
    ├── Dockerfile                # For containerization
    ├── docker-compose.yml        # Local development
    └── setup.sh                  # Ubuntu setup script
```

### Local Access Methods
**Option 1: Email Reports (Recommended)**
- Automated daily email at 7 AM with top 3 suggestions
- Include charts, analysis, and performance tracking
- Accessible on phone during commute

**Option 2: SSH Access**
- SSH into home PC from anywhere
- Run command: `python tradescout_report.py`
- Get instant formatted report in terminal

**Option 3: Local Web Dashboard** 
- Simple web interface at `http://localhost:5000`
- View when at home PC
- Charts, performance tracking, manual trade entry

**Option 4: File-Based Reports**
- Generate daily text/HTML reports
- Save to shared folder (Dropbox, Google Drive)
- Access from any device

---

## Trade Suggestion Algorithm

### Overnight Analysis Workflow
```python
def run_overnight_analysis():
    """
    Runs every evening to analyze after-hours activity
    and prepare morning trade suggestions
    """
    
    # 1. After-hours screening (4 PM - 8 PM ET)
    after_hours_movers = scan_after_hours_activity()
    
    # 2. Pre-market analysis (4 AM - 9:30 AM ET)  
    pre_market_gaps = analyze_pre_market_gaps()
    
    # 3. News and sentiment analysis
    overnight_news = analyze_overnight_news()
    sentiment_scores = calculate_sentiment_scores()
    
    # 4. Technical analysis
    technical_setups = identify_technical_patterns()
    
    # 5. Generate trade suggestions
    trade_suggestions = generate_morning_suggestions(
        after_hours_movers,
        pre_market_gaps,
        overnight_news,
        sentiment_scores,
        technical_setups
    )
    
    # 6. Rank and filter top 3-5 suggestions
    top_suggestions = rank_suggestions(trade_suggestions)
    
    # 7. Generate morning report
    create_morning_report(top_suggestions)
    send_morning_email(top_suggestions)
    
    return top_suggestions

def generate_trade_suggestion(symbol, analysis_data):
    """
    Creates a structured trade suggestion
    """
    return {
        'symbol': symbol,
        'direction': 'LONG' or 'SHORT',
        'suggested_entry': price,
        'stop_loss': price,
        'profit_target_1': price,
        'profit_target_2': price,
        'position_size_percent': 2.0,  # % of portfolio
        'confidence_score': 0.85,
        'rationale': "Gap up on earnings beat + high volume + bullish sentiment",
        'risk_reward_ratio': 1.5,
        'max_hold_time': '2 hours',
        'timestamp': datetime.now()
    }
```

---

## Development Phases

### Phase 1: MVP Development (3-4 weeks)
**Core Research Assistant**
- [ ] Set up data collection (Alpha Vantage + News API - mostly free)
- [ ] Basic overnight analysis algorithm
- [ ] Simple web dashboard for viewing suggestions
- [ ] Daily email reports with top 3 trade ideas
- [ ] Manual trade entry system

**Deliverables:**
- Working research assistant with daily suggestions
- Performance tracking for suggested vs actual trades
- Basic morning email reports

### Phase 2: Enhanced Analysis (2-3 weeks)
**Advanced Features**
- [ ] Sentiment analysis integration (Reddit, StockTwits)
- [ ] Enhanced technical indicators
- [ ] Historical pattern recognition
- [ ] Improved risk/reward calculations
- [ ] Better dashboard with charts

**Deliverables:**
- More sophisticated trade suggestions
- Better visualization of analysis
- Historical performance insights

### Phase 3: Optimization (Ongoing)
**Enhancement Areas**
- [ ] Machine learning for pattern recognition
- [ ] Advanced charting and analysis tools
- [ ] Mobile-friendly interface
- [ ] Integration with portfolio tracking tools

---

## Claude Integration Plan

### CLAUDE.md Documentation Strategy
- **Daily Dev Logs:** Track development progress and decisions
- **Code Review Partner:** Use Claude for code quality and optimization
- **Strategy Backtesting:** Collaborate on algorithm improvements
- **Documentation Generation:** Auto-generate API docs and user guides
- **Debugging Assistant:** Help troubleshoot complex trading logic

### Claude-Assisted Development Workflow
1. **Planning:** Use Claude to refine technical specifications
2. **Architecture:** Review system design and suggest improvements
3. **Implementation:** Code review and optimization suggestions
4. **Testing:** Help design comprehensive test scenarios
5. **Deployment:** Assist with DevOps and monitoring setup

---

## Regulatory & Compliance Considerations

### Key Requirements
- **Pattern Day Trading Rules:** Account for PDT regulations
- **Risk Disclosures:** Clear warnings about trading risks
- **Data Licensing:** Ensure proper licensing for market data
- **Broker Compliance:** Follow broker-specific API guidelines
- **Tax Reporting:** Track all trades for tax purposes

### Disclaimers Required
- Not financial advice - educational/informational purposes
- Past performance doesn't guarantee future results
- High-risk trading strategy with potential for significant losses
- Users should consult with financial advisors

---

## Performance Tracking System

### Suggested Trades Performance
```python
# Track all suggestions whether taken or not
suggested_trade = {
    'date': '2025-07-21',
    'symbol': 'AAPL',
    'suggestion_type': 'LONG',
    'entry_price': 195.50,
    'stop_loss': 190.00,
    'target_1': 202.00,
    'target_2': 208.00,
    'confidence': 0.85,
    'rationale': 'Earnings beat + pre-market gap up',
    
    # Track performance automatically
    'max_price_reached': 201.75,
    'min_price_reached': 194.80,
    'close_price_eod': 199.20,
    'suggestion_result': 'WIN',  # Hit target 1
    'max_gain_percent': 3.2,
    'suggestion_score': 8.5  # 1-10 rating
}

# Actual trades you execute manually
actual_trade = {
    'date': '2025-07-21',
    'symbol': 'AAPL',
    'based_on_suggestion': True,
    'entry_price': 195.75,  # Your actual entry
    'exit_price': 201.50,   # Your actual exit
    'shares': 50,
    'total_profit': 287.50,
    'hold_time': '2.5 hours',
    'notes': 'Exited early due to resistance at $201'
}
```

### Daily Morning Report Format
```
📊 TRADESCOUT MORNING BRIEF - July 21, 2025

🎯 TOP TRADE SUGGESTIONS:

1. NVDA - LONG Setup ⭐⭐⭐⭐⭐
   Entry: $172.50 | Stop: $168.00 | Target: $178.00
   Rationale: Strong pre-market gap on datacenter demand news
   Risk/Reward: 1:1.2 | Confidence: 92%

2. TSLA - SHORT Setup ⭐⭐⭐⭐
   Entry: $385.00 | Stop: $392.00 | Target: $375.00
   Rationale: Rejection at resistance + high put/call ratio
   Risk/Reward: 1:1.4 | Confidence: 78%

3. AAPL - LONG Setup ⭐⭐⭐
   Entry: $195.50 | Stop: $190.00 | Target: $202.00
   Rationale: Earnings beat + analyst upgrades
   Risk/Reward: 1:1.2 | Confidence: 71%

📈 YESTERDAY'S SUGGESTION PERFORMANCE:
   Total Suggestions: 3
   Winners: 2 | Losers: 1
   Avg Gain on Winners: +2.4%
   Avg Loss on Losers: -1.8%

📝 Your Trading Summary:
   Trades Taken: 1/3 suggestions
   Your P&L: +$287.50 (AAPL long)
   
🔍 Click here to view full analysis dashboard
```

---

## Budget Estimation

### Development Costs (2-3 months)
- **Your Time Investment:** Personal project - priceless! 🎯
- **Data Subscriptions:** **$0/month** (100% free APIs!)
- **Infrastructure:** **$0/month** (running locally on your home PC)
- **Tools:** $0-20 one-time (optional code editor, etc.)

### Ongoing Operational Costs
- **Data APIs:** **$0/month** (free tiers)
- **Infrastructure:** **$0/month** (local hosting)
- **Electricity:** ~$2-5/month (PC running 24/7)

**Total Initial Investment:** $0-20  
**Monthly Operating Cost:** $0-5 (basically just electricity)

*Can't beat free! Perfect for validating the concept.*

---

## Risk Assessment

### Technical Risks
- **Data Feed Issues:** Start with free APIs, upgrade as needed
- **Algorithm Accuracy:** Track suggested vs actual performance to improve
- **System Downtime:** Personal project - occasional downtime is acceptable

### Personal Trading Risks
- **Following Bad Suggestions:** Always do your own verification before trading
- **Overconfidence:** Remember the system is learning and improving
- **FOMO Trading:** Stick to suggested position sizes and risk management

### Mitigation Strategies
- Start with paper tracking for 1-2 months to validate suggestions
- Only risk money you can afford to lose
- Always maintain stop losses on actual trades
- Keep detailed logs to improve the system over time

---

## Free Data Sources Strategy

### Primary Stack (100% Free to Start)
```python
# Market Data: Polygon.io Free + yfinance combo
import polygon
from polygon import RESTClient

# Polygon for fundamentals and historical analysis  
polygon_client = RESTClient(api_key="your_free_key")
fundamentals = polygon_client.get_ticker_details("AAPL")
historical = polygon_client.list_aggs("AAPL", 1, "day", "2024-01-01", "2024-12-31")

# yfinance for real-time and after-hours data
import yfinance as yf
ticker = yf.Ticker("AAPL")
hist = ticker.history(period="5d", interval="1m", prepost=True)
current_price = ticker.info['regularMarketPrice']

# News: NewsAPI (1000 free calls/day)
import requests
news_response = requests.get(
    "https://newsapi.org/v2/everything?q=AAPL&apiKey=YOUR_KEY"
)

# Social Sentiment: Reddit API (free)
import praw
reddit = praw.Reddit(client_id="your_id", client_secret="your_secret")
```

### What We Get for Free
- **Polygon.io FREE:** 
  - Fundamentals (P/E, market cap, etc.)
  - 2 years of historical data
  - Technical indicators
  - End-of-day prices
  - 5 API calls/minute (plenty for overnight analysis)

- **yfinance:** 
  - Real-time market prices
  - After-hours and pre-market data
  - Unlimited API calls
  - Quick market scanning

- **NewsAPI + Reddit:**
  - 1000 news articles/day
  - Unlimited social sentiment data
  - RSS feeds for additional coverage

### Linux Development Advantages
```python
# logging_setup.py - Proper Linux logging
import logging
import logging.handlers

def setup_logging():
    """
    Set up Linux-style logging with rotation
    """
    
    # Main application log
    logger = logging.getLogger('tradescout')
    logger.setLevel(logging.INFO)
    
    # Rotating file handler (10MB max, keep 5 files)
    file_handler = logging.handlers.RotatingFileHandler(
        '/home/user/TradeScout/logs/tradescout.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    
    # Console handler for development
    console_handler = logging.StreamHandler()
    
    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# process_manager.py - Linux process management
import psutil
import os
import signal

class TradeScoutManager:
    """Manage TradeScout processes on Linux"""
    
    def __init__(self):
        self.pid_file = '/tmp/tradescout.pid'
    
    def start_daemon(self):
        """Start TradeScout as background daemon"""
        if self.is_running():
            print("TradeScout already running")
            return
        
        # Fork process
        pid = os.fork()
        if pid == 0:
            # Child process - run TradeScout
            self.run_main_loop()
        else:
            # Parent process - save PID and exit
            with open(self.pid_file, 'w') as f:
                f.write(str(pid))
            print(f"TradeScout started with PID {pid}")
    
    def stop_daemon(self):
        """Stop TradeScout daemon"""
        if not self.is_running():
            print("TradeScout not running")
            return
        
        with open(self.pid_file, 'r') as f:
            pid = int(f.read().strip())
        
        os.kill(pid, signal.SIGTERM)
        os.remove(self.pid_file)
        print("TradeScout stopped")
    
    def is_running(self):
        """Check if TradeScout is running"""
        if not os.path.exists(self.pid_file):
            return False
        
        with open(self.pid_file, 'r') as f:
            pid = int(f.read().strip())
        
        return psutil.pid_exists(pid)
```

### SSH Access & Remote Management
```bash
# ssh_interface.py - Remote access commands
#!/usr/bin/env python3

import argparse
import sys
from datetime import datetime

def main():
    parser = argparse.ArgumentParser(description='TradeScout Remote Interface')
    parser.add_argument('command', choices=[
        'status', 'suggestions', 'performance', 'logs', 'scan'
    ])
    
    args = parser.parse_args()
    
    if args.command == 'status':
        show_system_status()
    elif args.command == 'suggestions':
        show_current_suggestions()
    elif args.command == 'performance':
        show_performance_summary()
    elif args.command == 'logs':
        show_recent_logs()
    elif args.command == 'scan':
        run_live_market_scan()

def show_system_status():
    """Show TradeScout system status"""
    print("🔍 TradeScout System Status")
    print("=" * 40)
    
    # Check if daemon is running
    manager = TradeScoutManager()
    status = "RUNNING" if manager.is_running() else "STOPPED"
    print(f"Service Status: {status}")
    
    # Show last analysis time
    from storage.database_manager import DatabaseManager
    db = DatabaseManager()
    last_analysis = db.get_last_analysis_time()
    print(f"Last Analysis: {last_analysis}")
    
    # Show upcoming cron jobs
    import subprocess
    result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
    active_jobs = len([line for line in result.stdout.split('\n') 
                      if 'tradescout' in line.lower()])
    print(f"Scheduled Jobs: {active_jobs}")

# Make script executable from anywhere
if __name__ == "__main__":
    main()

# Usage examples:
# ssh user@home-server "cd TradeScout && python ssh_interface.py status"
# ssh user@home-server "cd TradeScout && python ssh_interface.py suggestions"
# ssh user@home-server "cd TradeScout && python ssh_interface.py performance"
```

### Docker Setup (Cloud Migration Ready)
```dockerfile
# Dockerfile - Linux container for easy cloud deployment
FROM ubuntu:22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    build-essential \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install TA-Lib
RUN wget http://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz \
    && tar -xzf ta-lib-0.4.0-src.tar.gz \
    && cd ta-lib \
    && ./configure --prefix=/usr \
    && make && make install \
    && cd .. && rm -rf ta-lib*

# Set working directory
WORKDIR /app

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 tradescout && chown -R tradescout:tradescout /app
USER tradescout

# Expose port for web interface
EXPOSE 5000

# Command to run TradeScout
CMD ["python3", "app.py"]
```

---

*This plan provides a comprehensive roadmap for building a sophisticated momentum trading application. Regular reviews and adjustments will be necessary as development progresses and market conditions evolve.*