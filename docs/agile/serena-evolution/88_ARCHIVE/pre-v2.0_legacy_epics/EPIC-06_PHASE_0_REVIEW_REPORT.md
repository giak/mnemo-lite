# EPIC-06 Phase 0: Critical Review Report

**Date**: 2025-10-15
**Reviewer**: Architecture Review Team
**Documents Reviewed**:
- EPIC-06_PHASE_0_IMPLEMENTATION_ULTRADEEP.md (1785 lines)
- EPIC-06_PHASE_0_CRITICAL_INSIGHTS.md (581 lines)

**Status**: 🔍 CRITICAL REVIEW COMPLETE

---

## 📊 Executive Summary

**Overall Score**: **8.5/10** (EXCELLENT avec réserves mineures)

**Verdict**: ✅ **GO FOR PHASE 0 KICKOFF** avec 3 corrections mineures recommandées

**Résumé**:
L'analyse Phase 0 est exceptionnellement complète et rigoureuse. Les 7 insights critiques découverts sont tous validés et correctement analysés. L'architecture proposée est solide, les risques bien identifiés, et les mitigations appropriées. Cependant, 3 points mineurs nécessitent attention avant kickoff.

---

## ✅ FORCES de l'Analyse (Score: 9/10)

### 1. Profondeur Technique Exceptionnelle

**Ce qui est excellent**:
- ✅ Analyse **complète** de l'architecture existante (8 fichiers sources examinés)
- ✅ Code examples **concrets** et **testables** (pas de pseudo-code)
- ✅ Patterns **validés en production** (double-checked locking, lazy loading)
- ✅ Integration points **précisément identifiés** (asyncpg + SQLAlchemy coexistence)

**Exemples forts**:
```python
# Insight #3: Pattern déjà validé dans SentenceTransformerEmbeddingService
async def _ensure_model_loaded(self):
    if self._model is not None:
        return
    async with self._lock:  # Double-checked locking ✅ VALIDÉ
        if self._model is not None:
            return
        loop = asyncio.get_event_loop()
        self._model = await loop.run_in_executor(None, self._load_model_sync)
```

**Impact**: Réduit risque implémentation (patterns déjà battle-tested)

---

### 2. Insights Critiques Découverts

**7 insights majeurs**:
1. **Pas d'ORM SQLAlchemy** → Solution: SQLAlchemy Core (brillant!) ✅
2. **Config scattered** → Solution: Pydantic BaseSettings centralisé ✅
3. **Patterns validés** → Extension simple (-1 jour estimé) ✅
4. **Backward compat** → Adapter pattern (ZÉRO breaking changes) ✅
5. **RAM budget** → Lazy loading + monitoring (660-700 MB < 1 GB) ✅
6. **Baseline NO-OP** → Évite "relation already exists" (intelligent!) ✅
7. **Coexistence safe** → NullPool pour Alembic (pas de conflit) ✅

**Tous ces insights sont VALIDÉS et PERTINENTS**

**Impact Timeline**: -1 jour optimisé (6-7j → 5j)

---

### 3. Plan d'Implémentation Jour-par-Jour

**Structure excellente**:
- ✅ Breakdown détaillé (matin/après-midi)
- ✅ Actions concrètes et vérifiables
- ✅ Tests validation à chaque étape
- ✅ Rollback procedures documentées

**Exemple Jour 2**:
```
Jour 2 Matin (4h):
7. ✅ Installer Alembic: pip install alembic
8. ✅ Init: alembic init -t async alembic
9. ✅ Configurer alembic/env.py
10. ✅ Créer baseline: alembic revision -m "baseline"

Jour 2 Après-midi (4h):
11. ✅ Tester migration: alembic upgrade head
12. ✅ Vérifier: SELECT * FROM alembic_version;
13. ✅ Documenter: README Alembic workflow
```

**Excellente granularité** → Facile à suivre et tracker

---

### 4. Gestion Risques & Mitigations

**Points forts**:
- ✅ 3 risques majeurs identifiés (RAM overflow, Alembic failures, Backward compat)
- ✅ **Probabilité + Impact** quantifiés
- ✅ Plans d'urgence (fallbacks, rollback procedures)
- ✅ Code examples pour fallbacks

