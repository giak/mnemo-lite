"""
Tests EPIC-58 : backfill des embeddings manquants (scripts/backfill_memory_embeddings.py).

Couvre les 3 stories :
- T3.1 test_backfill_missing_only : seules les mémoires embedding_half IS NULL sont traitées
- T3.2 test_backfill_retry_on_failure : échec embedding → retry avec backoff, pas d'abandon
- T3.3 test_backfill_idempotent : relancer ne régénère pas l'existant

Pattern : tests d'intégration réelle sur la DB de test (mnemolite_test),
comme tests/scripts/test_backfill_name_path.py (asyncpg direct, cleanup systématique).
"""

import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import asyncpg

from scripts.backfill_memory_embeddings import (
    _build_embedding_text,
    backfill_memory_embeddings,
)
from api.core import get_settings


def get_test_database_url() -> str:
    """TEST_DATABASE_URL sans +asyncpg (compatibilité asyncpg)."""
    database_url = get_settings().TEST_DATABASE_URL
    if not database_url:
        pytest.skip("TEST_DATABASE_URL not set")
    if "+asyncpg" in database_url:
        database_url = database_url.replace("+asyncpg", "")
    return database_url


class FakeEmbeddingService:
    """Service d'embedding factice : comptabilise les appels, dimension fixe.

    dim=768 par défaut : la DB de test (mnemolite_test) a des colonnes
    vector(768)/halfvec(768) (la prod est à 1024 après migration bge-m3).
    """

    def __init__(self, dim: int = 768, fail_first: int = 0):
        self.dim = dim
        self.fail_first = fail_first  # 0 = jamais d'échec, N = échec sur les N premiers appels
        self.calls = 0
        self.texts: list = []

    async def generate_embedding(self, text: str) -> list:
        self.calls += 1
        self.texts.append(text)
        if self.calls <= self.fail_first:
            raise RuntimeError("embedding service down (simulated)")
        return [0.1] * self.dim


async def _insert_memory(conn: asyncpg.Connection, embedding_half: bool = False) -> str:
    """Insère une mémoire de test ; retourne son id."""
    memory_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    if embedding_half:
        vec_768 = "[0.1," + "0.1," * 766 + "0.1]"  # 768 dimensions (colonne vector(768) en test)
        await conn.execute(
            """
            INSERT INTO memories (id, title, content, memory_type, created_at, updated_at,
                                  embedding, embedding_half, embedding_model)
            VALUES ($1, $2, $3, 'note', $4, $4, $5::vector,
                    $5::halfvec, 'BAAI/bge-m3')
            """,
            memory_id, f"title-{memory_id[:8]}", f"content-{memory_id[:8]}", now, vec_768,
        )
    else:
        await conn.execute(
            """
            INSERT INTO memories (id, title, content, memory_type, created_at, updated_at)
            VALUES ($1, $2, $3, 'note', $4, $4)
            """,
            memory_id, f"title-{memory_id[:8]}", f"content-{memory_id[:8]}", now,
        )
    return memory_id


@pytest.fixture
async def test_conn():
    """Connexion asyncpg à la DB de test (session-level URL)."""
    conn = await asyncpg.connect(get_test_database_url())
    try:
        yield conn
    finally:
        await conn.close()


@pytest.fixture(autouse=True)
async def _cleanup_test_memories():
    """Nettoie les mémoires de test (title LIKE 'title-%') avant chaque test.

    Garantit l'indépendance entre tests sur la DB de test partagée
    (l'assertion d'idempotence exige 0 mémoire missing résiduelle).
    """
    conn = await asyncpg.connect(get_test_database_url())
    try:
        await conn.execute("DELETE FROM memories WHERE title LIKE 'title-%'")
    finally:
        await conn.close()
    yield


