"""
Shared fixtures for configuration tests.
"""

import ast
import re
from pathlib import Path
from typing import Dict, Set

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def env_vars_in_code(project_root: Path) -> Dict[str, Set[str]]:
    result = {
        "os_getenv": set(),
        "os_environ_get": set(),
        "os_environ_direct": set(),
        "settings_fields": set(),
    }

    source_dirs = [
        project_root / "api",
        project_root / "workers",
        project_root / "scripts",
    ]

    getenv_pat = re.compile(r"""os\.getenv\s*\(\s*["']([A-Z_]+)["']""")
    envget_pat = re.compile(r"""os\.environ\.get\s*\(\s*["']([A-Z_]+)["']""")
    envdir_pat = re.compile(r"""os\.environ\s*\[\s*["']([A-Z_]+)["']""")

    for src_dir in source_dirs:
        if not src_dir.exists():
            continue
        for pyfile in sorted(src_dir.rglob("*.py")):
            if "node_modules" in str(pyfile) or "__pycache__" in str(pyfile):
                continue
            try:
                text = pyfile.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for m in getenv_pat.finditer(text):
                result["os_getenv"].add(m.group(1))
            for m in envget_pat.finditer(text):
                result["os_environ_get"].add(m.group(1))
            for m in envdir_pat.finditer(text):
                result["os_environ_direct"].add(m.group(1))

    # Parse AppSettings class fields
    settings_file = project_root / "api" / "core" / "settings.py"
    if settings_file.exists():
        try:
            tree = ast.parse(settings_file.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == "AppSettings":
                    for item in node.body:
                        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                            name = item.target.id
                            if name.isupper():
                                result["settings_fields"].add(name)
        except Exception:
            pass

    return result


@pytest.fixture(scope="session")
def env_example_doc(project_root: Path) -> Dict[str, str]:
    env_path = project_root / ".env.example"
    documented = {}
    if not env_path.exists():
        return documented
    text = env_path.read_text()
    for line in text.splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        # Remove leading # and whitespace
        if line.startswith("#"):
            line = line[1:].strip()
        # Split on first =
        if "=" in line:
            name, rest = line.split("=", 1)
            name = name.strip()
            if name and name[0].isupper() and name.isupper():
                documented[name] = rest.strip()
    return documented


@pytest.fixture(scope="session")
def docker_compose_env(project_root: Path) -> Set[str]:
    dc_path = project_root / "docker-compose.yml"
    env_vars = set()
    if not dc_path.exists():
        return env_vars
    text = dc_path.read_text()
    pat = re.compile(r"""\$\{?([A-Z][A-Z_0-9]+)\}?""")
    for m in pat.finditer(text):
        name = m.group(1)
        if name not in ("HOME", "PWD", "UID", "GID", "PATH", "SHELL", "USER"):
            env_vars.add(name)
    return env_vars
