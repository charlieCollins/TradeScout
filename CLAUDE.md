# TradeScout Development Guide

**Project:** Personal Market Research Assistant - TradeScout  
**Developer:** Charlie Collins  
**Start Date:** July 20, 2025  
**Repository:** https://github.com/charlieCollins/TradeScout (Private)

## Core Principles
- Feature branch development - no backwards compatibility needed
- Clarity over cleverness - simple solutions preferred
- Research → Plan → Test → Implement workflow

## Critical Workflow
1. **Research**: Explore codebase, understand patterns
2. **Plan**: Create detailed plan and verify with me  
3. **Test-Driven Development**: Write failing tests first
4. **Implement**: Code to pass tests with validation checkpoints

**Always say:** "Let me research the codebase and create a plan before implementing."

## Implementation Standards

### Design Patterns
- **Strategy**: Interchangeable algorithms (momentum detection)
- **Adapter**: External APIs (YFinance, Polygon)
- **Factory**: Provider creation
- **Repository**: Data access abstraction
- **Decorator**: Caching, rate limiting

### Coding Standards
- Delete old code when replacing
- Meaningful names: `userID` not `id`
- Early returns to reduce nesting
- No comments unless asked


## Testing & Quality

### Code Complete Criteria
- ✓ All lint/type checks pass
- ✓ Adequate test coverage
- ✓ All tests pass
- ✓ Feature works end-to-end
- ✓ Old code deleted

### Testing Strategy
- Complex business logic → Tests first
- Simple CRUD → Tests after
- Skip tests for main() and CLI parsing

## Communication & Collaboration

### When to Ask for Review
- Architectural decisions affecting multiple components
- Major refactors (>3 files or >100 lines)
- Adding new dependencies
- Stuck >15 minutes
- Uncertain about solution approach

### Progress Updates Format
```
✓ Implemented authentication (tests passing)
✓ Added rate limiting  
✗ Token expiration issue - investigating
```

### Critical Thinking Partnership
- Analyze merits and limitations objectively
- Present alternatives when they exist
- Point out flaws constructively
- Avoid "You're right" - lead with analysis

## Problem Solving

### When Stuck
1. **Stop** - Don't spiral into complex solutions
2. **Delegate** - Use agents for parallel investigation
3. **Ultrathink** - For complex problems
4. **Step back** - Re-read requirements
5. **Simplify** - Simple solution usually correct
6. **Ask** - Present options with trade-offs

### Multiple Agents Strategy
- Spawn agents for parallel codebase exploration
- One agent for tests, another for implementation
- Delegate research tasks to agents
- Use for complex refactoring

## Project Architecture

### Critical Data Rules - PRICE COMPARISONS

**ALWAYS:**
1. **Previous SESSION close** = Last regular trading session close (could be today, yesterday, 3 days ago - doesn't matter)
   - Get from bulk snapshot API
   
2. **Current REAL-TIME price** = The price RIGHT NOW (pre-market, regular, after-hours - doesn't matter)
   - Get from individual real-time quote API

**The calculation is ALWAYS:**
- Change = Current real-time price - Previous session close
- Change % = (Change / Previous session close) × 100

**PERIOD. That's it.**

### Development vs Production Separation
- **Production** (`src/tradescout/`): Clean code, standard cache
- **Exploration** (`data/examples/`): Simple file saving for API results
- **Principle**: Production code pristine, exploration uses file caching

### Technology Stack
- **Backend**: Python CLI with Rich interface
- **Database**: SQLite (implemented)
- **APIs**: Multi-provider system (Polygon PREMIUM SUBSCRIPTION - NOT FREE TIER, YFinance, Finnhub, Alpha Vantage, NewsAPI)
- **Web Scrapers**: Extended hours data collection
- **Platform**: Linux/Ubuntu/WSL2
- **Budget**: $0-50/month (includes POLYGON PREMIUM SUBSCRIPTION)
- **IMPORTANT**: We have a PREMIUM Polygon subscription - NEVER assume free tier limitations

## Session Management

### TODO File Management (CLAUDE_TODO.md)
- Keep CLAUDE_TODO.md concise and forward-looking only
- Remove completed tasks regularly - we don't need historical completed work cluttering the file
- Focus on what's next to do, not what's already been accomplished
- Completed work and session based information should be documented in CLAUDE_CONTEXT.md instead of elsewhere
- The TODO file should be actionable and clean for the next session
- **Sync TODOs to CLAUDE_TODO.md every hour** - For session continuity

### TodoWrite Best Practices
- Always use TodoWrite for task management
- Mark tasks as completed immediately upon finishing
- Clean up completed tasks from the list regularly
- Keep active TODO list focused on current and upcoming work

## Key Reminders
- Never commit unless explicitly asked
- Cache API calls to avoid rate limits
- Save example data to avoid repeated API calls