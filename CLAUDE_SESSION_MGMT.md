# Session Management & State Continuity

This file provides standardized workflows for Claude Code session management, designed to be imported into project CLAUDE.md files.

## Session Initialization (/hello command workflow)

### 1. Initialize Session - Parallel Operations

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

### 2. Provide Session Briefing
Generate a concise briefing including:
- **Current State**: Brief summary of where we left off
- **Today's Priorities**: Top 3-5 tasks from TODO list
- **Context**: Any important context from previous session
- **Ready to Start**: Confirm readiness to begin work

### 3. Set Up Working Memory
- **CRITICAL**: Use TodoWrite tool to sync all pending tasks from CLAUDE_TODO.md
- Extract all incomplete tasks and add them to TodoWrite with appropriate priority levels
- Note any blockers from previous session
- Prepare for the first task

### Example Session Briefing Format:
```markdown
## Session Briefing - [Date]

### 📍 Current State

### 🎯 Today's Priorities

### 📋 Context

### ✅ Ready to Start

Which task would you like to start with?
```

## Session Wrap-up (/goodbye command workflow)

### 1. Session Wrap-up - Parallel Operations

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

### 2. Generate Final Session Summary

**After parallel tasks complete, provide unified summary:**
- **Completed Today**: List of completed tasks with key outcomes
- **In Progress**: Current state of ongoing work
- **Blockers**: Any issues that need resolution
- **Next Session**: Top 3-5 priorities for next time
- **Action Items**: Any commits needed, config updates, etc.

### Example Session Summary Format:
```markdown
## Session Summary - [Date]

### ✅ Completed Today
- 

### 🔄 In Progress
- 

### ⚠️ Blockers/Issues
- 

### 🎯 Next Session Priorities
1. 

### 📝 Notes
- 
```

## File Structure & Dependencies

This session management system works with:
- **CLAUDE.md** - Main project instructions (imports this file)
- **CLAUDE_TODO.md** - Task synchronization with TodoWrite tool
- **CLAUDE_CONTEXT.md** - Session history and context storage
- **CLAUDE_LESSONS_LEARNED.md** - Development insights and redirections

## Context Preservation Guidelines

### When context gets long:
- Re-read the main CLAUDE.md file
- Summarize progress in session entries
- Document current state before major changes

### Long-term State Management:
- Keep CLAUDE_CONTEXT.md entries for 3 days max
- Archive important insights to CLAUDE_LESSONS_LEARNED.md
- Maintain CLAUDE_TODO.md with current priorities
- Use `claude --continue` or `claude --resume` for session continuity

## Integration Notes

This file is designed to be imported into project CLAUDE.md files using:
```markdown
@CLAUDE_SESSION_MGMT.md
```

The workflows reference TodoWrite tool integration and assume standard Claude Code slash command setup.