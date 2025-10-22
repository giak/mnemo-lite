---
name: epic-workflow
description: EPIC/Story workflow management. Use for EPIC analysis, Story implementation, completion reports, planning, commits, documentation.
---
# Skill: EPIC Workflow & Story Management

**Version**: 1.0.0
**Category**: Workflow, Documentation, Project Management
**Auto-invoke**: EPIC, Story, completion, analysis, implementation, plan, commit

---

## Purpose

Complete workflow for managing EPICs and Stories in MnemoLite project, from analysis through implementation to completion documentation. Includes templates, checklists, commit patterns, and quality standards.

---

## When to Use This Skill

Use this skill when:
- Starting a new EPIC or Story
- Creating analysis documents
- Implementing features
- Writing completion reports
- Updating project documentation (CLAUDE.md, README)
- Planning story points
- Creating git commits for EPIC work

**Problem solved**: Consistent, high-quality EPIC execution with complete documentation trail

---

## EPIC/Story Workflow (End-to-End)

### Phase 1: Analysis (TEMP → DRAFT → RESEARCH)

**When**: New EPIC or Story assigned

**Steps**:
1. Create TEMP brainstorming doc (if needed for complex stories)
2. Create ANALYSIS doc in `docs/agile/serena-evolution/03_EPICS/`
3. Analyze requirements, dependencies, technical approach
4. Break down into phases/tasks
5. Estimate story points

**Template**: See "Analysis Document Template" below

**Output**: `EPIC-XX_STORY_XX.X_ANALYSIS.md`

---

### Phase 2: Implementation Planning

**When**: Analysis complete, ready to code

**Steps**:
1. Create IMPLEMENTATION_PLAN doc (if complex, >3 pts)
2. Create todo list using TodoWrite tool
3. Identify files to create/modify
4. Plan test strategy
5. Identify documentation updates needed

**Template**: See "Implementation Plan Template" below

**Output**:
- `EPIC-XX_STORY_XX.X_IMPLEMENTATION_PLAN.md` (optional)
- Todo list (via TodoWrite)

---

### Phase 3: Implementation

**When**: Plan approved, ready to code

**Workflow**:
```
1. Create branch (if needed)
   git checkout -b feature/EPIC-XX-story-XX.X

2. Implement following TEST-FIRST principle
   - Write tests first
   - Implement minimal code to pass tests
   - Refactor if needed

3. Run tests continuously
   make api-test
   # OR for specific file
   make api-test-file file=tests/path/to/test.py

4. Update todos as you complete tasks
   TodoWrite → mark in_progress → mark completed

5. Verify all tests pass
   make api-test  # Full test suite

6. Update documentation (see Phase 4)
```

**Principles**:
- **EXTEND > REBUILD**: Copy existing pattern, adapt (10× faster)
- **Test-first**: Write tests before implementation
- **Minimal change**: Smallest change that solves problem
- **Async-first**: All DB operations must be async/await

---

### Phase 4: Documentation Updates

**When**: Implementation complete, before commit

**Required Updates**:

#### 1. CLAUDE.md
**When to update**:
- New major feature (EPIC completion): Add to §ARCH, §STRUCTURE, §REF
- New gotcha discovered: Would go to skill:mnemolite-gotchas now (not CLAUDE.md)
- New skill created: Add to §SKILLS.AVAILABLE

**How to update**:
- Use compressed DSL format
- Keep to 1-2 lines per addition
- Follow existing patterns

**Example**:
```markdown
# Before
◊Robustness: timeouts(13.ops) + transactions(3.repos) → production.ready (EPIC-12.13/23pts)

# After (Story 12.3 added)
◊Robustness: timeouts(13.ops) + circuit.breakers(Redis+Embedding) + transactions(3.repos) → production.ready (EPIC-12.13/23pts)
```

#### 2. EPIC README (e.g., EPIC-12_README.md)
**Always update**:
- Story status (PENDING → COMPLETE)
- Points progress (e.g., 8/23 pts → 13/23 pts)
- Completion date
- Link to completion report

#### 3. EPIC Main Doc (e.g., EPIC-12_ROBUSTNESS.md)
**Update**:
- Story status
- Link to completion report
- Update progress percentage

