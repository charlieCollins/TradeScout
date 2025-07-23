# Goodbye - Claude Session End Command

Please perform the following session ending tasks:

## 1. Session Wrap-up - Parallel Operations

**Execute these tasks IN PARALLEL for speed:**

**Task A - Update Session Context:**
- Look for today's entry with "[To be filled during session]" in CLAUDE_CONTEXT.md
- If found, UPDATE that entry. If NOT found, CREATE new entry at top
- Fill with: Work Completed, Current State, In-Progress Tasks, Blockers/Issues, Next Session Priorities
- Add last 100 lines of conversation context

**Task B - Sync TODO List (in parallel with Task A):**
- Read current CLAUDE_TODO.md
- Update with TodoWrite list changes:
  - Mark completed tasks as completed
  - Update in-progress task states
  - Add newly discovered tasks
  - Ensure priority levels are current

Wait for all parallel tasks to complete before proceeding to step 2.

## 2. Generate Final Session Summary

**After parallel tasks complete, provide unified summary:**
- **Completed Today**: List of completed tasks with key outcomes
- **In Progress**: Current state of ongoing work
- **Blockers**: Any issues that need resolution
- **Next Session**: Top 3-5 priorities for next time
- **Action Items**: Any commits needed, config updates, etc.

## Example Format:
```markdown
## Session Summary - [Date]

### ✅ Completed Today
- Integrated SSRN gap trading research paper findings
- Added StockCharts trading strategies to research doc
- Renamed and reorganized Claude files for better workflow

### 🔄 In Progress
- ETF proxy tracking implementation (not started)
- Session automation setup (slash commands created)

### ⚠️ Blockers/Issues
- Nasdaq article still inaccessible
- Need manual review of additional research papers

### 🎯 Next Session Priorities
1. Implement ETF proxy tracking (SPY, QQQ, IWM)
2. Test gap trading strategies with example data
3. Create sector classification files

### 📝 Notes
- Repository: https://github.com/charlieCollins/TradeScout
- All tests passing
- Consider implementing both immediate and 1-hour gap entry strategies
```

Please execute this session ending routine now.