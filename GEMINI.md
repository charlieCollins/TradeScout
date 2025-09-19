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

