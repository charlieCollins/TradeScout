# TradeScout Web Interface

**Location:** `src/web/`
**Tech Stack:** FastAPI backend + Vanilla JavaScript frontend
**Status:** ✅ Production ready

---

## Quick Start

### Method 1: Using the Script (Recommended)
```bash
./tradescout-web
```

This automatically:
- Activates the virtual environment
- Starts the server on http://localhost:8000
- Enables auto-reload for development

### Method 2: Manual Start
```bash
source venv/bin/activate
uvicorn src.web.web_app:app --reload --host 0.0.0.0 --port 8000
```

### Access the interface:
- **Web Dashboard:** http://localhost:8000
- **API Docs:** http://localhost:8000/docs

---

## Features

### Web Interface (http://localhost:8000)
- **Screener Dashboard:** Visual cards for all available screeners
- **One-Click Execution:** Run screeners with a single button click
- **Live Results:** Real-time market data displayed in sortable tables
- **Market Context:** Session, date, universe info displayed automatically
- **Export to CSV:** Download screener results
- **Responsive Design:** Works on desktop, tablet, and mobile

### Available Screeners
- **Gainers:** Top gaining stocks (context-aware for premarket/regular/afterhours/closed)
- **Losers:** Top losing stocks (context-aware)
- **Momentum:** High momentum stocks
- **Volume:** High volume movers
- **Custom:** Add more screeners via YAML configs in `configs/screeners/`

### API Endpoints
- `GET /api/screeners` - List all available screeners
- `GET /api/screeners/{name}/run` - Execute a screener
- `GET /api/assets/{symbol}` - Get asset details
- `GET /api/prices/{symbol}/latest` - Get latest price
- `GET /api/universes/active/current` - Get active universe
- See http://localhost:8000/docs for complete API documentation

---

## Architecture

### Backend (`src/web/web_app.py`)
- FastAPI server with dependency injection
- DataServiceV2 → Repository → SQLModel → SQLite
- Screener execution via ScreenerEngine
- Market context via AppContext
- Cache-aside pattern with TTL management

### Frontend (`src/web/static/`)
- **index.html:** Main page structure
- **style.css:** Dark theme with TradeScout branding
- **app.js:** Fetch API calls, table rendering, CSV export
- **tradescout-logo.svg:** Logo image

### Data Flow
```
User clicks "Run Screener"
  ↓
JavaScript fetches /api/screeners/{name}/run
  ↓
FastAPI endpoint loads screener YAML config
  ↓
ScreenerEngine executes query against database
  ↓
Results + market context returned as JSON
  ↓
JavaScript renders sortable table
```

---

## Configuration

### Environment Variables
```bash
# Optional API keys (free signups)
export FINNHUB_API_KEY="your_finnhub_api_key"       # News data
export FRED_API_KEY="your_fred_api_key"             # Economic data
export TRADESCOUT_DB_PATH="/path/to/tradescout.db"  # Optional
```

### Screener Configs
Add custom screeners by creating YAML files in `configs/screeners/`

Example:
```yaml
name: my_screener
description: "My custom screener"
enabled: true
valid_sessions: ["regular", "afterhours"]
filters:
  - field: "day_volume"
    operator: ">"
    value: 1000000
```

---

## Customization

### Change Port
```bash
uvicorn src.web.web_app:app --port 8001
```

### Production Deployment
```bash
uvicorn src.web.web_app:app --host 0.0.0.0 --port 8000 --workers 4
```

### Modify Styling
Edit `src/web/static/style.css` - color scheme defined in CSS variables at top of file

---

## Troubleshooting

**Port already in use:**
```bash
lsof -i :8000
kill -9 <PID>
```

**Static files not loading:**
- Ensure `src/web/static/` directory exists
- Check file permissions
- Verify logo copied to `src/web/static/tradescout-logo.svg`

**API errors:**
- Check `POLYGON_API_KEY` environment variable is set
- Verify database exists: `./tradescout database info`
- Check server logs for detailed error messages

**No screeners found:**
- Verify YAML files exist in `configs/screeners/`
- Check YAML syntax is valid
- Ensure `enabled: true` in screener configs

---

## Next Steps

### Future Enhancements
- [ ] Add gap analysis to web interface
- [ ] Real-time price updates via WebSocket
- [ ] Historical performance charts
- [ ] User authentication
- [ ] Saved screener presets
- [ ] Email/SMS alerts for screener hits
- [ ] Portfolio tracking

### Extending the Interface
1. Add new API endpoints in `src/web/web_app.py`
2. Create new frontend pages in `src/web/static/`
3. Update `app.js` to fetch and display new data
4. Follow existing patterns for consistency

---

**Documentation Updated:** 2025-10-20