---

### Phase 5: Completion Report

**When**: Story fully implemented and tested

**Template**: See "Completion Report Template" below

**Required Sections**:
1. **Header**: Story name, points, status, date, commits
2. **Executive Summary**: What was delivered, key metrics
3. **Acceptance Criteria**: Checklist (all ✅)
4. **Implementation Details**: Files created/modified, code snippets
5. **Testing Results**: Test counts, pass/fail rates
6. **Integration Validation**: How feature was verified
7. **Related Documents**: Links to analysis, plans, etc.

**Output**: `docs/agile/serena-evolution/03_EPICS/EPIC-XX_STORY_XX.X_COMPLETION_REPORT.md`

---

### Phase 6: Git Commit

**When**: All documentation updated, tests passing

**Commit Message Pattern**:
```bash
<type>(EPIC-XX): <description>

<optional body>

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only
- `test`: Test only
- `refactor`: Code refactoring
- `perf`: Performance improvement
- `chore`: Maintenance

**Examples**:
```bash
# Story implementation
feat(EPIC-12): Implement Story 12.3 - Circuit Breakers (5 pts)

# Documentation
docs(EPIC-12): Add Story 12.3 Completion Report

# Bug fix during story
fix(EPIC-11): Correct name_path parent ordering (reverse=True)

# Multiple files in one commit
feat(EPIC-10): Implement L1 Cache with LRU eviction (8 pts)

Adds in-memory L1 cache layer with 100MB limit and MD5-based
cache keys for code chunks. Integrates with existing L2/L3 cascade.
```

**Multi-commit stories**: Break into logical commits
```bash
# Commit 1: Core implementation
feat(EPIC-12): Implement circuit breaker core (Story 12.3 Phase 1)

# Commit 2: Integration
feat(EPIC-12): Add Redis circuit breaker (Story 12.3 Phase 2)

# Commit 3: Final integration
feat(EPIC-12): Add embedding circuit breaker (Story 12.3 Phase 3)

# Commit 4: Documentation
docs(EPIC-12): Add Story 12.3 completion report and update docs
```

---

## Document Templates

### Analysis Document Template

```markdown
# EPIC-XX Story XX.X: [Story Name] - Analysis

**Story**: [Story Name]
**Story Points**: X pts
**Priority**: P1/P2/P3
**Status**: ANALYSIS
**Created**: YYYY-MM-DD
**Author**: Claude Code + [User Name]

---

## Story Definition

[Copy story description from EPIC README]

### Acceptance Criteria

- [ ] Criterion 1
- [ ] Criterion 2
- [ ] ...

---

## Technical Analysis

### Current State

[What exists now]

### Proposed Changes

[What needs to change]

### Dependencies

- Service X
- Database table Y
- External dependency Z

### Technical Approach

[How to implement, architecture decisions]

---

## Implementation Phases

### Phase 1: [Name] (X pts)
**Deliverables**:
- File A
- File B

**Tests**:
- Test X
- Test Y

### Phase 2: [Name] (X pts)
...

---

## Testing Strategy

### Unit Tests
- Test scenario 1
- Test scenario 2

### Integration Tests
- Integration scenario 1
- Integration scenario 2

### Coverage Target
XX% coverage for new code

---

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Risk 1 | High | Mitigation plan |

---

## Story Points Breakdown

| Phase | Complexity | Testing | Docs | Total |
|-------|------------|---------|------|-------|
| Phase 1 | 1.5 | 0.5 | 0.5 | 2.5 |
| Phase 2 | 2.0 | 0.5 | 0.5 | 3.0 |
| **Total** | | | | **5.5** |

Rounded to: **5 pts** or **6 pts**

---

## Related Documents

- EPIC-XX_README.md
- EPIC-XX_[MAIN_DOC].md
```

---

### Implementation Plan Template (Optional, for complex stories)

```markdown
# EPIC-XX Story XX.X: [Story Name] - Implementation Plan

**Based on**: EPIC-XX_STORY_XX.X_ANALYSIS.md
**Created**: YYYY-MM-DD
**Target Completion**: YYYY-MM-DD

---

## Phase 1: [Name]

