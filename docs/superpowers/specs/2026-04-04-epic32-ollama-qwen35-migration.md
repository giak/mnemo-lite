# EPIC-32: Migration LM Studio → Ollama (Qwen3.5)

> **Statut:** DRAFT | **Date:** 2026-04-04 | **Auteur:** giak
> **Inspiration:** Benchmark SLM vs LLM, sortie Qwen3.5 (il y a 2 jours), problèmes json_schema LM Studio

---

## 1. Problem Statement

L'architecture actuelle utilise **LM Studio** avec un modèle 7B+ (Qwen2.5-7B) pour l'extraction d'entités et la compréhension de requêtes.

**Problèmes identifiés :**
1. **RAM excessive** : 4-8 GB pour un seul modèle
2. **json_schema rejeté** : LM Studio rejette `response_format.json_schema` → fallback `json_repair` (moins fiable)
3. **Dépendance desktop** : LM Studio nécessite une UI, pas headless, pas Dockerisable
4. **Latence** : 1-3s par appel (modèle lourd)
5. **Pas de modèle officiel** : LM Studio n'a pas de modèle propre, utilise des GGUF tiers

**Conséquences :**
- L'extraction d'entités échoue souvent (pas d'entités nommées extraites)
- 80-90% de la RAM LLM est gaspillée
- Pas de fallback automatisé en production

---

## 2. Solution Overview

Remplacer LM Studio par **Ollama** avec **Qwen3.5:4b** comme modèle unique pour toutes les tâches LLM.

**Pourquoi Qwen3.5:4b ?**
- Sorti il y a 2 jours — state-of-the-art pour sa taille
- **json_schema natif** via Ollama (résout le problème d'extraction)
- **~2.5 GB RAM** (vs 5.5 GB pour 7B) — réduction de 55%
- **<500ms latence** (vs 1-3s) — 5-10× plus rapide
- **Officiel Ollama** — maintenance garantie, mises à jour automatiques
- **Headless** — parfait pour Docker, pas d'UI nécessaire
- **Un seul modèle** — query understanding + entity extraction avec le même modèle

**Alternative ultra-légère :** `qwen3.5:2b` (~1.5 GB RAM) si la RAM est critique.

---

## 3. Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Ollama :11434 (headless)                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  qwen3.5:4b (~2.5 GB RAM)                           │    │
│  │  ├── Query understanding (synchrone, <200ms)        │    │
│  │  └── Entity extraction (async, 200-400ms)           │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  Embeddings (inchangés)                                      │
│  ├── nomic-embed-text (~260 MB)                             │
│  └── jina-embeddings-code (~400 MB)                         │
│  Total embeddings : ~660 MB                                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│  MnemoLite API/MCP                                           │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  OllamaClient (remplace LMStudioClient)             │    │
│  │  ├── base_url: http://ollama:11434/v1               │    │
│  │  ├── model: qwen3.5:4b                              │    │
│  │  ├── json_schema natif (plus besoin de json_repair) │    │
│  │  └── Fallback: si Ollama down → skip silencieux     │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Stories

### Story 32.1: OllamaClient — Remplacement de LMStudioClient

**Objectif** : Créer un client Ollama compatible OpenAI qui utilise `json_schema` natif.

**Fichier** : `api/services/ollama_client.py`

```python
"""
Ollama Client — OpenAI-compatible client for Ollama.

Uses native json_schema for structured output (no json_repair fallback needed).
"""
import os
from typing import Optional, Dict, Any

import httpx
import structlog

logger = structlog.get_logger(__name__)


class OllamaClient:
    """
    HTTP client for Ollama's OpenAI-compatible API.
    
    Supports native json_schema for guaranteed structured JSON output.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0,
    ):
        self.base_url = (base_url or os.getenv("OLLAMA_URL", "http://ollama:11434/v1")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_MODEL", "qwen3.5:4b")
        self.timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None
        self._available: Optional[bool] = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.timeout, connect=5.0),
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def is_available(self) -> bool:
        """Check if Ollama is running and model is loaded."""
        if self._available is not None:
            return self._available
        try:
            client = self._get_client()
            resp = await client.get(f"{self.base_url}/models")
            if resp.status_code == 200:
                models = resp.json().get("data", [])
                self._available = any(self.model in m.get("id", "") for m in models)
                return self._available
            self._available = False
            return False
        except Exception as e:
            self._available = False
            logger.debug("ollama_unavailable", error=str(e))
            return False

    async def extract_json(
        self,
        system_prompt: str,
        user_content: str,
        json_schema: Dict[str, Any],
        temperature: float = 0.1,
    ) -> Optional[Dict[str, Any]]:
        """
        Extract structured JSON using native json_schema.
        
        Ollama supports json_schema natively — no fallback needed.
        """
        try:
            client = self._get_client()
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content},
                    ],
                    "temperature": temperature,
                    "max_tokens": 2048,
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": json_schema,
                    },
                },
            )
            
            if resp.status_code != 200:
                logger.warning("ollama_request_failed", status=resp.status_code, body=resp.text[:200])
                return None

            data = resp.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not content:
                return None

            import json
            return json.loads(content)

        except Exception as e:
            logger.debug("ollama_extract_error", error=str(e))
            return None

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
```

**Fichiers** :
- Créer : `api/services/ollama_client.py`
- Modifier : `api/services/entity_extraction_service.py` — utiliser `OllamaClient`
- Modifier : `api/services/query_understanding_service.py` — utiliser `OllamaClient`
- Supprimer : `api/services/lm_studio_client.py`

---

### Story 32.2: Docker Compose — Ajouter Ollama, retirer LM Studio

**Objectif** : Mettre à jour `docker-compose.yml` pour utiliser Ollama headless.

**Modifications** :
```yaml
# Retirer les variables LM_STUDIO_*
# Ajouter :
services:
  ollama:
    image: ollama/ollama:latest
    container_name: mnemo-ollama
    restart: unless-stopped
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    environment:
      - OLLAMA_HOST=0.0.0.0:11434
      - OLLAMA_MODELS=/root/.ollama/models
    networks:
      - backend

  api:
    environment:
      - OLLAMA_URL=http://ollama:11434/v1
      - OLLAMA_MODEL=qwen3.5:4b
      - OLLAMA_TIMEOUT=30

volumes:
  ollama_data:
```

**Fichiers** :
- Modifier : `docker-compose.yml` — ajouter service ollama, retirer LM Studio vars

---

### Story 32.3: Migration des services existants

**Objectif** : Mettre à jour tous les services qui utilisent `LMStudioClient`.

**Services à modifier** :
- `EntityExtractionService` — remplacer `LMStudioClient` par `OllamaClient`
- `QueryUnderstandingService` — remplacer `LMStudioClient` par `OllamaClient`
- `MCP server` — initialiser `OllamaClient` au lieu de `LMStudioClient`
- `docker-compose.yml` — variables d'environnement

**Fichiers** :
- Modifier : `api/services/entity_extraction_service.py`
- Modifier : `api/services/query_understanding_service.py`
- Modifier : `api/mnemo_mcp/server.py`
- Supprimer : `api/services/lm_studio_client.py`

---

### Story 32.4: Tests TDD

**Objectif** : Tester le nouveau client Ollama et la migration.

**Tests** :
- `test_ollama_client.py` — disponibilité, extraction json_schema, fallback
- `test_entity_extraction_ollama.py` — extraction avec Ollama
- `test_query_understanding_ollama.py` — décomposition requête avec Ollama

**Fichiers** :
- Créer : `tests/services/test_ollama_client.py`
- Créer : `tests/services/test_entity_extraction_ollama.py`
- Créer : `tests/services/test_query_understanding_ollama.py`

---

## 5. Ordre d'implémentation

1. **Story 32.1** — OllamaClient
2. **Story 32.3** — Migration des services
3. **Story 32.2** — Docker Compose
4. **Story 32.4** — Tests TDD

---

## 6. Matrice de dégradation

| Scénario | Comportement |
|----------|-------------|
| Ollama non démarré | Skip silencieux, fallback recherche brute |
| Modèle non pullé | Log warning, skip extraction |
| json_schema échoue | Retry 1×, puis skip (Ollama supporte nativement) |
| Ollama crash en cours de route | Timeout 30s, skip, fallback |

---

## 7. Métriques de succès

| Métrique | Actuel (LM Studio 7B) | Cible (Ollama 4B) |
|----------|----------------------|-------------------|
| RAM LLM | 4-8 GB | ~2.5 GB |
| Latence query | 1-3s | <500ms |
| Latence extraction | 1-3s | 200-400ms |
| json_schema support | ❌ (fallback json_repair) | ✅ (natif) |
| Headless | ❌ (UI desktop) | ✅ (Docker) |
| Qualité extraction | Bonne (7B) | Bonne (4B SOTA) |

---

## 8. Risques et mitigations

| Risque | Probabilité | Impact | Mitigation |
|--------|------------|--------|------------|
| Qwen3.5:4b pas assez bon pour extraction | Faible | Moyen | Fallback vers qwen3.5:9b si besoin |
| Ollama pull long au premier démarrage | Moyenne | Faible | Pull manuel avant `make up` |
| json_schema toujours rejeté | Très faible | Moyen | Retry avec `response_format: "json_object"` |
| RAM insuffisante pour 4B | Faible | Moyen | Passer à qwen3.5:2b (~1.5 GB) |

---

## 9. Dépendances

- **Ollama installé** sur la machine hôte (déjà fait)
- **Modèle qwen3.5:4b** pullé via `ollama pull qwen3.5:4b`
- **Aucune nouvelle dépendance Python** (httpx déjà présent)
