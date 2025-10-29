# Elicitation Patterns Guide (EPIC-23 Story 23.11)

**Status**: ✅ Production-ready
**Version**: 1.0.0
**Date**: 2025-10-28

## Overview

This document describes standardized patterns for human-in-the-loop confirmations (elicitation) in MnemoLite's MCP server. Elicitation is used to request user approval before executing destructive, large-scale, or ambiguous operations.

## When to Use Elicitation

### ✅ Use Elicitation For:

1. **Destructive Operations**
   - Permanent deletion (hard delete)
   - Cache clearing
   - Data purging

2. **Large Operations**
   - Indexing >10,000 files
   - Bulk updates
   - Resource-intensive tasks

3. **Context-Changing Operations**
   - Project switching
   - Environment changes
   - Configuration updates

4. **Ambiguous Situations**
   - Multiple matches found
   - Conflicting options
   - Unclear user intent

### ❌ Don't Use Elicitation For:

1. **Reversible Operations**
   - Soft delete (can be restored)
   - Read operations
   - Cache hits

2. **Idempotent Operations**
   - Health checks
   - Status queries
   - Repeated safe operations

3. **Automated Workflows**
   - Use bypass flags (`confirm=True`) for automation
   - CI/CD pipelines
   - Batch processing scripts

## API Reference

### `request_confirmation()`

Request yes/no confirmation from user.

```python
from mnemo_mcp.elicitation import request_confirmation

result = await request_confirmation(
    ctx,
    action="Delete Memory",
    details="Memory 'User preferences' will be permanently deleted",
    dangerous=True  # Shows ⚠️ warning icon
)

if result.confirmed:
    # Proceed with operation
    ...
else:
    # Abort and return cancellation response
    ...
```

**Parameters:**
- `ctx: Context` - MCP context with `elicit()` method
- `action: str` - Action name (e.g., "Delete Memory", "Switch Project")
- `details: str` - Detailed description of consequences
- `dangerous: bool = False` - If True, shows ⚠️ warning icon

**Returns:**
- `ElicitationResult` with:
  - `confirmed: bool` - True if user selected "yes"
  - `cancelled: bool` - True if user selected "no"
  - `selected_option: Optional[str]` - Selected option ("yes" or "no")

**Error Handling:**
- On error, returns `cancelled=True` (safe default)
- Logs error at ERROR level
- Never raises exceptions

---

### `request_choice()`

Request user to select from multiple options.

```python
from mnemo_mcp.elicitation import request_choice

try:
    choice = await request_choice(
        ctx,
        question="Which project to index?",
        choices=["project-a", "project-b", "project-c"],
        default="project-a"  # Currently unused, for future
    )
    print(f"User selected: {choice}")
except ValueError as e:
    # User cancelled or elicitation failed
    logger.info("Operation cancelled", error=str(e))
```

**Parameters:**
- `ctx: Context` - MCP context with `elicit()` method
- `question: str` - Question to ask user
- `choices: List[str]` - Available choices (2-10 recommended)
- `default: Optional[str] = None` - Default choice (for future use)

**Returns:**
- `str` - Selected choice

**Raises:**
- `ValueError` - If user selects "Cancel" or elicitation fails

**Automatic Features:**
- Adds "Cancel" option automatically
- User can always cancel operation

---

### `ElicitationResult` Model

```python
class ElicitationResult(BaseModel):
    confirmed: bool = Field(description="Whether user confirmed action")
    selected_option: Optional[str] = Field(default=None, description="Selected option")
    cancelled: bool = Field(default=False, description="Whether user cancelled")
```

## Usage Patterns

### Pattern 1: Destructive Operation (Hard Delete)

```python
async def execute(self, ctx: Context, id: str, permanent: bool = False):
    """Delete memory (soft delete by default)."""

    if not permanent:
        # Soft delete - no elicitation needed
        return await self.memory_repository.soft_delete(id)

    # Hard delete - requires elicitation
    existing_memory = await self.memory_repository.get_by_id(id)

    result = await request_confirmation(
        ctx,
        action="Permanently Delete Memory",
        details=(
            f"Memory '{existing_memory.title}' will be permanently deleted.\n"
            f"This action cannot be undone.\n\n"
            f"• Type: {existing_memory.memory_type}\n"
            f"• Created: {existing_memory.created_at.strftime('%Y-%m-%d')}\n"
        ),
        dangerous=True  # ⚠️ Shows warning
    )

    if not result.confirmed:
        logger.info("deletion_cancelled", memory_id=id)
        return CancelledResponse(
            success=False,
            message="Deletion cancelled by user"
        )

    # Proceed with hard delete
    await self.memory_repository.delete_permanently(id)
    return SuccessResponse(...)
```

