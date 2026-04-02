# EPIC-23 Story 23.11 ULTRATHINK: Elicitation Flows

**Date**: 2025-10-28
**Story**: 23.11 - Elicitation Flows (1 pt, ~3h)
**Phase**: Phase 3 - Production & Polish
**Status**: 🔍 **BRAINSTORMING & DESIGN**

---

## Table of Contents

1. [Context Analysis](#context-analysis)
2. [Requirements Analysis](#requirements-analysis)
3. [Architecture Analysis](#architecture-analysis)
4. [Implementation Strategy](#implementation-strategy)
5. [Testing Strategy](#testing-strategy)
6. [Risk Analysis](#risk-analysis)
7. [Decision Log](#decision-log)
8. [Implementation Plan](#implementation-plan)

---

## 1. Context Analysis

### 1.1 Current State (Before Story 23.11)

**Completed Stories** (8/12, 78%):
- ✅ Story 23.1: Project Structure & FastMCP Setup (3 pts)
- ✅ Story 23.2: Code Search Tool (3 pts)
- ✅ Story 23.3: Memory Tools & Resources (2 pts)
- ✅ Story 23.4: Code Graph Resources (3 pts)
- ✅ Story 23.5: Project Indexing Tools (2 pts)
- ✅ Story 23.6: Analytics & Observability (2 pts)
- ✅ Story 23.10: Prompts Library (2 pts)
- ✅ Story 23.7: Configuration & Utilities (1 pt)

**Total**: 18/23 story points (78%)

**Current Elicitation Status**:
- ✅ **Story 23.6 (clear_cache)**: Elicitation ALREADY IMPLEMENTED
  - Uses `ctx.elicit()` with schema validation
  - File: `api/mnemo_mcp/tools/analytics_tools.py:63-91`
  - Prompts user before clearing cache layers

- ⏳ **Story 23.3 (delete_memory permanent)**: TODO at line 449
  - Hard delete requires confirmation
  - Currently has basic logic, no elicitation yet
  - File: `api/mnemo_mcp/tools/memory_tools.py:449`

- ⏳ **Story 23.7 (switch_project)**: TODO at line 63
  - Project switch requires confirmation
  - Currently has `confirm` bypass flag
  - File: `api/mnemo_mcp/tools/config_tools.py:63`

### 1.2 What Story 23.11 Adds

**New Capabilities** (2 sub-stories):
1. **Sub-Story 23.11.1**: Elicitation Helpers & Patterns
   - Reusable helper functions (`request_confirmation`, `request_choice`)
   - Standardized elicitation patterns
   - Integration with existing TODO locations

2. **Sub-Story 23.11.2**: Elicitation UX Patterns Documentation
   - Best practices for elicitation UX
   - Pattern catalog (destructive ops, large ops, choices)
   - Anti-patterns to avoid

**Impact**:
- Completes TODOs in Stories 23.3 and 23.7
- Standardizes elicitation across all tools
- Improves UX with consistent confirmation flows

---

## 2. Requirements Analysis

### 2.1 Functional Requirements

#### FR1: Confirmation Elicitation (Sub-Story 23.11.1)
- **Must**: Prompt user for confirmation before destructive operations
- **Must**: Show clear description of action and consequences
- **Must**: Support "dangerous" flag for critical operations
- **Must**: Allow bypass via `confirm=True` parameter
- **Should**: Log elicitation events for audit trail

#### FR2: Choice Elicitation (Sub-Story 23.11.1)
- **Must**: Prompt user to choose from multiple options
- **Must**: Add "Cancel" option automatically
- **Must**: Raise ValueError if user cancels
- **Should**: Support default option

#### FR3: Pattern Documentation (Sub-Story 23.11.2)
- **Must**: Document 4 core patterns (destructive, large ops, choices, bypass)
- **Must**: Provide code examples for each pattern
- **Must**: Document best practices and anti-patterns
- **Should**: Include Claude Desktop UI mockups

### 2.2 Non-Functional Requirements

#### NFR1: Performance
- Elicitation adds minimal overhead (<10ms)
- No blocking on timeout (graceful degradation)

#### NFR2: Compatibility
- Works with FastMCP Context.elicit() API
- Compatible with MCP 2025-06-18 specification
- Backward compatible with existing `confirm` flags

#### NFR3: Testability
- All elicitation paths unit testable
- Mock-friendly API (ctx.elicit can be mocked)

#### NFR4: UX Consistency
- Consistent prompt formatting across all tools
- Consistent option naming ("Confirm" vs "Cancel")
- Clear distinction between safe and dangerous operations

### 2.3 Constraints

#### Technical Constraints
1. **FastMCP API**: Must use `ctx.elicit()` (not `ctx.request_elicitation()`)
   - Discovered via code inspection (Story 23.6 already uses this)
   - Schema-based response validation

2. **Backward Compatibility**: Must support existing `confirm` bypass flags
   - Story 23.3: `permanent=True` flag
   - Story 23.7: `confirm=True` flag
   - These flags should skip elicitation

3. **No Database**: Elicitation state is ephemeral (no persistence needed)

#### Business Constraints
1. **Time Budget**: 3h total (2h helpers + 1h doc)
2. **Scope**: Implement only for destructive operations (read ops don't need elicitation)

---

## 3. Architecture Analysis

### 3.1 Existing Elicitation Implementation

**File**: `api/mnemo_mcp/tools/analytics_tools.py:63-91`

```python
# Current implementation in clear_cache tool
response = await ctx.elicit(
    prompt=(
        f"Clear {layer} cache ({layer_desc[layer]})?\n\n"
        f"This will:\n"
        f"• Remove all cached data from {layer}\n"
        f"• Temporarily degrade performance until cache is repopulated\n"
        f"• Force all requests to hit slower storage layers\n"
        f"• Impact: {impact_level}\n\n"
        f"Proceed with cache clear?"
    ),
    schema={"type": "string", "enum": ["yes", "no"]}
)

if response.value == "no":
    return {
        "success": False,
        "message": "Cache clear cancelled by user"
    }
```

**Observations**:
1. Uses `ctx.elicit()` (not `ctx.request_elicitation()`)
2. Schema-based validation (`enum: ["yes", "no"]`)
3. Structured prompt with bullet points
4. Checks `response.value` for user choice
5. Returns early if cancelled

### 3.2 FastMCP Elicitation API

**Method Signature** (inferred from existing usage):
```python
async def elicit(
    self,
    prompt: str,
    schema: dict
) -> ElicitationResponse
```

**Response Structure**:
```python
class ElicitationResponse:
    value: str  # Selected option
```

**Schema Types**:
- `{"type": "string", "enum": [...]}`  # Multiple choice
- `{"type": "boolean"}`  # Yes/no
- `{"type": "string"}`  # Free text (avoid for elicitation)

### 3.3 Proposed Helper Architecture

**Module**: `api/mnemo_mcp/elicitation.py`

```python
# Pydantic models
class ElicitationRequest(BaseModel):
    """Configuration for elicitation prompt."""
    title: str
    prompt: str
    options: list[str]
    default: Optional[str] = None
    dangerous: bool = False

class ElicitationResult(BaseModel):
    """Result from elicitation."""
    confirmed: bool
    selected_option: Optional[str] = None
    cancelled: bool = False

# Helper functions
async def request_confirmation(
    ctx: Context,
    action: str,
    details: str,
    dangerous: bool = False
) -> ElicitationResult:
    """Request user confirmation (Yes/No)."""
    ...

async def request_choice(
    ctx: Context,
    question: str,
    choices: list[str],
    default: Optional[str] = None
) -> str:
    """Request user to choose from options."""
    ...
```

**Key Design Decisions**:
1. **Separate models from functions**: Pydantic models for validation, pure functions for logic
2. **Context as parameter**: Pass MCP Context explicitly (no global state)
3. **Return ElicitationResult**: Structured result with `confirmed`, `selected_option`, `cancelled` fields
4. **Raise on cancel for choices**: `request_choice()` raises ValueError if cancelled (fail fast)
5. **Log all elicitations**: Structured logging for audit trail

### 3.4 Integration Points

**Story 23.3 (delete_memory permanent)**:
```python
# Before (TODO at line 449)
# TODO: Implement elicitation flow when FastMCP supports it

# After (with Story 23.11)
if permanent:
    result = await request_confirmation(
        ctx,
        action="Permanently Delete Memory",
        details=f"Memory '{existing_memory.title}' will be permanently deleted. This cannot be undone.",
        dangerous=True
    )

    if not result.confirmed:
        return DeleteMemoryResponse(
            success=False,
            message="Permanent deletion cancelled by user"
        )
```

**Story 23.7 (switch_project)**:
```python
# Before (TODO at line 63)
# TODO (Story 23.11): Add elicitation for confirmation

# After (with Story 23.11)
if not request.confirm:
    result = await request_confirmation(
        ctx,
        action="Switch Project",
        details=f"Switch to repository '{request.repository}'? This will change the context for all searches.",
        dangerous=False
    )

    if not result.confirmed:
        return SwitchProjectResponse(
            success=False,
            message="Project switch cancelled by user",
            repository=request.repository,
            indexed_files=0,
            total_chunks=0,
            languages=[]
        )
```

### 3.5 Testing Architecture

**Mock Strategy**:
```python
# Mock ctx.elicit() in unit tests
ctx = MagicMock()
ctx.elicit = AsyncMock(
    return_value=MagicMock(value="yes")  # User confirms
)

result = await request_confirmation(ctx, action="Test", details="Details")
assert result.confirmed is True
```

**Test Coverage**:
1. Confirmation confirmed (user selects "yes")
2. Confirmation cancelled (user selects "no")
3. Choice selected (user picks option)
4. Choice cancelled (user picks "Cancel")
5. Dangerous flag changes prompt
6. Logging events captured

---

## 4. Implementation Strategy

### 4.1 Sub-Story 23.11.1: Elicitation Helpers (2h)

**Phase 1: Create Helper Module** (45 min)

**File**: `api/mnemo_mcp/elicitation.py` (~150 lines)

```python
"""
MCP Elicitation Helpers (EPIC-23 Story 23.11).

Reusable helpers for human-in-the-loop confirmations and choices.
"""
import structlog
from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field
from typing import Optional, List

logger = structlog.get_logger()


# ============================================================================
# Pydantic Models
# ============================================================================

class ElicitationRequest(BaseModel):
    """Configuration for elicitation prompt."""

    title: str = Field(description="Title shown in UI")
    prompt: str = Field(description="Detailed prompt text")
    options: List[str] = Field(description="Available options")
    default: Optional[str] = Field(default=None, description="Default option")
    dangerous: bool = Field(default=False, description="Show warning UI")


class ElicitationResult(BaseModel):
    """Result from user elicitation."""

    confirmed: bool = Field(description="Whether user confirmed action")
    selected_option: Optional[str] = Field(default=None, description="Selected option")
    cancelled: bool = Field(default=False, description="Whether user cancelled")


# ============================================================================
# Helper Functions
# ============================================================================

async def request_confirmation(
    ctx: Context,
    action: str,
    details: str,
    dangerous: bool = False
) -> ElicitationResult:
    """
    Request user confirmation for an action.

    Shows a Yes/No prompt with clear action description. Use `dangerous=True`
    for destructive operations (deletion, cache clearing).

    Args:
        ctx: MCP context with elicit() method
        action: Action name (e.g., "Delete Memory", "Clear Cache")
        details: Detailed description of consequences
        dangerous: If True, shows warning icon and emphasizes risk

    Returns:
        ElicitationResult with confirmed/cancelled status

    Example:
        >>> result = await request_confirmation(
        ...     ctx,
        ...     action="Delete Memory",
        ...     details="Memory 'foo' will be permanently deleted",
        ...     dangerous=True
        ... )
        >>> if result.confirmed:
        ...     # Proceed with deletion
    """
    logger.info("elicitation.confirm", action=action, dangerous=dangerous)

    # Build prompt
    title = f"⚠️ Confirm: {action}" if dangerous else f"Confirm: {action}"

    prompt_text = f"{details}\n\nProceed?"

    # Options
    options = ["yes", "no"]

    # Call MCP elicit API
    try:
        response = await ctx.elicit(
            prompt=f"{title}\n\n{prompt_text}",
            schema={"type": "string", "enum": options}
        )

        confirmed = response.value == "yes"

        logger.info(
            "elicitation.result",
            action=action,
            confirmed=confirmed,
            dangerous=dangerous
        )

        return ElicitationResult(
            confirmed=confirmed,
            selected_option=response.value,
            cancelled=(response.value == "no")
        )

    except Exception as e:
        logger.error(
            "elicitation.error",
            action=action,
            error=str(e)
        )
        # On error, assume cancelled (safe default)
        return ElicitationResult(
            confirmed=False,
            selected_option=None,
            cancelled=True
        )


async def request_choice(
    ctx: Context,
    question: str,
    choices: List[str],
    default: Optional[str] = None
) -> str:
    """
    Request user to choose from multiple options.

    Automatically adds "Cancel" option. Raises ValueError if user cancels.

    Args:
        ctx: MCP context with elicit() method
        question: Question to ask user
        choices: List of available choices
        default: Default choice (optional)

    Returns:
        Selected choice string

    Raises:
        ValueError: If user selects "Cancel"

    Example:
        >>> choice = await request_choice(
        ...     ctx,
        ...     question="Which project to index?",
        ...     choices=["project-a", "project-b", "project-c"]
        ... )
        >>> print(f"Indexing {choice}")
    """
    logger.info("elicitation.choice", question=question, choices=choices)

    # Add Cancel option
    all_options = choices + ["Cancel"]

    # Call MCP elicit API
    try:
        response = await ctx.elicit(
            prompt=f"{question}\n\nSelect one:",
            schema={"type": "string", "enum": all_options}
        )

        selected = response.value

        if selected == "Cancel":
            logger.info("elicitation.cancelled", question=question)
            raise ValueError("User cancelled operation")

        logger.info("elicitation.choice_selected", choice=selected)

        return selected

    except Exception as e:
        logger.error(
            "elicitation.choice_error",
            question=question,
            error=str(e)
        )
        raise ValueError("Elicitation failed or cancelled") from e
```

**Phase 2: Update Existing Tools** (45 min)

**File 1**: `api/mnemo_mcp/tools/memory_tools.py`
- Add elicitation to `delete_memory(permanent=True)`
- Remove TODO comment at line 449
- Import: `from mnemo_mcp.elicitation import request_confirmation`

**File 2**: `api/mnemo_mcp/tools/config_tools.py`
- Add elicitation to `switch_project(confirm=False)`
- Remove TODO comment at line 63
- Import: `from mnemo_mcp.elicitation import request_confirmation`

**Phase 3: Unit Tests** (30 min)

**File**: `tests/mnemo_mcp/test_elicitation.py` (~200 lines)

Tests:
1. `test_request_confirmation_confirmed()` - User confirms
2. `test_request_confirmation_cancelled()` - User cancels
3. `test_request_confirmation_dangerous()` - Dangerous flag
4. `test_request_confirmation_error()` - Elicit fails
5. `test_request_choice_selected()` - User picks option
6. `test_request_choice_cancelled()` - User cancels (raises ValueError)
7. `test_request_choice_error()` - Elicit fails (raises ValueError)

### 4.2 Sub-Story 23.11.2: UX Patterns Documentation (1h)

**File**: `docs/mcp/ELICITATION_PATTERNS.md` (~1500 words)

**Sections**:
1. **Overview** (200 words)
   - What is elicitation
   - When to use it
   - FastMCP API basics

2. **Pattern 1: Destructive Confirmation** (300 words)
   - When: Permanent deletion, irreversible actions
   - UX: `dangerous=True`, clear consequences
   - Example: delete_memory permanent

3. **Pattern 2: Large Operation Warning** (250 words)
   - When: Operations >30s or >1000 items
   - UX: Show estimated time/count
   - Example: index_project with >10k files

4. **Pattern 3: Ambiguous Choice** (250 words)
   - When: Multiple valid options
   - UX: List options, add Cancel
   - Example: Multiple projects with same name

5. **Pattern 4: Bypass with Flag** (200 words)
   - When: Automation/scripting
   - UX: `confirm=True` parameter
   - Example: Automated deletion in tests

6. **Best Practices** (150 words)
   - Always `dangerous=True` for deletion
   - Show specific numbers ("10,234 files" not "many")
   - Test both confirmed and cancelled paths
   - Log elicitation events

7. **Anti-Patterns** (150 words)
   - Don't elicit for read operations
   - Don't elicit for fast operations (<1s)
   - Don't show technical UUIDs (use human names)
   - Don't nest elicitations (confusing)

---

## 5. Testing Strategy

### 5.1 Unit Tests (30 min)

**File**: `tests/mnemo_mcp/test_elicitation.py`

**Coverage Matrix**:

| Function | Test Case | Expected Behavior |
|----------|-----------|-------------------|
| `request_confirmation` | User confirms | `confirmed=True, cancelled=False` |
| `request_confirmation` | User cancels | `confirmed=False, cancelled=True` |
| `request_confirmation` | Dangerous flag | Prompt includes ⚠️ |
| `request_confirmation` | Elicit fails | `confirmed=False` (safe default) |
| `request_choice` | User selects option | Returns selected string |
| `request_choice` | User cancels | Raises ValueError |
| `request_choice` | Elicit fails | Raises ValueError |

**Mock Strategy**:
```python
@pytest.fixture
def mock_context_confirm():
    """Mock context that confirms action."""
    ctx = MagicMock()
    ctx.elicit = AsyncMock(return_value=MagicMock(value="yes"))
    return ctx

@pytest.fixture
def mock_context_cancel():
    """Mock context that cancels action."""
    ctx = MagicMock()
    ctx.elicit = AsyncMock(return_value=MagicMock(value="no"))
    return ctx
```

### 5.2 Integration Tests (Existing Stories)

**Test 1: delete_memory with elicitation** (Story 23.3)
```python
@pytest.mark.asyncio
async def test_delete_memory_permanent_with_elicitation(mock_context_confirm):
    """Test permanent deletion with user confirmation."""
    tool = DeleteMemoryTool()
    # ... setup ...

    # Should call elicit and proceed with deletion
    response = await tool.execute(
        ctx=mock_context_confirm,
        id=memory_id,
        permanent=True
    )

    assert response.success is True
    mock_context_confirm.elicit.assert_called_once()
```

**Test 2: switch_project with elicitation** (Story 23.7)
```python
@pytest.mark.asyncio
async def test_switch_project_with_elicitation(mock_context_confirm):
    """Test project switch with user confirmation."""
    tool = SwitchProjectTool()
    # ... setup ...

    # Should call elicit and switch project
    response = await tool.execute(
        ctx=mock_context_confirm,
        request=SwitchProjectRequest(repository="test", confirm=False)
    )

    assert response.success is True
    mock_context_confirm.elicit.assert_called_once()
```

### 5.3 Test Execution

```bash
# Run elicitation tests
EMBEDDING_MODE=mock pytest tests/mnemo_mcp/test_elicitation.py -v

# Run integration tests (existing stories)
EMBEDDING_MODE=mock pytest tests/mnemo_mcp/test_memory_tools.py::test_delete_memory_permanent_with_elicitation -v
EMBEDDING_MODE=mock pytest tests/mnemo_mcp/test_config_tools.py::test_switch_project_with_elicitation -v

# Run all MCP tests
EMBEDDING_MODE=mock pytest tests/mnemo_mcp/ -v
```

**Expected Results**:
- 7 new tests in `test_elicitation.py`
- 2 integration tests updated (delete_memory, switch_project)
- Total: 227 tests passing (218 current + 7 new + 2 updated)

---

## 6. Risk Analysis

### 6.1 Technical Risks

#### Risk 1: FastMCP API Mismatch
- **Probability**: Low
- **Impact**: High (API incompatibility)
- **Mitigation**: Story 23.6 already uses `ctx.elicit()` successfully
- **Fallback**: If API changes, update helpers only (single point of failure)

#### Risk 2: Timeout Handling
- **Probability**: Medium
- **Impact**: Medium (hung operations if user AFK)
- **Mitigation**: FastMCP should have built-in timeout (default 60s)
- **Fallback**: Catch exception, return `cancelled=True`

#### Risk 3: Testing Complexity
- **Probability**: Low
- **Impact**: Low (mocking is straightforward)
- **Mitigation**: Use simple AsyncMock for `ctx.elicit()`
- **Example**: Already done in other tests

### 6.2 Integration Risks

#### Risk 4: Breaking Existing Bypass Flags
- **Probability**: Low
- **Impact**: High (breaks automation)
- **Mitigation**: Keep `confirm=True` and `permanent=True` flags
- **Test**: Verify bypass flags skip elicitation

#### Risk 5: UX Inconsistency
- **Probability**: Medium
- **Impact**: Medium (confusing user experience)
- **Mitigation**: Document standard patterns in ELICITATION_PATTERNS.md
- **Review**: User testing with MCP Inspector

### 6.3 Documentation Risks

#### Risk 6: Pattern Documentation Out of Date
- **Probability**: Low
- **Impact**: Low (doc drift)
- **Mitigation**: Keep doc close to code (same PR)
- **Process**: Update doc when patterns change

---

## 7. Decision Log

### Decision 1: Use `ctx.elicit()` Not `ctx.request_elicitation()`

**Context**: Phase 3 breakdown specifies `ctx.request_elicitation()` but Story 23.6 uses `ctx.elicit()`

**Options**:
1. Use `ctx.request_elicitation()` as spec'd
2. Use `ctx.elicit()` as implemented in Story 23.6

**Decision**: Use `ctx.elicit()` ✅

**Rationale**:
- Story 23.6 (clear_cache) already uses `ctx.elicit()` successfully
- FastMCP Context only has `elicit()` method (verified via dir())
- Phase 3 breakdown was based on older MCP spec
- Align with working implementation > spec document

**Impact**: Helpers will use `ctx.elicit()` API

---

### Decision 2: Return `ElicitationResult` Object Not Boolean

**Context**: Need to return confirmation status + metadata

**Options**:
1. Return `bool` (simple but limited)
2. Return `ElicitationResult` object (structured)
3. Return `dict` (untyped)

**Decision**: Return `ElicitationResult` Pydantic model ✅

**Rationale**:
- Type-safe with Pydantic validation
- Can include `confirmed`, `selected_option`, `cancelled` fields
- Extensible (can add fields later without breaking)
- Consistent with other MCP models

**Impact**: All callers use `result.confirmed` not `result`

---

### Decision 3: Raise ValueError on Cancelled Choice

**Context**: What should `request_choice()` do if user cancels?

**Options**:
1. Return None (implicit failure)
2. Return "Cancel" string (caller must check)
3. Raise ValueError (explicit failure)

**Decision**: Raise ValueError ✅

**Rationale**:
- Explicit failure (fail fast)
- Forces caller to handle cancellation
- Pythonic (exceptions for exceptional cases)
- Consistent with other Python APIs

**Impact**: Callers must handle ValueError or let it propagate

---

### Decision 4: Log All Elicitation Events

**Context**: Should we log every elicitation?

**Options**:
1. No logging (silent)
2. Debug level only
3. Info level (audit trail)

**Decision**: Info level logging ✅

**Rationale**:
- Audit trail for security/compliance
- Useful for debugging user behavior
- Matches Story 23.6 pattern (already logs)
- Structured logging (JSON parseable)

**Impact**: Every elicitation logged with action, result, dangerous flag

---

### Decision 5: Standardize Prompt Formatting

**Context**: How should prompts be formatted?

**Options**:
1. Free-form (caller decides)
2. Template-based (fixed structure)
3. Hybrid (helpers add structure, caller provides details)

**Decision**: Hybrid approach ✅

**Rationale**:
- Helpers add title, format, options
- Caller provides action-specific details
- Consistent UI across all tools
- Flexible for edge cases

**Format**:
```
⚠️ Confirm: {action}  # Optional ⚠️ if dangerous

{details}

Proceed?

[Options: yes, no]
```

---

## 8. Implementation Plan

### 8.1 Timeline (3h total)

| Phase | Task | Duration | Cumulative |
|-------|------|----------|------------|
| **Phase 1** | Create `elicitation.py` module | 45 min | 0.75h |
| **Phase 2** | Update `memory_tools.py` (delete) | 20 min | 1.08h |
| **Phase 2** | Update `config_tools.py` (switch) | 20 min | 1.42h |
| **Phase 2** | Review & test integration | 5 min | 1.5h |
| **Phase 3** | Create unit tests | 30 min | 2h |
| **Phase 4** | Write ELICITATION_PATTERNS.md | 45 min | 2.75h |
| **Phase 4** | Update Progress Tracker | 10 min | 2.92h |
| **Buffer** | Testing & polish | 5 min | 3h |

### 8.2 Implementation Steps

#### Step 1: Create Elicitation Module (45 min)

**File**: `api/mnemo_mcp/elicitation.py`

**Tasks**:
1. Create Pydantic models (ElicitationRequest, ElicitationResult)
2. Implement `request_confirmation()` function
3. Implement `request_choice()` function
4. Add structured logging
5. Add comprehensive docstrings

**Validation**:
- No syntax errors
- Type hints complete
- Docstrings comprehensive
- Import test: `from mnemo_mcp.elicitation import request_confirmation`

#### Step 2: Update memory_tools.py (20 min)

**File**: `api/mnemo_mcp/tools/memory_tools.py`

**Changes**:
1. Import `request_confirmation` at top
2. Replace TODO comment at line 449 with elicitation code
3. Handle ElicitationResult (return early if cancelled)

**Code**:
```python
# At top of file
from mnemo_mcp.elicitation import request_confirmation

# At line 449 (replace TODO)
if permanent:
    result = await request_confirmation(
        ctx,
        action="Permanently Delete Memory",
        details=(
            f"Memory '{existing_memory.title}' (ID: {id}) will be permanently deleted.\n"
            f"This action cannot be undone.\n\n"
            f"Memory details:\n"
            f"• Type: {existing_memory.memory_type}\n"
            f"• Created: {existing_memory.created_at.strftime('%Y-%m-%d')}\n"
            f"• Content length: {len(existing_memory.content)} chars"
        ),
        dangerous=True
    )

    if not result.confirmed:
        return DeleteMemoryResponse(
            success=False,
            message="Permanent deletion cancelled by user"
        )
```

**Validation**:
- No syntax errors
- Elicitation called before deletion
- Graceful handling if cancelled

#### Step 3: Update config_tools.py (20 min)

**File**: `api/mnemo_mcp/tools/config_tools.py`

**Changes**:
1. Import `request_confirmation` at top
2. Replace TODO comment at line 63 with elicitation code
3. Handle ElicitationResult (return early if cancelled)

**Code**:
```python
# At top of file
from mnemo_mcp.elicitation import request_confirmation

# At line 63 (replace TODO)
if not request.confirm:
    result = await request_confirmation(
        ctx,
        action="Switch Project",
        details=(
            f"Switch to repository '{request.repository}'?\n\n"
            f"This will change the active context for:\n"
            f"• All code searches\n"
            f"• Graph queries\n"
            f"• Memory searches\n\n"
            f"Current project will be deactivated."
        ),
        dangerous=False
    )

    if not result.confirmed:
        logger.info(
            "switch_project.cancelled",
            repository=request.repository
        )
        return SwitchProjectResponse(
            success=False,
            message="Project switch cancelled by user",
            repository=request.repository,
            indexed_files=0,
            total_chunks=0,
            languages=[]
        )
```

**Validation**:
- No syntax errors
- Elicitation skipped if `confirm=True`
- Graceful handling if cancelled

#### Step 4: Create Unit Tests (30 min)

**File**: `tests/mnemo_mcp/test_elicitation.py`

**Tests** (7 total):
1. `test_request_confirmation_confirmed()`
2. `test_request_confirmation_cancelled()`
3. `test_request_confirmation_dangerous_flag()`
4. `test_request_confirmation_error_handling()`
5. `test_request_choice_selected()`
6. `test_request_choice_cancelled()`
7. `test_request_choice_error_handling()`

**Validation**:
```bash
EMBEDDING_MODE=mock pytest tests/mnemo_mcp/test_elicitation.py -v
# Expected: 7/7 tests passing
```

#### Step 5: Update Integration Tests (15 min)

**Files**:
- `tests/mnemo_mcp/test_memory_tools.py` - Add elicitation test
- `tests/mnemo_mcp/test_config_tools.py` - Add elicitation test

**Validation**:
```bash
EMBEDDING_MODE=mock pytest tests/mnemo_mcp/ -v
# Expected: 227/227 tests passing (218 + 7 + 2)
```

#### Step 6: Write Documentation (45 min)

**File**: `docs/mcp/ELICITATION_PATTERNS.md`

**Sections**:
1. Overview (200 words)
2. Pattern 1: Destructive Confirmation (300 words)
3. Pattern 2: Large Operation Warning (250 words)
4. Pattern 3: Ambiguous Choice (250 words)
5. Pattern 4: Bypass with Flag (200 words)
6. Best Practices (150 words)
7. Anti-Patterns (150 words)

**Validation**:
- All patterns documented
- Code examples provided
- Best practices clear
- Markdown renders correctly

#### Step 7: Update Progress Tracker (10 min)

**File**: `docs/agile/serena-evolution/03_EPICS/EPIC-23_PROGRESS_TRACKER.md`

**Updates**:
- Mark Story 23.11 as ✅ COMPLETED
- Update progress: 19/23 pts (83%)
- Add completion time (actual vs estimated)
- Update test count: 227 tests

#### Step 8: Create Completion Report (30 min)

**File**: `docs/agile/serena-evolution/03_EPICS/EPIC-23_STORY_23.11_COMPLETION_REPORT.md`

**Sections**:
- Executive Summary
- Deliverables (helpers, integration, doc)
- Architecture (elicitation patterns)
- Testing (7 new tests)
- Integration (Stories 23.3, 23.7 completed)
- Files Created/Modified
- Lessons Learned

---

## 9. Validation Checklist

### 9.1 Functional Validation

- [ ] `request_confirmation()` returns ElicitationResult
- [ ] `request_choice()` returns selected option
- [ ] `request_choice()` raises ValueError on cancel
- [ ] Dangerous flag shows warning in prompt
- [ ] Logging captures all elicitation events
- [ ] Integration with delete_memory works
- [ ] Integration with switch_project works
- [ ] Bypass flags (`confirm=True`) still work

### 9.2 Test Validation

- [ ] 7 new unit tests passing
- [ ] 2 integration tests passing
- [ ] Total 227 tests passing
- [ ] 100% code coverage for elicitation.py

### 9.3 Documentation Validation

- [ ] ELICITATION_PATTERNS.md created
- [ ] All 4 patterns documented
- [ ] Code examples provided
- [ ] Best practices listed
- [ ] Anti-patterns documented
- [ ] Markdown renders correctly

### 9.4 Code Quality Validation

- [ ] No syntax errors
- [ ] Type hints complete
- [ ] Docstrings comprehensive
- [ ] Structured logging used
- [ ] No hardcoded strings (use variables)
- [ ] Follows existing code style

---

## 10. Success Criteria

**Story 23.11 is complete when**:

1. ✅ `elicitation.py` module created with helpers
2. ✅ `memory_tools.py` TODO removed, elicitation added
3. ✅ `config_tools.py` TODO removed, elicitation added
4. ✅ 7 unit tests created and passing
5. ✅ 2 integration tests updated and passing
6. ✅ ELICITATION_PATTERNS.md documentation created
7. ✅ Progress Tracker updated
8. ✅ Completion Report created
9. ✅ All TODOs for elicitation resolved
10. ✅ Total tests: 227/227 passing

---

**ULTRATHINK Generated**: 2025-10-28 09:30
**Status**: Ready for implementation
**Estimated Time**: 3h (aligned with original estimate)
**Risk Level**: Low (straightforward helpers + doc)