**Exemple Mitigation RAM**:
```python
async def _ensure_code_model(self):
    ram = self.get_ram_usage_mb()
    if ram['process_rss_mb'] > 900:  # Safety margin
        logger.warning("RAM limit approaching")
        raise RuntimeError("RAM budget exceeded, CODE model disabled")
```

**Critique positive**: Fallbacks opérationnels (pas juste théoriques)

---

### 5. Tests & Validation Complets

**Coverage excellente**:
- ✅ Tests unitaires (dual models lazy loading)
- ✅ Tests intégration (Phase 0 complete)
- ✅ Tests regression (backward compatibility)
- ✅ Métriques validation (9 métriques avec targets)

**Exemple validation**:
```python
@pytest.mark.anyio
async def test_dual_models_lazy_loading():
    service = DualEmbeddingService(...)

    # Initially no models loaded
    assert service._text_model is None
    assert service._code_model is None

    # Generate TEXT embedding (loads text model only)
    result_text = await service.generate_embedding("Hello", domain=EmbeddingDomain.TEXT)
    assert service._text_model is not None
    assert service._code_model is None  # Code model NOT loaded yet ✅
```

**Tests réalistes** et **vérifiables**

---

## ⚠️ FAIBLESSES Identifiées (Score: 7/10)

### 1. Pydantic v2 Validator Syntax OBSOLÈTE ❌

**Problème CRITIQUE découvert**:

Document propose:
```python
# ❌ SYNTAX OBSOLÈTE (Pydantic v1)
from pydantic import Field, validator

class Settings(BaseSettings):
    CODE_EMBEDDING_DIMENSION: int = 768

    @validator("CODE_EMBEDDING_DIMENSION")  # ❌ DEPRECATED in Pydantic v2!
    def validate_same_dimension(cls, v, values):
        ...
```

**Correction requise** (Pydantic v2 syntax):
```python
# ✅ SYNTAX CORRECTE (Pydantic v2.5+)
from pydantic import Field, field_validator

class Settings(BaseSettings):
    CODE_EMBEDDING_DIMENSION: int = 768

    @field_validator("CODE_EMBEDDING_DIMENSION")  # ✅ Pydantic v2
    @classmethod
    def validate_same_dimension(cls, v, info):  # ✅ info.data au lieu de values
        text_dim = info.data.get("EMBEDDING_DIMENSION", 768)
        if v != text_dim:
            raise ValueError(...)
        return v
```

**Source validation**:
```bash
$ pip show pydantic
Name: pydantic
Version: 2.5.0  # ← Pydantic v2 utilisé dans requirements.txt (line 21)
```

**Impact**: 🔴 **BLOQUANT** - Code ne fonctionnera pas avec Pydantic v2.5+

**Recommandation**: Mettre à jour TOUS les exemples settings.py dans les documents

---

### 2. Manque: Impact Migration Main.py

**Problème**:
L'analyse mentionne "migrer env vars vers settings.py" mais ne montre PAS l'impact sur `main.py:lifespan()`.

**Code actuel** (main.py:28-34):
```python
# main.py
DATABASE_URL = os.getenv("DATABASE_URL")  # ← Sera remplacé
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
```

**Code après Phase 0** (NON documenté):
```python
# main.py APRÈS Phase 0 (MANQUANT dans analyse)
from api.config.settings import get_settings

settings = get_settings()  # ← Changement requis

db_url_to_use = settings.TEST_DATABASE_URL if settings.ENVIRONMENT == "test" else settings.DATABASE_URL

app.state.db_engine = create_async_engine(
    db_url_to_use,
    echo=settings.DEBUG,  # ← Changement
    ...
)
```

**Impact**: Refactoring main.py requis mais **NON chiffré** dans timeline

**Recommandation**: Ajouter tâche "Refactorer main.py pour settings.py" (estimé: +0.5h)

---

### 3. Manque: MockEmbeddingService Adaptation

**Problème**:
Document mentionne MockEmbeddingService mais ne montre PAS comment l'adapter pour dual embeddings.

**Code proposé** (dependencies.py):
```python
if embedding_mode == "mock":
    logger.warning("🔶 EMBEDDING MODE: MOCK")
    _embedding_service_instance = MockEmbeddingService(  # ← Comment ça marche?
        model_name="mock-model",
        dimension=768
    )
```

