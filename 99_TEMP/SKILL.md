---
name: document-lifecycle
description: Document lifecycle management (TEMP/DRAFT/RESEARCH/DECISION/ARCHIVE). Use for organizing docs, managing ADRs, preventing doc chaos.
---
# Document Lifecycle Management Skill

**Version**: 1.0
**Author**: Human + AI (Claude)
**Date**: 2025-01-20
**Purpose**: Manage document lifecycle during AI-assisted deep thinking and brainstorming

---

## When to Use This Skill

Use this skill when:
- Creating multiple research/analysis documents during brainstorming
- Managing architectural decision records (ADRs)
- Need clear distinction between temporary vs permanent documents
- Working on long-term projects with evolving documentation
- Collaborating with humans who need to understand document status at a glance

**Problem solved**: Prevents document proliferation chaos ("which file is the source of truth?")

---

## Core Principle: Screaming Architecture for Documents

### The Problem

During deep thinking/brainstorming, AIs and humans create many files:
- Some are temporary (just thinking out loud)
- Some are work-in-progress (drafts, research)
- Some are decisions (permanent, source of truth)
- Some are historical (archived, superseded)

**Without structure**: Confusion, duplication, lost context, unclear status

### The Solution: Screaming Names + Clear Lifecycle

**Every filename must SCREAM its purpose and lifecycle**

---

## Naming Convention

### Format

```
{TYPE}_{DATE}_{TOPIC}.md
```

- `TYPE`: Lifecycle prefix (see table below)
- `DATE`: ISO 8601 (`YYYY-MM-DD`) for temporary files only
- `TOPIC`: Descriptive name

### Type Prefixes (SCREAMING)

| Prefix | Lifecycle | Meaning | When to Delete/Archive |
|--------|-----------|---------|------------------------|
| `TEMP_` | Volatile | Quick scratch, thinking out loud | After session (7 days max) |
| `DRAFT_` | Short-term | Structured thinking, not ready | Promote or archive (30 days) |
| `RESEARCH_` | Medium-term | Deep analysis, exploration | Archive when → decision |
| `DECISION_` | Permanent | Official decisions, ADRs | Never (update in place) |
| `CONTROL_` | Permanent | Dashboards, indexes | Never (always update) |
| `ARCHIVE_` | Historical | Read-only historical record | Never (keep forever) |

### Examples

```
✅ GOOD:
TEMP_2025-01-20_cache_ideas.md           (temporary, dated)
DRAFT_2025-01-19_lsp_integration.md      (WIP, dated)
RESEARCH_2025-01-18_performance_benchmarks.md  (deep dive, dated)
DECISION_ADR-001_cache_strategy.md       (permanent, no date)
CONTROL_MISSION_CONTROL.md               (dashboard, no date)
ARCHIVE_2025-01-19_SYNTHESIS.md          (historical, dated)

❌ BAD:
adr_validation_report.md                 (no type, no date)
deep_challenge_synthesis.md              (no type, no date)
cache_analysis.md                        (no type, no date)
notes.md                                 (generic, no context)
```

---

## Directory Structure

### Recommended Layout

```
project/
├── 00_CONTROL/          # Dashboards, indexes (CONTROL_*)
├── 01_DECISIONS/        # Permanent ADRs (DECISION_*)
├── 02_RESEARCH/         # Active research (RESEARCH_*, DRAFT_*)
├── 03_[DOMAIN]/         # Domain-specific permanent docs
├── 88_ARCHIVE/          # Historical archives (ARCHIVE_*)
│   └── YYYY-MM-DD_topic/   (organized by date)
└── 99_TEMP/             # Volatile scratch (TEMP_*)
```

**Numbering rationale**:
- `00-09`: Core, most important (alphabetically first)
- `88`: Archive (near end, clearly separate)
- `99`: Temporary (very end, disposable)

---

## Workflow: From Thinking to Decision

### Phase 1: Temporary Exploration (TEMP)

**When**: Initial idea, quick thinking

```bash
# Create scratch notes
touch 99_TEMP/TEMP_2025-01-20_my_idea.md

# Free-form thinking, no structure needed
# Edit, iterate, explore

# Decision: Worth pursuing?
# YES → Promote to DRAFT
# NO  → Delete file
```

**Characteristics**:
- No formal structure
- Stream of consciousness OK
- Can delete anytime
- Lifetime: Session only (7 days max)

### Phase 2: Draft Structure (DRAFT)

**When**: Idea has potential, needs structure

```bash
# Promote from TEMP or create directly
mv 99_TEMP/TEMP_*_my_idea.md \
   02_RESEARCH/DRAFT_2025-01-20_my_idea.md

# Add structure:
# - Problem statement
# - Proposed solution
# - Open questions

# Decision: Ready for deep dive?
# YES → Promote to RESEARCH
# NO  → Keep iterating or archive
```