**Key Points:**
- Use `dangerous=True` for irreversible operations
- Provide detailed context (title, type, date)
- Return `CancelledResponse` if user declines
- Log cancellation at INFO level

---

### Pattern 2: Context Switch (Project Switching)

```python
async def execute(self, ctx: Context, request: SwitchProjectRequest):
    """Switch active project."""

    # Allow bypass for automation
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
            dangerous=False  # Not destructive, just context change
        )

        if not result.confirmed:
            return CancelledResponse(
                success=False,
                message="Project switch cancelled by user",
                repository=request.repository
            )

    # Proceed with switch
    ...
```

**Key Points:**
- Use `confirm` parameter to bypass elicitation
- Explain context change impact
- Use `dangerous=False` for non-destructive operations
- Return informative cancellation message

---

### Pattern 3: Multiple Choice (Ambiguous Input)

```python
async def execute(self, ctx: Context, query: str):
    """Index project (handles multiple matches)."""

    # Find matching projects
    matches = find_projects(query)

    if len(matches) > 1:
        # Ambiguous - ask user to choose
        try:
            selected = await request_choice(
                ctx,
                question=f"Found {len(matches)} projects matching '{query}':",
                choices=[m.name for m in matches]
            )
            project = next(m for m in matches if m.name == selected)
        except ValueError:
            # User cancelled
            return CancelledResponse(
                success=False,
                message="Project selection cancelled"
            )
    elif len(matches) == 1:
        # Unambiguous - proceed without elicitation
        project = matches[0]
    else:
        raise ValueError(f"No projects found matching '{query}'")

    # Proceed with indexing
    ...
```

**Key Points:**
- Only elicit when ambiguous (>1 match)
- Handle `ValueError` for cancellation
- Provide clear question and options
- Return informative error messages

---

## Bypass Flags for Automation

All tools with elicitation support bypass flags:

```python
# Python API
await tool.execute(
    ctx,
    repository="my-project",
    confirm=True  # Bypass elicitation
)

# Claude Desktop (JSON args)
{
  "repository": "my-project",
  "confirm": true
}
```

**Use Cases:**
- CI/CD pipelines
- Batch processing scripts
- Automated testing
- API integrations

**Best Practices:**
- Document bypass flags in tool descriptions
- Default to `confirm=False` (require elicitation)
- Log bypass usage for audit trail

---

## Testing Patterns

### Unit Tests for Elicitation Helpers

```python
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_context_confirm():
    """Mock MCP context that confirms action."""
    ctx = MagicMock()
    ctx.elicit = AsyncMock(return_value=MagicMock(value="yes"))
    return ctx

@pytest.fixture
def mock_context_cancel():
    """Mock MCP context that cancels action."""
    ctx = MagicMock()
    ctx.elicit = AsyncMock(return_value=MagicMock(value="no"))
    return ctx

@pytest.mark.asyncio
async def test_confirmation_yes(mock_context_confirm):
    result = await request_confirmation(
        mock_context_confirm,
        action="Test",
        details="Test details"
    )
    assert result.confirmed is True
    assert result.cancelled is False
```

### Integration Tests for Tools

```python
@pytest.fixture
def mock_ctx():
    """Mock MCP Context with elicitation."""
    ctx = MagicMock()
    # Default to "yes" confirmation
    ctx.elicit = AsyncMock(return_value=MagicMock(value="yes"))
    return ctx

@pytest.mark.asyncio
async def test_delete_hard_requires_confirmation(mock_ctx):
    """Test hard delete requires elicitation."""
    tool = DeleteMemoryTool()

    # Mock will return "yes" - operation proceeds
    response = await tool.execute(
        ctx=mock_ctx,
        id="abc-123",
        permanent=True
    )

    assert response["permanent"] is True
    mock_ctx.elicit.assert_called_once()
```

---

## Logging and Audit Trail

All elicitation events are logged at INFO level:

```python
# Elicitation initiated
logger.info("elicitation.confirm", action="Delete Memory", dangerous=True)

# User response
logger.info("elicitation.result", action="Delete Memory", confirmed=True)

# Operation cancelled
logger.info("deletion_cancelled", memory_id="abc-123", title="User prefs")

# Errors (safe default: cancelled)
logger.error("elicitation.error", action="Delete Memory", error="...", error_type="...")
```

**Audit Trail Benefits:**
- Track destructive operations
- Identify user cancellations
- Debug elicitation issues
- Compliance and security

---

## Error Handling

### Safe Defaults

Elicitation uses **fail-safe defaults** on errors:

```python
try:
    response = await ctx.elicit(...)
    return ElicitationResult(confirmed=(response.value == "yes"), ...)
except Exception as e:
    logger.error("elicitation.error", error=str(e))
    # Safe default: assume cancelled
    return ElicitationResult(confirmed=False, cancelled=True)
```

