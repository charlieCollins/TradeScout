# Presentation Context - Output-Agnostic Command Design

**Status:** ✅ Complete
**Created:** 2025-10-18
**Completed:** 2025-10-18
**Pattern:** Dependency Injection + Adapter Pattern

## Summary

Successfully refactored TradeScout's command layer to be output-agnostic using the PresentationContext pattern:

**Completed:**
- ✅ Created `PresentationContext` to manage output adapters
- ✅ Injected all CLI adapters in `main.py`
- ✅ Refactored ALL commands to use adapter pattern
- ✅ Created Web adapters for API endpoints
- ✅ Pattern fully implemented across CLI and Web

**CLI Adapters Created (11):**
1. `CLIScreenerOutputAdapter` - Screener results
2. `CLIGapAnalysisAdapter` - Gap analysis results
3. `CLIGapPerformanceAdapter` - Gap backtest performance
4. `CLIBootstrapOutputAdapter` - Bootstrap operations (CLI-only)
5. `CLINewsOutputAdapter` - News/sentiment results
6. `CLIAssetOutputAdapter` - Asset information
7. `CLIMarketOutputAdapter` - Market updates and context
8. `CLIUniverseOutputAdapter` - Universe listings
9. `CLIValidateOutputAdapter` - Validation results
10. `CLIFedOutputAdapter` - Federal reserve data
11. `CLIDatabaseOutputAdapter` - Database statistics (CLI-only)

**Web Adapters Created (8):**
1. `WebScreenerOutputAdapter` - Screener results as JSON
2. `WebGapOutputAdapter` - Gap analysis as JSON
3. `WebMarketOutputAdapter` - Market data as JSON
4. `WebAssetOutputAdapter` - Asset information as JSON
5. `WebNewsOutputAdapter` - News/sentiment as JSON
6. `WebUniverseOutputAdapter` - Universe data as JSON
7. `WebValidateOutputAdapter` - Validation results as JSON
8. `WebFedOutputAdapter` - Federal reserve data as JSON

**Note:** Bootstrap and Database operations are CLI-only utilities (no web adapters)

---

## Design Problem

Commands were coupled to specific output formats, making it impossible to reuse business logic across different interfaces:

**❌ Before:**
```python
# screener_commands.py
def screener(app_context, screener_name):
    results = screener_engine.execute_screener(...)

    # HARDCODED to CLI output
    console.print(f"Found {len(results)} results")
    table = Table(...)
    console.print(table)
```

**Issues:**
- Business logic mixed with presentation
- Can't use same command for Web API (needs JSON)
- Can't test results programmatically
- Can't swap output formats

---

## Design Solution

**Separation of Concerns:** Application State vs. Presentation Layer

```
┌─────────────────────────────────────────────────┐
│           AppContext (Application State)        │
├─────────────────────────────────────────────────┤
│ • Database connections                          │
│ • API clients (Polygon)                         │
│ • Services (DataServiceV2, MarketContextService)│
│ • Active universe                               │
│                                                 │
│ ┌─────────────────────────────────────────┐   │
│ │  PresentationContext (Display Layer)    │   │
│ ├─────────────────────────────────────────┤   │
│ │ • screener_adapter (injected)           │   │
│ │ • gap_adapter (injected)                │   │
│ │ • asset_adapter (injected)              │   │
│ └─────────────────────────────────────────┘   │
└─────────────────────────────────────────────────┘
```

**Key Principle:** AppContext contains a nested PresentationContext that holds output adapters.

---

## Architecture Components

### 1. PresentationContext (Presentation Layer Manager)

**File:** `src/utils/presentation_context.py`

```python
class PresentationContext:
    """Manages output adapters - separate from application state.

    This is the PRESENTATION LAYER - concerns about HOW to display results.
    Injected differently by CLI vs Web vs Test environments.
    """

    def __init__(self, screener_adapter=None, gap_adapter=None, asset_adapter=None):
        self.screener_adapter = screener_adapter  # CLI/Web/JSON adapter
        self.gap_adapter = gap_adapter
        self.asset_adapter = asset_adapter
```