**Characteristics**:
- Basic structure
- Outline defined
- Still exploratory
- Lifetime: Days to weeks (30 days max)

### Phase 3: Research & Analysis (RESEARCH)

**When**: Deep dive needed, exploring alternatives

```bash
# Rename DRAFT → RESEARCH
mv 02_RESEARCH/DRAFT_*_my_idea.md \
   02_RESEARCH/RESEARCH_2025-01-20_deep_dive_topic.md

# Deep analysis:
# - Multiple alternatives (3-5)
# - Benchmarks, comparisons
# - Scoring matrices
# - Pros/cons analysis

# Decision: Ready to commit?
# YES → Update DECISION file
# NO  → Continue research
```

**Characteristics**:
- Comprehensive analysis
- Evidence-based
- Multiple alternatives explored
- Scoring/comparison
- Lifetime: Until decision made

### Phase 4: Decision & Integration (DECISION)

**When**: Research complete, ready to commit

```bash
# Update existing ADR (or create new)
# DECISION files are PERMANENT

 - living documents
# Edit: 01_DECISIONS/DECISION_ADR-001_topic.md

# Add/update frontmatter:
---
type: DECISION
status: active
updated: 2025-01-20
supersedes:
  - RESEARCH_2025-01-18_topic_analysis.md
related:
  - DECISION_ADR-002_related_topic.md
---

# Update CONTROL files:
# - CONTROL_MISSION_CONTROL.md
# - CONTROL_DOCUMENT_INDEX.md
```

**Characteristics**:
- Single source of truth
- Permanent (never delete)
- Living document (update in place)
- YAML frontmatter mandatory

### Phase 5: Archive Research (ARCHIVE)

**When**: Research integrated into decision

```bash
# Create archive directory
TOPIC="cache_strategy"
DATE=$(date +%Y-%m-%d)
mkdir -p 88_ARCHIVE/${DATE}_${TOPIC}

# Move research files with ARCHIVE_ prefix
for file in 02_RESEARCH/RESEARCH_*${TOPIC}*.md; do
  basename=$(basename "$file")
  new_name="ARCHIVE_${basename#RESEARCH_}"
  mv "$file" "88_ARCHIVE/${DATE}_${TOPIC}/$new_name"
done

# Create archive README
cat > "88_ARCHIVE/${DATE}_${TOPIC}/README.md" <<EOF
# Archive: $TOPIC
Archived: $DATE
Status: Integrated into DECISION_ADR-xxx
Files: [list files]
Summary: [key findings]
EOF
```

**Characteristics**:
- Read-only (never modify)
- Historical reference
- Organized by date + topic
- README explaining context

---

## Mandatory Frontmatter (YAML)

### For All Non-TEMP Files

```yaml
---
type: DECISION | RESEARCH | DRAFT | ARCHIVE | CONTROL
status: active | obsolete | superseded | archived
created: YYYY-MM-DD
updated: YYYY-MM-DD
lifecycle: permanent | temporary | archived
supersedes: []          # Files this replaces
superseded_by: null     # File that replaces this (if any)
related: []             # Related files
contributors: [Human, Claude]
---
```

### Why Frontmatter Matters

1. **Automated indexing**: Scripts can generate document catalogs
2. **Lifecycle tracking**: Know when files were created/updated
3. **Dependency graph**: Understand relationships between documents
4. **Audit trail**: Track evolution of decisions

---

## Rules to Follow

### Rule 1: Single Source of Truth (SSOT)

- For each topic, exactly ONE `DECISION_` file exists
- All `RESEARCH_` files must reference which `DECISION_` they feed into
- If `RESEARCH_` contradicts `DECISION_`, mark with `status: challenge`

### Rule 2: Date All Temporary Files

- `TEMP_`, `DRAFT_`, `RESEARCH_` → MUST have `YYYY-MM-DD` in filename
- `DECISION_`, `CONTROL_` → NO date (permanent, always current)
- `ARCHIVE_` → Date represents when archived

### Rule 3: Archive on Decision

**Trigger**: When `RESEARCH_` findings are integrated into `DECISION_`

**Action**:
1. Update `DECISION_` file
2. Move `RESEARCH_` to `88_ARCHIVE/YYYY-MM-DD_topic/`
3. Add `ARCHIVE_` prefix
4. Create `README.md` in archive directory
5. Update `CONTROL_` files

### Rule 4: Time-Based Cleanup

- `TEMP_` files: Delete after 7 days if not promoted
- `DRAFT_` files: Review after 30 days, promote or archive
- `RESEARCH_` files: Archive when decision made (no time limit)