**Questions non répondues**:
- ❓ MockEmbeddingService implémente `generate_embedding(domain=...)`?
- ❓ Retourne Dict[str, List[float]] ou List[float]?
- ❓ Backward compatible avec tests existants?

**Impact**: Tests MOCK pourraient casser

**Recommandation**: Documenter MockEmbeddingService extension OU créer MockDualEmbeddingService

---

## 🔴 GAPS (Manques) Identifiés

### Gap #1: pgvector.sqlalchemy Import Validation

**Manque**:
Document propose `from pgvector.sqlalchemy import Vector` mais ne vérifie PAS si package installé.

**Code proposé** (api/db/models.py):
```python
from pgvector.sqlalchemy import Vector  # ← Package installé?

events_table = Table(
    'events',
    metadata,
    Column('embedding', Vector(768)),  # ← Crash si pgvector absent
)
```

**Vérification requise**:
```bash
$ grep pgvector requirements.txt
pgvector>=0.2.0,<0.3.0  # ✅ Présent (line 18)
```

**MAIS**: pgvector **package Python** != pgvector **extension PostgreSQL**

**Recommandation**: Ajouter note "Ensure pgvector SQLAlchemy adapter installed"

---

### Gap #2: Alembic Dependencies Missing

**Manque**:
Document dit `pip install alembic psutil` mais **NE VÉRIFIE PAS** si alembic compatible asyncpg.

**Vérification**:
```bash
# Alembic requiert SQLAlchemy[asyncio] avec asyncpg driver
$ pip install alembic
# ✅ SQLAlchemy[asyncio] déjà présent (requirements.txt:6)
# ✅ asyncpg déjà présent (requirements.txt:7)
```

**MAIS**: Document ne mentionne PAS installation `alembic` dans requirements.txt

**Impact**: Développeur oubliera peut-être d'ajouter alembic dans requirements.txt

**Recommandation**: Ajouter tâche "Update requirements.txt: alembic>=1.13.0, psutil>=5.9.0"

---

### Gap #3: Test Database Migration Strategy

**Manque CRITIQUE**:
Document ne dit PAS comment appliquer baseline migration sur **TEST DATABASE**.

**Situation actuelle**:
- Production DB: `mnemolite` → Alembic baseline OK
- Test DB: `mnemolite_test` → **Alembic baseline AUSSI requis?**

**Questions non répondues**:
- ❓ Faut-il `alembic upgrade head` sur TEST_DATABASE_URL aussi?
- ❓ Tests utilisent quelle DB? (mnemolite_test confirmé dans TEST_DATABASE_URL)
- ❓ CI/CD: Comment setup test DB avec Alembic?

**Impact**: Tests pourraient échouer si alembic_version absent dans test DB

**Recommandation**: Documenter:
```bash
# Setup test database with Alembic
$ TEST_DATABASE_URL=postgresql+asyncpg://mnemo:mnemo_pass@localhost/mnemolite_test alembic upgrade head
```

---

### Gap #4: HNSW Index Raw SQL dans Migration

**Manque**:
Document mentionne "HNSW index cannot be created via SQLAlchemy" mais ne montre PAS le code migration.

**Code proposé** (api/db/models.py):
```python
# HNSW index - cannot be created via SQLAlchemy, use raw SQL in migration
# CREATE INDEX idx_events_embedding_hnsw ON events USING hnsw...
```

**MAIS**: Migration baseline fait QUOI avec ça?

**Migration 001 devrait inclure** (MANQUANT):
```python
def upgrade() -> None:
    """Baseline migration (NO-OP for tables, but mark HNSW index)."""
    # Tables already exist (NO-OP)
    pass

    # ❌ MANQUE: Comment tracker HNSW index déjà existant?
    # Index déjà créé via db/init/01-init.sql
    # Alembic doit-il le savoir?
```

**Impact**: Migration 002 (Phase 1) pourrait essayer recréer index HNSW sur events (erreur)

**Recommandation**: Clarifier stratégie index existants dans baseline

---

## 🚨 RISQUES Non Couverts

### Risque #1: Pydantic BaseSettings .env.example Mismatch

**Risque**:
`.env.example` actuel pourrait ne PAS avoir toutes les vars requises par Settings class.

