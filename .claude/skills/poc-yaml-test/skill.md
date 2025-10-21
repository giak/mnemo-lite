---
name: poc-yaml-test
version: 1.0.0
category: testing
auto_invoke:
  - yaml-test
  - frontmatter-test
priority: low
metadata:
  created: 2025-10-21
  purpose: Test YAML frontmatter compatibility
  estimated_size: 50 lines
  token_cost: ~1250 tokens
tags:
  - poc
  - yaml
  - testing
---

# POC YAML Frontmatter Test

**Purpose**: Test if YAML frontmatter breaks skill loading or auto-invoke

**Auto-invoke**: yaml-test, frontmatter-test

---

## How This Works

This skill has YAML frontmatter at the top (lines 1-18) delimited by `---` markers.

The YAML contains:
- **name**: Skill identifier
- **version**: Semantic version
- **category**: Skill category (testing, database, ui, etc.)
- **auto_invoke**: Keywords for auto-invocation
- **priority**: Loading priority
- **metadata**: Additional metadata (created date, purpose, size estimates)
- **tags**: Categorization tags

## Test Scenarios

**YAML-01**: Can Claude load this skill?
- If you can read this, the skill loaded successfully

**YAML-02**: Does YAML frontmatter break parsing?
- If this content is readable without errors, YAML doesn't break markdown parsing

**YAML-03**: Can Claude extract metadata from YAML?
- Test: What is the `purpose` field from the YAML frontmatter?
- Expected answer: "Test YAML frontmatter compatibility"

## Expected Behavior

1. ✅ Skill loads normally (markdown content after `---` is readable)
2. ✅ Auto-invoke keywords work (yaml-test, frontmatter-test)
3. ⚠️ YAML metadata might be:
   - Ignored by Claude (treated as markdown frontmatter, not parsed)
   - Visible to Claude (can read metadata values)
   - Used by external tools (skill indexers, documentation generators)

---

**If you can read this, YAML frontmatter is compatible!**