### Rule 5: Always Update Control

When you change a `DECISION_` file:
1. Update `CONTROL_MISSION_CONTROL.md` (central dashboard)
2. Update `CONTROL_DOCUMENT_INDEX.md` (document catalog)
3. Update frontmatter (supersedes, updated date)

---

## Checklist: Creating a New Document

- [ ] Choose correct `TYPE_` prefix based on lifecycle
- [ ] Add `YYYY-MM-DD` date if temporary (TEMP/DRAFT/RESEARCH)
- [ ] Use descriptive `TOPIC` name (kebab-case)
- [ ] Add YAML frontmatter (except TEMP)
- [ ] Declare relationships (`supersedes`, `related`)
- [ ] Place in correct directory (00_CONTROL, 01_DECISIONS, 02_RESEARCH, 88_ARCHIVE, 99_TEMP)

## Checklist: Making a Decision

- [ ] Complete `RESEARCH_` analysis (alternatives, benchmarks, scoring)
- [ ] Update (or create) `DECISION_ADR-xxx` file
- [ ] Update frontmatter (`updated` date, `supersedes` list)
- [ ] Archive all related `RESEARCH_` files to `88_ARCHIVE/YYYY-MM-DD_topic/`
- [ ] Create archive `README.md` (summary, key findings)
- [ ] Update `CONTROL_MISSION_CONTROL.md` (central dashboard)
- [ ] Update `CONTROL_DOCUMENT_INDEX.md` (document catalog)

## Checklist: Weekly Maintenance

- [ ] Review `99_TEMP/` → delete files >7 days old
- [ ] Review `02_RESEARCH/DRAFT_*` → archive or promote if >30 days
- [ ] Review `02_RESEARCH/RESEARCH_*` → archive if decision made
- [ ] Regenerate `CONTROL_DOCUMENT_INDEX.md` (if needed)
- [ ] Verify `CONTROL_MISSION_CONTROL.md` is current

---

## Example: Full Workflow

### Scenario: Researching cache strategy

```bash
# Day 1: Initial idea
touch 99_TEMP/TEMP_2025-01-15_cache_ideas.md
# Quick notes: Redis? Dragonfly? Dual-layer?

# Day 2: Worth exploring
mv 99_TEMP/TEMP_2025-01-15_cache_ideas.md \
   02_RESEARCH/DRAFT_2025-01-15_cache_strategy.md
# Add structure: problem, alternatives, questions

# Day 3-5: Deep dive
mv 02_RESEARCH/DRAFT_2025-01-15_cache_strategy.md \
   02_RESEARCH/RESEARCH_2025-01-15_cache_alternatives.md
# Explore: Redis Standard, Dragonfly, Valkey, KeyDB
# Benchmark: performance, pérennité, complexity
# Score: 5 dimensions (Performance, Simplicité, Coût, Risque, Pérennité)

# Day 6: Decision ready
# Edit: 01_DECISIONS/DECISION_ADR-001_cache_strategy.md
# Add findings: Redis Standard recommended (pérennité > performance)
# Update frontmatter:
---
type: DECISION
status: active
updated: 2025-01-19
supersedes:
  - RESEARCH_2025-01-15_cache_alternatives.md
---

# Day 7: Archive research
mkdir -p 88_ARCHIVE/2025-01-19_cache_strategy
mv 02_RESEARCH/RESEARCH_2025-01-15_cache_alternatives.md \
   88_ARCHIVE/2025-01-19_cache_strategy/ARCHIVE_2025-01-15_cache_alternatives.md

# Create README
cat > 88_ARCHIVE/2025-01-19_cache_strategy/README.md <<EOF
# Archive: Cache Strategy Research
Archived: 2025-01-19
Status: Integrated into DECISION_ADR-001
Key Finding: Redis Standard > Dragonfly (pérennité priority)
EOF

# Update control files
# - CONTROL_MISSION_CONTROL.md: Add "Cache decision made: Redis Standard"
# - CONTROL_DOCUMENT_INDEX.md: Update active research count, archive count
```

---

## Anti-Patterns (What NOT to Do)

### ❌ Generic Names
```
notes.md              # No context!
analysis.md           # Which analysis?
research.md           # What research?
```

### ❌ No Dates on Temporary Files
```
RESEARCH_cache_analysis.md    # When was this? Still relevant?
DRAFT_lsp_integration.md      # How old is this draft?
```

### ❌ No Type Prefix
```
cache_strategy_research.md     # Is this temporary or permanent?
adr_validation.md              # Is this a decision or analysis?
```