**Why separate from AppContext?**
- AppContext = "What is the state of the application?" (DB, APIs, data)
- PresentationContext = "How should we display results?" (CLI, Web, JSON)
- Different concerns, different lifecycles

### 2. Result Models (Output-Agnostic Data Containers)

**File:** `src/models/dataclass/screener_result.py`

```python
@dataclass
class ScreenerResult:
    """Pure data - no display logic, no CLI dependencies.

    Contains ALL information needed to display results in ANY format.
    Can be serialized, tested, logged, cached.
    """
    screener_name: str
    results: List[Dict[str, Any]]
    screener_def: Dict[str, Any]
    resolved_config: Dict[str, Any]
    market_context: Any  # MarketContext
    excluded_count: int
    snapshot_time: Optional[str] = None
    sessions_text: Optional[str] = None
    warnings: Optional[List[str]] = None
    data_date_summary: Optional[Dict[str, Any]] = None
```

**Design Principle:** Result models are plain dataclasses with ZERO display logic.

### 3. Output Adapters (Format-Specific Display)

**File:** `src/output/cli_screener_adapter.py`

```python
class CLIScreenerOutputAdapter:
    """CLI-specific display using Rich library."""

    def display_screener_results(self, result: ScreenerResult):
        """Takes result model, displays with Rich tables/formatting."""
        # Extract data from model
        # Create Rich tables
        # Print to console
```

**File:** `src/output/json_output_adapter.py` (future)

```python
class JSONOutputAdapter:
    """Web API display - serializes to JSON."""

    def display_screener_results(self, result: ScreenerResult):
        """Takes result model, returns JSON dict."""
        return {
            "screener": result.screener_name,
            "results": result.results,
            "excluded_count": result.excluded_count,
            # ... serialize all fields
        }
```

**Design Principle:** Adapters implement format-specific display logic for a result model.

### 4. Dependency Injection (Interface Layer)

**File:** `src/cli/main.py` (CLI injects CLI adapters)

```python
@click.group()
@pass_config
def main(app_context, ...):
    # CLI layer injects CLI adapters
    if app_context.presentation is None:
        from utils.presentation_context import PresentationContext
        from output.cli_screener_adapter import CLIScreenerOutputAdapter

        app_context.presentation = PresentationContext(
            screener_adapter=CLIScreenerOutputAdapter(),
            # More adapters as we refactor other commands
        )
```

**File:** `src/web/app.py` (future - Web injects JSON adapters)

```python
def create_app():
    # Web layer injects JSON adapters
    app_context = AppContext(
        presentation=PresentationContext(
            screener_adapter=JSONOutputAdapter()
        )
    )

    @app.get("/api/screener/{name}")
    def run_screener(name: str):
        # Same business logic as CLI!
        result = screener_logic(app_context, name)
        return result  # JSONOutputAdapter returns dict
```

**Design Principle:** Interface layer (CLI/Web) injects appropriate adapters.

### 5. Output-Agnostic Commands

**File:** `src/cli/screener_commands.py`

```python
def screener(app_context, screener_name: str, ...):
    """Command is completely agnostic to output format."""

    # Execute business logic (same for CLI/Web/Test)
    screener_engine = ScreenerEngine(data_service, app_context)
    results, excluded_count = screener_engine.execute_screener(...)

    # Create output-agnostic result model
    result = ScreenerResult(
        screener_name=screener_name,
        results=results,
        screener_def=screener_def,
        resolved_config=resolved_config,
        market_context=market_context,
        excluded_count=excluded_count,
        snapshot_time=snapshot_time,
        sessions_text=sessions_text,
        warnings=all_warnings,
        data_date_summary=data_date_summary
    )

    # Display using injected adapter (command doesn't know if CLI/Web/JSON!)
    app_context.presentation.screener_adapter.display_screener_results(result)
```

**Design Principle:** Commands create result models and delegate display to injected adapters.

---

## Data Flow

