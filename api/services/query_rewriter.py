"""
Query Rewriting Service (EPIC-35 Story 35.3).

Expands search queries with synonyms for better recall.
"""
import re
from typing import List, Dict

# Developer-focused synonym dictionary
SYNONYMS: Dict[str, List[str]] = {
    # Authentication & Security
    "auth": ["authentication", "authorization", "login", "signin"],
    "login": ["authentication", "signin", "auth"],
    "password": ["passwd", "pwd", "credentials", "secret"],
    "token": ["jwt", "bearer", "access_token", "refresh_token"],
    "permission": ["role", "access", "privilege", "authz"],

    # Database
    "db": ["database", "postgres", "postgresql", "sql"],
    "query": ["select", "sql", "fetch", "retrieve"],
    "migration": ["alembic", "schema", "ddl", "alter"],
    "connection": ["pool", "engine", "session", "db_url"],

    # Cache
    "cache": ["redis", "memcached", "ttl", "evict", "lru"],
    "invalidate": ["evict", "flush", "clear", "purge"],

    # API & HTTP
    "api": ["endpoint", "route", "handler", "controller", "rest"],
    "request": ["req", "http", "get", "post", "put", "delete"],
    "response": ["resp", "return", "result", "output"],
    "error": ["exception", "fail", "crash", "bug", "traceback"],
    "status": ["code", "http_status", "200", "404", "500"],

    # Code structure
    "func": ["function", "def", "method", "routine"],
    "class": ["type", "struct", "model", "schema"],
    "interface": ["protocol", "abc", "abstract", "contract"],
    "module": ["package", "lib", "library", "component"],
    "import": ["require", "include", "dependency", "dep"],

    # Config & Environment
    "config": ["setting", "option", "env", "environment", "conf"],
    "env": ["environment", "variable", "dotenv", "config"],
    "secret": ["key", "api_key", "token", "credential"],

    # Testing
    "test": ["unit", "integration", "pytest", "mock", "fixture"],
    "assert": ["expect", "verify", "check", "validate"],

    # Async & Concurrency
    "async": ["await", "coroutine", "concurrent", "parallel"],
    "lock": ["mutex", "semaphore", "thread", "race"],

    # Logging & Monitoring
    "log": ["logging", "logger", "debug", "info", "warn", "trace"],
    "monitor": ["metric", "alert", "health", "status", "observe"],
    "trace": ["span", "traceback", "stack", "call"],

    # File & Path
    "file": ["path", "filepath", "filename", "file_path"],
    "dir": ["directory", "folder", "path"],

    # General dev terms
    "init": ["initialize", "setup", "bootstrap", "start"],
    "create": ["new", "make", "build", "generate", "insert"],
    "update": ["modify", "change", "edit", "patch", "put"],
    "delete": ["remove", "drop", "destroy", "rm"],
    "read": ["get", "fetch", "load", "retrieve", "select"],
    "write": ["save", "store", "persist", "insert"],
    "check": ["verify", "validate", "test", "inspect"],
    "run": ["execute", "start", "launch", "invoke"],
    "stop": ["halt", "shutdown", "terminate", "kill"],
}


def rewrite_query(query: str, expand: bool = True) -> str:
    """
    Expand query with synonyms for better recall.

    Args:
        query: Original search query
        expand: Whether to expand with synonyms (default: True)

    Returns:
        Expanded query string with synonyms appended

    Examples:
        >>> rewrite_query("auth function")
        'auth function authentication authorization login signin func function def method'
        >>> rewrite_query("auth function", expand=False)
        'auth function'
    """
    if not expand or not query:
        return query

    tokens = re.findall(r'[a-zA-Z0-9\u00C0-\u024F]+', query.lower())
    expanded = []
    seen = set()

    for token in tokens:
        if token not in seen:
            expanded.append(token)
            seen.add(token)
        # Add synonyms
        for synonym in SYNONYMS.get(token, []):
            if synonym not in seen:
                expanded.append(synonym)
                seen.add(synonym)

    return " ".join(expanded)


def get_synonyms(word: str) -> List[str]:
    """Get synonyms for a single word."""
    return SYNONYMS.get(word.lower(), [])


def has_synonyms(query: str) -> bool:
    """Check if any token in the query has synonyms."""
    tokens = re.findall(r'[a-zA-Z0-9\u00C0-\u024F]+', query.lower())
    return any(token in SYNONYMS for token in tokens)