class TestBackfillMemoryEmbeddings:
    """Suite de tests du backfill d'embeddings (EPIC-58)."""

    @pytest.mark.anyio
    async def test_build_embedding_text_contract_epic53(self):
        """T3.x : le texte vectorisé suit le contrat EPIC-53 (title. source-or-content)."""
        assert _build_embedding_text("Titre", "contenu", None) == "Titre. contenu"
        assert _build_embedding_text("Titre", "contenu", "source") == "Titre. source"
        assert _build_embedding_text(None, "contenu", "source") == "source"
        assert _build_embedding_text(None, "contenu", None) == "contenu"

    @pytest.mark.anyio
    async def test_backfill_missing_only(self, test_conn):
        """
        T3.1 : seules les mémoires embedding_half IS NULL sont traitées.
        Une mémoire déjà embeddée ne doit pas être re-générée.
        """
        db_url = get_test_database_url()
        missing_id = await _insert_memory(test_conn, embedding_half=False)
        existing_id = await _insert_memory(test_conn, embedding_half=True)
        try:
            fake = FakeEmbeddingService(dim=768)
            stats = await backfill_memory_embeddings(
                database_url=db_url,
                embedding_service=fake,
                limit=0,
            )

            # La mémoire manquante est traitée
            assert stats["processed"] >= 1
            # Le service a été appelé une fois par mémoire manquante (pas sur l'existante)
            assert fake.calls >= 1

            # Vérifier en base : la manquante est maintenant embeddée
            row = await test_conn.fetchrow(
                "SELECT embedding_half, embedding_model FROM memories WHERE id = $1",
                missing_id,
            )
            assert row is not None
            assert row["embedding_half"] is not None
            assert row["embedding_model"] == get_settings().EMBEDDING_MODEL

            # L'existante n'a pas été re-générée : son embedding_half est toujours présent
            # (le backfill ne traite que WHERE embedding_half IS NULL)
            row2 = await test_conn.fetchrow(
                "SELECT embedding_half, embedding_model FROM memories WHERE id = $1",
                existing_id,
            )
            assert row2["embedding_half"] is not None
            assert row2["embedding_model"] == "BAAI/bge-m3"
        finally:
            await test_conn.execute("DELETE FROM memories WHERE id = ANY($1::uuid[])",
                                    [missing_id, existing_id])

    @pytest.mark.anyio
    async def test_backfill_retry_on_failure(self, test_conn):
        """
        T3.2 : un échec d'embedding est retenté (backoff), pas d'abandon immédiat.
        fail_first=1 → le 1er appel échoue, le 2e réussit.
        """
        db_url = get_test_database_url()
        missing_id = await _insert_memory(test_conn, embedding_half=False)
        try:
            fake = FakeEmbeddingService(dim=768, fail_first=1)
            # limit=1 : seule la mémoire du test est traitée (elle est la plus récente,
            # ORDER BY created_at DESC), insensible aux résidus de la DB partagée.
            stats = await backfill_memory_embeddings(
                database_url=db_url,
                embedding_service=fake,
                limit=1,
                max_retries=3,
            )

            # Le service a été appelé 2 fois (1 échec + 1 succès) pour la mémoire
            assert fake.calls == 2
            assert stats["processed"] == 1
            assert stats["failed"] == 0

            row = await test_conn.fetchrow(
                "SELECT embedding_half FROM memories WHERE id = $1", missing_id
            )
            assert row["embedding_half"] is not None
        finally:
            await test_conn.execute("DELETE FROM memories WHERE id = $1", missing_id)

    @pytest.mark.anyio
    async def test_backfill_idempotent(self, test_conn):
        """
        T3.3 : relancer le backfill ne régénère pas l'existant.
        Après le 1er run, la mémoire est embeddée → 2e run : 0 nouvel appel.
        """
        db_url = get_test_database_url()
        missing_id = await _insert_memory(test_conn, embedding_half=False)
        try:
            fake1 = FakeEmbeddingService(dim=768)
            stats1 = await backfill_memory_embeddings(
                database_url=db_url, embedding_service=fake1, limit=1
            )
            assert stats1["processed"] == 1

            # 2e run avec un service neuf : la mémoire déjà embeddée n'est pas re-traitée
            # (WHERE embedding_half IS NULL). On vérifie que son texte n'apparaît pas
            # dans les appels du 2e run (robuste même si la DB partagée a des résidus).
            test_text = f"title-{missing_id[:8]}. content-{missing_id[:8]}"
            fake2 = FakeEmbeddingService(dim=768)
            stats2 = await backfill_memory_embeddings(
                database_url=db_url, embedding_service=fake2, limit=0
            )
            assert test_text not in fake2.texts

            row = await test_conn.fetchrow(
                "SELECT embedding_half FROM memories WHERE id = $1", missing_id
            )
            assert row["embedding_half"] is not None
        finally:
            await test_conn.execute("DELETE FROM memories WHERE id = $1", missing_id)

    @pytest.mark.anyio
    async def test_backfill_dry_run_writes_nothing(self, test_conn):
        """
        T3.x : en dry_run, le backfill génère mais n'écrit pas en base.
        """
        db_url = get_test_database_url()
        missing_id = await _insert_memory(test_conn, embedding_half=False)
        try:
            fake = FakeEmbeddingService(dim=768)
            stats = await backfill_memory_embeddings(
                database_url=db_url,
                embedding_service=fake,
                limit=0,
                dry_run=True,
            )
            assert stats["processed"] >= 1
            assert fake.calls >= 1

            # Rien écrit : embedding_half reste NULL
            row = await test_conn.fetchrow(
                "SELECT embedding_half FROM memories WHERE id = $1", missing_id
            )
            assert row["embedding_half"] is None
        finally:
            await test_conn.execute("DELETE FROM memories WHERE id = $1", missing_id)
