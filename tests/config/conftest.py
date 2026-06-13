"""
Shared fixtures for comprehensive project-wide config audit (P4).
Couvre TOUS les fichiers Python du projet, pas seulement api/workers/scripts.
"""

import ast
import re
from pathlib import Path
from typing import Dict, List, Set

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

EXCLUDE_DIRS = {".git", ".venv", "frontend", "__pycache__", "archive", "legacy",
                "node_modules", ".mypy_cache", ".pytest_cache", ".ruff_cache"}


def _get_all_pyfiles(root: Path) -> List[Path]:
    """Get ALL .py files in the project excluding noise dirs."""
    files = []
    for f in sorted(root.rglob("*.py")):
        parts = f.parts
        if not any(e in parts for e in EXCLUDE_DIRS):
            files.append(f)
    return files


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def all_pyfiles(project_root: Path) -> List[Path]:
    """All Python files in the project (excluding noise)."""
    return _get_all_pyfiles(project_root)


@pytest.fixture(scope="session")
def env_vars_in_code(all_pyfiles: List[Path]) -> Dict[str, Set[str]]:
    """
    Scan ALL Python files for os.getenv, os.environ.get, os.environ[] calls.
    Also parse ALL Settings/BaseSettings subclasses to extract their fields.
    """
    result = {
        "os_getenv": set(),
        "os_environ_get": set(),
        "os_environ_direct": set(),
        "settings_fields": set(),       # AppSettings fields
        "mcp_config_fields": set(),     # MCPConfig fields
        "worker_settings_fields": set(),# workers Settings fields
        "global_constants": {},         # file_path -> [(line, var_name, value)]
    }

    getenv_pat = re.compile(r"os\.getenv\s*\(\s*[\"']([A-Z_]+)[\"']")
    envget_pat = re.compile(r"os\.environ\.get\s*\(\s*[\"']([A-Z_]+)[\"']")
    envdir_pat = re.compile(r"os\.environ\s*\[\s*[\"']([A-Z_]+)[\"']")

    for pyfile in all_pyfiles:
        try:
            text = pyfile.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        relpath = pyfile.relative_to(PROJECT_ROOT)

        for m in getenv_pat.finditer(text):
            result["os_getenv"].add(m.group(1))
        for m in envget_pat.finditer(text):
            result["os_environ_get"].add(m.group(1))
        for m in envdir_pat.finditer(text):
            result["os_environ_direct"].add(m.group(1))

    # Parse ALL Settings classes
    settings_files = [
        (PROJECT_ROOT / "api" / "core" / "settings.py", "settings_fields"),
        (PROJECT_ROOT / "api" / "mnemo_mcp" / "config.py", "mcp_config_fields"),
        (PROJECT_ROOT / "workers" / "config" / "settings.py", "worker_settings_fields"),
    ]

    for sfile, field_key in settings_files:
        if sfile.exists():
            try:
                tree = ast.parse(sfile.read_text())
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        for item in node.body:
                            if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                                result[field_key].add(item.target.id)
            except Exception:
                pass

    return result


@pytest.fixture(scope="session")
def env_example_doc(project_root: Path) -> Dict[str, str]:
    """Parse .env.example into {VAR_NAME: default_value}."""
    env_path = project_root / ".env.example"
    documented = {}
    if not env_path.exists():
        return documented
    text = env_path.read_text()
    for line in text.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        if line.startswith("#"):
            line = line[1:].strip()
        if "=" in line:
            name, rest = line.split("=", 1)
            name = name.strip()
            if name and name[0].isupper() and name.isupper():
                documented[name] = rest.strip()
    return documented


@pytest.fixture(scope="session")
def docker_compose_env(project_root: Path) -> Set[str]:
    """Extract env vars referenced in docker-compose.yml."""
    dc_path = project_root / "docker-compose.yml"
    env_vars = set()
    if not dc_path.exists():
        return env_vars
    text = dc_path.read_text()
    pat = re.compile(r"\$\{?([A-Z][A-Z_0-9]+)\}?")
    OS_SHELL_VARS = {"HOME", "PWD", "UID", "GID", "PATH", "SHELL", "USER", "HOSTNAME"}
    for m in pat.finditer(text):
        name = m.group(1)
        if name not in OS_SHELL_VARS:
            env_vars.add(name)
    return env_vars



@pytest.fixture(scope="session")
def pydantic_env_vars(project_root: Path) -> Dict[str, Set[str]]:
    """
    Extract env var names from ALL BaseSettings subclasses that use env_prefix.
    Parses SettingsConfigDict for env_prefix and combines with field names.
    Returns {class_name: set of full env var names}.
    """
    import ast as _ast
    
    result = {}
    
    # Files to scan for BaseSettings subclasses
    settings_files = [
        project_root / "api" / "core" / "settings.py",
        project_root / "api" / "mnemo_mcp" / "config.py",
        project_root / "workers" / "config" / "settings.py",
    ]
    
    for sfile in settings_files:
        if not sfile.exists():
            continue
        try:
            tree = _ast.parse(sfile.read_text())
            for node in _ast.walk(tree):
                if isinstance(node, _ast.ClassDef):
                    # Check if it inherits from BaseSettings
                    is_basesettings = any(
                        isinstance(base, _ast.Name) and base.id == "BaseSettings"
                        for base in node.bases
                    )
                    if not is_basesettings:
                        continue
                    
                    # Find the env_prefix
                    prefix = ""
                    for item in node.body:
                        if isinstance(item, _ast.Assign):
                            for target in item.targets:
                                if isinstance(target, _ast.Name) and target.id == "model_config":
                                    if isinstance(item.value, _ast.Call):
                                        for kw in item.value.keywords:
                                            if kw.arg == "env_prefix":
                                                if isinstance(kw.value, _ast.Constant):
                                                    prefix = kw.value.value
                    
                    # Extract field names (AnnAssign with type annotation)
                    fields = set()
                    for item in node.body:
                        if isinstance(item, _ast.AnnAssign) and isinstance(item.target, _ast.Name):
                            field_name = item.target.id
                            if prefix:
                                # Build env var name: PREFIX + UPPER_FIELD_NAME
                                env_name = prefix + field_name.upper()
                            else:
                                # No prefix: env var name = field name uppercased
                                # (works for AppSettings + workers Settings which use case_sensitive=False)
                                env_name = field_name.upper()
                            fields.add(env_name)
                    
                    if fields:
                        result[node.name] = fields
        except Exception:
            pass
    
    return result
