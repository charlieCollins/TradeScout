# TradeScout

Personal Market Research Assistant for momentum trading opportunities.

## Quick Start

1. **Setup Environment**
   ```bash
   python3 -m venv tradescout_env
   source tradescout_env/bin/activate
   pip install -r requirements.txt
   ```

2. **Configure APIs**
   ```bash
   cp config/.env.template .env
   # Edit .env with your API keys
   ```

3. **Run Analysis**
   ```bash
   # Morning suggestions
   python scripts/morning_analysis.py
   
   # Real-time scan
   python scripts/realtime_scan.py
   ```

## Features

- **Overnight Analysis**: Scans after-hours and pre-market activity
- **Trade Suggestions**: Generates 3-5 daily momentum opportunities  
- **Performance Tracking**: Tracks suggested vs actual trade performance
- **Risk Management**: Built-in position sizing and stop-loss calculations

## Data Sources

- **Market Data**: Polygon.io (free) + Yahoo Finance
- **News**: NewsAPI (1000 free calls/day)
- **Sentiment**: Reddit API (free)

## Architecture

Clean interface-driven design with external APIs adapted to internal models. See `/docs` for detailed documentation.

## Development

- **Platform**: Linux/WSL + IntelliJ IDEA
- **Database**: SQLite (local) → PostgreSQL (cloud migration ready)
- **Testing**: pytest with interface mocking
- **Deployment**: Docker + systemd service

## Documentation

- [Project Plan](docs/TRADE_SCOUT_PLAN.md) - Complete project roadmap and strategy
- [Architecture](docs/ARCHITECTURE.md) - Technical architecture and interfaces
- [CLAUDE.md](CLAUDE.md) - Development guidelines and collaboration notes

## License

Personal project - not for distribution