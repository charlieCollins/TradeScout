# Sentiment Detection System

**Last Updated**: 2025-09-30
**Status**: Planning Phase
**Purpose**: Track market-moving events and sentiment signals

---

## What Are Sentiment Events?

**Sentiment events** represent market psychology signals and market-moving events that influence trading behavior. They are **separate from price patterns** like gaps, though they often correlate.

### Core Concept

**Sentiment** = Market psychology, news, events that move markets
**NOT** = Price patterns (gaps, momentum spikes, volume spikes)

### Examples of Sentiment Events

| Category | Event Type | Description | Example |
|----------|-----------|-------------|---------|
| **News** | `news_positive` | Positive news sentiment | Product launch announcement |
| **News** | `news_negative` | Negative news sentiment | Scandal, lawsuit, recall |
| **News** | `news_neutral` | Informational news | Routine filings, conferences |
| **Analyst** | `analyst_upgrade` | Analyst rating increase | Goldman upgrades AAPL to Buy |
| **Analyst** | `analyst_downgrade` | Analyst rating decrease | Morgan Stanley downgrades to Sell |
| **Earnings** | `earnings_beat` | Earnings exceed expectations | Company beats EPS estimates |
| **Earnings** | `earnings_miss` | Earnings below expectations | Company misses revenue targets |
| **Regulatory** | `regulatory_approval` | FDA approval, legal win | Drug approval granted |
| **Regulatory** | `regulatory_concern` | Investigation, compliance issue | SEC investigation announced |
| **Social** | `social_buzz_spike` | Unusual social media attention | Stock trending on social platforms |

---

## Relationship to Price Patterns

### Sentiment and Gaps Are Separate Systems

**Gap Detection** (handled by screeners/gap analyzer):
- Detects price patterns: gap_up, gap_down, momentum_spike
- Analyzes price movements from `asset_prices` table
- Uses technical thresholds (2% gap minimum, magnitude classification)

**Sentiment Detection** (handled by sentiment system):
- Detects market-moving events from news, analysts, social signals
- Stores events in `sentiment_types` and `sentiment_events` tables
- Uses sentiment scores, impact magnitude, reasoning

### How They Correlate

```
Sentiment → Gap (Causation)
├─ Earnings beat → Gap up at market open
├─ Negative news → Gap down next day
└─ Analyst upgrade → Pre-market gap up

Gap → Sentiment (Reverse Causation)
├─ Huge gap up (>10%) → Creates market buzz
├─ Extreme gap down → Media attention, analyst commentary
└─ Unexpected gap → Triggers news research/investigation
```

### Integration Point: Catalyst Validation

**Gap Analyzer Use Case**:
When a gap is detected, check for sentiment catalysts:

```python
gap_detected = detect_gap("AAPL", date(2025, 1, 15))
# Gap up: 5.2%

sentiment_events = get_sentiment_events(
    symbol="AAPL",
    date_range=(date(2025, 1, 14), date(2025, 1, 15))
)
# Found: news_positive event (product launch announcement)

# Conclusion: Gap has news catalyst → Higher confidence trade
```

**Trading Strategy Application**:
- **Gap with catalyst**: Enter with full position size
- **Gap without catalyst**: Reduce position size or skip
- **Catalyst without gap**: Monitor for delayed price reaction

---

## Database Schema

### Table: `sentiment_types`

Defines types of sentiment events that can be detected.

```sql
CREATE TABLE sentiment_types (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,           -- 'news_positive', 'analyst_upgrade'
    description TEXT,
    category TEXT,                        -- 'news', 'analyst', 'earnings', 'regulatory', 'social'
    parameters TEXT,                      -- JSON: {"min_confidence": 0.7, "sources": ["polygon", "finnhub"]}
    is_active BOOLEAN DEFAULT TRUE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Purpose**: Configuration for different event types
**Managed By**: `SentimentTypesManager`
**Bootstrap**: Predefined types loaded on initialization

### Table: `sentiment_events`

Stores detected sentiment events for specific assets.

```sql
CREATE TABLE sentiment_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_id INTEGER NOT NULL,
    sentiment_type_id INTEGER NOT NULL,

    -- Event timing
    event_date DATE NOT NULL,
    event_time TIME,
    session TEXT CHECK(session IN ('premarket', 'regular', 'afterhours')),

    -- Event measurements
    value DECIMAL(12,4),                 -- Sentiment score, confidence level
    magnitude TEXT CHECK(magnitude IN ('small', 'medium', 'large', 'extreme')),

    -- Additional context
    details TEXT,                         -- JSON: {"title": "...", "reasoning": "...", "source": "..."}

    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (asset_id) REFERENCES assets (id),
    FOREIGN KEY (sentiment_type_id) REFERENCES sentiment_types (id)
);
```

**Purpose**: Store detected sentiment events
**Managed By**: `SentimentEventsManager`
**Populated By**: `SentimentDetectionService` (fetches from APIs)

---

## Architecture Components

### Models

**Location**: `src/models/`

#### SentimentType
```python
@dataclass(frozen=True)
class SentimentType:
    id: int
    name: str  # 'news_positive', 'analyst_upgrade'
    description: str
    category: str  # 'news', 'analyst', 'earnings', 'regulatory', 'social'
    parameters: Dict[str, Any]  # Detection/scoring config
    is_active: bool
    created_at: datetime
