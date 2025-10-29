"""
MCP Elicitation Helpers (EPIC-23 Story 23.11).

Reusable helpers for human-in-the-loop confirmations and choices.

This module provides standardized elicitation patterns for:
- Destructive operations (delete, clear cache)
- Large operations (indexing >10k files)
- Ambiguous choices (multiple projects found)

Usage:
    >>> from mnemo_mcp.elicitation import request_confirmation, request_choice
    >>> result = await request_confirmation(
    ...     ctx,
    ...     action="Delete Memory",
    ...     details="Memory 'foo' will be permanently deleted",
    ...     dangerous=True
    ... )
    >>> if result.confirmed:
    ...     # Proceed with deletion
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
        >>> else:
        ...     # Abort operation
    """
    logger.info("elicitation.confirm", action=action, dangerous=dangerous)

    # Build prompt with warning if dangerous
    title = f"⚠️ Confirm: {action}" if dangerous else f"Confirm: {action}"
    prompt_text = f"{details}\n\nProceed?"

    # Options for Yes/No confirmation
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
            selected=response.value,
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
            error=str(e),
            error_type=type(e).__name__
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
        default: Default choice (optional, currently not used but for future)

    Returns:
        Selected choice string

    Raises:
        ValueError: If user selects "Cancel" or elicitation fails

    Example:
        >>> choice = await request_choice(
        ...     ctx,
        ...     question="Which project to index?",
        ...     choices=["project-a", "project-b", "project-c"]
        ... )
        >>> print(f"Indexing {choice}")
    """
    logger.info(
        "elicitation.choice",
        question=question,
        choices=choices,
        default=default
    )

    # Add Cancel option automatically
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

        logger.info(
            "elicitation.choice_selected",
            question=question,
            choice=selected
        )

        return selected

    except ValueError:
        # Re-raise cancellation (expected flow)
        raise
    except Exception as e:
        logger.error(
            "elicitation.choice_error",
            question=question,
            error=str(e),
            error_type=type(e).__name__
        )
        raise ValueError("Elicitation failed or cancelled") from e