```
┌──────────────┐
│ CLI main.py  │ Injects CLIScreenerOutputAdapter into PresentationContext
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  AppContext  │ Contains: presentation.screener_adapter = CLIScreenerOutputAdapter
└──────┬───────┘
       │
       ▼
┌──────────────────┐
│ screener command │ Executes business logic, creates ScreenerResult
└──────┬───────────┘
       │
       ▼
┌─────────────────────┐
│  ScreenerResult     │ Plain dataclass with all data (no display logic)
└──────┬──────────────┘
       │
       ▼
┌───────────────────────────────────────┐
│ app_context.presentation              │
│   .screener_adapter                   │
│   .display_screener_results(result)   │ Uses injected adapter
└──────┬────────────────────────────────┘
       │
       ▼
┌────────────────────────────┐
│ CLIScreenerOutputAdapter   │ Displays with Rich tables/formatting
└────────────────────────────┘
```

**If Web:** Same flow, but Web injects JSONOutputAdapter → Returns JSON dict

---

## Benefits

### ✅ Separation of Concerns
- **AppContext:** Application state (DB, APIs, services)
- **PresentationContext:** Display adapters (CLI, Web, JSON)
- **Result Models:** Pure data containers
- **Adapters:** Format-specific display

### ✅ Reusability
- Same business logic works for CLI, Web, Tests
- No code duplication between interfaces
- Easy to add new output formats

### ✅ Testability
```python
# Test without CLI dependencies
def test_screener():
    result = screener_logic(app_context, "gainers")
    assert result.screener_name == "gainers"
    assert len(result.results) > 0
    # No CLI output, just check data
```

### ✅ Flexibility
```python
# Switch adapters at runtime
if args.json:
    app_context.presentation.screener_adapter = JSONOutputAdapter()
else:
    app_context.presentation.screener_adapter = CLIScreenerOutputAdapter()
```

### ✅ Maintainability
- Display changes don't affect business logic
- Business logic changes don't affect display
- Each component has single responsibility

---

## Implementation Checklist

For refactoring other commands (gap, asset, market):

### Step 1: Create Result Model
- [ ] Create `src/models/dataclass/{command}_result.py`
- [ ] Define dataclass with ALL data needed for display
- [ ] NO display logic in model

### Step 2: Create CLI Adapter
- [ ] Create `src/output/cli_{command}_adapter.py`
- [ ] Implement `display_{command}_results(result)` method
- [ ] Use Rich library for formatting
- [ ] Adapt existing display classes if they exist

### Step 3: Update PresentationContext
- [ ] Add `{command}_adapter` attribute to `PresentationContext`
- [ ] Update `__init__` signature

### Step 4: Inject Adapter
- [ ] Update `main.py` to instantiate CLI adapter
- [ ] Add to `PresentationContext` initialization

### Step 5: Refactor Command
- [ ] Remove hardcoded `console.print()` calls
- [ ] Build result model with all data
- [ ] Call `app_context.presentation.{command}_adapter.display_results(result)`

### Step 6: Test
- [ ] Verify command still works
- [ ] Verify output looks identical
- [ ] Verify no hardcoded console usage remains

---

## Commands Status

### All Commands Use PresentationContext Pattern

| Domain | CLI Adapter | Web Adapter | Result Model(s) | Status |
|--------|-------------|-------------|-----------------|--------|
| **Screener** | CLIScreenerOutputAdapter | WebScreenerOutputAdapter | ScreenerResult | ✅ Complete |
| **Gap Analysis** | CLIGapAnalysisAdapter | WebGapOutputAdapter | GapAnalysisResult | ✅ Complete |
| **Gap Backtest** | CLIGapPerformanceAdapter | WebGapOutputAdapter | GapPerformanceResult | ✅ Complete |
| **Market** | CLIMarketOutputAdapter | WebMarketOutputAdapter | MarketUpdateResult, MarketContextResult, MarketBackfillResult | ✅ Complete |
| **Asset** | CLIAssetOutputAdapter | WebAssetOutputAdapter | AssetInfoResult, PriceDataResult, MarketContextResult, SentimentEventsResult | ✅ Complete |
| **News** | CLINewsOutputAdapter | WebNewsOutputAdapter | NewsResult | ✅ Complete |
| **Universe** | CLIUniverseOutputAdapter | WebUniverseOutputAdapter | UniverseListResult, UniverseInfoResult | ✅ Complete |
| **Validate** | CLIValidateOutputAdapter | WebValidateOutputAdapter | VolumeValidationResult | ✅ Complete |
| **Fed** | CLIFedOutputAdapter | WebFedOutputAdapter | FedDataResult | ✅ Complete |
| **Bootstrap** | CLIBootstrapOutputAdapter | N/A (CLI-only) | BootstrapResult | ✅ Complete |
| **Database** | CLIDatabaseOutputAdapter | N/A (CLI-only) | DatabaseStats | ✅ Complete |

