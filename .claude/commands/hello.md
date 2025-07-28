# Hello - Claude Session Start Command

Please perform the following session starting tasks:

## 1. Initialize Session - Parallel Operations

**Execute these tasks IN PARALLEL for speed:**

**Task A - Context File Management:**
- Check if CLAUDE_CONTEXT.md exists (create if needed)
- Remove entries older than 3 days
- Check for existing today's entry with "[To be filled during session]"
- If no today's entry exists, create new timestamped entry at TOP:

```markdown
## Session Entry - [YYYY-MM-DD HH:MM]

### Work Completed
- [To be filled during session]

### Current State
- [To be filled during session]

### In-Progress Tasks
- [To be filled during session]

### Blockers/Issues
- [To be filled during session]

### Next Session Priorities
- [To be filled during session]

### Conversation Context
[To be filled at session end]

---
```

**Task B - Read Project Files (in parallel with Task A):**
- Read CLAUDE.md - Project guidelines and principles
- Read CLAUDE_TODO.md - Current task list and priorities
- Read CLAUDE_CONTEXT.md - Previous session contexts

Wait for all parallel tasks to complete before proceeding to step 2.

## 2. Provide Session Briefing
Generate a concise briefing including:
- **Current State**: Brief summary of where we left off
- **Today's Priorities**: Top 3-5 tasks from TODO list
- **Context**: Any important context from previous session
- **Ready to Start**: Confirm readiness to begin work

## 3. Set Up Working Memory
- **CRITICAL**: Use TodoWrite tool to sync all pending tasks from CLAUDE_TODO.md
- Extract all incomplete tasks and add them to TodoWrite with appropriate priority levels
- Note any blockers from previous session
- Prepare for the first task

## Example Format:
```markdown
## Session Briefing - [Date]

### 📍 Current State
Last session we integrated gap trading research from SSRN paper and StockCharts. 
The research doc now has comprehensive academic findings and practical strategies.

### 🎯 Today's Priorities
1. **ETF Proxy Tracking** (High) - Implement SPY, QQQ, IWM tracking
2. **Direct Index Symbols** (Medium) - Add ^GSPC, ^IXIC support
3. **Sector Classification** (Medium) - Create sector data files

### 📋 Context
- Phase 1 market movers complete and working
- Gap trading research significantly enhanced
- All tests passing, system healthy

### ✅ Ready to Start
System checked, context loaded, ready to begin with ETF proxy tracking implementation.

Which task would you like to start with?
```

Please execute this session starting routine now.