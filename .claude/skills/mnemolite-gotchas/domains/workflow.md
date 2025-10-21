# Git & Workflow Gotchas

**Purpose**: Git patterns, commit conventions, and workflow gotchas

**When to reference**: Creating commits, managing branches, or following EPIC workflow

---

## 🟡 GIT-01: Commit Message Pattern for EPICs

**Rule**: EPIC commits follow specific pattern

```bash
# ✅ CORRECT
git commit -m "feat(EPIC-12): Implement Story 12.3 - Circuit Breakers (5 pts)"
git commit -m "docs(EPIC-11): Update Story 11.2 completion report"
git commit -m "fix(EPIC-10): Correct cache TTL calculation"

# ❌ WRONG - No EPIC reference
git commit -m "Add circuit breakers"
git commit -m "Update docs"
```

**Pattern**: `<type>(EPIC-XX): <description>`

**Types**: `feat`, `fix`, `docs`, `test`, `refactor`, `perf`, `chore`

**Why**: Easy to track EPIC progress, filter commits by EPIC

---

## 🟡 GIT-02: Interactive Commands Not Supported

**Rule**: NEVER use `-i` flag with git commands (not supported in Docker)

```bash
# ✅ CORRECT
git add file1.py file2.py

# ❌ WRONG - Will hang
git add -i  # Interactive mode not supported!
git rebase -i HEAD~3  # Will hang!
```

**Why**: Docker exec doesn't support interactive TTY for git

**Detection**: Command hangs indefinitely

**Fix**: Use non-interactive alternatives

---

## 🟡 GIT-03: Empty Commits

**Rule**: If no changes to commit, don't create empty commit

```bash
# Check if changes exist
git status

# If "nothing to commit", skip commit
# DON'T: git commit --allow-empty
```

**Why**: Empty commits pollute history, provide no value

**Detection**: `git log` shows commits with no diff

---

**Total Git & Workflow Gotchas**: 3