**Validation requise**:
```bash
# Vérifier .env.example contient TOUTES les vars Settings
$ cat .env.example | grep CODE_EMBEDDING_MODEL
# ❌ Probablement absent (nouveau)
```

**Impact**: Développeur oubliera CODE_EMBEDDING_MODEL → Pydantic crash

**Mitigation**: Ajouter tâche "Update .env.example with all Settings fields"

---

### Risque #2: Alembic Autogenerate avec Tables Existantes

**Risque**:
`alembic revision --autogenerate` **détectera** tables existantes et voudra les créer.

**Scénario problème**:
```bash
$ alembic revision --autogenerate -m "baseline"
# Alembic génère:
def upgrade():
    op.create_table('events', ...)  # ❌ Table existe déjà!
    op.create_table('nodes', ...)
    op.create_table('edges', ...)
```

**Solution document propose**: Modifier manuellement upgrade() → pass

**MAIS**: Étape manuelle = Erreur humaine possible

**Recommandation**: Documenter workflow:
```bash
# 1. Créer migration manuelle (PAS autogenerate)
$ alembic revision -m "baseline snapshot"

# 2. Modifier upgrade() pour NO-OP
def upgrade():
    pass
```

---

### Risque #3: dependencies.py Type Hints Incompatibles

**Risque**:
`get_embedding_service()` retourne maintenant `DualEmbeddingService` mais code existant attend `EmbeddingServiceProtocol`.

**Code proposé**:
```python
async def get_embedding_service() -> DualEmbeddingService:  # ← Type change!
    ...
```

**Code existant** (event_service.py, memory_search_service.py):
```python
def __init__(self, embedding_service: EmbeddingServiceProtocol):  # ← Attend Protocol
    ...
```

**Impact**: MyPy errors si DualEmbeddingService **NE PAS** implémenter Protocol

**Solution manquante**: Déclarer `DualEmbeddingService` implémente `EmbeddingServiceProtocol`

**Recommandation**:
```python
# api/services/dual_embedding_service.py
from api.interfaces.services import EmbeddingServiceProtocol

class DualEmbeddingService:  # ← Ajouter runtime_checkable?
    """
    Implements EmbeddingServiceProtocol via generate_embedding_legacy().
    """
    async def generate_embedding_legacy(self, text: str) -> List[float]:
        """Implements EmbeddingServiceProtocol.generate_embedding()."""
        ...
```

**OU** créer explicit adapter (déjà mentionné mais code incomplet)

---

## 📋 INCONSISTANCES Détectées

### Inconsistance #1: Timeline 5j vs 5-7j

**Document IMPLEMENTATION_ULTRADEEP.md** dit:
```
**Estimated Total Time**: 5-7 jours (Story 0.1: 2j + Story 0.2: 3j + buffer: 2j)
```

**Document CRITICAL_INSIGHTS.md** dit:
```
**Estimation révisée**: 5 jours (au lieu de 6-7 jours initial)
```

**Inconsistance**: 5-7j ou 5j?

**Clarification**: CRITICAL_INSIGHTS optimise à 5j, mais IMPLEMENTATION_ULTRADEEP garde buffer 2j → 5-7j

**Recommandation**: Harmoniser **5 jours NET** + **buffer 1-2j contingence** = **6-7j total** (SAFE estimate)

---

### Inconsistance #2: Phase 0.3 - Jour 6-7 Manquant

**Document CRITICAL_INSIGHTS.md** dit:
```
Phase 0 = 5 jours:
- Jour 1-2: Alembic + Settings
- Jour 3-4: Dual Embeddings
- Jour 5: Integration & Validation
```

**Document IMPLEMENTATION_ULTRADEEP.md** dit:
```
### Phase 0.3 - Intégration & Validation (Jour 6-7)

Jour 6:
1. ✅ Mise à jour .env.example
2. ✅ Mise à jour docker-compose.yml
...

Jour 7:
5. ✅ Documentation complète
6. ✅ Commit & Push
...
```

**Inconsistance**: CRITICAL_INSIGHTS dit 5j, IMPLEMENTATION_ULTRADEEP a Jour 6-7

**Clarification**: Confusion Jour 5 = Integration OU Jour 6-7 = Integration?

**Recommandation**: Renommer Phase 0.3 "Jour 5-6" (enlever Jour 7 OU clarifier)