### Files to Create
- `path/to/file1.py` - [Purpose]
- `tests/path/to/test_file1.py` - [Purpose]

### Files to Modify
- `path/to/existing.py` - [What to change]

### Implementation Steps
1. Step 1
2. Step 2
3. ...

### Tests to Write
- [ ] Test 1: [Description]
- [ ] Test 2: [Description]

### Validation
- [ ] Run `make api-test`
- [ ] Verify [specific behavior]

---

## Phase 2: [Name]
...

---

## Documentation Updates Checklist

- [ ] Update CLAUDE.md (if needed)
- [ ] Update EPIC-XX_README.md
- [ ] Update EPIC-XX_[MAIN_DOC].md
- [ ] Create completion report
- [ ] Update related skills (if gotchas discovered)

---

## Git Commit Plan

```bash
# Commit 1
feat(EPIC-XX): [Phase 1 description]

# Commit 2
feat(EPIC-XX): [Phase 2 description]

# Commit 3
docs(EPIC-XX): Add Story XX.X completion report
```
```

---

### Completion Report Template

```markdown
# EPIC-XX Story XX.X: [Story Name] - Completion Report

**Story**: [Story Name]
**Story Points**: X pts
**Priority**: PX
**Status**: ✅ COMPLETE
**Completion Date**: YYYY-MM-DD
**Developer**: Claude Code + [User Name]
**Commits**:
- aaabbbc - feat(EPIC-XX): [commit message 1]
- dddeeef - feat(EPIC-XX): [commit message 2]
- ggghhhi - docs(EPIC-XX): [commit message 3]

---

## Executive Summary

[1-2 paragraph summary of what was delivered and key outcomes]

### Deliverables

✅ **Phase 1**: [Name] (X pts)
- Deliverable 1
- Deliverable 2

✅ **Phase 2**: [Name] (X pts)
- Deliverable 1
- Deliverable 2

### Key Metrics (if applicable)

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Metric 1 | Value | Value | XX% |
| Metric 2 | Value | Value | XXx faster |

---

## Acceptance Criteria (X/X COMPLETE) ✅

- [x] Criterion 1 ✅
  - Implementation details
  - Validation method

- [x] Criterion 2 ✅
  - Implementation details
  - Validation method

---

## Implementation Details

### Phase 1: [Name] (X pts)

#### Files Created

**`path/to/file.py`** (~XXX lines)
- Feature 1
- Feature 2
- **Quality**: EXCELLENT/GOOD

**`tests/path/to/test.py`** (~XXX lines)
- X tests created
- **Result**: All passing

#### Files Modified

**`path/to/existing.py`**
- Change 1 (line XXX)
- Change 2 (line YYY)

### Phase 2: [Name] (X pts)
...

---

## Testing Results

### Unit Tests
- **Total**: XX tests
- **Passing**: XX/XX (100%)
- **Coverage**: XX%

### Integration Tests
- **Total**: XX tests
- **Passing**: XX/XX (XX%)
- **Issues**: [If any, explain]

### Overall
**XX/XX tests passing (XX%)**

---

## Integration Validation

[How the feature was validated in the full system]

**Example**:
```bash
# Start system
make up

# Test endpoint
curl http://localhost:8001/v1/[endpoint]

# Verify behavior
[Expected output]
```

**Result**: ✅ Working as expected

---

## Documentation Updates

- [x] CLAUDE.md updated (version bumped to vX.X.X)
- [x] EPIC-XX_README.md updated (progress XX/YY pts)
- [x] EPIC-XX_[MAIN_DOC].md updated
- [x] Completion report created (this document)
- [x] Skills updated (if applicable)

---

## Operational Considerations (if applicable)

### Configuration
[New environment variables, config files]

### Monitoring
[New metrics, logs, health checks]

### Deployment
[Special deployment considerations]

### Rollback
[How to rollback if needed]

---

## Lessons Learned

### What Went Well
- Item 1
- Item 2

### Challenges
- Challenge 1 and how it was resolved
- Challenge 2 and how it was resolved

### Future Improvements
- Potential enhancement 1
- Potential enhancement 2

---

## Related Documents