### ❌ Not Archiving Research
```
02_RESEARCH/
  ├── RESEARCH_2025-01-10_old_analysis.md  # Decision made, but not archived!
  ├── RESEARCH_2025-01-15_also_old.md      # Clutter!
  └── RESEARCH_2025-01-20_current.md       # Which is current?
```

### ❌ Not Updating Control
```
# Made decision, but CONTROL_MISSION_CONTROL.md not updated
# Result: Control dashboard shows old status!
```

---

## Benefits

### For Humans

- **Instant clarity**: Filename tells you everything (type, date, topic, status)
- **No confusion**: Clear distinction between temporary vs permanent
- **Easy navigation**: Know where to look (CONTROL → DECISIONS → RESEARCH → ARCHIVE)
- **Reduced cognitive load**: Don't need to remember file status

### For AI Agents

- **Clear instructions**: Know which files to update vs archive vs create
- **Lifecycle awareness**: Understand when to promote/archive files
- **Relationship tracking**: Frontmatter enables dependency management
- **Automated indexing**: Can generate catalogs programmatically

### For Teams

- **Scalable**: Works for 10 or 1000 documents
- **Auditable**: Full history in archives with context
- **Collaborative**: Anyone can understand file status
- **Low overhead**: ~5 min per document (frontmatter + naming)

---

## ROI Analysis

**Before** (typical research chaos):
- 10+ research files, unclear status
- ~30 min to find "source of truth"
- Duplicate work (recreate lost context)
- Cognitive overhead

**After** (screaming architecture):
- Clear lifecycle, explicit status
- <2 min to find current decision (check CONTROL_MISSION_CONTROL)
- No duplicates (archive on decision)
- Minimal cognitive load

**Cost**: ~5 min overhead per document (frontmatter + naming)
**Benefit**: 10-15× faster navigation, zero confusion
**ROI**: 10-15× positive

---

## Adapting This Skill

### For Your Project

1. **Adjust directory structure**: Use your domain names (e.g., `03_EPICS`, `04_STORIES`)
2. **Modify prefixes**: Add project-specific prefixes (e.g., `SPEC_`, `TEST_`)
3. **Customize lifecycle rules**: Adjust time limits (7/30 days) to your needs
4. **Extend frontmatter**: Add project-specific metadata

### For Different Domains

- **Software**: ADRs, RFCs, technical specs
- **Research**: Papers, experiments, data analysis
- **Product**: PRDs, user stories, roadmaps
- **Content**: Articles, drafts, publications

**Core principle remains**: Screaming names + clear lifecycle

---

## Tools & Automation

### Generate Document Index

```bash
#!/bin/bash
# generate_index.sh

echo "# Document Index"
echo "Generated: $(date +%Y-%m-%d)"
echo ""

echo "## Control Documents"
find 00_CONTROL -name "*.md" -type f | sort

echo "## Decisions (ADRs)"
find 01_DECISIONS -name "*.md" -type f | sort

echo "## Active Research"
find 02_RESEARCH -name "*.md" -type f | sort

echo "## Archives"
find 88_ARCHIVE -type d -name "20*" | sort -r
```

### Archive Research

```bash
#!/bin/bash
# archive_research.sh <topic>

TOPIC=$1
DATE=$(date +%Y-%m-%d)
ARCHIVE_DIR="88_ARCHIVE/${DATE}_${TOPIC}"

mkdir -p "$ARCHIVE_DIR"

# Move RESEARCH files
for file in 02_RESEARCH/RESEARCH_*${TOPIC}*.md; do
  [ -f "$file" ] || continue
  basename=$(basename "$file")
  new_name="ARCHIVE_${basename#RESEARCH_}"
  mv "$file" "$ARCHIVE_DIR/$new_name"
  echo "✅ Archived: $new_name"
done

# Create README
cat > "$ARCHIVE_DIR/README.md" <<EOF
# Archive: $TOPIC
Archived: $DATE
Status: Research completed
Files: $(ls -1 "$ARCHIVE_DIR"/*.md | wc -l)

## Summary
[Add summary here]

## Key Findings
[Add findings here]
EOF

echo "✅ Archive created: $ARCHIVE_DIR"
```

---

## Further Reading

- **Screaming Architecture** (Robert C. Martin): https://blog.cleancoder.com/uncle-bob/2011/09/30/Screaming-Architecture.html
- **ADR methodology**: https://adr.github.io/
- **Document lifecycle management**: https://en.wikipedia.org/wiki/Document_lifecycle

---

## Version History

- **v1.0** (2025-01-20): Initial skill creation based on MnemoLite serena-evolution reorganization

---

**Skill maintained by**: Human + AI collaboration
**License**: MIT (adapt freely)
**Feedback**: Iterate and improve based on usage
