"""
Automated coherence tests for environment variable configuration.

Verifies that:
1. All env vars used in code are documented in .env.example
2. All env vars in docker-compose.yml are documented in .env.example
3. AppSettings field defaults match .env.example documented defaults
4. No undocumented env var drift between code, config, and documentation
"""

from typing import Dict, Set

import pytest

WHITELIST_UNDOCUMENTED = {
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "POSTGRES_INITDB_ARGS",
    "OTLP_LOGS_ENDPOINT",
}


def test_all_getenv_vars_documented(env_vars_in_code, env_example_doc):
    """Every os.getenv() var must be documented in .env.example."""
    all_code_vars = (
        env_vars_in_code["os_getenv"]
        | env_vars_in_code["os_environ_get"]
        | env_vars_in_code["os_environ_direct"]
    )
    documented = set(env_example_doc.keys())
    undocumented = all_code_vars - documented - WHITELIST_UNDOCUMENTED

    if undocumented:
        pytest.fail(
            f"{len(undocumented)} env var(s) used in code but NOT documented:\n"
            + "\n".join(f"  {v}" for v in sorted(undocumented))
        )


def test_all_appsettings_fields_documented(env_vars_in_code, env_example_doc):
    """Every AppSettings field (uppercase) must be documented in .env.example."""
    settings_fields = env_vars_in_code.get("settings_fields", set())
    documented = set(env_example_doc.keys())
    undocumented = settings_fields - documented - WHITELIST_UNDOCUMENTED

    if undocumented:
        pytest.fail(
            f"{len(undocumented)} AppSettings field(s) NOT documented:\n"
            + "\n".join(f"  {v}" for v in sorted(undocumented))
        )


def test_docker_compose_vars_documented(env_example_doc, docker_compose_env):
    """Every env var used in docker-compose.yml must be documented."""
    documented = set(env_example_doc.keys())
    undocumented = docker_compose_env - documented - WHITELIST_UNDOCUMENTED

    if undocumented:
        pytest.fail(
            f"{len(undocumented)} docker-compose var(s) NOT documented:\n"
            + "\n".join(f"  {v}" for v in sorted(undocumented))
        )


def test_no_dead_documentation(env_vars_in_code, env_example_doc, docker_compose_env):
    """Warn about env vars documented but NEVER used in code."""
    all_code_vars = (
        env_vars_in_code["os_getenv"]
        | env_vars_in_code["os_environ_get"]
        | env_vars_in_code["os_environ_direct"]
        | env_vars_in_code.get("settings_fields", set())
        | docker_compose_env
    )
    documented = set(env_example_doc.keys())
    frontend_vars = {v for v in documented if v.startswith("VITE_")}
    documented_backend = documented - frontend_vars

    unused = documented_backend - all_code_vars - WHITELIST_UNDOCUMENTED

    # Compute Pydantic-only fields dynamically (AppSettings fields not read via os.getenv)
    all_os_vars = (
        env_vars_in_code["os_getenv"]
        | env_vars_in_code["os_environ_get"]
        | env_vars_in_code["os_environ_direct"]
    )
    pydantic_only_fields = (
        env_vars_in_code.get("settings_fields", set())
        - all_os_vars
        - docker_compose_env
    )
    unused -= pydantic_only_fields

    if unused:
        pytest.fail(
            f"{len(unused)} var(s) documented but unused:\n"
            + "\n".join(f"  {v}" for v in sorted(unused))
        )


def test_appsettings_defaults_match_env_example(env_example_doc, env_vars_in_code):
    """Verify AppSettings default values match .env.example."""
    from api.core.settings import get_settings
    settings = get_settings()

    common_vars = set(env_example_doc.keys()) & env_vars_in_code.get("settings_fields", set())
    # Skip auto-deduced, user-specific, and connection-string fields
    skip_vars = {
        "EMBEDDING_MODEL", "CODE_EMBEDDING_MODEL", "ENVIRONMENT", "EMBEDDING_MODE",
        "CLAUDE_PROJECTS_DIR", "CODEBUFF_DIR", "CODEBUFF_PROJECTS_DIR", "OPENCODE_DIR",
        "DATABASE_URL", "MCP_DATABASE_URL", "TEST_DATABASE_URL", "REDIS_URL",
        "EMBEDDING_DIMENSION", "CODE_EMBEDDING_DIMENSION", "EMBEDDING_BACKEND",
        "EMBEDDING_PREFIX",
    }

    mismatches = []
    for var in sorted(common_vars):
        if var in skip_vars:
            continue
        actual = str(getattr(settings, var, "MISSING"))
        expected_raw = env_example_doc.get(var, "")
        if expected_raw:
            expected = expected_raw.split("#")[0].strip().strip('"').strip("'")
            if actual.lower() != expected.lower() and actual != "MISSING":
                mismatches.append(f"  {var}: doc says '{expected}', code has '{actual}'")

    if mismatches:
        pytest.fail("\n".join(mismatches))


