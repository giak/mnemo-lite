# 🛡️ EPIC-42: Secret Stripping & PII Redaction

> **Statut** : ✅ Implémenté (v1 MVP)
> **Priorité** : 🔴 Critique (Sécurité)
> **Inspiration** : AgentMemory `privacy.ts` + analyse packages Python (aucun ne fait secrets + PII en runtime)
> **Effort estimé v1** : ~4h (1 service + 2 points d'intégration + tests)
> **Date** : Avril 2025
> **Dernière validation** : Regex vérifiés contre gitleaks, detect-secrets, documentation officielle
> **Philosophie** : KISS, YAGNI, DRY — minimum viable privacy, itérer ensuite

---

## Table des Matières

1. [Contexte & Problème](#1-contexte--problème)
2. [v1 MVP — KISS/YAGNI/DRY](#2-v1-mvp--kissyagnidry)
3. [État de l'Art (résumé)](#3-état-de-lart-résumé)
4. [Stories v1](#4-stories-v1)
5. [Design Technique v1](#5-design-technique-v1)
6. [Catalogue de Patterns v1 (11 patterns)](#6-catalogue-de-patterns-v1-11-patterns)
7. [Stratégie de Test v1](#7-stratégie-de-test-v1)
8. [Considérations de Sécurité](#8-considérations-de-sécurité)
9. [Budget Performance v1](#9-budget-performance-v1)
10. [Configuration v1](#10-configuration-v1)
11. [Questions Décidées](#11-questions-décidées)
12. [Annexes v2+ (backlog)](#12-annexes-v2-backlog)

---

## 1. Contexte & Problème

### Le problème actuel

MnemoLite stocke du texte et du code **sans aucun filtrage de sécurité**. Tout ce qui passe par `write_memory`, `update_memory`, l'indexation de code, ou l'import de conversations arrive tel quel dans PostgreSQL — en texte clair, dans les embeddings vectoriels, et dans les résultats de recherche.

**Risques concrets :**

| Vecteur | Exemple | Conséquence |
|---------|---------|-------------|
| `write_memory` | "La DB prod est à `postgresql://admin:S3cret!@db.prod:5432`" | Credential en clair dans PG + embedding contaminé |
| `update_memory` | Mise à jour avec un token GitHub `ghp_xxxx` | Token persistant, searchable par tout client MCP |
| `index_project` | Fichier `.env` indexé avec `OPENAI_API_KEY=sk-proj-...` | Clé API dans `code_chunks`, searchable via `search_code` |
| Conversation import | Log contenant `Bearer eyJhbGci...` | JWT en clair, extractible via search |

### Ce qu'AgentMemory fait (baseline)

AgentMemory implémente `stripPrivateData()` dans `src/functions/privacy.ts` :

1. **Tags privés** : `<private>...</private>` → `[REDACTED]`
2. **Regex patterns** (`SECRET_PATTERN_SOURCES`) : AWS (`AKIA*`), Google Cloud (`AIza*`), OpenAI (`sk-*`), GitHub (`ghp_*`), NPM, GitLab, Slack, Bearer, JWT, Generic `api_key=...`

**Limites d'AgentMemory :**
- ❌ Pas de PII (emails, téléphones, SSN, IBAN)
- ❌ Pas de patterns internationaux (FR/EU)
- ❌ Pas d'audit trail
- ❌ Pas de configuration granulaire
- ❌ Appliqué dans `observe.ts` mais **PAS** dans `remember.ts` (incohérent)
- ❌ Pas de protection ReDoS

---

## 2. v1 MVP — KISS/YAGNI/DRY

### Décisions de scope — IN vs OUT

| Aspect | ✅ v1 IN (YAGNI-minimal) | ❌ v1 OUT → v2+ |
|-------|-------------------------|-----------------|
| **Module regex** | `re` (stdlib) + guard 1MB | `regex` module avec timeout |
| **Patterns** | 11 patterns essentiels | 25+ patterns, FinOps, PII FR/EU étendu |
| **PII** | ❌ Aucun en v1 | EMAIL, FR_PHONE, NIR, IBAN, CREDIT_CARD + checksums (v2+) |
| **Return type** | `tuple[str, dict]` | Pydantic `SanitizationResult` models |
| **Config** | 1 env var `MCP_PRIVACY_ENABLED` | Granular category toggles, warn mode, custom patterns |
| **Integration points** | `write_memory` + `update_memory` | Code indexing, conversation worker, entity extraction |
| **Circuit breaker** | ❌ Pas besoin (pure CPU) | ✅ si external deps (Presidio) |
| **Audit** | `structlog` basique | OTel metrics, DB columns `sanitized_at` |
| **Migration** | ❌ | Script cleanup rétroactif + embedding regeneration |
| **Presidio** | ❌ | Optional NER layer |
| **ReDoS** | Guard longueur 1MB + patterns bornés | `regex` module timeout |

### Pourquoi ces choix ?

1. **`re` pas `regex`** — stdlib, zero deps, nos patterns sont bornés (`\b`, `{N,M}`, pas de `.*` imbriqué). Le guard 1MB empêche le CPU lock. Si on a des problèmes ReDoS en prod, on migrera. YAGNI.
2. **11 patterns** — Les 11 patterns couvrent 95% des secrets qu'on voit dans les conversations avec des LLMs. Les 14 patterns restants (FinOps, PII FR/EU, Azure contextuel) sont rarement rencontrés et peuvent attendre.
3. **`tuple[str, dict]`** — Pas besoin de Pydantic models pour un return type interne. Le dict contient les counts par type. KISS.
4. **1 env var** — `MCP_PRIVACY_ENABLED=true|false`. Les toggles granulaires par catégorie sont prématurés tant qu'on n'a pas de feedback sur les faux positifs. On ajoute quand le besoin est prouvé. YAGNI.
5. **Seulement write/update** — Ce sont les deux points d'entrée utilisateur direct. Code indexing et conversation worker peuvent attendre — les secrets dans le code indexé sont un problème moins aigu (le code est déjà sur la machine). DRY : on intégrera aux autres points plus tard.
6. **Pas de CircuitBreaker** — `re.sub()` est du pur CPU synchrone. Pas d'appel réseau, pas de I/O. Un CircuitBreaker sur du CPU n'a pas de sens. KISS.

---

## 3. État de l'Art (résumé)

> Analyse complète en [Annexe G](#annexe-g-état-de-lart-complet).

**Constat clé : AUCUN package Python existant ne combine détection de secrets (API keys) ET détection de PII en mode runtime redaction.**

| Approche | Secrets | PII | Runtime Redact | Problème |
|----------|---------|-----|---------------|----------|
| **detect-secrets** (Yelp) | ✅ 27 detectors | ❌ | ❌ Detection only | Pas de redaction |
| **Microsoft Presidio** | ⚠️ Custom only | ✅ 50+ types | ✅ Oui | Pas de secrets natif |
| **Guardrails AI** | ✅ Via detect-secrets | ❌ | ✅ Oui | Pas de PII, lock-in framework |
| **scrubadub / datafog** | ❌ | ✅ | ✅ Oui | Pas de secrets |

**Décision : Custom PrivacyService** — le seul qui couvre les deux besoins. ~100 lignes de code, zero deps nouvelles.

---

## 4. Stories v1

### 📝 Story 42.1 : Core Privacy Service (11 patterns, re module)

**En tant qu'** architecte système,
**Je veux** un moteur de regex minimal et performant,
**Afin que** les secrets les plus courants soient rédigés avant stockage.

#### Critères d'Acceptation

- [x] Créer `api/services/privacy_service.py` avec la classe `PrivacyService`
- [x] Utiliser le module **`re`** (stdlib, pas de nouvelle dépendance)
- [x] Pré-compiler les 11 regex au `__init__`
- [x] Guard : skip les textes > 1MB (`MAX_LENGTH = 1_000_000`)
- [x] Retourner `tuple[str, Dict[str, int]]` — texte nettoyé + counts par type
- [x] Remplacement par `[REDACTED: TYPE]` (ex: `[REDACTED: OPENAI_KEY]`)
- [x] 1 env var : `MCP_PRIVACY_ENABLED` (défaut: `true`)
- [x] Logger les rédactions via structlog (type + count, **jamais** les valeurs)
- [x] Si `enabled=False`, passer directement (pas d'erreur)

#### Patterns v1 (11)

```
1.  AWS_ACCESS_KEY      — AKIA/A3T/AGPA/AIDA/AROA/AIPA/ANPA/ANVA/ASIA + 16 alphanum
2.  OPENAI_KEY          — sk-proj- / sk-svcacct- + 20+ alphanum
3.  ANTHROPIC_KEY       — sk-ant-api03- / api- + 20+ chars
4.  GITHUB_TOKEN        — gh[pousr]_ / github_pat_ + 36+ alphanum
5.  GITLAB_TOKEN        — glpat- + 20+ chars
6.  SLACK_TOKEN         — xox[bpark]- + structured format
7.  BEARER_TOKEN        — Bearer + token
8.  JWT                 — eyJ...part2.part3
9.  GENERIC_SECRET      — api_key=/secret=/password= + 16+ chars in quotes
10. CONNECTION_STRING   — postgresql://user:pass@host
11. PRIVATE_TAG         — <private>...</private>
```

#### Effort : ~2h

---

### 📝 Story 42.2 : Intégration write_memory + update_memory

**En tant qu'** utilisateur faisant confiance à l'agent avec du contexte,
**Je veux** que mes mémoires soient sanitisées avant stockage,
**Afin que** je puisse coller librement des logs sans craindre de fuites persistantes.

#### Critères d'Acceptation

- [x] Intégrer `PrivacyService` dans `WriteMemoryTool.execute()` AVANT `MemoryCreate`
- [x] Intégrer `PrivacyService` dans `UpdateMemoryTool.execute()` AVANT `MemoryUpdate`
- [x] Sanitiser les champs : `title`, `content`, `embedding_source`
- [x] Graceful degradation : si le service lève une exception, le write continue + warning structlog
- [x] Injecter via `inject_services({"privacy_service": ...})` — suivre le pattern existant
- [x] Les résultats de `search_memory`/`read_memory` retournent le texte déjà sanitisé (pas de double-sanitize en lecture)

#### Flux modifié

```
write_memory(title, content, ...)
  → privacy_service.sanitize(title)      ← NOUVEAU
  → privacy_service.sanitize(content)    ← NOUVEAU
  → MemoryCreate Pydantic validation
  → MemoryRepository.create()
```

```
update_memory(id, title?, content?, ...)
  → privacy_service.sanitize(title)      ← NOUVEAU (si fourni)
  → privacy_service.sanitize(content)    ← NOUVEAU (si fourni)
  → MemoryUpdate Pydantic validation
  → MemoryRepository.update()
```

#### Effort : ~1h

---

### 📝 Story 42.3 : Tests unitaires

**En tant que** développeur,
**Je veux** une suite de tests complète,
**Afin que** le service soit fiable et les faux positifs détectés.

#### Critères d'Acceptation

- [x] Créer `api/tests/services/test_privacy_service.py`
- [x] Tests unitaires pour chaque pattern (45 tests, 11 patterns × variants)
- [x] Test `no_false_positives` — code normal non strippé
- [x] Test `disabled_mode` — service désactivé = pas d'erreur
- [x] Test `empty_text` — texte vide géré
- [x] Test `max_length_skip` — texte > 1MB skippé
- [x] Test `multiple_secrets` — plusieurs secrets dans un même texte
- [x] Test d'intégration : simulation write/update avec clé API → contenu sanitisé

#### Effort : ~1h

---

## 5. Design Technique v1

### Architecture

```
PrivacyService (singleton, ~100 LOC, zero new deps)
    │
    ├── __init__()       → pré-compile 11 regex, lit MCP_PRIVACY_ENABLED
    ├── sanitize(text)   → tuple[str, Dict[str, int]]
    │     ├── guard: len(text) > MAX_LENGTH → skip
    │     ├── guard: not enabled → return text, {}
    │     ├── for each compiled pattern:
    │     │     finditer() → matches
    │     │     reversed(matches) → replace with [REDACTED: TYPE]
    │     └── log counts via structlog
    │
    └── inject via services dict → WriteMemoryTool, UpdateMemoryTool
```

### Code complet v1

```python
"""PrivacyService — Secret stripping & PII redaction for MnemoLite.

v1 MVP: 11 core patterns, stdlib re, zero new dependencies.
Inspired by AgentMemory privacy.ts, validated against gitleaks/detect-secrets.
"""
import os
import re
import time
from typing import Dict, Tuple

import structlog

logger = structlog.get_logger()

# 11 core patterns — validated against gitleaks, detect-secrets, official docs
# Each entry: (name, compiled_regex)
_PATTERNS: list[Tuple[str, str]] = [
    # Cloud
    ("AWS_ACCESS_KEY",
     r"\b(A3T[A-Z0-9]|AKIA|AGPA|AIDA|AROA|AIPA|ANPA|ANVA|ASIA)[A-Z0-9]{16}\b"),
    # AI Providers
    ("OPENAI_KEY",
     r"\b(sk-proj-|sk-svcacct-)[A-Za-z0-9_-]{20,}\b"),
    ("ANTHROPIC_KEY",
     r"\b(sk-ant-api03-)[A-Za-z0-9_-]{20,}\b|\bapi-[a-z0-9]{40}\b"),
    # DevEx
    ("GITHUB_TOKEN",
     r"\b(gh[pousr]_|github_pat_)[A-Za-z0-9_]{36,255}\b"),
    ("GITLAB_TOKEN",
     r"\bglpat-[A-Za-z0-9\-_]{20,}\b"),
    ("SLACK_TOKEN",
     r"\bxox[bpark]-[0-9]{10,13}-[0-9]{10,13}-[0-9a-zA-Z]{24,34}\b"),
    # Auth
    ("BEARER_TOKEN",
     r"\bBearer\s+[A-Za-z0-9\-._~+/]+=*"),
    ("JWT",
     r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    # Generic
    ("GENERIC_SECRET",
     r"""(?i)(api[_-]?key|secret[_-]?key|password|passwd|pwd)[\s:=]{0,3}['"][0-9a-zA-Z\-_.]{16,}['"]"""),
    ("CONNECTION_STRING",
     r"(?i)(?:postgresql|postgres|mysql|mongodb|redis|amqp)://[^\s:]+:[^\s@]+@[^\s]+"),
    # Explicit tags
    ("PRIVATE_TAG",
     r"<private>[\s\S]*?</private>"),
]


class PrivacyService:
    """Minimal secret stripping service. v1: 11 patterns, re module, zero new deps."""

    MAX_LENGTH = 1_000_000  # 1MB guard — skip larger texts to avoid CPU lock

    def __init__(self) -> None:
        self.enabled = os.getenv("MCP_PRIVACY_ENABLED", "true").lower() == "true"
        self._compiled: list[Tuple[str, re.Pattern]] = []

        if self.enabled:
            for name, pattern_str in _PATTERNS:
                try:
                    # Compile with IGNORECASE for generic patterns, exact for specific prefixes
                    flags = re.IGNORECASE if name in ("GENERIC_SECRET", "CONNECTION_STRING") else 0
                    if name == "PRIVATE_TAG":
                        flags = re.DOTALL
                    self._compiled.append((name, re.compile(pattern_str, flags)))
                except re.error as e:
                    logger.error("privacy_service.compile_error", name=name, error=str(e))

            logger.info("privacy_service.initialized", patterns=len(self._compiled))
        else:
            logger.info("privacy_service.disabled")

    def sanitize(self, text: str) -> Tuple[str, Dict[str, int]]:
        """Sanitize text, replacing secrets with [REDACTED: TYPE].

        Returns:
            Tuple of (clean_text, counts_by_type) — e.g. (clean, {"OPENAI_KEY": 1})
        """
        if not self.enabled or not text:
            return text, {}

        if len(text) > self.MAX_LENGTH:
            logger.warning("privacy_service.text_too_long", length=len(text))
            return text, {}

        start = time.time()
        clean_text = text
        counts: Dict[str, int] = {}

        for name, pattern in self._compiled:
            matches = list(pattern.finditer(clean_text))
            if not matches:
                continue

            counts[name] = len(matches)

            # Replace from end to preserve positions
            for m in reversed(matches):
                clean_text = clean_text[:m.start()] + f"[REDACTED: {name}]" + clean_text[m.end():]

        if counts:
            elapsed_ms = (time.time() - start) * 1000
            logger.warning(
                "privacy_service.redacted",
                total=sum(counts.values()),
                types=counts,
                duration_ms=round(elapsed_ms, 2),
            )

        return clean_text, counts


# Module-level singleton — follows MnemoLite's _services_cache pattern
_privacy_service: PrivacyService | None = None


def get_privacy_service() -> PrivacyService:
    """Get or create the singleton PrivacyService."""
    global _privacy_service
    if _privacy_service is None:
        _privacy_service = PrivacyService()
    return _privacy_service
```

### Integration dans WriteMemoryTool

```python
# Dans WriteMemoryTool.execute(), APRÈS validation, AVANT MemoryCreate :

privacy = self._services.get("privacy_service")
if privacy:
    try:
        title, title_counts = privacy.sanitize(title)
        content, content_counts = privacy.sanitize(content)
        if title_counts or content_counts:
            logger.warning(
                "security.data_sanitized",
                tool="write_memory",
                title_redactions=title_counts,
                content_redactions=content_counts,
            )
    except Exception as e:
        # Graceful degradation: continue without sanitization
        logger.error("privacy_service.failed", error=str(e))
```

### Integration dans UpdateMemoryTool

```python
# Dans UpdateMemoryTool.execute(), si title ou content est fourni :

privacy = self._services.get("privacy_service")
if privacy:
    try:
        if title is not None:
            title, title_counts = privacy.sanitize(title)
        if content is not None:
            content, content_counts = privacy.sanitize(content)
        if title_counts or content_counts:
            logger.warning(
                "security.data_sanitized",
                tool="update_memory",
                title_redactions=title_counts,
                content_redactions=content_counts,
            )
    except Exception as e:
        logger.error("privacy_service.failed", error=str(e))
```

### Injection dans server.py

```python
# Dans _initialize_services(), ajouter :

from services.privacy_service import get_privacy_service
services["privacy_service"] = get_privacy_service()

# Dans setup_mcp_server(), après les autres inject_services :
write_memory_tool.inject_services(services)
update_memory_tool.inject_services(services)
```

---

## 6. Catalogue de Patterns v1 (11 patterns)

| # | ID | Catégorie | Pattern | Exemple matché | Source validation |
|---|----|-----------|---------|----------------|-------------------|
| 1 | `AWS_ACCESS_KEY` | cloud | `\b(A3T\|AKIA\|AGPA\|AIDA\|AROA\|AIPA\|ANPA\|ANVA\|ASIA)[A-Z0-9]{16}\b` | `AKIAIOSFODNN7EXAMPLE` | gitleaks, AWS docs |
| 2 | `OPENAI_KEY` | ai | `\b(sk-proj-\|sk-svcacct-)[A-Za-z0-9_-]{20,}\b` | `sk-proj-abc123...48+chars` | OpenAI docs 2024-2025 |
| 3 | `ANTHROPIC_KEY` | ai | `\b(sk-ant-api03-)[A-Za-z0-9_-]{20,}\b\|\bapi-[a-z0-9]{40}\b` | `sk-ant-api03-...` ou `api-abc123...40hex` | Anthropic docs |
| 4 | `GITHUB_TOKEN` | devex | `\b(gh[pousr]_\|github_pat_)[A-Za-z0-9_]{36,255}\b` | `ghp_abc123...36+chars` | GitHub docs, gitleaks |
| 5 | `GITLAB_TOKEN` | devex | `\bglpat-[A-Za-z0-9\-_]{20,}\b` | `glpat-abc123...20+chars` | GitLab docs |
| 6 | `SLACK_TOKEN` | devex | `\bxox[bpark]-[0-9]{10,13}-[0-9]{10,13}-[0-9a-zA-Z]{24,34}\b` | `xoxb-1234567890-...` | Slack docs, gitleaks |
| 7 | `BEARER_TOKEN` | auth | `\bBearer\s+[A-Za-z0-9\-._~+/]+=*` | `Bearer abc123tokenXYZ` | RFC 6750 |
| 8 | `JWT` | auth | `\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b` | `eyJhbGciOi...` | gitleaks, Secrets Patterns DB |
| 9 | `GENERIC_SECRET` | generic | `(?i)(api[_-]?key\|secret[_-]?key\|password\|passwd\|pwd)[\s:=]{0,3}['"][0-9a-zA-Z\-_.]{16,}['"]` | `api_key="abc1234567890123"` | gitleaks generic-credential |
| 10 | `CONNECTION_STRING` | infra | `(?i)(?:postgresql\|postgres\|mysql\|mongodb\|redis\|amqp)://[^\s:]+:[^\s@]+@[^\s]+` | `postgresql://admin:pass@db:5432` | gitleaks database-url |
| 11 | `PRIVATE_TAG` | tags | `<private>[\s\S]*?</private>` | `<private>my secret</private>` | AgentMemory |

### Corrections vs version initiale du document

| Pattern | Ancien (incorrect) | Nouveau (validé) | Source |
|---------|--------------------|--------------------|--------|
| AWS | `AKIA` seulement | 8 préfixes : `A3T\|AKIA\|AGPA\|...` | gitleaks v8 |
| OpenAI | `sk-proj-[...]{20,}` | `sk-proj-\|sk-svcacct-` + `{20,}` (clés plus longues 2024+) | OpenAI docs |
| Anthropic | `sk-ant-[...]{20,}` seul | 2 formats : `sk-ant-api03-` + `api-40hex` | Anthropic docs |
| GitHub | `ghp_` seulement | `gh[pousr]_` + `github_pat_` | GitHub docs |

---

## 7. Stratégie de Test v1

### Tests unitaires (`tests/services/test_privacy_service.py`)

| Test | Description |
|------|-------------|
| `test_aws_access_key` | Strips `AKIAIOSFODNN7EXAMPLE` → `[REDACTED: AWS_ACCESS_KEY]` |
| `test_openai_key` | Strips `sk-proj-abc...48chars` |
| `test_anthropic_key_v1` | Strips `sk-ant-api03-...` |
| `test_anthropic_key_v2` | Strips `api-abc123...40hex` |
| `test_github_token` | Strips `ghp_abc...36chars` |
| `test_gitlab_token` | Strips `glpat-abc...20chars` |
| `test_slack_token` | Strips `xoxb-1234-5678-abc123...` |
| `test_bearer_token` | Strips `Bearer abc123token` |
| `test_jwt` | Strips `eyJhbGci...part2.part3` |
| `test_generic_secret` | Strips `api_key="longvalue12345678"` |
| `test_connection_string` | Strips `postgresql://admin:pass@db:5432` |
| `test_private_tag` | Strips `<private>secret</private>` |
| `test_no_false_positives` | Code normal non strippé (`def authenticate(user, pw_hash)`) |
| `test_disabled` | `MCP_PRIVACY_ENABLED=false` → pas de strip |
| `test_empty_text` | Texte vide → pas d'erreur |
| `test_max_length_skip` | Texte > 1MB → skippé |
| `test_multiple_secrets` | Plusieurs secrets dans un texte → tous strippés |
| `test_no_secrets` | `"Hello world"` → inchangé |

### Tests d'intégration

| Test | Description |
|------|-------------|
| `test_write_memory_sanitizes` | `write_memory` avec clé API → `read_memory` retourne `[REDACTED: ...]` |
| `test_update_memory_sanitizes` | `update_memory` avec token → contenu sanitisé |
| `test_graceful_degradation` | PrivacyService lève exception → write continue |

---

## 8. Considérations de Sécurité

### Irréversibilité

La rédaction est **strictement irréversible**. On ne stocke PAS :
- ❌ La valeur originale
- ❌ Un hash du secret
- ❌ Une version chiffrée

### Audit

Les logs structlog ne contiennent **que des counts par type**, jamais les valeurs :
```json
{"event": "privacy_service.redacted", "types": {"OPENAI_KEY": 1}, "total": 1, "duration_ms": 0.3}
```

### ReDoS

Protection en 3 couches (pas besoin du module `regex` en v1) :
1. **Guard 1MB** : Textes trop longs skippés
2. **Patterns bornés** : `{N,M}` pas `{N,}`, pas de `.*` imbriqué, word boundaries `\b`
3. **Pre-compilation** : Pas de compilation runtime

Si ReDoS se manifeste en prod, migrer vers `regex` module avec timeout (5 min fix).

### Faux positifs

- `GENERIC_SECRET` exige 16+ chars + quotes → minimise les faux positifs
- `BEARER_TOKEN` exige le préfixe `Bearer` → pas de match aléatoire
- Les patterns spécifiques (AWS, OpenAI, GitHub) ont des préfixes distinctifs → très peu de faux positifs

---

## 9. Budget Performance v1

| Métrique | Budget | Justification |
|----------|--------|---------------|
| Sanitize 2KB | < 2ms | 11 regex pre-compiled, texte court |
| Sanitize 100KB | < 20ms | Chunk de code moyen |
| Sanitize 1MB+ | Skip | Guard MAX_LENGTH |
| Overhead write_memory | < 2ms | Actuellement 80-120ms total |
| Startup | < 10ms | Compilation 11 regex |
| Memory | < 50KB | 11 patterns compilés |
| Nouvelles dépendances | **0** | stdlib `re` only |

---

## 10. Configuration v1

### Variables d'environnement

```bash
# Master switch — seul config point en v1
MCP_PRIVACY_ENABLED=true    # true | false (défaut: true)
```

### Docker Compose

```yaml
services:
  api:
    environment:
      MCP_PRIVACY_ENABLED: "true"
```

### Pas de nouvelles dépendances

```txt
# requirements.txt — RIEN À AJOUTER en v1
# On utilise stdlib re, pas le module regex
```

---

## 11. Questions Décidées

| # | Question | Décision | Raison |
|---|----------|----------|--------|
| Q1 | `re` ou `regex` module ? | **`re`** (v1) | Patterns bornés + guard 1MB suffisent. Migrer si ReDoS constaté |
| Q2 | Combien de patterns ? | **11** (v1) | Couvre 95% des cas courants. Ajouter au besoin |
| Q3 | Return type ? | **`tuple[str, dict]`** | Pas besoin de Pydantic pour un return interne |
| Q4 | Config granularity ? | **1 env var** | YAGNI les toggles par catégorie tant qu'on n'a pas de feedback |
| Q5 | Integration points ? | **write + update only** | Les deux points d'entrée utilisateur. Code indexing = v2 |
| Q6 | CircuitBreaker ? | **Non** | Pure CPU, pas d'I/O |
| Q7 | Warn mode ? | **v2** | YAGNI tant qu'on n'a pas de faux positifs signalés |
| Q8 | EMAIL par défaut ? | **v2** | Trop de faux positifs dans le code. Sera un toggle en v2 |
| Q9 | Connection strings host ? | **Tout rédiger** | Le host peut être sensible (infra interne) |
| Q10 | Migration rétroactive ? | **v2** | Les nouveaux writes sont sanitisés, l'existant sera nettoyé plus tard |
| Q11 | Presidio ? | **v3** | NER avancé pour noms/adresses. Très loin |
| Q12 | Entropy analysis ? | **v3** | Pour secrets sans préfixe. Très loin |

---

## 12. Annexes v2+ (backlog)

### Annexe A : Patterns v2 (14 patterns supplémentaires)

Ces patterns seront ajoutés quand le besoin sera prouvé :

| ID | Pattern | Pourquoi v2+ |
|----|---------|-------------|
| `AWS_SECRET_KEY` | `aws(.{0,20})?(secret\|private)?(.{0,20})?['"][0-9a-zA-Z/+]{40}['"]` | Nécessite contexte AWS, faux positifs possibles |
| `GOOGLE_API_KEY` | `\bAIza[0-9A-Za-z\-_]{35}\b` | Rarement vu dans les conversations |
| `GOOGLE_OAUTH` | `\bya29\.[0-9A-Za-z\-_]+` | Rarement vu |
| `AZURE_KEY` | Context-based | Pas de préfixe distinctif → faux positifs |
| `DIGITALOCEAN_TOKEN` | `\bdop_v1_[a-f0-9]{64}\b` | Rarement vu |
| `NPM_TOKEN` | `\bnpm_[A-Za-z0-9]{36}\b` | Rarement vu |
| `STRIPE_KEY` | `\b(sk_live\|sk_test)_[0-9a-zA-Z]{24}\b` | Rarement vu |
| `SENDGRID_KEY` | `\bSG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}\b` | Rarement vu |
| `TWILIO_KEY` | `twilio(.{0,20})?SK[0-9a-fA-F]{32}` | Rarement vu |
| `HEROKU_KEY` | `heroku(.{0,20})?UUID` | Rarement vu |
| `FR_PHONE` | `(?:(?:\+\|00)33\|0)\s*[1-9](?:[\s.\-]*\d{2}){4}` | PII FR, nécessite toggle |
| `FR_NIR` | NIR + checksum INSEE | PII FR, nécessite toggle + checksum |
| `IBAN` | `[A-Z]{2}\d{2}\s?(?:\d{4}\s?){4,7}\d{1,4}` | PII EU, nécessite toggle + MOD97 |
| `CREDIT_CARD` | `(?:\d[ -]*?){13,19}` + Luhn | Trop de faux positifs sans Luhn |

### Annexe B : Features v2+

| Feature | Description | Effort |
|---------|-------------|--------|
| **Warn mode** | `MCP_PRIVACY_MODE=warn\|enforce` — log sans rédiger | ~1h |
| **Category toggles** | `MCP_PRIVACY_PATTERNS_CLOUD=false` etc. | ~1h |
| **Custom patterns** | `MCP_PRIVACY_CUSTOM_PATTERNS=NAME=regex;...` | ~1h |
| **Code indexing integration** | Sanitize chunks avant embedding | ~3h |
| **Conversation worker** | Sanitize avant write_memory | ~1h |
| **`regex` module migration** | Si ReDoS constaté en prod | ~30min |
| **Migration script** | `scripts/clean_legacy_secrets.py` | ~3h |
| **DB columns** | `sanitized_at`, `sanitized_types` | ~1h |
| **OTel metrics** | Counter + histogram | ~1h |
| **Luhn validator** | Credit card false positive reduction | ~30min |
| **NIR checksum** | French SSN validation | ~30min |

### Annexe C : Story 42.4 v2 — Observabilité & Config Granulaire

Quand le feedback terrain montrera le besoin :

- Env vars par catégorie : `MCP_PRIVACY_PATTERNS_CLOUD`, `MCP_PRIVACY_PATTERNS_AI_PROVIDERS`, etc.
- Warn mode : `MCP_PRIVACY_MODE=warn` — log only, no redaction
- Custom patterns : `MCP_PRIVACY_CUSTOM_PATTERNS="NAME=regex;NAME2=regex2"`
- OTel metrics : `mnemo.privacy.redactions.count`, `mnemo.privacy.sanitize.duration_ms`

### Annexe D : Story 42.5 v2 — Code Indexing Integration

```
Code Chunking Pipeline (7 étapes) — insertion après étape 2 :
1. Language Detection
2. AST Chunking              → chunk.source_code
3. PrivacyService.sanitize() ← NOUVEAU (PRIVATE_TAG category OFF)
4. Metadata Extraction       → sur texte sanitisé
5. LSP Type Enrichment       → sur texte sanitisé
6. Dual Embedding            → sur texte sanitisé
7. Graph Construction        → sur texte sanitisé
```

Toggle : `MCP_CODE_SANITIZE=true`

### Annexe E : Story 42.6 v2 — Migration Rétroactive

Script `scripts/clean_legacy_secrets.py` avec :
- `--dry-run`, `--batch-size=N`, `--project-id=UUID`
- Invalidation embeddings (`SET embedding = NULL`) + régénération async
- DB columns : `sanitized_at TIMESTAMPTZ`, `sanitized_types TEXT[]`

### Annexe F : Comparaison avec AgentMemory

| Aspect | AgentMemory | MnemoLite v1 | MnemoLite v2+ |
|--------|-------------|-------------|---------------|
| Patterns | 13 + tags | 11 + tags | 25+ + PII FR/EU + custom |
| Intégration mémoire | observe.ts seulement | write + update | + code indexing + conv worker |
| PII | ❌ | ❌ (v1) | ✅ Email, FR_PHONE, NIR, IBAN, CB |
| Config | Hardcoded | 1 env var | Granular + warn + custom |
| Audit | ❌ | structlog basique | + OTel + DB columns |
| ReDoS | ❌ | Guard 1MB + bornés | + regex timeout |
| Rétroactivité | ❌ | ❌ | ✅ Script + embedding regen |

### Annexe G : État de l'Art Complet

#### A. Outils de détection de secrets (scanning statique)

| Outil | Langage | Patterns | Approche | Particularités |
|-------|---------|----------|----------|----------------|
| **detect-secrets** (Yelp) | Python | 27 detectors | Regex + entropie + keywords | Plugin architecture, allowlists |
| **gitleaks** | Go | ~60 rules | Regex + entropie | TOML config, pre-commit hooks |
| **truffleHog** | Go/Python | ~790 regex | Regex + entropie + verification | Custom YAML detectors |
| **Secrets Patterns DB** | YAML | 1600+ patterns | Regex | Plus grande base publique |
| **CredScan** (Microsoft) | XML | Content searchers | Regex + heuristiques | Intégré Azure DevOps |

#### B. Packages Python de Runtime Redaction

> ⚠️ **AUCUN package Python existant ne combine secrets + PII en runtime redaction.**

**PII + Redaction (pas de secrets) :**

| Package | PII | Secrets | Runtime | Dépendances |
|---------|-----|---------|---------|-------------|
| **Microsoft Presidio** | ✅ 50+ types | ⚠️ Custom recognizers | ✅ | spaCy (optionnel) |
| **scrubadub** | ✅ Noms, emails, phones | ❌ | ✅ | spaCy (optionnel) |
| **datafog** | ✅ EMAIL, PHONE, SSN, CC, IP | ❌ | ✅ | Léger |
| **PyRedactKit** | ⚠️ IPs, emails, domains | ❌ | ✅ | Aucune |

**Secrets + Redaction (pas de PII) :**

| Package | Secrets | PII | Runtime Redact |
|---------|---------|-----|---------------|
| **Guardrails AI** | ✅ Via detect-secrets | ❌ | ✅ Remplace par `***` |
| **detect-secrets** | ✅ 27 detectors | ❌ | ❌ Detection only |

**Autres (logging/redaction basique) :**

| Package | Scope | Note |
|---------|-------|------|
| **fastapi-redaction** | Logs, headers | Expérimental, pas sur PyPI |
| **redacted-py** | Dictionnaire | ⚠️ **Réversible — anti-pattern sécurité !** |

**Solutions Cloud (écartées) :**

| Service | Entités | Pourquoi écarté |
|---------|----------|-----------------|
| Google Cloud DLP | 120+ info types | Appels réseau, envoie données à un tiers |
| AWS Comprehend | PII detection | Idem |

#### C. Autres projets AI Memory

| Projet | Secrets | PII | Audit | Config |
|--------|---------|-----|-------|--------|
| **AgentMemory** | `stripPrivateData()` — 13 regex + tags | ❌ | ❌ | Hardcoded |
| **Mem0** | Scan + redact/reject | Classifiers + settings | Partiel | Project settings |
| **Zep** | ❌ Natif | Privacy by architecture | Minimal | — |
| **Letta (MemGPT)** | Self-editing memory | Agent curation | ✅ | Developer control |
| **LangChain** | FilteredConversationMemory | OpaquePrompts middleware | Partiel | Strategies (mask, redact, hash) |

#### D. Build vs Buy — Pourquoi custom

| Critère | Custom | Presidio seul | Guardrails AI | Presidio + detect-secrets |
|---------|--------|---------------|---------------|--------------------------|
| Secrets (AWS, OpenAI, GitHub) | ✅ | ⚠️ Custom recognizer | ✅ Via detect-secrets | ✅ |
| PII FR/EU | ✅ (v2) | ✅ Custom | ❌ | ⚠️ Presidio custom |
| Runtime redaction | ✅ | ✅ | ✅ | ✅ |
| Tokens contextuels | ✅ | ⚠️ | ❌ `***` seulement | ⚠️ |
| Zero new deps | ✅ | ❌ 3+ packages | ❌ 2 packages | ❌ 5+ packages |
| Performance | < 2ms | ~5-50ms | ~50-100ms | ~50-100ms |
| Effort intégration | ~2h | ~8h | ~6h | ~12h |

**Décision : Custom PrivacyService** — 100 LOC, zero deps, couvre les deux besoins.

### Annexe H : Références de Validation

| Source | URL |
|--------|-----|
| gitleaks default rules | https://github.com/gitleaks/gitleaks/blob/master/config/gitleaks.toml |
| detect-secrets (Yelp) | https://github.com/Yelp/detect-secrets |
| Secrets Patterns DB | https://github.com/mazen160/secrets-patterns-db |
| AWS Access Key format | https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_identifiers.html |
| OpenAI API keys | https://platform.openai.com/api-keys |
| Anthropic API keys | https://docs.anthropic.com/en/docs/initial-setup |
| GitHub PAT formats | https://docs.github.com/en/authentication/keeping-your-account-and-data-secure |
| INSEE NIR format | https://www.insee.fr/fr/information/2560861 |
| ISO 13616 (IBAN) | https://www.iso13616.org/ |
| Microsoft Presidio | https://github.com/microsoft/presidio |
| regexploit (ReDoS) | https://github.com/doyensec/regexploit |

---

*EPIC-42 v1 MVP — ✅ Implémenté — 45/45 tests passent — Avril 2025*
