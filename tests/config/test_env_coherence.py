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
    skip_vars = {"EMBEDDING_MODEL", "CODE_EMBEDDING_MODEL", "ENVIRONMENT", "EMBEDDING_MODE"}

    mismatches = []
    for var in sorted(common_vars):
        if var in skip_vars:
            continue
        actual = str(getattr(settings, field, "MISSING"))
        expected_raw = env_example_doc.get(var, "")
        if expected_raw:
            expected = expected_raw.split("#")[0].strip().strip('"').strip("'")
            if actual != expected and actual != "MISSING":
                mismatches.append(f"  {var}: doc says '{expected}', code has '{actual}'")

    if mismatches:
        pytest.fail("\n".join(mismatches))
