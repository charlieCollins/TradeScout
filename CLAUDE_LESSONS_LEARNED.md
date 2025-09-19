# Claude Development Lessons Learned

**Project:** TradeScout - Personal Market Research Assistant
**Purpose:** Document critical development insights, antipatterns, and redirections to prevent future mistakes

---

## 🚨 Critical Code Quality Lessons

### **NEVER Fake Business Logic Implementations**

**Date:** 2025-09-16
**Context:** Gap analysis market cap filtering
**Issue:** Implemented fake filtering logic that appears to work but doesn't actually filter anything

**The Bad Code:**
```python
# Market cap check (requires fundamentals data - placeholder for now)
# TODO: Add market cap filtering when fundamentals API is implemented
# if market_cap < criteria["min_market_cap"]:
#     return False

return True  # Always passes - MISLEADING!
```

**Why This Is Terrible:**
1. **Silent Failures**: Code appears to work but produces wrong results
2. **False Confidence**: Stakeholders think feature is implemented
3. **Debug Nightmare**: Hard to trace why filtering isn't working
4. **Production Risk**: Academic strategy depends on market cap filtering

**Correct Approaches:**
```python
# Option 1: Fail explicitly
if not market_cap_available:
    raise NotImplementedError("Market cap filtering requires fundamentals API")

# Option 2: Remove criteria entirely
# Don't include market cap in criteria until implemented

# Option 3: Implement properly
market_cap = get_market_cap(symbol)  # Actually get the data
if market_cap < criteria["min_market_cap"]:
    return False
```

**Key Principle:**
**"Fail Fast, Fail Loud" > "Fake It Till You Make It"**

Code should either work correctly or fail obviously. Never silently pretend to work.

---

## 📝 Development Guidelines

### **When Feature Dependencies Are Missing:**
1. **Document the dependency explicitly** in code and architecture docs
2. **Fail with clear error messages** if dependency is required
3. **Remove incomplete features** from public interfaces until ready
4. **Never return fake success** for unimplemented functionality

### **Code Review Red Flags:**
- Commented-out business logic that should be active
- TODOs in production filtering/validation code
- Functions that always return True/False regardless of input
- "Placeholder" implementations in critical paths

---

---

## 🚨 AI Code Generation Quality Issues

### **Claude Code Tends to Generate Poor Quality Without Heavy Direction**

**Date:** 2025-09-18
**Context:** After weeks of development with Claude Code
**Issue:** AI assistant generates repetitive, low-quality code and recreates things over and over without heavy constraints

**The Problem:**
- Claude Code generates "crap" without heavy direction/constraints
- Recreates the same components repeatedly
- Produces boilerplate-heavy, over-engineered solutions
- Lacks consistency across sessions
- Introduces unnecessary complexity

**Root Causes:**
1. **Insufficient specification** - Vague requirements lead to generic solutions
2. **No architectural constraints** - Freedom leads to inconsistent patterns
3. **Context loss** - Assistant forgets previous decisions and patterns
4. **Over-eagerness** - Tries to be "helpful" by adding unnecessary features

**Solution - Heavy Direction Strategy:**
```
1. Create detailed specifications BEFORE coding
2. Define exact database schemas upfront
3. Specify precise API contracts
4. Establish clear architectural boundaries
5. Start fresh when design is flawed (don't try to fix bad foundations)
```

**Better Approach Example:**
```
BAD: "Create a gap analysis system"
- Results in generic, over-engineered mess

GOOD: "Implement this exact 8-table schema [provide schema]
       with these specific query patterns [provide queries]
       using only these libraries [list libraries]"
- Results in focused, clean implementation
```

**Key Principles:**
- **Specify, don't describe** - Give exact schemas, not high-level ideas
- **Constrain creativity** - Limit choices to prevent over-engineering
- **Start over when needed** - Bad foundations can't be fixed
- **Review frequently** - Catch deviations early

---

*This document helps maintain code quality by learning from mistakes and establishing clear standards for future development.*