**Architecture:**
- All commands build result models (output-agnostic data)
- CLI commands use CLI adapters (Rich formatting)
- Web endpoints use Web adapters (JSON serialization)
- Same business logic works for both CLI and Web

---

## Design Decisions

### Why PresentationContext inside AppContext?

**Alternative:** Pass both contexts separately
```python
def screener(app_context, presentation_context, ...):  # Two parameters
```

**Chosen:** Nest PresentationContext in AppContext
```python
def screener(app_context, ...):
    app_context.presentation.screener_adapter  # One parameter
```

**Reason:** Cleaner API, presentation is part of application runtime context.

### Why Result Models instead of returning raw data?

**Alternative:** Commands return dicts/lists
```python
def screener(...):
    return {"results": [...], "excluded": 123}  # Unstructured
```

**Chosen:** Commands create typed result models
```python
def screener(...):
    return ScreenerResult(results=[...], excluded_count=123)  # Typed, structured
```

**Reason:** Type safety, documentation, IDE support, validation.

### Why adapters instead of formatters?

**Alternative:** Have formatters that return strings
```python
formatter.format(result) -> str
```

**Chosen:** Adapters that handle display directly
```python
adapter.display(result)  # Handles all I/O
```

**Reason:** More flexible - CLI can print, Web can return JSON, some outputs can't be strings (binary files, streams).

---

## Future Enhancements

### Web Integration
```python
# src/web/app.py
from fastapi import FastAPI
from utils.presentation_context import PresentationContext
from output.json_output_adapter import JSONOutputAdapter

app_context = AppContext(
    presentation=PresentationContext(
        screener_adapter=JSONOutputAdapter()
    )
)

@app.get("/api/screener/{name}")
def run_screener(name: str):
    # Reuse same screener logic!
    from cli.screener_commands import screener_logic
    result = screener_logic(app_context, name)
    return result  # JSONOutputAdapter makes it JSON-serializable
```

### Testing Framework
```python
# tests/test_screener.py
from utils.presentation_context import PresentationContext
from output.test_output_adapter import TestOutputAdapter  # Captures results

test_adapter = TestOutputAdapter()
app_context = AppContext(
    presentation=PresentationContext(
        screener_adapter=test_adapter
    )
)

result = screener_logic(app_context, "gainers")
assert test_adapter.captured_result.screener_name == "gainers"
```

### Hybrid Output
```python
# CLI with optional JSON export
if args.export_json:
    json_adapter = JSONOutputAdapter()
    json_data = json_adapter.display_screener_results(result)
    with open("results.json", "w") as f:
        json.dump(json_data, f)

# Also show in CLI
cli_adapter.display_screener_results(result)
```

---

## References

- **Design Patterns Used:**
  - Dependency Injection (adapters injected at runtime)
  - Adapter Pattern (adapts result model to specific output format)
  - Strategy Pattern (swap output strategies)

- **Related Docs:**
  - `docs/ARCHITECTURE.md` - Overall system architecture
  - `docs/OUTPUT_PLANNING.md` - Original output adapter planning

- **Key Files:**
  - `src/utils/presentation_context.py` - PresentationContext definition
  - `src/utils/app_context.py` - AppContext with nested presentation
  - `src/models/dataclass/screener_result.py` - Result model example
  - `src/output/cli_screener_adapter.py` - CLI adapter example
  - `src/cli/screener_commands.py` - Output-agnostic command example