- EPIC-XX_README.md
- EPIC-XX_[MAIN_DOC].md
- EPIC-XX_STORY_XX.X_ANALYSIS.md
- EPIC-XX_STORY_XX.X_IMPLEMENTATION_PLAN.md (if exists)

---

**Completed by**: Claude Code + [User Name]
**Review Status**: Approved
**Merged**: Yes/No
```

---

## Story Point Estimation Guide

### Complexity Factors

1. **Code Complexity** (40%)
   - 1 pt: Single file, <100 lines, straightforward logic
   - 2 pts: 2-3 files, 100-300 lines, moderate logic
   - 3 pts: 4-6 files, 300-600 lines, complex logic
   - 5 pts: 7+ files, 600+ lines, very complex logic

2. **Testing Effort** (30%)
   - 0.5 pt: 5-10 unit tests
   - 1 pt: 10-20 unit tests + integration tests
   - 2 pts: 20+ unit tests + complex integration tests
   - 3 pts: Extensive test suite + performance tests

3. **Integration Complexity** (20%)
   - 0.5 pt: Isolated, no external dependencies
   - 1 pt: Integrates with 1-2 services
   - 2 pts: Integrates with 3+ services, complex interactions
   - 3 pts: Cross-cutting, affects multiple layers

4. **Documentation** (10%)
   - 0.5 pt: Code comments + docstrings
   - 1 pt: + README updates + completion report
   - 1.5 pts: + Analysis doc + implementation plan
   - 2 pts: + Migration guide + operational docs

### Estimation Examples

**Story: Add timeout to single operation (EPIC-12 Story 12.1 partial)**
- Code: 1 file, ~50 lines → 1 pt
- Tests: 5 unit tests → 0.5 pt
- Integration: Uses existing timeout utility → 0.5 pt
- Docs: Update completion report → 0.5 pt
- **Total**: ~2.5 pts → Round to **2-3 pts**

**Story: Circuit Breaker Implementation (EPIC-12 Story 12.3)**
- Code: 3 new files (~500 lines) + 3 modified files → 3 pts
- Tests: 17 unit + 9 integration = 26 tests → 2 pts
- Integration: Affects Redis cache + Embedding service → 2 pts
- Docs: Analysis + implementation plan + completion → 1.5 pts
- **Total**: ~8.5 pts → Round to **8 pts** (actual was 5 pts - user adjusted)

**Story: Simple database migration (add column)**
- Code: 1 SQL file, ~20 lines → 0.5 pt
- Tests: Verify migration + rollback → 0.5 pt
- Integration: Minimal, backward compatible → 0.5 pt
- Docs: Migration notes → 0.5 pt
- **Total**: ~2 pts

---

## Quality Standards

### Code Quality
- [ ] Follows EXTEND > REBUILD principle
- [ ] All DB operations are async/await
- [ ] Implements appropriate Protocol interface
- [ ] Uses type hints (Python)
- [ ] Docstrings for public methods
- [ ] No hardcoded values (use config)
- [ ] Error handling and logging
- [ ] No critical gotchas violated (check skill:mnemolite-gotchas)

### Test Quality
- [ ] Unit tests for all new functions/methods
- [ ] Integration tests for cross-layer features
- [ ] Tests are isolated (no dependencies)
- [ ] Tests use EMBEDDING_MODE=mock
- [ ] Tests use TEST_DATABASE_URL
- [ ] All tests passing (100% for new code)
- [ ] Coverage ≥80% for new code

### Documentation Quality
- [ ] Analysis doc (if >3 pts)
- [ ] Implementation plan (if complex)
- [ ] Completion report (always)
- [ ] CLAUDE.md updated (if needed)
- [ ] EPIC README updated
- [ ] EPIC main doc updated
- [ ] Code comments for complex logic
- [ ] Docstrings follow conventions

### Git Quality
- [ ] Commit messages follow pattern
- [ ] Logical commit boundaries (not "WIP" commits)
- [ ] No secrets in commits
- [ ] Tests passing before commit
- [ ] Documentation updated in same commit or follow-up

---

## Common Patterns

### Multi-Phase Story Implementation

**When**: Story >3 pts, multiple logical phases

**Pattern**:
```bash
# Phase 1: Core implementation
git add api/utils/new_feature.py tests/utils/test_new_feature.py
git commit -m "feat(EPIC-XX): Implement Story XX.X Phase 1 - Core Feature"