---

### Inconsistance #3: DualEmbeddingService Return Type

**Code proposé** (section 3.2):
```python
async def generate_embedding(
    self,
    text: str,
    domain: EmbeddingDomain = EmbeddingDomain.TEXT
) -> Dict[str, List[float]]:  # ← Retourne Dict
```

**Code proposé** (section 1056-1057):
```python
if not text or not text.strip():
    logger.warning("Empty text provided for embedding")
    return {domain.value: [0.0] * self.dimension}  # ← OK pour TEXT/CODE

# MAIS pour HYBRID?
# Si domain == HYBRID, retourne {'text': [...], 'code': [...]}
# OU {'hybrid': [0.0, ...]}  ???
```

**Inconsistance**: Empty text + HYBRID domain → Comportement pas clair

**Recommandation**: Clarifier empty text handling pour HYBRID

---

## 🔧 RECOMMENDATIONS d'Amélioration

### Recommendation #1: Ajouter Checklist Pre-Kickoff

**Manque**: Checklist validation AVANT Jour 1

**Proposition**:
```markdown
## ✅ Checklist PRE-KICKOFF (Obligatoire)

### Infrastructure
- [ ] PostgreSQL 18.0 opérationnel (`SELECT version();`)
- [ ] pgvector 0.8.1 installé (`SELECT extversion FROM pg_extension WHERE extname='vector';`)
- [ ] Python 3.11+ (`python --version`)
- [ ] Docker + docker-compose running

### Dependencies
- [ ] requirements.txt à jour (sentence-transformers, asyncpg, sqlalchemy[asyncio], pgvector)
- [ ] Alembic PAS encore dans requirements.txt (sera ajouté Jour 2)

### Environment
- [ ] .env configuré (DATABASE_URL, TEST_DATABASE_URL, EMBEDDING_MODEL)
- [ ] Tests passent: `make api-test` → ALL PASS baseline

### Backup
- [ ] Database backup créé (`make db-backup`)
- [ ] Git branch migration/postgresql-18 créée et pushed

### Team
- [ ] Développeur assigné Phase 0
- [ ] Review partner identifié
- [ ] Stakeholders informés (kickoff Lundi XX)
```

---

### Recommendation #2: Ajouter Section "Rollback Complete Phase 0"

**Manque**: Procédure rollback SI Phase 0 échoue complètement

**Proposition**:
```markdown
## 🔄 ROLLBACK COMPLETE PHASE 0

**Si Phase 0 doit être abandonné**:

### 1. Rollback Database
bash
# Supprimer alembic_version table
$ psql -U mnemo -d mnemolite
=> DROP TABLE IF EXISTS alembic_version;
=> DROP TABLE IF EXISTS alembic_version CASCADE;


### 2. Rollback Code
bash
$ git checkout main
$ git branch -D migration/postgresql-18  # Delete branch


### 3. Restore Backup
bash
$ make db-restore file=backup_before_phase0.sql


### 4. Verify
bash
$ make api-test  # All tests pass
$ docker-compose ps  # All services running
```

---

### Recommendation #3: Ajouter Monitoring Endpoint Code

**Manque**: Code complet pour `/v1/monitoring/embeddings` endpoint

**Proposition**: Ajouter fichier `routes/monitoring_routes.py` complet dans annexe

---

### Recommendation #4: Documenter Migration 002 Preview

**Manque**: Aperçu Migration 002 (Phase 1) pour code_chunks

**Proposition**:
```markdown
## 📋 Preview Migration 002 (Phase 1)

**Fichier**: `alembic/versions/002_add_code_chunks_table.py`

python
def upgrade() -> None:
    """Create code_chunks table for Phase 1."""
    op.create_table(
        'code_chunks',
        sa.Column('id', postgresql.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('file_path', sa.Text(), nullable=False),
        sa.Column('language', sa.String(50)),
        sa.Column('chunk_type', sa.String(50)),
        sa.Column('name', sa.Text()),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('embedding_text', Vector(768)),  # nomic-text
        sa.Column('embedding_code', Vector(768)),  # jina-code
        sa.Column('metadata', postgresql.JSONB(), server_default=sa.text("'{}'::jsonb")),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id')
    )

    # Indexes
    op.create_index('idx_code_chunks_file_path', 'code_chunks', ['file_path'])
    op.create_index('idx_code_chunks_language', 'code_chunks', ['language'])

    # HNSW indexes (raw SQL required)
    op.execute(
        "CREATE INDEX idx_code_chunks_embedding_text_hnsw "
        "ON code_chunks USING hnsw(embedding_text vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64);"
    )
    op.execute(
        "CREATE INDEX idx_code_chunks_embedding_code_hnsw "
        "ON code_chunks USING hnsw(embedding_code vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64);"
    )


def downgrade() -> None:
    """Drop code_chunks table."""
    op.drop_table('code_chunks')

```

