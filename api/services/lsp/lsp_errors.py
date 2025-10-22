"""
LSP Error Classes.

Story: EPIC-13 Story 13.1 - Pyright LSP Wrapper
Author: Claude Code
Date: 2025-10-22
"""


class LSPError(Exception):
    """Base exception for LSP operations."""
    pass


class LSPInitializationError(LSPError):
    """LSP server initialization failed."""
    pass


class LSPCommunicationError(LSPError):
    """LSP communication error (protocol, network)."""
    pass


class LSPTimeoutError(LSPError):
    """LSP request timed out."""
    pass


class LSPServerCrashedError(LSPError):
    """LSP server process crashed."""
    pass
