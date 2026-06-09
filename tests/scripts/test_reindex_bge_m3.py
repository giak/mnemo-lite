"""
Tests unitaires pour reindex_bge_m3.py — EPIC-48 Story 48.3

Couvre :
- build_db_url() avec DATABASE_URL (cas nominal)
- build_db_url() avec POSTGRES_* individuelles
- build_db_url() avec POSTGRES_USER="" (le bug historique — chaine vide)
- build_db_url() avec fallback vers les defauts
"""

import os
import sys
import pytest

# Add scripts dir to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../scripts"))

from reindex_bge_m3 import build_db_url


class TestBuildDbUrl:
    """Tests pour la construction robuste de l'URL de connexion DB."""

    def test_datatable_url_priority(self, monkeypatch):
        """DATABASE_URL doit etre utilise en priorite absolue."""
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@host:5432/db")
        monkeypatch.setenv("POSTGRES_USER", "ignored_user")
        monkeypatch.setenv("POSTGRES_HOST", "ignored_host")

        url = build_db_url()

        assert "postgresql+asyncpg://user:pass@host:5432/db" == url

    def test_postgres_vars_individual(self, monkeypatch):
        """Sans DATABASE_URL, les POSTGRES_* individuelles sont utilisees."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("POSTGRES_USER", "myuser")
        monkeypatch.setenv("POSTGRES_PASSWORD", "mypass")
        monkeypatch.setenv("POSTGRES_HOST", "myhost")
        monkeypatch.setenv("POSTGRES_PORT", "9999")
        monkeypatch.setenv("POSTGRES_DB", "mydb")

        url = build_db_url()

        assert "postgresql+asyncpg://myuser:mypass@myhost:9999/mydb" == url

    def test_empty_user_string_falls_back_to_default(self, monkeypatch):
        """BUG HISTORIQUE : POSTGRES_USER="" (chaine vide) donnait user vide.
        L'operateur 'or' doit utiliser le defaut."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("POSTGRES_USER", "")  # chaine VIDE — pas absente
        monkeypatch.setenv("POSTGRES_PASSWORD", "mypass")
        monkeypatch.setenv("POSTGRES_HOST", "myhost")
        monkeypatch.setenv("POSTGRES_DB", "mydb")

        url = build_db_url()

        # Le defaut "mnemo" doit remplacer la chaine vide
        assert "postgresql+asyncpg://mnemo:mypass@myhost:5432/mydb" == url

    def test_empty_password_falls_back(self, monkeypatch):
        """POSTGRES_PASSWORD="" doit aussi tomber sur le defaut."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("POSTGRES_PASSWORD", "")
        monkeypatch.setenv("POSTGRES_HOST", "myhost")

        url = build_db_url()

        # Le defaut pour password est "mnemo"
        # URL attendue: postgresql+asyncpg://mnemo:mnemo@myhost:5432/mnemolite
        assert url == "postgresql+asyncpg://mnemo:mnemo@myhost:5432/mnemolite"

    def test_all_defaults_when_no_env(self, monkeypatch):
        """Sans aucune variable d'environnement, les defauts sont utilises."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("POSTGRES_USER", raising=False)
        monkeypatch.delenv("POSTGRES_PASSWORD", raising=False)
        monkeypatch.delenv("POSTGRES_HOST", raising=False)
        monkeypatch.delenv("POSTGRES_PORT", raising=False)
        monkeypatch.delenv("POSTGRES_DB", raising=False)

        url = build_db_url()

        # Defauts: mnemo / mnemo / db / 5432 / mnemolite
        assert "postgresql+asyncpg://mnemo:mnemo@db:5432/mnemolite" == url

    def test_docker_network_hostname(self, monkeypatch):
        """Dans le reseau Docker, le hostname par defaut est 'db' (pas 'localhost')."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.delenv("POSTGRES_HOST", raising=False)

        url = build_db_url()

        assert "@db:" in url
        assert "@localhost:" not in url