**Rationale:**
- Prevents accidental destructive operations
- User can retry operation
- Explicit error logging

### ValueError for Cancellation

`request_choice()` raises `ValueError` on cancellation:

```python
try:
    choice = await request_choice(ctx, question="...", choices=[...])
except ValueError:
    # User cancelled - expected flow
    return CancelledResponse(...)
```

**Rationale:**
- Distinguishes cancellation from errors
- Explicit handling required
- Prevents silent failures

---

## FastMCP Integration

MnemoLite uses FastMCP SDK (v1.12.3) for elicitation:

```python
from mcp.server.fastmcp import Context

response = await ctx.elicit(
    prompt="Confirm: Delete Memory\n\nMemory 'foo' will be deleted. Proceed?",
    schema={"type": "string", "enum": ["yes", "no"]}
)

confirmed = response.value == "yes"
```

**API Details:**
- Method: `Context.elicit(prompt: str, schema: dict)`
- Returns: Object with `value` attribute
- Schema: JSON Schema for validation
- Async: Returns awaitable

---

## Migration Guide (For Existing Tools)

### Before (Without Elicitation)

```python
async def execute(self, ctx: Context, id: str):
    # Direct deletion
    await self.repository.delete_permanently(id)
    return {"success": True}
```

### After (With Elicitation)

```python
from mnemo_mcp.elicitation import request_confirmation

async def execute(self, ctx: Context, id: str, confirm: bool = False):
    # Request confirmation (unless bypassed)
    if not confirm:
        result = await request_confirmation(
            ctx,
            action="Delete Item",
            details="This action cannot be undone",
            dangerous=True
        )

        if not result.confirmed:
            return {"success": False, "message": "Cancelled by user"}

    # Proceed with deletion
    await self.repository.delete_permanently(id)
    return {"success": True}
```

**Migration Checklist:**
1. ✅ Add `from mnemo_mcp.elicitation import request_confirmation`
2. ✅ Add `confirm: bool = False` parameter
3. ✅ Wrap destructive operation in `if not confirm:` block
4. ✅ Return cancellation response if `not result.confirmed`
5. ✅ Add elicitation mock to tests (`ctx.elicit = AsyncMock(...)`)
6. ✅ Document bypass flag in tool description

---

## Examples in Production

### Current Tools Using Elicitation

1. **`delete_memory` Tool** (`memory_tools.py:449`)
   - Use case: Permanent memory deletion
   - Dangerous: ✅ True
   - Bypass: `permanent=False` (soft delete, no elicitation)

2. **`switch_project` Tool** (`config_tools.py:64`)
   - Use case: Project context switching
   - Dangerous: ❌ False
   - Bypass: `confirm=True` parameter

3. **`clear_cache` Tool** (`analytics_tools.py:64`)
   - Use case: Cache layer clearing (L1/L2/L3)
   - Dangerous: ✅ True (for production caches)
   - Bypass: None (always requires confirmation)

---

## Best Practices

### ✅ Do:

1. **Provide Context** - Explain what will happen and why
2. **Use Dangerous Flag** - For irreversible operations
3. **Log Everything** - Audit trail for security
4. **Test Both Paths** - Confirm AND cancel branches
5. **Return Informative Messages** - Help users understand cancellation
6. **Implement Bypass Flags** - Support automation
7. **Safe Defaults** - Assume cancelled on error

### ❌ Don't:

1. **Elicit for Read Operations** - Only for writes/deletes
2. **Elicit Repeatedly** - Combine multiple checks into one
3. **Ignore Cancellations** - Always respect user choice
4. **Skip Logging** - Audit trail is critical
5. **Use for Idempotent Ops** - Status checks don't need elicitation
6. **Assume "Yes"** - Never default to destructive operations

---

## Future Enhancements (Post-EPIC-23)

1. **Multi-Step Confirmations** - Chain multiple elicitations
2. **Conditional Elicitation** - Based on operation size/risk
3. **Timeout Handling** - Auto-cancel after N seconds
4. **User Preferences** - Remember "don't ask again" choices
5. **Audit Dashboard** - View elicitation history
6. **Custom Schemas** - Beyond yes/no (ratings, text input)

---

## References

- **EPIC-23 Story 23.11**: Elicitation Flows (ULTRATHINK)
- **Implementation**: `api/mnemo_mcp/elicitation.py`
- **Unit Tests**: `api/tests/mnemo_mcp/test_elicitation.py`
- **FastMCP SDK**: https://github.com/jlowin/fastmcp (v1.12.3)
- **MCP Protocol**: 2025-06-18 specification

---

**Document Version**: 1.0.0
**Last Updated**: 2025-10-28
**Author**: Claude (EPIC-23 Story 23.11)
**Status**: ✅ Production-ready