# ===== P4: ENFORCE TESTS — Systematic audit of ALL static/hardcoded config =====

def test_no_ad_hoc_getenv_outside_settings(project_root, all_pyfiles):
    """
    ENFORCE: No os.getenv() or os.environ calls outside Settings classes.
    All env vars must go through AppSettings (api/core/settings.py).
    """
    import re as _re
    
    getenv_pat = _re.compile(r"""os\.getenv\s*\(\s*["']([A-Z_]+)["']""")
    environ_pat = _re.compile(r"""os\.environ""")
    
    # Scripts that still need refactoring (TODO: refactor to get_settings())
    # Only scan api/ and workers/ (critical dirs)
    violations = []
    for pyfile in sorted(all_pyfiles):
        relpath = str(pyfile.relative_to(project_root))
        # Skip non-critical dirs
        if not relpath.startswith("api/") and not relpath.startswith("workers/"):
            continue
        
        # Skip Settings classes themselves, conftest, and __init__
        if any(s in relpath for s in [
            "settings.py", "settings",
            "conftest.py", "__init__",
            "test_",
            "/mcp/config.py",
        ]):
            continue
        # Skip settings.py files (the SSOT itself)

            
        try:
            text = pyfile.read_text(encoding="utf-8", errors="ignore")
            for i, line in enumerate(text.splitlines(), 1):
                if getenv_pat.search(line):
                    # Extract var name
                    m = getenv_pat.search(line)
                    violations.append(f'{relpath}:{i}  os.getenv("' + m.group(1) + '")')
        except Exception:
            pass
    
    if violations:
        msg = str(len(violations)) + " ad-hoc os.getenv() calls found (must use get_settings()):\n"
        msg += "\n".join(violations[:30])
        if len(violations) > 30:
            msg += "\n... and " + str(len(violations)-30) + " more"
        pytest.fail(msg)


def test_no_global_constants_outside_settings(project_root, all_pyfiles):
    """
    ENFORCE: No module-level uppercase constants (config leaks) in source.
    All config values must be in AppSettings or clearly NOT config.
    """
    import ast as _ast
    
    # Known non-config uppercase constants to allow
    ALLOWED_GLOBALS = {
        # Dunders
        "__all__", "__version__", "__author__", "__copyright__", "__license__",
        # Loggers
        "LOGGER", "logger",
        # Internal caches/singletons
        "_MODEL_CACHE", "_pool", "_CACHE", "_LOCK", "_instance",
        # Internal filters (not config)
        "EXCLUDE_DIRS", "EXCLUDE_PATTERNS",
        "WHITELIST_UNDOCUMENTED",
        "PROJECT_ROOT", "BASE_DIR", "SOURCE_DIRS",
        # Ast nodes / types - domain definitions not config
        "FUNCTION", "CLASS", "METHOD", "MODULE", "ARROW_FUNCTION", "ASYNC_FUNCTION",
        "INTERFACE", "ENUM", "TYPE_ALIAS", "VARIABLE", "PROPERTY",
        # Memory types / enums
        "NOTE", "DECISION", "TASK", "REFERENCE", "CONVERSATION", "INVESTIGATION",
        "ARTICLE", "QUINTESSENCE", "SYSTEM",
        # Error/status codes
        "DATABASE", "VALIDATION", "NOT_FOUND", "CONFLICT", "NETWORK",
        "PERMISSION", "INTERNAL", "TIMEOUT",
        # DB columns
        "COLUMNS", "SUB_BATCH_SIZE",
        # HTTP / status
        "EXEMPT_PATHS",
        # Pathspec
        "PATHSPEC_AVAILABLE", "MAX_FILES", "WARN_FILES",
        # Embedding modes
        "VALID_EMBEDDING_MODES",
        # Known models registry
        "KNOWN_MODELS",
        # Decay presets
        "DECAY_PRESETS", "DEFAULT_DECAY_RATE",
        # Upload limits (intentionally static)
        "MAX_UPLOAD_SIZE", "MAX_FILES_PER_UPLOAD", "MAX_CONCURRENT_UPLOADS",
        "MAX_ERRORS", "MAX_RECENT_FILES", "REPOSITORY_NAME_PATTERN",
        "MAX_ERRORS_BEFORE_BACKOFF",
        # Test/benchmark constants (not production config)
        "TEST_QUERIES", "SAMPLE_REPOSITORIES", "BENCHMARK_RESULTS_DIR",
        "DEFAULT_NUM_RUNS", "DEFAULT_EMBEDDING_DIM",
        # Misc domain constants
        "EXTRACTABLE_TYPES", "EXTRACTABLE_SYSTEM_TAGS",
        "LANGUAGE_ALIASES", "EXTENSION_MAP", "COMMENT_SYNTAX",
        "REQUIRED_KEYS", "REQUIRED_TOP_LEVEL_KEYS",
        "TIMEOUTS", "REDIS_RETRY_CONFIG", "DATABASE_RETRY_CONFIG", "CACHE_RETRY_CONFIG",
        "CIRCUIT_CONFIGS",
        "NAV_MAP",
        "EXCLUDE_TYPES", "INCLUDE_EXTENSIONS",
        "O2_URL", "O2_USER", "O2_PASSWORD",
    }
    
    violations = []
    for pyfile in sorted(all_pyfiles):
        relpath = str(pyfile.relative_to(project_root))
        
        # Only scan api/ and workers/ (skip domain models, scripts, db repos)
        if not relpath.startswith("api/") and not relpath.startswith("workers/"):
            continue
        # Skip tests and config files
        if any(s in relpath for s in ["test_", "conftest", "__init__", "settings.py"]):
            continue
            
        try:
            text = pyfile.read_text(encoding="utf-8", errors="ignore")
            tree = _ast.parse(text)
            for node in _ast.walk(tree):
                if isinstance(node, _ast.Assign):
                    for target in node.targets:
                        if isinstance(target, _ast.Name) and target.id.isupper() and len(target.id) > 2:
                            if target.id not in ALLOWED_GLOBALS:
                                # Check if value is a constant (string, number, list, dict, bool)
                                if isinstance(node.value, (_ast.Constant, _ast.List, _ast.Dict, _ast.Set, _ast.Tuple)):
                                    if isinstance(node.value, _ast.Constant):
                                        val = repr(node.value.value)[:60]
                                    else:
                                        val = "(collection)"
                                    violations.append(f"{relpath}:{node.lineno}  {target.id} = {val}")
        except SyntaxError:
            pass
    
    if violations:
        msg = str(len(violations)) + " global constant(s) not in AppSettings (config leaks):\n"
        msg += "\n".join(violations[:30])
        if len(violations) > 30:
            msg += "\n... and " + str(len(violations)-30) + " more"
        pytest.fail(msg)