# Phase 2: Integration
git add api/services/service.py tests/integration/test_feature.py
git commit -m "feat(EPIC-XX): Implement Story XX.X Phase 2 - Service Integration"

# Phase 3: Documentation
git add docs/agile/serena-evolution/03_EPICS/EPIC-XX_STORY_XX.X_COMPLETION_REPORT.md
git add docs/agile/serena-evolution/03_EPICS/EPIC-XX_README.md
git add CLAUDE.md
git commit -m "docs(EPIC-XX): Add Story XX.X completion report and update docs"
```

**Why**: Logical commit boundaries, easier review, easier rollback

---

### Story with Database Migration

**When**: Story requires schema changes

**Pattern**:
```bash
# 1. Create migration file
touch db/migrations/vX_to_vY.sql

# 2. Implement migration
cat > db/migrations/v4_to_v5.sql <<EOF
-- Add new column
ALTER TABLE code_chunks ADD COLUMN new_field TEXT;
-- Add index
CREATE INDEX idx_new_field ON code_chunks(new_field);
-- Update schema_version
INSERT INTO schema_version (version, description) VALUES ('v5', 'Add new_field');
EOF

# 3. Test migration
make db-shell
# Run migration manually, verify

# 4. Update application code to use new field

# 5. Commit together
git add db/migrations/v4_to_v5.sql api/services/service.py
git commit -m "feat(EPIC-XX): Add new_field with migration (Story XX.X)"
```

---

### Story with New Skill

**When**: Story discovers new gotchas or patterns worth documenting

**Pattern**:
```bash
# 1. Implement story normally

# 2. During implementation, note gotchas in todo
TodoWrite: "Document new gotcha: [description]"

# 3. After implementation, update skill
vi .claude/skills/mnemolite-gotchas/skill.md
# Add new gotcha section

# 4. Commit skill update separately
git add .claude/skills/mnemolite-gotchas/skill.md
git commit -m "docs: Update mnemolite-gotchas skill with [new pattern]"

# 5. Reference in completion report
```

---

## Troubleshooting

### "Story taking longer than estimated"
**Cause**: Underestimated complexity or unforeseen issues

**Action**:
1. Update todo list with actual tasks
2. Break remaining work into smaller chunks
3. Document obstacles in completion report ("Lessons Learned")
4. Adjust future estimates based on learnings

### "Tests failing after implementation"
**Cause**: Integration issues, missing mocks, fixture problems

**Action**:
1. Check skill:mnemolite-gotchas for common test issues
2. Verify TEST_DATABASE_URL set
3. Verify EMBEDDING_MODE=mock
4. Check fixture scope (function vs module)
5. Run tests individually to isolate issue

### "Documentation update overwhelming"
**Cause**: Too many docs to update

**Action**:
1. Use checklist (Phase 4 above)
2. Update incrementally during implementation
3. Use templates (this skill)
4. Commit docs separately if needed

### "Unclear where to document something"
**Decision Tree**:
- Universal principle? → CLAUDE.md §PRINCIPLES
- Critical gotcha (breaks code)? → CLAUDE.md §CRITICAL.RULES
- Contextual gotcha? → skill:mnemolite-gotchas
- EPIC-specific? → EPIC completion report
- Architecture pattern? → skill:mnemolite-architecture (future)
- Testing pattern? → skill:mnemolite-testing (future)

---

## Related Skills

- **document-lifecycle**: Document management (TEMP→DRAFT→RESEARCH→DECISION)
- **mnemolite-gotchas**: Common pitfalls, debugging (reference during implementation)
- **mnemolite-testing**: Test patterns (reference when writing tests)
- **mnemolite-architecture**: Architecture patterns (reference during design)

---

## Version History

- **v1.0** (2025-10-21): Initial skill creation, extracted patterns from EPIC-10, EPIC-11, EPIC-12

---

**Skill maintained by**: Human + AI collaboration
**Auto-invoke keywords**: EPIC, Story, completion, analysis, implementation, plan, commit, documentation
**Template updates**: Add examples as new EPICs completed
