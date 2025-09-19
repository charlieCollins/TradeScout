# TradeScout Development Guide

**Project:** Personal Market Research Assistant - TradeScout
**Developer:** Charlie Collins
**Start Date:** July 20, 2025
**Repository:** https://github.com/charlieCollins/TradeScout (Private)

## Development Partnership & Philosophy

We're building production-quality code together. Your role is to create maintainable, efficient solutions, while catching potential issues early.
When you seem stuck or problems are overly complex, I'll redirect you - my guidance helps you stay on track.

## Core Principles
- Feature branch development - no backwards compatibility needed
- Clarity over cleverness - simple solutions preferred
- Research → Plan → Test → Implement workflow
- **REMINDER**: If this file hasn't been referenced in 30+ minutes, RE-READ IT!

## Critical Workflow - ALWAYS FOLLOW THIS!

### Research → Plan → Implement
**NEVER JUMP STRAIGHT TO CODING!** Always follow this sequence:
1. **Research**: Explore codebase, understand patterns
2. **Plan**: Create detailed plan and verify with me
3. **Test-Driven Development**: Write failing tests first
4. **Implement**: Code to pass tests with validation checkpoints

**Always say:** "Let me research the codebase and create a plan before implementing."

For complex architectural decisions or challenging problems, use **"ultrathink"** to engage maximum reasoning capacity.

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
When responding to ideas or proposals:
1. First analyse the merits and limitations objectively
2. Present alternative viewpoints or approaches when any exist
3. Only then give your assessment
4. Use phrases like "That approach has X benefits, though consider Y" instead of "You're right"

Be intellectually honest. If an idea has flaws or limitations, point them out constructively. Act as a critical thinking partner, not a yes-person.
When analysing proposals, always consider: What could go wrong? What are the trade-offs? What alternatives exist?
Skip phrases like "You're absolutely right", "That's a great idea", "Excellent point" - Lead with analysis, not agreement.

## Problem Solving


## Advanced Techniques

### Multiple Agents Strategy
*Leverage subagents aggressively* for better results:

* Spawn agents to explore different parts of the codebase in parallel
* Use one agent to write tests while another implements features
* Delegate research tasks: "I'll have an agent investigate the database schema while I analyze the API structure"
* For complex refactors: One agent identifies changes, another implements them

Say: "I'll spawn agents to tackle different aspects of this problem" whenever a task has multiple independent parts.

### Problem-Solving When Stuck
When you're stuck or confused:
1. **Stop** - Don't spiral into complex solutions
2. **Delegate** - Consider spawning agents for parallel investigation
3. **Ultrathink** - For complex problems, say "I need to ultrathink through this challenge" to engage deeper reasoning
4. **Step back** - Re-read the requirements
5. **Simplify** - The simple solution is usually correct
6. **Ask** - "I see two approaches: [A] vs [B]. Which do you prefer?"

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

## Session Management & State Continuity

### Session Continuity
- Run `claude --continue` or `claude --resume` to resume conversations
- Session workflows imported via @CLAUDE_SESSION_MGMT.md

### Optional Session Management Commands
Use `/hello` and `/goodbye` slash commands for structured session management:

**Benefits of structured session workflow:**
- **Explicit context bridging** - Ensures nothing falls through cracks
- **TODO synchronization** - Bridges Claude's TodoWrite with persistent files
- **Progress documentation** - Creates searchable session history
- **Handoff preparation** - Good for team environments

**Alternative:** Simple `claude --continue` for lightweight session resumption without ceremony.

### Import-Based Context Management
@CLAUDE_SESSION_MGMT.md
@CLAUDE_LESSONS_LEARNED.md

### File Structure
- `CLAUDE.md` - Main project instructions with imports
- `CLAUDE_TODO.md` - Task synchronization (separate file for tool compatibility)
- `CLAUDE_CONTEXT.md` - Session history and context storage (managed by workflows)
- `CLAUDE_LESSONS_LEARNED.md` - Development insights and redirections

### TODO File Management (CLAUDE_TODO.md)
- Keep CLAUDE_TODO.md concise and forward-looking only
- Remove completed tasks regularly - we don't need historical completed work cluttering the file
- Focus on what's next to do, not what's already been accomplished
- The TODO file should be actionable and clean for the next session

### TodoWrite Best Practices
- Always use TodoWrite for task management
- Mark tasks as completed immediately upon finishing
- Clean up completed tasks from the list regularly
- Keep active TODO list focused on current and upcoming work

## Key Reminders
- Never commit unless explicitly asked
- Cache API calls to avoid rate limits
- Save example data to avoid repeated API calls