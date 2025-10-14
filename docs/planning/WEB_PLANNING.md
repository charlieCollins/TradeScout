# TradeScout Web API - Quick Start Guide

**Status:** ✅ Implemented and working
**Location:** `src/api/web_app.py`
**Framework:** FastAPI
**Architecture:** DataServiceV2 → Repository → SQLModel → Database

---

## Starting the Web Server

**Important:** Activate virtual environment first, or use full path to uvicorn

### Option 1: With venv activated (recommended)
```bash
cd /home/ccollins/projects/TradeScout
source venv/bin/activate
uvicorn src.api.web_app:app --reload --host 0.0.0.0 --port 8000
```

### Option 2: Using venv path directly (no activation needed)
```bash
cd /home/ccollins/projects/TradeScout
venv/bin/uvicorn src.api.web_app:app --reload --host 0.0.0.0 --port 8000
```

### Option 3: Production mode (no auto-reload)
```bash
source venv/bin/activate
uvicorn src.api.web_app:app --host 0.0.0.0 --port 8000
```

**Server will be running at:** `http://localhost:8000`

---

## Interactive Documentation

Once server is running:

- **Swagger UI (Interactive):** http://localhost:8000/docs
- **ReDoc (Alternative):** http://localhost:8000/redoc
- **OpenAPI JSON:** http://localhost:8000/openapi.json

**Swagger UI lets you test all endpoints directly in the browser!**

---

## Available Endpoints

### Core Endpoints
```
GET  /                                    # API info and available endpoints
GET  /health                              # Health check
```

### Assets
```
GET  /api/assets/{symbol}                 # Get asset by symbol
     ?force_refresh=true                  # Force fresh data from API
```

### Markets/Exchanges
```
GET  /api/markets                         # List all markets
GET  /api/markets/{code}                  # Get market by code (e.g., XNAS)
```

### Fundamentals
```
GET  /api/fundamentals/{asset_id}         # Get fundamentals by asset ID
```

### Providers
```
GET  /api/providers                       # List all providers
GET  /api/providers/{name}                # Get provider by name (e.g., polygon)
```

### Universes
```
GET  /api/universes                       # List all universes
GET  /api/universes/{name}                # Get universe by name
GET  /api/universes/{name}/memberships    # Get universe memberships
GET  /api/universes/active/current        # Get currently active universe
```

### Prices
```
GET  /api/prices/{symbol}/latest          # Get latest price for symbol
GET  /api/prices/gaps                     # Find prices with gaps
     ?min_gap_percent=3.0                 # Minimum gap percentage
```

---

## Example API Calls

### Using curl

```bash
# Health check
curl http://localhost:8000/health

# Get API info
curl http://localhost:8000/

# Get asset info for AAPL
curl http://localhost:8000/api/assets/AAPL

# Force refresh AAPL from Polygon API
curl "http://localhost:8000/api/assets/AAPL?force_refresh=true"

# Get all markets
curl http://localhost:8000/api/markets

# Get Nasdaq market
curl http://localhost:8000/api/markets/XNAS

# Get fundamentals for asset ID 7535
curl http://localhost:8000/api/fundamentals/7535

# Get active universe
curl http://localhost:8000/api/universes/active/current

# Get latest price for NVDA
curl http://localhost:8000/api/prices/NVDA/latest

# Find stocks with gaps > 3%
curl "http://localhost:8000/api/prices/gaps?min_gap_percent=3.0"
```

### Using Python requests

```python
import requests

# Get asset
response = requests.get("http://localhost:8000/api/assets/AAPL")
asset = response.json()
print(asset)

# Get latest price
response = requests.get("http://localhost:8000/api/prices/NVDA/latest")
price = response.json()
print(price)

# Find gaps
response = requests.get("http://localhost:8000/api/prices/gaps",
                       params={"min_gap_percent": 3.0})
gaps = response.json()
print(gaps)
```

---

## Architecture Notes

**Cache-Aside Pattern:**
- All endpoints check database first (cache)
- If data is stale or missing → fetch from Polygon API
- Update database with fresh data
- Return results

**TTL (Time-To-Live):**
- Assets: 3 days
- Fundamentals: 30 days
- Prices: Configurable per query

**Benefits:**
- Fast responses (database cache)
- Always fresh data (automatic API fetching)
- Reduced API quota usage
- Type-safe with Pydantic/SQLModel

---

## Environment Setup

**Required:**
```bash
export POLYGON_API_KEY="your_api_key_here"
```

**Optional:**
```bash
export TRADESCOUT_DB_PATH="/custom/path/to/tradescout.db"
```

---

## Stopping the Server

Press `Ctrl+C` in the terminal where uvicorn is running.

---

## Next Steps / Future Enhancements

- [ ] Add POST endpoints for bootstrap operations
- [ ] Add WebSocket support for real-time price updates
- [ ] Add authentication/API keys
- [ ] Add rate limiting
- [ ] Add request logging/metrics
- [ ] Add CORS middleware for web clients
- [ ] Add batch endpoints (multiple symbols at once)

---

## Troubleshooting

**Server won't start:**
- Check if port 8000 is already in use: `lsof -i :8000`
- Try a different port: `uvicorn src.api.web_app:app --port 8001`

**"POLYGON_API_KEY not configured" error:**
- Make sure environment variable is set: `echo $POLYGON_API_KEY`
- Set it: `export POLYGON_API_KEY="your_key"`

**Database errors:**
- Ensure database exists: `./tradescout database info`
- Initialize if needed: `./tradescout database init`
- Bootstrap data: `./tradescout database bootstrap-all`

---

**Documentation Generated:** 2025-10-13