```

#### SentimentEvent
```python
@dataclass(frozen=True)
class SentimentEvent:
    id: int
    asset_id: int
    sentiment_type_id: int
    event_date: date
    event_time: Optional[time]
    session: Optional[str]  # When event published/occurred
    value: Decimal  # Sentiment score, confidence, magnitude
    magnitude: str  # Impact level: small/medium/large/extreme
    details: Dict[str, Any]  # Full context (title, reasoning, source)
    created_at: datetime
```

### Managers

**Pattern**: Follow Manager/Provider architecture

#### SentimentTypesManager
**File**: `src/database/managers/sentiment_types_manager.py`
**Extends**: `BaseManager`
**Responsibilities**:
- CRUD operations for sentiment types
- Bootstrap predefined types
- Query types by category

**Methods**:
- `get_entity_from_database(name: str) -> Optional[SentimentType]`
- `set_entity_to_database(name: str, sentiment_type: SentimentType) -> bool`
- `get_all_types(category: Optional[str]) -> List[SentimentType]`

**TTL**: 1 year (types rarely change)

#### SentimentEventsManager
**File**: `src/database/managers/sentiment_events_manager.py`
**Extends**: `BaseManager`
**Responsibilities**:
- CRUD operations for sentiment events
- Query events by asset, date range, type
- Aggregate sentiment for analysis

**Methods**:
- `get_entity_from_database(event_id: int) -> Optional[SentimentEvent]`
- `set_entity_to_database(event_id: int, event: SentimentEvent) -> bool`
- `get_events_by_asset(asset_id: int, start_date: date, end_date: date) -> List[SentimentEvent]`
- `get_events_by_type(sentiment_type_id: int, start_date: date, end_date: date) -> List[SentimentEvent]`
- `get_events_by_date_range(start_date: date, end_date: date) -> List[SentimentEvent]`

**TTL**: 90 days (historical events kept for analysis)

### Providers

**Pattern**: API providers fetch external data

#### PolygonNewsProvider
**File**: `src/api/provider/polygon_news_provider.py`
**API Endpoint**: `/v2/reference/news`
**Responsibilities**:
- Fetch news articles with sentiment analysis
- Parse Polygon news API responses
- Handle pagination, rate limiting

**Methods**:
- `fetch_news_for_symbol(symbol, published_after, published_before, limit) -> List[Dict]`
- `fetch_recent_news_for_universe(symbols, hours_ago) -> Dict[str, List[Dict]]`

**API Response Example**:
```json
{
  "title": "Apple Announces New Product",
  "published_utc": "2025-01-15T14:30:00Z",
  "tickers": ["AAPL"],
  "insights": [
    {
      "ticker": "AAPL",
      "sentiment": "positive",
      "sentiment_reasoning": "Product launch announcement typically drives positive sentiment"
    }
  ]
}
```

### Detection Service

**Pattern**: Orchestration layer (combines managers + providers + business logic)

#### SentimentDetectionService
**File**: `src/services/sentiment_detection_service.py`

**What It Does**:
The detection service is an orchestration layer that combines multiple components to detect and store sentiment events. Similar to how `DataService` orchestrates bootstrap operations.

**Workflow**:
```
1. Fetch news from PolygonNewsProvider (API calls)
   ↓
2. Parse sentiment from API responses (business logic)
   ↓
3. Create SentimentEvent model objects (data transformation)
   ↓
4. Store via SentimentEventsManager (database operations)
```

**Responsibilities**:
- Orchestrate sentiment detection from multiple sources
- Transform API data into SentimentEvent models
- Store events via managers
- Classify sentiment magnitude
- Apply filtering/validation rules

**Methods**:
- `detect_news_sentiment(symbol, lookback_days) -> List[SentimentEvent]`
- `detect_news_for_universe(universe_name, lookback_hours) -> int`
- `classify_magnitude(sentiment_score, source_reliability) -> str`

**Why Separate from Managers/Providers?**
- **Managers**: Only database CRUD, no business logic
- **Providers**: Only API calls, no database writes
- **Detection Service**: Combines both + detection/classification logic
- Similar to `DataService` which orchestrates bootstrap operations

### DataService Integration

**File**: `src/services/data_service.py`

**Methods Added**:
```python
def bootstrap_sentiment_types(self) -> int:
    """Bootstrap predefined sentiment types to database."""

