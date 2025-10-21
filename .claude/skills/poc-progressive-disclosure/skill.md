# POC Progressive Disclosure - Test Skill

**Purpose**: Test if Claude Code can load Level 3 files via @filename.md references

**Auto-invoke**: poc-test, test-progressive, level3-test

---

## How This Works

This is a minimal test skill with a 3-level structure:

- **Level 1** (Metadata): Name + auto-invoke keywords
- **Level 2** (This file): Basic instructions and index
- **Level 3** (External files): Detailed content loaded on-demand

## Test Instructions

When troubleshooting errors, you should reference **@critical.md** for critical gotchas.

### Test Scenarios

**TEST-01**: Database connection fails
→ Check @critical.md #TEST-01

**TEST-02**: Cache initialization errors
→ Check @critical.md #TEST-02

**TEST-03**: Async/await issues
→ Check @critical.md #TEST-03

---

**Expected Behavior**:
- Claude loads this file (~20 lines, ~500 tokens)
- Claude can reference and read @critical.md when needed (~30 lines, ~750 tokens)
- Total: ~50 lines instead of monolithic 50 lines (same for small test, but validates pattern)
