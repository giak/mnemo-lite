# 🛡️ EPIC-42: Enterprise-Grade Secret Stripping & PII Redaction

> **Statut** : 📝 Spécification  
> **Priorité** : 🔴 Critique (Sécurité)  
> **Inspiration** : AgentMemory `privacy.ts` — étendu pour l'architecture dual-pillar de MnemoLite  
> **Effort estimé** : ~16h (5 stories)  
> **Date** : Avril 2025  

---

## Table des Matières

1. [Contexte & Problème](#1-contexte--problème)
2. [Vue d'Ensemble de l'Epic](#2-vue-densemble-de-lepic)
3. [Stories Détaillées](#3-stories-détaillées)
4. [Design Technique](#4-design-technique)
5. [Catalogue de Patterns](#5-catalogue-de-patterns)
6. [Plan de Migration](#6-plan-de-migration)
7. [Stratégie de Test](#7-stratégie-de-test)
8. [Considérations de Sécurité](#8-considérations-de-sécurité)
9. [Budget Performance](#9-budget-performance)
10. [Configuration & Déploiement](#10-configuration--déploiement)
11. [Questions Ouvertes](#11-questions-ouvertes)

---

## 1. Contexte & Problème

### Le problème actuel

MnemoLite stocke du texte et du code **sans aucun filtrage de sécurité**. Tout ce qui passe par `write_memory`, `update_memory`, l'indexation de code, ou l'import de conversations arrive tel quel dans PostgreSQL — en texte clair, dans les embeddings vectoriels, et dans les résultats de recherche.

**Risques concrets :**

| Vecteur | Exemple | Conséquence |
|---------|---------|-------------|
| `write_memory` | "La DB prod est à `postgresql://admin:S3cret!@db.prod:5432`" | Credential en clair dans PG + embedding vectoriel contaminé |
| `update_memory` | Mise à jour avec un token GitHub `ghp_xxxx` | Token persistant, searchable par tout client MCP |
| `index_project` | Fichier `.env` indexé avec `OPENAI_API_KEY=sk-proj-...` | Clé API dans `code_chunks`, searchable via `search_code` |
| Conversation import | Log contenant `Bearer eyJhbGci...` | JWT en clair, extractible via search |
| Code indexing | Hardcoded `AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/...` | Secret AWS dans le graphe de code |

### Ce qu'AgentMemory fait (baseline)

AgentMemory implémente `stripPrivateData()` dans `src/functions/privacy.ts` :

1. **Tags privés** : `<private>...</private>` → `[REDACTED]`
2. **Regex patterns** (`SECRET_PATTERN_SOURCES`) :
   - Cloud/SaaS : AWS (`AKIA*`), Google Cloud (`AIza*`), DigitalOcean (`dop_v1_*`)
   - AI Providers : OpenAI (`sk-proj-*`, `sk-*`), Anthropic (`sk-ant-*`)
   - DevEx : GitHub (`ghp_*`, `github_pat_*`), NPM (`npm_*`), GitLab (`glpat-*`), Slack (`xoxb-*`)
   - Auth : Bearer tokens, JWT (`eyJ...`)
   - Generic : `api_key=...`, `secret=...` (20+ chars)

**Limites d'AgentMemory :**
- ❌ Pas de PII (emails, téléphones, SSN, IBAN)
- ❌ Pas de patterns internationaux (FR/EU)
- ❌ Pas d'audit trail
- ❌ Pas de configuration granulaire
- ❌ Appliqué dans `observe.ts` mais **PAS** dans `remember.ts` (incohérent)
- ❌ Pas de nettoyage rétroactif
- ❌ Pas d'intégration code indexing (n'a pas de code intelligence)

### Ce que MnemoLite doit faire en plus

MnemoLite a **deux piliers** qu'AgentMemory n'a pas, ce qui élargit le périmètre :

1. **Code Intelligence** — Les chunks de code (`.env`, configs, hardcoded secrets) doivent aussi être nettoyés
2. **Embeddings vectoriels** — Les secrets ne doivent pas être encodés numériquement dans l'espace vectoriel
3. **Contexte FR/EU** — NIR, IBAN, téléphones français doivent être filtrés
4. **Observabilité** — Audit trail structlog + métriques OpenTelemetry
5. **Rétroactivité** — Les données existantes doivent être nettoyées

---

## 2. Vue d'Ensemble de l'Epic

### Description

Implémenter un pipeline de sanitisation robuste, performant et configurable via un `PrivacyService` central. Ce service intercepte les données **avant** l'embedding et le stockage, sur tous les points d'entrée (mémoire, code, conversations), en rédigeant irréversiblement les secrets tout en laissant une trace d'audit.

### Business Value

| Axe | Impact |
|-----|--------|
| **Sécurité** | Empêche la fuite de credentials dans la DB, les embeddings, et les résultats de recherche |
| **Conformité GDPR** | Filtre les PII (NIR, IBAN, emails) avant stockage — obligation légale en EU |
| **Confiance utilisateur** | L'utilisateur peut coller des logs librement sans craindre une persistance de secrets |
| **Safe Vector Space** | Les embeddings ne contiennent pas de données sensibles numériquement encodées |
| **Safe LLM Context** | Le contexte envoyé aux LLMs (consolidation, query understanding) est sanitized |

### Architecture cible

```
                    ┌─────────────────────────────────────┐
                    │         PrivacyService              │
                    │  (singleton, pre-compiled regex)    │
                    │                                     │
                    │  sanitize(text) → SanitizationResult│
                    │    ├── clean_text: str              │
                    │    └── metadata: RedactionMetadata   │
                    │         ├── redacted: bool           │
                    │         └── counts_by_type: Dict     │
                    └──────────┬──────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                 ▼
     ┌────────────┐  ┌──────────────┐  ┌────────────────┐
     │ Pilier B   │  │  Pilier A    │  │ Workers        │
     │ Mémoire    │  │  Code Intel  │  │ Conversations  │
     │            │  │              │  │                │
     │ write_mem  │  │ chunk_source │  │ import_conv    │
     │ update_mem │  │ .env files   │  │ conversation_  │
     │ embed_src  │  │ config files │  │ worker.py      │
     └────────────┘  └──────────────┘  └────────────────┘
```

---

## 3. Stories Détaillées

---

### 📝 Story 42.1 : Core Privacy Service & Regex Engine

**En tant qu'** architecte système,  
**Je veux** un moteur de regex performant et configurable,  
**Afin que** les secrets et PII soient détectés et rédigés de façon fiable sans impact sur les latences.

#### Critères d'Acceptation

- [ ] Créer `api/services/privacy_service.py` avec la classe `PrivacyService`
- [ ] Pré-compiler tous les regex au démarrage (pas de compilation à la volée)
- [ ] Supporter les **patterns baseline AgentMemory** :
  - Cloud/SaaS : AWS, Google Cloud, Azure, DigitalOcean
  - AI Providers : OpenAI, Anthropic
  - DevEx : GitHub, NPM, GitLab, Slack
  - Auth : Bearer tokens, JWT
  - Generic : `api_key=`, `password=`, `secret:`, connection strings
- [ ] Supporter les **tags explicites** : `<private>...</private>` → `[REDACTED: PRIVATE_TAG]`
- [ ] Supporter les **patterns internationaux FR/EU** :
  - Téléphones français (`+33 6...`, `06...`)
  - NIR / Carte Vitale (numéro de sécurité sociale)
  - IBAN (format FR/EU)
  - Emails
- [ ] Remplacement par tokens contextuels : `[REDACTED: OPENAI_KEY]`, `[REDACTED: FR_NIR]`, etc.
- [ ] Retourner un `SanitizationResult` avec `clean_text` + `RedactionMetadata` (counts par type, jamais les valeurs brutes)
- [ ] Configuration granulaire : pouvoir désactiver des catégories de patterns via env vars ou config

#### Détails Techniques

```python
class RedactionMetadata(BaseModel):
    redacted: bool
    counts_by_type: Dict[str, int]  # {"OPENAI_KEY": 1, "FR_PHONE": 2}
    # JAMAIS de raw values

class SanitizationResult(BaseModel):
    clean_text: str
    metadata: RedactionMetadata

class PrivacyService:
    def __init__(self, config: Optional[Dict] = None):
        self.enabled = True
        self._compiled: Dict[str, re.Pattern] = {}
        self._load_config(config)
        self._compile_all()
    
    def sanitize(self, text: str) -> SanitizationResult:
        """Sanitize text, replace secrets with [REDACTED: TYPE] tokens."""
        ...
    
    def sanitize_batch(self, texts: List[str]) -> List[SanitizationResult]:
        """Batch sanitize for code chunking (multiple chunks)."""
        ...
```

#### Effort : ~4h

---

### 📝 Story 42.2 : Intégration Pipeline Mémoire Sémantique

**En tant qu'** utilisateur faisant confiance à l'agent avec du contexte conversationnel,  
**Je veux** que mes mémoires soient sanitisées avant d'être sauvées ou embedded,  
**Afin que** je puisse coller librement des logs ou des détails d'environnement sans craindre de fuites persistantes.

#### Critères d'Acceptation

- [ ] Intégrer `PrivacyService` dans `WriteMemoryTool.execute()` AVANT la création du `MemoryCreate`
- [ ] Intégrer `PrivacyService` dans `UpdateMemoryTool.execute()` AVANT la création du `MemoryUpdate`
- [ ] Sanitiser les champs : `title`, `content`, `embedding_source`
- [ ] Sanitiser AVANT l'extraction d'entités (GLiNER via Redis Streams) — le worker ne doit pas voir les secrets
- [ ] Logger les rédactions via `structlog` (type + count, jamais les valeurs) :
  ```python
  logger.warning(
      "security.data_sanitized",
      memory_id=memory.id,
      title_redactions=title_res.metadata.counts_by_type,
      content_redactions=content_res.metadata.counts_by_type,
  )
  ```
- [ ] Si le PrivacyService est indisponible (circuit breaker), le write doit continuer avec un warning (graceful degradation)
- [ ] Les résultats de `search_memory` et `read_memory` retournent le texte déjà sanitisé (pas besoin de double-sanitiser en lecture)

#### Flux modifié

```
write_memory(title, content, ...) 
  → PrivacyService.sanitize(title)     ← NOUVEAU
  → PrivacyService.sanitize(content)   ← NOUVEAU  
  → PrivacyService.sanitize(embedding_source)  ← NOUVEAU
  → MemoryCreate Pydantic validation
  → MemoryRepository.create()
  → Entity extraction (async, reçoit texte sanitisé)
```

```
update_memory(id, title?, content?, ...)
  → PrivacyService.sanitize(title)     ← NOUVEAU (si fourni)
  → PrivacyService.sanitize(content)   ← NOUVEAU (si fourni)
  → MemoryUpdate Pydantic validation
  → MemoryRepository.update()
  → Embedding regeneration (sur texte sanitisé)
```

#### Effort : ~3h

---

### 📝 Story 42.3 : Intégration Code Intelligence Indexing

**En tant que** développeur indexant des dépôts de code,  
**Je veux** que le stripping automatique s'applique pendant l'indexation de code,  
**Afin que** les URIs de base de données hardcodées, les fichiers `.env`, et les clés API legacy ne finissent pas dans le CodeGraphe ou l'index vectoriel.

#### Critères d'Acceptation

- [ ] Intégrer `PrivacyService` dans `CodeChunkingService` ou `CodeIndexingService` (étape 2/3 du pipeline)
- [ ] Quand un chunk de code est lu, il doit être sanitisé avant d'être passé à `DualEmbeddingService` ou `GraphConstructionService`
- [ ] Ajouter un toggle de configuration : `MCP_CODE_SANITIZE=true` (défaut : true) — permet de bypasser dans les environnements trusted/offline
- [ ] Les fichiers `.env`, `settings.py`, `config.yaml`, etc. doivent être spécialement traités (déjà détectés par `FileClassificationService` comme "config")
- [ ] Les noms de symboles (name_path) ne doivent PAS être sanitisés — seule la source_code du chunk l'est
- [ ] La sanitisatoin doit se faire APRÈS le chunking (pour préserver la structure AST) mais AVANT l'embedding

#### Flux modifié (Code Indexing 7 étapes)

```
1. Language Detection
2. AST Chunking                    → chunk.source_code
3. PrivacyService.sanitize(source) ← NOUVEAU (sur source_code uniquement)
4. Metadata Extraction             → sur texte sanitisé
5. LSP Type Enrichment            → sur texte sanitisé
6. Dual Embedding                  → sur texte sanitisé
7. Graph Construction              → sur texte sanitisé
```

#### Cas particulier : connection strings dans le code

```python
# AVANT sanitisation
DATABASE_URL = "postgresql://admin:S3cretPass@db.prod.example.com:5432/mydb"

# APRÈS sanitisation  
DATABASE_URL = "postgresql://admin:[REDACTED: GENERIC_SECRET]@db.prod.example.com:5432/mydb"
```

Le pattern de connection string doit matcher les credentials intégrés dans les URIs.

#### Effort : ~3h

---

### 📝 Story 42.4 : Observabilité, Configuration & Audit Trail

**En tant qu'** ingénieur SecOps,  
**Je veux** suivre les événements de rédaction et configurer les patterns actifs,  
**Afin que** je puisse surveiller les risques de sécurité et désactiver les patterns causant des faux positifs.

#### Critères d'Acceptation

- [ ] **Configuration par env vars** (minimal, pas de fichier YAML requis) :
  ```
  MCP_PRIVACY_ENABLED=true                    # Master switch
  MCP_PRIVACY_PATTERNS_CLOUD=true             # AWS, GCP, Azure, DO
  MCP_PRIVACY_PATTERNS_AI_PROVIDERS=true      # OpenAI, Anthropic
  MCP_PRIVACY_PATTERNS_DEVEX=true             # GitHub, NPM, GitLab, Slack
  MCP_PRIVACY_PATTERNS_AUTH=true              # Bearer, JWT
  MCP_PRIVACY_PATTERNS_GENERIC=true           # api_key=, password=, secret=
  MCP_PRIVACY_PATTERNS_PII=true               # Email, phone, SSN, IBAN
  MCP_PRIVACY_PATTERNS_PRIVATE_TAGS=true      # <private>...</private>
  MCP_PRIVACY_PATTERNS_CONNECTION_STRINGS=true # postgresql://user:pass@host
  MCP_CODE_SANITIZE=true                      # Code indexing toggle
  MCP_PRIVACY_MAX_SANITIZE_LENGTH=1000000     # 1MB max text length
  ```
- [ ] **Patterns custom** via env var : `MCP_PRIVACY_CUSTOM_PATTERNS=openai_org_[a-z0-9]{24};my_token_[a-z]{32}`
- [ ] **Métriques OpenTelemetry** :
  - Counter : `mnemo.privacy.redactions.count` (groupé par `type` : OPENAI_KEY, AWS_KEY, etc.)
  - Counter : `mnemo.privacy.sanitize.calls` (total calls)
  - Histogram : `mnemo.privacy.sanitize.duration_ms` (temps de sanitisatoin)
- [ ] **Audit logging structlog** :
  ```json
  {
    "event": "security.data_sanitized",
    "memory_id": "abc-123",
    "title_redactions": {"OPENAI_KEY": 1},
    "content_redactions": {"AWS_KEY": 2, "FR_PHONE": 1},
    "total_redactions": 4,
    "sanitize_duration_ms": 1.2
  }
  ```
- [ ] **JAMAIS** de logging des valeurs brutes matchées — uniquement le type et le count
- [ ] **Health check** : `get_memory_health` doit inclure `privacy_service: enabled/patterns_count`

#### Effort : ~3h

---

### 📝 Story 42.5 : Migration Rétroactive des Données Existantes

**En tant qu'** administrateur de base de données,  
**Je veux** un outil pour scanner les enregistrements existants et appliquer les nouveaux patterns de privacy,  
**Afin que** les secrets legacy actuellement résidant dans la base de données soient purgés.

#### Critères d'Acceptation

- [ ] Créer un script async `scripts/clean_legacy_secrets.py`
- [ ] Traiter les tables : `memories` et `code_chunks` en batches (100 rows/batch)
- [ ] Pour chaque row : exécuter `PrivacyService.sanitize()` sur `title`/`content` (mémoires) ou `source_code` (chunks)
- [ ] Si des changements sont détectés :
  - Mettre à jour le texte dans la DB
  - Programmer la régénération de l'embedding (via Redis Stream `embedding:regenerate` ou flag)
- [ ] Supporter `--dry-run` : rapporte ce qui serait strippé sans modifier la DB
- [ ] Supporter `--table=memories|code_chunks|all` (défaut : all)
- [ ] Supporter `--batch-size=N` (défaut : 100)
- [ ] Supporter `--project-id=UUID` pour cibler un projet spécifique
- [ ] Générer un rapport de synthèse :
  ```
  === Legacy Secret Cleanup Report ===
  Table: memories
    Scanned: 1247
    Cleaned: 23
    Redaction types: {OPENAI_KEY: 8, AWS_KEY: 5, GENERIC_SECRET: 7, FR_PHONE: 3}
    Embeddings queued for regeneration: 23
  Table: code_chunks
    Scanned: 8456
    Cleaned: 142
    Redaction types: {CONNECTION_STRING: 67, GENERIC_SECRET: 43, OPENAI_KEY: 32}
    Embeddings queued for regeneration: 142
  ```

#### Attention : Impact sur les embeddings existants

Quand le texte d'une mémoire ou d'un chunk est modifié, l'embedding existant ne correspond plus au texte. Deux options :

| Option | Avantage | Inconvénient |
|--------|----------|--------------|
| **A : Régénérer immédiatement** | Embeddings cohérents | Long (10-50s par embedding), bloque le script |
| **B : Invalider + régénérer async** | Rapide, non-bloquant | Embeddings incohérents temporairement (recherche dégradée) |

**Recommandation** : Option B — Invalider l'embedding (`SET embedding = NULL, embedding_half = NULL`) et pousser un message dans Redis Stream `embedding:regenerate` pour traitement async par le worker.

#### Effort : ~3h

---

## 4. Design Technique

### A. Architecture du Service

```python
# api/services/privacy_service.py

import re
import time
from typing import Dict, List, Optional, Tuple
from pydantic import BaseModel
import structlog
import os

logger = structlog.get_logger("privacy_service")


class RedactionMetadata(BaseModel):
    """Metadata about what was redacted — never contains raw values."""
    redacted: bool
    counts_by_type: Dict[str, int]


class SanitizationResult(BaseModel):
    """Result of sanitization: clean text + metadata."""
    clean_text: str
    metadata: RedactionMetadata


class PatternCategory:
    """Categories of patterns for granular enable/disable."""
    CLOUD = "cloud"
    AI_PROVIDERS = "ai_providers"
    DEVEX = "devex"
    AUTH = "auth"
    GENERIC = "generic"
    PII = "pii"
    PRIVATE_TAGS = "private_tags"
    CONNECTION_STRINGS = "connection_strings"


# Default pattern registry
DEFAULT_PATTERNS: Dict[str, Tuple[str, str]] = {
    # ─── Private Tags ─────────────────────────────────
    "PRIVATE_TAG": (
        r'<private>[\s\S]*?</private>',
        PatternCategory.PRIVATE_TAGS
    ),
    # ─── Cloud / SaaS ────────────────────────────────
    "AWS_ACCESS_KEY": (
        r'\b(AKIA[0-9A-Z]{16})\b',
        PatternCategory.CLOUD
    ),
    "AWS_SECRET_KEY": (
        r'\b(AWS_SECRET_ACCESS_KEY\s*=\s*["\']?([A-Za-z0-9/+=]{40})["\']?)\b',
        PatternCategory.CLOUD
    ),
    "GOOGLE_API_KEY": (
        r'\b(AIza[0-9A-Za-z\-_]{35})\b',
        PatternCategory.CLOUD
    ),
    "AZURE_KEY": (
        r'\b([a-zA-Z0-9]{34}==)\b',
        PatternCategory.CLOUD  # Simplified; refine in implementation
    ),
    "DIGITALOCEAN_TOKEN": (
        r'\b(dop_v1_[a-f0-9]{64})\b',
        PatternCategory.CLOUD
    ),
    # ─── AI Providers ────────────────────────────────
    "OPENAI_KEY": (
        r'\b(sk-proj-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9_-]{20,})\b',
        PatternCategory.AI_PROVIDERS
    ),
    "ANTHROPIC_KEY": (
        r'\b(sk-ant-[A-Za-z0-9_-]{20,})\b',
        PatternCategory.AI_PROVIDERS
    ),
    # ─── DevEx ───────────────────────────────────────
    "GITHUB_TOKEN": (
        r'\b(ghp_[A-Za-z0-9]{36}|gho_[A-Za-z0-9]{36}|ghu_[A-Za-z0-9]{36}|ghs_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{82})\b',
        PatternCategory.DEVEX
    ),
    "NPM_TOKEN": (
        r'\b(npm_[A-Za-z0-9]{36})\b',
        PatternCategory.DEVEX
    ),
    "GITLAB_TOKEN": (
        r'\b(glpat-[A-Za-z0-9\-]{20,})\b',
        PatternCategory.DEVEX
    ),
    "SLACK_TOKEN": (
        r'\b(xox[bposa]-[0-9]{10,13}-[0-9]{10,13}-[0-9a-zA-Z]{24,34})\b',
        PatternCategory.DEVEX
    ),
    # ─── Auth ────────────────────────────────────────
    "BEARER_TOKEN": (
        r'\bBearer\s+[A-Za-z0-9\-._~+/]+=*\b',
        PatternCategory.AUTH
    ),
    "JWT": (
        r'\b(eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})\b',
        PatternCategory.AUTH
    ),
    # ─── Generic Secrets ─────────────────────────────
    "GENERIC_KEY_VALUE": (
        r'\b(?:api[-_]?key|apikey|secret[-_]?key|access[-_]?token|auth[-_]?token|private[-_]?key)\s*[=:]\s*["\']?([A-Za-z0-9_\-]{20,})["\']?',
        PatternCategory.GENERIC
    ),
    "PASSWORD_VALUE": (
        r'\b(?:password|passwd|pwd)\s*[=:]\s*["\']?([^\s"\']{8,})["\']?',
        PatternCategory.GENERIC
    ),
    # ─── Connection Strings ────────────────────────────
    "CONNECTION_STRING": (
        r'(?:postgresql|mysql|mongodb|redis|amqp)://[^\s]+:[^\s]+@[^\s]+',
        PatternCategory.CONNECTION_STRINGS
    ),
    # ─── PII ─────────────────────────────────────────
    "EMAIL": (
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        PatternCategory.PII
    ),
    "FR_PHONE": (
        r'\b(?:(?:\+|00)33|0)\s*[1-9](?:[\s.-]*\d{2}){4}\b',
        PatternCategory.PII
    ),
    "FR_NIR": (
        r'\b[12]\s*\d{2}\s*(?:1[0-2]|0[1-9]|[235-9][0-9]|2[AB])\s*(?:0[1-9]|[1-8]\d|9[0-5]|2[AB])\s*\d{3}\s*\d{3}\s*\d{2}\b',
        PatternCategory.PII
    ),
    "IBAN": (
        r'\b[A-Z]{2}\d{2}\s?(?:\d{4}\s?){2,7}\d{1,4}\b',
        PatternCategory.PII
    ),
    "CREDIT_CARD": (
        r'\b(?:\d[ -]*?){13,19}\b',  # Simplified; refine with Luhn check
        PatternCategory.PII
    ),
}


class PrivacyService:
    """
    Enterprise-grade secret stripping & PII redaction service.
    
    Pre-compiles all regex patterns on startup for performance.
    Supports granular enable/disable per pattern category.
    Returns sanitized text with audit metadata (never raw values).
    """
    
    MAX_SANITIZE_LENGTH = 1_000_000  # 1MB — skip larger texts to avoid CPU lock
    
    def __init__(self, config: Optional[Dict] = None):
        self.enabled = self._get_config(config, "MCP_PRIVACY_ENABLED", True, bool)
        self._category_enabled: Dict[str, bool] = {}
        self._compiled: Dict[str, re.Pattern] = {}
        self._custom_patterns: Dict[str, re.Pattern] = {}
        
        if self.enabled:
            self._load_categories(config)
            self._compile_patterns()
            self._load_custom_patterns(config)
            logger.info(
                "privacy_service.initialized",
                enabled=True,
                patterns_count=len(self._compiled),
                categories={k: v for k, v in self._category_enabled.items()},
            )
        else:
            logger.info("privacy_service.disabled")
    
    def _get_config(self, config, env_key, default, type_func):
        """Get config from dict or env var."""
        if config and env_key in config:
            return type_func(config[env_key])
        return type_func(os.getenv(env_key, str(default)))
    
    def _load_categories(self, config):
        """Load which pattern categories are enabled."""
        for cat in [
            PatternCategory.CLOUD, PatternCategory.AI_PROVIDERS,
            PatternCategory.DEVEX, PatternCategory.AUTH,
            PatternCategory.GENERIC, PatternCategory.PII,
            PatternCategory.PRIVATE_TAGS, PatternCategory.CONNECTION_STRINGS,
        ]:
            env_key = f"MCP_PRIVACY_PATTERNS_{cat.upper()}"
            self._category_enabled[cat] = self._get_config(config, env_key, True, bool)
    
    def _compile_patterns(self):
        """Pre-compile all enabled patterns."""
        for name, (pattern_str, category) in DEFAULT_PATTERNS.items():
            if self._category_enabled.get(category, True):
                try:
                    self._compiled[name] = re.compile(pattern_str, re.IGNORECASE | re.DOTALL)
                except re.error as e:
                    logger.error("privacy_service.pattern_compile_error", name=name, error=str(e))
    
    def _load_custom_patterns(self, config):
        """Load custom patterns from env var MCP_PRIVACY_CUSTOM_PATTERNS."""
        custom_str = self._get_config(config, "MCP_PRIVACY_CUSTOM_PATTERNS", "", str)
        if not custom_str:
            return
        # Format: "pattern_name1=regex1;pattern_name2=regex2"
        for entry in custom_str.split(";"):
            if "=" in entry:
                name, pattern = entry.split("=", 1)
                try:
                    self._custom_patterns[name.strip()] = re.compile(pattern.strip(), re.IGNORECASE)
                    logger.info("privacy_service.custom_pattern_loaded", name=name.strip())
                except re.error as e:
                    logger.error("privacy_service.custom_pattern_error", name=name.strip(), error=str(e))
            else:
                # Simple pattern without name
                try:
                    self._custom_patterns[f"CUSTOM_{len(self._custom_patterns)}"] = re.compile(entry.strip(), re.IGNORECASE)
                except re.error:
                    pass
    
    def sanitize(self, text: str) -> SanitizationResult:
        """
        Sanitize text by replacing secrets/PII with [REDACTED: TYPE] tokens.
        
        Args:
            text: Input text to sanitize
            
        Returns:
            SanitizationResult with clean_text and redaction metadata
        """
        if not self.enabled or not text:
            return SanitizationResult(
                clean_text=text,
                metadata=RedactionMetadata(redacted=False, counts_by_type={})
            )
        
        # Skip excessively long texts
        if len(text) > self.MAX_SANITIZE_LENGTH:
            logger.warning(
                "privacy_service.text_too_long",
                length=len(text),
                max=self.MAX_SANITIZE_LENGTH,
            )
            return SanitizationResult(
                clean_text=text,
                metadata=RedactionMetadata(redacted=False, counts_by_type={"SKIPPED_LENGTH": 1})
            )
        
        start = time.time()
        clean_text = text
        counts: Dict[str, int] = {}
        
        # Apply all compiled patterns
        for p_type, pattern in self._compiled.items():
            matches = pattern.findall(clean_text)
            if matches:
                clean_text = pattern.sub(f"[REDACTED: {p_type}]", clean_text)
                counts[p_type] = len(matches) if isinstance(matches[0], str) else len(matches)
        
        # Apply custom patterns
        for p_type, pattern in self._custom_patterns.items():
            matches = pattern.findall(clean_text)
            if matches:
                clean_text = pattern.sub(f"[REDACTED: {p_type}]", clean_text)
                counts[p_type] = len(matches)
        
        elapsed_ms = (time.time() - start) * 1000
        
        result = SanitizationResult(
            clean_text=clean_text,
            metadata=RedactionMetadata(
                redacted=bool(counts),
                counts_by_type=counts
            )
        )
        
        if counts:
            logger.info(
                "privacy_service.redacted",
                total_redactions=sum(counts.values()),
                types=counts,
                duration_ms=round(elapsed_ms, 2),
            )
        
        return result
    
    def sanitize_batch(self, texts: List[str]) -> List[SanitizationResult]:
        """Batch sanitize for code chunking."""
        return [self.sanitize(t) for t in texts]
    
    @property
    def patterns_count(self) -> int:
        return len(self._compiled) + len(self._custom_patterns)
```

### B. Intégration dans WriteMemoryTool

```python
# Dans WriteMemoryTool.execute(), APRÈS les validations basiques,
# AVANT la création du MemoryCreate :

privacy_service = self._services.get("privacy_service")
if privacy_service:
    try:
        title_res = privacy_service.sanitize(title)
        content_res = privacy_service.sanitize(content)
        
        title = title_res.clean_text
        content = content_res.clean_text
        
        if title_res.metadata.redacted or content_res.metadata.redacted:
            logger.warning(
                "security.data_sanitized",
                tool="write_memory",
                title_redactions=title_res.metadata.counts_by_type,
                content_redactions=content_res.metadata.counts_by_type,
            )
        
        # Sanitize embedding_source if provided
        if embedding_source:
            es_res = privacy_service.sanitize(embedding_source)
            embedding_source = es_res.clean_text
            if es_res.metadata.redacted:
                logger.warning(
                    "security.embedding_source_sanitized",
                    redactions=es_res.metadata.counts_by_type,
                )
    except Exception as e:
        # Graceful degradation: continue without sanitization
        logger.error("privacy_service.failed", error=str(e), fallback="proceeding_without_sanitization")
```

### C. Intégration dans Conversation Worker

```python
# Dans workers/conversation_worker.py, avant d'envoyer le contenu
# à write_memory ou à l'API :

privacy_service = ...  # injected or imported
if privacy_service:
    for msg in messages:
        result = privacy_service.sanitize(msg.get("content", ""))
        msg["content"] = result.clean_text
        if result.metadata.redacted:
            logger.info("conversation_worker.sanitized", redactions=result.metadata.counts_by_type)
```

---

## 5. Catalogue de Patterns

### Patterns Complets

| ID | Catégorie | Pattern | Exemple matché | Token de remplacement |
|----|-----------|---------|----------------|----------------------|
| `PRIVATE_TAG` | private_tags | `<private>[\s\S]*?</private>` | `<private>my secret</private>` | `[REDACTED: PRIVATE_TAG]` |
| `AWS_ACCESS_KEY` | cloud | `AKIA[0-9A-Z]{16}` | `AKIAIOSFODNN7EXAMPLE` | `[REDACTED: AWS_ACCESS_KEY]` |
| `AWS_SECRET_KEY` | cloud | `AWS_SECRET_ACCESS_KEY=...` | `AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/...` | `[REDACTED: AWS_SECRET_KEY]` |
| `GOOGLE_API_KEY` | cloud | `AIza[0-9A-Za-z\-_]{35}` | `AIzaSyA...35chars` | `[REDACTED: GOOGLE_API_KEY]` |
| `DIGITALOCEAN_TOKEN` | cloud | `dop_v1_[a-f0-9]{64}` | `dop_v1_abc123...64hex` | `[REDACTED: DIGITALOCEAN_TOKEN]` |
| `OPENAI_KEY` | ai_providers | `sk-proj-[...]{20,}` or `sk-[...]{20,}` | `sk-proj-abc123...` | `[REDACTED: OPENAI_KEY]` |
| `ANTHROPIC_KEY` | ai_providers | `sk-ant-[...]{20,}` | `sk-ant-api03-...` | `[REDACTED: ANTHROPIC_KEY]` |
| `GITHUB_TOKEN` | devex | `ghp_...`, `gho_...`, `github_pat_...` | `ghp_abc123...36chars` | `[REDACTED: GITHUB_TOKEN]` |
| `NPM_TOKEN` | devex | `npm_[A-Za-z0-9]{36}` | `npm_abc123...36chars` | `[REDACTED: NPM_TOKEN]` |
| `GITLAB_TOKEN` | devex | `glpat-[...]{20,}` | `glpat-abc123...` | `[REDACTED: GITLAB_TOKEN]` |
| `SLACK_TOKEN` | devex | `xoxb-...-...-...` | `xoxb-1234567890-...` | `[REDACTED: SLACK_TOKEN]` |
| `BEARER_TOKEN` | auth | `Bearer [A-Za-z0-9\-._~+/]+=*` | `Bearer abc123token` | `[REDACTED: BEARER_TOKEN]` |
| `JWT` | auth | `eyJ[...].[...].[...]` | `eyJhbGciOiJIUzI1...` | `[REDACTED: JWT]` |
| `GENERIC_KEY_VALUE` | generic | `api_key=...`, `secret_key=...` (20+ chars) | `api_key=abc1234567890123456789` | `[REDACTED: GENERIC_KEY_VALUE]` |
| `PASSWORD_VALUE` | generic | `password=...` (8+ chars) | `password=MyS3cretP@ss` | `[REDACTED: PASSWORD_VALUE]` |
| `CONNECTION_STRING` | connection_strings | `(postgres\|mysql\|mongo\|redis\|amqp)://user:pass@host` | `postgresql://admin:pass@db:5432` | `[REDACTED: CONNECTION_STRING]` |
| `EMAIL` | pii | Standard email regex | `user@example.com` | `[REDACTED: EMAIL]` |
| `FR_PHONE` | pii | `+33 6...` or `06...` | `+33 6 12 34 56 78` | `[REDACTED: FR_PHONE]` |
| `FR_NIR` | pii | French SSN (NIR/Carte Vitale) | `1 85 01 75 123 456 78` | `[REDACTED: FR_NIR]` |
| `IBAN` | pii | EU IBAN format | `FR76 1234 5678 9012 3456 7890 123` | `[REDACTED: IBAN]` |
| `CREDIT_CARD` | pii | 13-19 digit card number | `4111 1111 1111 1111` | `[REDACTED: CREDIT_CARD]` |

### Patterns Custom (via env var)

Format : `MCP_PRIVACY_CUSTOM_PATTERNS="OPENAI_ORG_KEY=openai_org_[a-z0-9]{24};COMPANY_TOKEN=ctk_[a-zA-Z]{32}"`

---

## 6. Plan de Migration

### Phase 1 : Déploiement du Service (Stories 42.1-42.4)

Les nouveaux writes sont automatiquement sanitisés. Les données existantes ne sont pas affectées.

### Phase 2 : Nettoyage Rétroactif (Story 42.5)

```bash
# Dry run d'abord
python scripts/clean_legacy_secrets.py --dry-run

# Puis nettoyage réel
python scripts/clean_legacy_secrets.py --batch-size=200

# Pour un projet spécifique
python scripts/clean_legacy_secrets.py --project-id=abc-123-uuid
```

### Phase 3 : Régénération des Embeddings

Les embeddings des records modifiés sont invalidés et régénérés async :

```sql
-- Les records avec embedding=NULL seront régénérés par le worker
UPDATE memories SET embedding = NULL, embedding_half = NULL 
WHERE content LIKE '%[REDACTED:%' AND embedding IS NOT NULL;
```

Le worker de régénération d'embeddings écoute le stream Redis `embedding:regenerate`.

---

## 7. Stratégie de Test

### Tests Unitaires (`tests/services/test_privacy_service.py`)

| Test | Description | Données de test |
|------|-------------|-----------------|
| `test_openai_key_stripped` | Match `sk-proj-*` et `sk-*` | `sk-proj-test1234567890abcdef` |
| `test_aws_key_stripped` | Match `AKIA*` | `AKIAIOSFODNN7EXAMPLE` |
| `test_github_token_stripped` | Match `ghp_*`, `github_pat_*` | `ghp_test1234567890abcdefghijklmnopqrstuvwxyz` |
| `test_jwt_stripped` | Match 3-part base64 | `eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.abc123def456` |
| `test_bearer_token_stripped` | Match Bearer prefix | `Bearer abc123tokenXYZ` |
| `test_connection_string_stripped` | Match DB URI with credentials | `postgresql://admin:S3cret@db:5432/mydb` |
| `test_private_tag_stripped` | Match `<private>...</private>` | `<private>my secret value</private>` |
| `test_private_tag_multiline` | Match across newlines | `<private>\nsecret\n</private>` |
| `test_fr_phone_stripped` | Match French phone | `+33 6 12 34 56 78`, `0612345678` |
| `test_fr_nir_stripped` | Match French SSN | `1 85 01 75 123 456 78` |
| `test_iban_stripped` | Match IBAN | `FR76 1234 5678 9012 3456 7890 123` |
| `test_email_stripped` | Match email | `user@example.com` |
| `test_generic_api_key_stripped` | Match `api_key=...` | `api_key=abc1234567890123456789` |
| `test_password_stripped` | Match `password=...` | `password=MyS3cretP@ss` |
| `test_no_false_positives_code` | Code normal non strippé | `def authenticate(user, password_hash)` |
| `test_no_false_positives_urls` | URLs sans credentials non strippées | `https://api.example.com/v1/endpoint` |
| `test_category_disable` | Désactiver une catégorie | `MCP_PRIVACY_PATTERNS_PII=false` |
| `test_custom_patterns` | Patterns custom | `openai_org_test1234567890abcd` |
| `test_batch_sanitize` | Sanitize batch de textes | Liste de 100 textes |
| `test_max_length_skip` | Texte trop long est skippé | Texte > 1MB |
| `test_graceful_degradation` | Service disabled = pas d'erreur | `enabled=False` |
| `test_empty_text` | Texte vide | `""` |
| `test_no_secrets` | Texte sans secrets | `"Hello world, how are you?"` |
| **Performance** | | |
| `test_sanitize_performance` | < 2ms per 2KB text | 2KB text, 20+ patterns |
| `test_sanitize_large_text` | < 50ms per 100KB text | 100KB text |

### Tests d'Intégration (`tests/tools/test_memory_tools_privacy.py`)

| Test | Description |
|------|-------------|
| `test_write_memory_sanitizes_secrets` | `write_memory` avec clé API → `read_memory` retourne `[REDACTED: OPENAI_KEY]` |
| `test_update_memory_sanitizes_secrets` | `update_memory` avec token → contenu sanitisé |
| `test_embedding_receives_sanitized_text` | Mock `embedding_service` → vérifie que le texte sanitisé est embedded |
| `test_entity_extraction_receives_sanitized_text` | Vérifie que GLiNER reçoit le texte sanitisé |
| `test_conversation_import_sanitizes` | Import conversation avec secret → sanitisé |

### Tests de Sécurité

| Test | Description |
|------|-------------|
| `test_audit_log_no_raw_values` | Vérifie que les logs structlog ne contiennent JAMAIS les valeurs brutes |
| `test_redo_resistance` | Patterns avec backtracking limité → pas de ReDoS |
| `test_cannot_reverse_redaction` | Vérifie que `[REDACTED: ...]` ne peut pas être inversé |

---

## 8. Considérations de Sécurité

### 8.1 Irréversibilité

La rédaction est **strictement irréversible**. Nous ne stockons pas :
- ❌ La valeur originale du secret
- ❌ Un hash du secret
- ❌ Une version chiffrée

Raison : Si un attaquant obtient l'accès DB ou log, il ne doit pouvoir retrouver le secret d'aucune façon. Un mécanisme de déchiffrement serait une faille de sécurité.

### 8.2 Audit Trail

L'audit log ne contient **que des métadonnées** :
```json
{
  "event": "security.data_sanitized",
  "tool": "write_memory",
  "title_redactions": {"OPENAI_KEY": 1},
  "content_redactions": {"AWS_KEY": 2},
  "total_redactions": 3
}
```

**Jamais** :
```json
// ❌ INTERDIT
{"event": "redacted", "original_value": "sk-proj-abc123..."}
```

### 8.3 ReDoS (Regular Expression Denial of Service)

Les patterns sont conçus pour éviter le backtracking catastrophique :
- Bornes fixes : `{20, 100}` au lieu de `{20,}`
- Pas de quantificateurs imbriqués : pas de `(.*)*`
- Évitement des alternations complexes non-anchored
- Limite de longueur de texte : `MAX_SANITIZE_LENGTH = 1MB`
- Considérer l'usage du module `regex` (avec timeout) pour les patterns complexes si `re` s'avère insuffisant

### 8.4 Faux Positifs

Les faux positifs les plus probables :
- `EMAIL` : Les adresses email dans du code légitime (ex: `contact@example.com` dans un README)
- `PASSWORD_VALUE` : Les variables nommées `password` dans du code (ex: `password_hash`, `password_field`)
- `CREDIT_CARD` : Les longs nombres (ex: numéros de commande, IDs)

**Mitigation** :
- Configuration granulaire pour désactiver des catégories
- Les patterns utilisent des bornes de longueur et des word boundaries (`\b`)
- Le `GENERIC_KEY_VALUE` exige 20+ chars pour éviter les faux positifs courts
- Les patterns PII sont désactivables séparément (`MCP_PRIVACY_PATTERNS_PII=false`)

### 8.5 Vector Space Contamination

Même si le texte est sanitisé avant embedding, les embeddings existants (pré-migration) contiennent potentiellement des secrets encodés numériquement. La Phase 2 (migration) + Phase 3 (régénération embeddings) corrigera cela.

---

## 9. Budget Performance

| Métrique | Budget | Justification |
|----------|--------|---------------|
| **Sanitize 2KB text** | < 2ms | 20+ regex pre-compiled, text court |
| **Sanitize 100KB text** | < 50ms | Chunk de code moyen |
| **Sanitize 1MB text** | Skip | Trop long, risque CPU lock |
| **Overhead write_memory** | < 5ms additionnel | Actuellement 80-120ms total, 5ms = négligeable |
| **Overhead code chunking** | < 10ms par chunk | Chunk moyen ~2KB, 10 chunks = 100ms |
| **Startup PrivacyService** | < 100ms | Compilation ~25 regexes |
| **Memory footprint** | < 1MB | Patterns pre-compiled, pas de cache texte |

---

## 10. Configuration & Déploiement

### Variables d'Environnement

```bash
# ─── Master Switch ──────────────────────────────────
MCP_PRIVACY_ENABLED=true

# ─── Pattern Category Toggles ──────────────────────
MCP_PRIVACY_PATTERNS_CLOUD=true
MCP_PRIVACY_PATTERNS_AI_PROVIDERS=true
MCP_PRIVACY_PATTERNS_DEVEX=true
MCP_PRIVACY_PATTERNS_AUTH=true
MCP_PRIVACY_PATTERNS_GENERIC=true
MCP_PRIVACY_PATTERNS_PII=true
MCP_PRIVACY_PATTERNS_PRIVATE_TAGS=true
MCP_PRIVACY_PATTERNS_CONNECTION_STRINGS=true

# ─── Code Indexing Toggle ──────────────────────────
MCP_CODE_SANITIZE=true

# ─── Custom Patterns ───────────────────────────────
MCP_PRIVACY_CUSTOM_PATTERNS="OPENAI_ORG_KEY=openai_org_[a-z0-9]{24};COMPANY_TOKEN=ctk_[a-zA-Z]{32}"

# ─── Performance ───────────────────────────────────
MCP_PRIVACY_MAX_SANITIZE_LENGTH=1000000
```

### Docker Compose

```yaml
services:
  api:
    environment:
      MCP_PRIVACY_ENABLED: "true"
      MCP_PRIVACY_PATTERNS_PII: "true"
      MCP_CODE_SANITIZE: "true"
```

### Injection dans le Service Container

```python
# Dans api/mnemo_mcp/server.py, au setup des services :

from services.privacy_service import PrivacyService

privacy_service = PrivacyService()  # Reads config from env
services["privacy_service"] = privacy_service
```

---

## 11. Questions Ouvertes

| # | Question | Options | Recommandation |
|---|----------|---------|----------------|
| Q1 | **L'EMAIL doit-il être strippé par défaut ?** | Les emails sont très fréquents dans le code et les mémoires légitimes. Faux positifs probables. | Désactiver par défaut (`MCP_PRIVACY_PATTERNS_PII=true` mais email en sous-catégorie `MCP_PRIVACY_PATTERNS_PII_EMAIL=false` par défaut) |
| Q2 | **Le CREDIT_CARD doit-il être strippé ?** | Pattern très large (13-19 digits), beaucoup de faux positifs (numéros de commande, IDs). | Désactiver par défaut, ou implémenter validation Luhn pour réduire les faux positifs |
| Q3 | **Faut-il sanitizer les résultats de recherche ?** | Les données sont déjà sanitisées à l'écriture, donc les résultats de lecture sont propres. Mais si le service est activé après des writes sans sanitisation... | Non — préférer la migration rétroactive (Story 42.5). La sanitisation en lecture créerait des incohérences avec les embeddings. |
| Q4 | **Comment gérer les `<private>` tags dans le code ?** | Le code peut légitimement contenir des strings HTML avec `<private>`. | Ne sanitizer que dans le Pilier B (mémoire), pas dans le Pilier A (code indexing). Le code doit rester fidèle à la source. |
| Q5 | **Faut-il un mode "warn-only" ?** | Log les détections sans rédiger, pour calibrer les patterns avant activation. | Oui — ajouter `MCP_PRIVACY_MODE=warn|enforce` (défaut: enforce). En mode "warn", les secrets sont loggés (type+count) mais pas rédigés. |
| Q6 | **Le script de migration doit-il toucher les soft-deleted memories ?** | Les mémoires soft-deleted contiennent peut-être des secrets aussi. | Non par défaut (`--include-deleted=false`), mais ajouter un flag `--include-deleted` pour les env paranos. |
| Q7 | **Faut-il ajouter une colonne `sanitized_at` à la table memories ?** | Permet de tracker quels records ont été sanitisés et quand. | Oui — ajouter `sanitized_at TIMESTAMPTZ` et `sanitized_types TEXT[]` pour les records migrés. |
| Q8 | **Connection strings : faut-il préserver le host ?** | `postgresql://admin:pass@db.prod:5432/mydb` → tout rédiger ou garder `db.prod:5432/mydb` ? | Rédiger uniquement le `user:pass@` → `postgresql://[REDACTED: CREDENTIALS]@db.prod:5432/mydb`. Le host et DB sont utiles pour la recherche. |

---

## Annexe A : Comparaison avec AgentMemory

| Aspect | AgentMemory | MnemoLite (EPIC-42) |
|--------|-------------|---------------------|
| **Patterns** | 13 regex + private tags | 21+ regex + private tags + PII + FR/EU + custom |
| **Intégration mémoire** | `observe.ts` uniquement (PAS `remember.ts`) | `write_memory` + `update_memory` + conversation import |
| **Intégration code** | ❌ Aucune | ✅ Code indexing + chunking |
| **PII** | ❌ Aucun | ✅ Email, FR_PHONE, FR_NIR, IBAN, CREDIT_CARD |
| **Config** | ❌ Hardcoded | ✅ Env vars granulaires + custom patterns |
| **Audit** | ❌ Aucun | ✅ structlog + OpenTelemetry |
| **Rétroactivité** | ❌ Aucun | ✅ Script migration + embedding regeneration |
| **Mode warn** | ❌ Aucun | ✅ `MCP_PRIVACY_MODE=warn\|enforce` |
| **ReDoS protection** | ❌ Aucune | ✅ Bounded patterns, MAX_SANITIZE_LENGTH |
| **Performance** | N/A (in-process, rapide) | < 2ms/2KB, < 50ms/100KB |

---

*Fin de spécification EPIC-42 — Prêt pour review et implémentation*