def get_sentiment_events(
    self,
    asset_id: Optional[int] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    sentiment_type: Optional[str] = None
) -> List[SentimentEvent]:
    """Query sentiment events with flexible filtering."""
```

---

## Data Flow

### News Sentiment Detection Flow

```
1. Trigger: CLI command or scheduled job
   └─ "Detect news sentiment for AAPL in last 7 days"

2. SentimentDetectionService.detect_news_sentiment("AAPL", 7)
   ├─ Get asset_id from symbol via AssetManager
   ├─ Get sentiment_type_id for "news_positive" via SentimentTypesManager
   └─ Call PolygonNewsProvider.fetch_news_for_symbol("AAPL", ...)

3. PolygonNewsProvider fetches from Polygon API
   └─ Returns List[Dict] of news articles with sentiment

4. SentimentDetectionService processes articles
   ├─ For each article with sentiment:
   │   ├─ Extract: title, published_utc, sentiment, reasoning
   │   ├─ Classify magnitude based on confidence + source
   │   ├─ Create SentimentEvent model
   │   └─ Store via SentimentEventsManager.set_entity_to_database()
   └─ Return List[SentimentEvent] created

5. Result: Sentiment events stored in database
   └─ Available for gap analyzer catalyst queries
```

### Catalyst Validation Flow (Gap Analyzer)

```
1. Gap Analyzer detects gap_up for AAPL on 2025-01-15
   └─ Gap: +5.2% at market open

2. Check for sentiment catalyst:
   └─ data_service.get_sentiment_events(
        asset_id=get_asset_id("AAPL"),
        start_date=date(2025, 1, 14),
        end_date=date(2025, 1, 15)
      )

3. SentimentEventsManager queries database
   └─ Finds: news_positive event on 2025-01-14 evening
           (Product launch announcement)

4. Gap Analyzer enriches gap signal:
   └─ Gap: +5.2%, Catalyst: YES (news_positive), Confidence: HIGH

5. Trading decision:
   └─ Enter gap trade with full position size
```

---

## Bootstrapping

### Predefined Sentiment Types

**Bootstrap Method**: `DataService.bootstrap_sentiment_types()`

**Initial Types** (Phase 1 - News Only):
```python
SENTIMENT_TYPES = [
    # News sentiment (Phase 1 - NOW)
    {"name": "news_positive", "category": "news", "description": "Positive news sentiment"},
    {"name": "news_negative", "category": "news", "description": "Negative news sentiment"},
    {"name": "news_neutral", "category": "news", "description": "Neutral/informational news"},

    # Earnings (Phase 2 - LATER)
    # Will be added when earnings integration is built
    # {"name": "earnings_beat", "category": "earnings", "description": "Earnings exceed expectations"},
    # {"name": "earnings_miss", "category": "earnings", "description": "Earnings below expectations"},

    # Analyst ratings (Phase 3 - FUTURE)
    # {"name": "analyst_upgrade", "category": "analyst", "description": "Analyst rating increase"},
    # {"name": "analyst_downgrade", "category": "analyst", "description": "Analyst rating decrease"},
]
```

**Phase 1 Focus**: Start with news sentiment only. Earnings and analyst ratings will be added in future phases.

**Parameters Field Examples**:
```json
{
  "min_confidence": 0.7,
  "sources": ["polygon", "finnhub"],
  "magnitude_thresholds": {
    "small": [0.0, 0.5],
    "medium": [0.5, 0.8],
    "large": [0.8, 1.0]
  }
}
```

---

## Magnitude Classification

**Purpose**: Classify impact level of sentiment events

### Classification Criteria

| Magnitude | News Sentiment | Analyst Action | Earnings Event |
|-----------|---------------|----------------|----------------|
| **small** | Routine update, low confidence | Price target adjustment | In-line with estimates |
| **medium** | Notable news, moderate confidence | Single analyst upgrade/downgrade | 5-10% beat/miss |
| **large** | Breaking news, high confidence | Multiple analyst changes | >10% beat/miss |
| **extreme** | Major market-moving event | Consensus shift | Massive surprise |

### News Sentiment Example

**Factors**:
- Sentiment confidence score from API
- Source reliability (major outlet vs. blog)
- Article prominence (headline vs. mention)
- Time proximity to market open

**Algorithm**:
```python
def classify_news_magnitude(sentiment_score: float, source: str) -> str:
    """Classify news sentiment magnitude.

    Args:
        sentiment_score: 0.0 to 1.0 (confidence in sentiment)
        source: 'polygon', 'finnhub', etc.
    """
    # Source reliability multiplier
    reliability = SOURCE_WEIGHTS.get(source, 0.5)

    # Adjusted score
    adjusted = sentiment_score * reliability

    if adjusted >= 0.8:
        return "large"
    elif adjusted >= 0.5:
        return "medium"
    else:
        return "small"