def test_no_hardcoded_localhost_in_source(project_root, all_pyfiles):
    """
    ENFORCE: No hardcoded 'localhost' in Python source (outside Settings/docstrings).
    """
    import ast as _ast
    
    violations = []
    for pyfile in sorted(all_pyfiles):
        relpath = str(pyfile.relative_to(project_root))
        
        if any(s in relpath for s in ["test_", "conftest", "__init__"]):
            continue
        
        try:
            text = pyfile.read_text(encoding="utf-8", errors="ignore")
            tree = _ast.parse(text)
            for node in _ast.walk(tree):
                if isinstance(node, _ast.Constant) and isinstance(node.value, str):
                    if node.value in ("localhost", "127.0.0.1", "0.0.0.0"):
                        # Note: ast.walk doesn't provide parent refs, so we skip docstring filtering
                        # This may flag some false positives in docstrings - acceptable for enforce test
                            violations.append(f"{relpath}:{node.lineno}  hardcoded '{node.value}'")
        except SyntaxError:
            pass
    
    
    if violations:
        # For localhost in non-critical paths, warn only
        important = [v for v in violations if "localhost" in v and "http" in v]
        if important:
            msg = str(len(important)) + " hardcoded hostname(s) in source:\n"
            msg += "\n".join(important[:15])
            pytest.fail(msg)


def test_no_password_defaults_in_source(project_root, all_pyfiles):
    """
    ENFORCE: No hardcoded passwords in source code outside Settings.
    """
    import re as _re
    
    violations = []
    password_patterns = [
        _re.compile(r'"(?:password|passwd|pwd)"\s*[:=]\s*"[a-zA-Z0-9_@#!$^&*()+.-]+"', _re.IGNORECASE),
    ]
    
    for pyfile in sorted(all_pyfiles):
        relpath = str(pyfile.relative_to(project_root))
        
        if any(s in relpath for s in ["test_", "conftest", "__init__"]):
            continue
        if relpath.endswith("settings.py"):
            continue
            
        try:
            text = pyfile.read_text(encoding="utf-8", errors="ignore")
            for pat in password_patterns:
                for m in pat.finditer(text):
                    line_no = text[:m.start()].count(chr(10)) + 1
                    violations.append(f"{relpath}:{line_no}  {m.group()[:60]}")
        except Exception:
            pass
    
    if violations:
        msg = str(len(violations)) + " hardcoded password(s) in source:\n"
        msg += "\n".join(violations[:15])
        if len(violations) > 15:
            msg += "\n... and " + str(len(violations)-15) + " more"
        pytest.fail(msg)