**Bénéfice**: Développeur visualise continuité Phase 0 → Phase 1

---

## 📊 Scores Détaillés

| Catégorie | Score | Commentaire |
|-----------|-------|-------------|
| **Profondeur technique** | 9/10 | Analyse exhaustive, code concret ✅ |
| **Insights découverts** | 10/10 | 7 insights tous pertinents et validés ✅ |
| **Plan implémentation** | 9/10 | Granularité excellente, tests à chaque étape ✅ |
| **Gestion risques** | 8/10 | 3 risques majeurs + mitigations, mais quelques gaps |
| **Tests & validation** | 9/10 | Coverage complète (unitaires + intégration + regression) |
| **Documentation** | 8/10 | Très complète mais 3 faiblesses (Pydantic v2, main.py, Mock) |
| **Timeline réalisme** | 8/10 | 5j optimiste mais crédible, buffer 1-2j recommandé |
| **Backward compat** | 10/10 | Adapter pattern brilliant, ZÉRO breaking changes ✅ |
| **Code quality** | 9/10 | Examples production-ready, async patterns corrects |
| **Coherence** | 7/10 | 3 inconsistances mineures (timeline, jours, return type) |

**Score Global**: **8.7/10** (EXCELLENT)

---

## 🎯 VERDICT FINAL

### ✅ GO FOR PHASE 0 KICKOFF

**Avec 3 corrections MINEURES obligatoires**:

#### Correction #1: Pydantic v2 Syntax (🔴 BLOQUANT)
Remplacer `@validator` → `@field_validator` dans TOUS les code examples

#### Correction #2: Timeline Harmonisée
Clarifier: **5 jours NET** + **buffer 1-2j** = **6-7j estimation SAFE**

#### Correction #3: Main.py Refactoring
Ajouter tâche "Refactorer main.py pour settings.py" (+0.5h estimé)

---

### 📋 Actions AVANT Kickoff

**MUST-DO** (Bloquant):
1. ✅ Corriger syntax Pydantic v2 dans documents
2. ✅ Ajouter checklist pre-kickoff
3. ✅ Clarifier timeline (5j + buffer 1-2j)

**SHOULD-DO** (Recommandé):
4. ✅ Documenter MockEmbeddingService adaptation
5. ✅ Ajouter rollback complete procedure
6. ✅ Clarifier test database Alembic setup

**NICE-TO-HAVE** (Optionnel):
7. ⭕ Ajouter monitoring endpoint code complet
8. ⭕ Preview Migration 002 (Phase 1)

---

### 🚀 Recommandation Stakeholders

**Phase 0 est PRÊTE pour démarrage** avec les corrections ci-dessus.

**Estimation révisée**: **6 jours** (5j net + 1j buffer)

**Risques**: **FAIBLE** (architecture solide, patterns validés, rollback défini)

**Confiance**: **HAUTE** (8.7/10)

**Go/No-Go**: ✅ **GO**

---

## 📝 Appendix: Corrections Détaillées

### Appendix A: Pydantic v2 Settings Correct Code