```

---

## Future Enhancements

### Phase 2: Analyst Ratings

**Data Source**: Finnhub, Polygon (if available)
**New Types**: `analyst_upgrade`, `analyst_downgrade`, `price_target_increase`, `price_target_decrease`

**Use Case**:
- Track analyst consensus changes
- Weight by analyst reputation (Goldman vs. small firm)
- Detect upgrades before market reaction

### Phase 3: Earnings Events

**Data Source**: Polygon earnings API, Finnhub
**New Types**: `earnings_beat`, `earnings_miss`, `guidance_raised`, `guidance_lowered`

**Use Case**:
- Track earnings surprises
- Validate gap-and-go entries (earnings gap + positive guidance)
- Avoid fade setups on earnings gaps (too risky)

### Phase 4: Social Sentiment

**Data Source**: Twitter/X API, Reddit, Stocktwits
**New Types**: `social_buzz_spike`, `sentiment_shift_positive`, `sentiment_shift_negative`

**Use Case**:
- Detect retail trader interest spikes
- Monitor meme stock behavior
- Track sentiment momentum

### Phase 5: Multi-Source Correlation

**Concept**: Combine multiple sentiment sources for stronger signals

**Example**:
```
AAPL on 2025-01-15:
├─ news_positive (product launch)
├─ analyst_upgrade (Goldman raises price target)
└─ social_buzz_spike (trending on Twitter)

= STRONG BULLISH CATALYST (high confidence trade)
```

---

## CLI Integration (Future)

**Planned Commands**:
```bash
# Bootstrap sentiment types
tradescout sentiment bootstrap-types

# Detect news sentiment for symbol
tradescout sentiment detect-news AAPL --days 7

# Detect news for entire universe
tradescout sentiment detect-universe default_universe --hours 24

# Query sentiment events
tradescout sentiment query --symbol AAPL --start 2025-01-01 --end 2025-01-31

# Show sentiment for gap analysis
tradescout gaps analyze --date 2025-01-15 --with-sentiment
```

---

## Testing Strategy

### Unit Tests

**Manager Tests**:
- `tests/test_sentiment_types_manager.py` (15+ tests)
- `tests/test_sentiment_events_manager.py` (20+ tests)

**Provider Tests**:
- `tests/test_polygon_news_provider.py` (10+ tests, mocked API)

**Detection Service Tests**:
- `tests/test_sentiment_detection_service.py` (15+ tests)

### Integration Tests

**End-to-End Flow**:
- Fetch news → Parse sentiment → Store events → Query by asset
- Bootstrap types → Detect sentiment → Validate catalyst

### Test Data

**Mock News API Response**:
```json
{
  "results": [
    {
      "id": "abc123",
      "publisher": {"name": "CNBC"},
      "title": "Apple Announces New Product Line",
      "author": "John Smith",
      "published_utc": "2025-01-15T14:30:00Z",
      "article_url": "https://cnbc.com/apple-news",
      "tickers": ["AAPL"],
      "insights": [
        {
          "ticker": "AAPL",
          "sentiment": "positive",
          "sentiment_reasoning": "Product launch typically drives positive market sentiment"
        }
      ]
    }
  ]
}
```

---

## Key Design Principles

### 1. Separation of Concerns

**Sentiment ≠ Price Patterns**
- Sentiment system tracks market psychology/events
- Gap analyzer tracks price patterns
- They integrate but remain separate systems

### 2. Flexible Schema

**Support Multiple Event Types**
- Current: News sentiment (positive/negative/neutral)
- Future: Analyst ratings, earnings, social sentiment
- Schema accommodates all via `category` and `parameters` fields

### 3. Manager/Provider Pattern

**Consistent Architecture**
- Managers: Database CRUD operations
- Providers: External API calls
- Detection Service: Business logic orchestration

### 4. Catalyst Validation, Not Prediction

**Use Case Focus**
- Don't predict gaps from sentiment
- Validate detected gaps with sentiment context
- Enhance trade confidence with catalyst confirmation

### 5. Extensible Design

**Future-Proof**
- Add new sentiment types without schema changes
- Add new providers without changing managers
- Combine sources for multi-signal analysis

---

## Summary

**What**: System for detecting and storing market-moving sentiment events

**Why**: Validate gap trading signals with catalyst confirmation

**How**: News API → Detection Service → Sentiment Events → Catalyst Query

**Integration**: Gap analyzer checks for sentiment events around detected gaps

**Future**: Expand to analyst ratings, earnings, social sentiment, multi-source correlation

**Status**: Planning complete, ready for Phase 1 implementation (models + managers + news provider)