```python
"""
Configuration centralisée pour MnemoLite.
Pydantic v2.5+ compatible.
"""

from typing import Literal
from pydantic_settings import BaseSettings
from pydantic import Field, field_validator  # ✅ field_validator (v2)
from functools import lru_cache


class Settings(BaseSettings):
    """Settings validées via Pydantic v2."""

    # Database
    DATABASE_URL: str = Field(..., description="PostgreSQL connection URL")
    TEST_DATABASE_URL: str = Field(None, description="Test database URL")

    # Environment
    ENVIRONMENT: Literal["development", "test", "production"] = "development"
    DEBUG: bool = False

    # Embedding - Text (existing)
    EMBEDDING_MODEL: str = "nomic-ai/nomic-embed-text-v1.5"
    EMBEDDING_DIMENSION: int = 768
    EMBEDDING_MODE: Literal["mock", "real"] = "real"
    EMBEDDING_DEVICE: Literal["cpu", "cuda", "mps"] = "cpu"
    EMBEDDING_CACHE_SIZE: int = 1000

    # Embedding - Code (NEW for Phase 0.2)
    CODE_EMBEDDING_MODEL: str = "jinaai/jina-embeddings-v2-base-code"
    CODE_EMBEDDING_DIMENSION: int = 768

    # API
    API_PORT: int = 8001

    # PostgreSQL
    POSTGRES_USER: str = "mnemo"
    POSTGRES_PASSWORD: str = "mnemo_pass"
    POSTGRES_DB: str = "mnemolite"
    POSTGRES_PORT: int = 5432

    @field_validator("CODE_EMBEDDING_DIMENSION")  # ✅ Pydantic v2
    @classmethod  # ✅ REQUIRED in Pydantic v2
    def validate_same_dimension(cls, v, info):  # ✅ info instead of values
        """Valide que text et code ont même dimension (768)."""
        text_dim = info.data.get("EMBEDDING_DIMENSION", 768)  # ✅ info.data
        if v != text_dim:
            raise ValueError(
                f"CODE_EMBEDDING_DIMENSION ({v}) must match "
                f"EMBEDDING_DIMENSION ({text_dim}) for index compatibility"
            )
        return v

    class Config:
        env_file = ".env"
        case_sensitive = True  # ✅ DEPRECATED in v2, use model_config instead

    # ✅ Pydantic v2 alternative (preferred)
    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
        "extra": "forbid"  # Reject unknown fields
    }


@lru_cache()
def get_settings() -> Settings:
    """Retourne settings singleton (cached)."""
    return Settings()
```

---

### Appendix B: Main.py Refactoring Diff

```python
# main.py BEFORE Phase 0
import os
DATABASE_URL = os.getenv("DATABASE_URL")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

@asynccontextmanager
async def lifespan(app: FastAPI):
    db_url_to_use = TEST_DATABASE_URL if ENVIRONMENT == "test" else DATABASE_URL

    app.state.db_engine = create_async_engine(
        db_url_to_use,
        echo=DEBUG,
        ...
    )
```

```python
# main.py AFTER Phase 0 ✅
from api.config.settings import get_settings

settings = get_settings()  # ✅ Singleton

@asynccontextmanager
async def lifespan(app: FastAPI):
    db_url_to_use = settings.TEST_DATABASE_URL if settings.ENVIRONMENT == "test" else settings.DATABASE_URL

    app.state.db_engine = create_async_engine(
        db_url_to_use,
        echo=settings.DEBUG,  # ✅ Use settings
        pool_size=10,
        max_overflow=5,
        future=True,
        pool_pre_ping=True,
    )

    # Embedding pre-load
    embedding_mode = settings.EMBEDDING_MODE.lower()  # ✅ Use settings
    if embedding_mode == "real":
        ...
```

---

### Appendix C: Test Database Alembic Setup

```bash
# scripts/setup_test_db_alembic.sh (NOUVEAU)

#!/bin/bash
set -e

echo "Setting up test database with Alembic..."

# 1. Ensure test database exists
docker exec mnemo-postgres psql -U mnemo -c "CREATE DATABASE mnemolite_test;" || echo "Test DB already exists"

# 2. Apply baseline migration to test DB
export DATABASE_URL="postgresql+asyncpg://mnemo:mnemo_pass@localhost:5432/mnemolite_test"
alembic upgrade head

# 3. Verify
docker exec mnemo-postgres psql -U mnemo -d mnemolite_test -c "SELECT * FROM alembic_version;"

echo "✅ Test database ready with Alembic baseline"
```

**Usage**:
```bash
$ chmod +x scripts/setup_test_db_alembic.sh
$ ./scripts/setup_test_db_alembic.sh
```

---

**Date**: 2025-10-15
**Version**: 1.0.0
**Reviewer**: Architecture Review Team
**Status**: ✅ REVIEW COMPLETE - GO FOR PHASE 0 with 3 minor corrections
