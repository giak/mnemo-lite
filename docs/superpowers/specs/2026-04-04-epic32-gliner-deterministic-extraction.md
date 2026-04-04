# EPIC-32: Deterministic Entity Extraction with GLiNER

> **Statut:** DRAFT | **Date:** 2026-04-04 | **Auteur:** giak
> **Remplace:** EPIC-32 (Migration LM Studio → Ollama) — annulée car les LLM hallucinent toujours.

---

## 1. Problem Statement

L'extraction d'entités par LLM (LM Studio, Ollama) présente des risques inacceptables pour MnemoLite :
- **Hallucinations** : Le LLM invente des entités non présentes dans le texte (~15-30% d'erreurs).
- **Instabilité** : Les résultats varient selon la température, le seed, la version du modèle.
- **Complexité** : Nécessite un serveur externe (Ollama/LM Studio), gestion de modèles, timeouts longs.
- **Coût** : RAM élevée (1.5-8 GB), latence élevée (200ms-3s).

**Conséquences** : Données corrompues en DB, recherche faussée, confiance perdue.

---

## 2. Solution Overview

Remplacer l'extraction LLM par **GLiNER** (Generalist and Lightweight Model for Named Entity Recognition).

**Pourquoi GLiNER ?**
- **Déterministe** : Zéro hallucination. Il identifie des spans dans le texte, ne génère rien.
- **Flexible** : Extrait n'importe quel type d'entité spécifié (technology, person, organization...).
- **Léger** : ~1.2 GB RAM, inférence CPU <200ms.
- **Local** : Modèle embarqué dans le container, zéro dépendance externe.
- **Validé** : POC réussi sur les vraies données MnemoLite (85-90% de précision, 0% d'hallucination).

**Architecture :**
```
Texte → GLiNER (extraction) → Post-processing (dédup, types, validation) → DB
```

---

## 3. Stories

### Story 32.1: GLiNER Service — Chargement et extraction

**Objectif** : Créer un service qui charge le modèle GLiNER et extrait les entités.

**Fichier** : `api/services/gliner_service.py`

```python
"""
GLiNER Service — Deterministic entity extraction.

Uses GLiNER (Generalist and Lightweight Model for NER) to extract
entities from text with zero hallucinations.
"""
import os
import json
from typing import List, Dict, Any, Optional

import structlog
from gliner import GLiNER

logger = structlog.get_logger(__name__)

# Default entity types for extraction
DEFAULT_ENTITY_TYPES = [
    "technology", "product", "file", "person", 
    "organization", "concept", "location"
]

class GLiNERService:
    """
    Service for deterministic entity extraction using GLiNER.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        entity_types: Optional[List[str]] = None,
    ):
        self.model_path = model_path or os.getenv("GLINER_MODEL_PATH", "/tmp/gliner_multi-v2.1")
        self.entity_types = entity_types or DEFAULT_ENTITY_TYPES
        self.model: Optional[GLiNER] = None
        self._load_model()

    def _load_model(self) -> None:
        """Load GLiNER model from local path."""
        try:
            logger.info("loading_gliner_model", path=self.model_path)
            self.model = GLiNER.from_pretrained(self.model_path)
            logger.info("gliner_model_loaded")
        except Exception as e:
            logger.error("gliner_model_load_failed", error=str(e))
            self.model = None

    def extract_entities(self, text: str) -> List[Dict[str, Any]]:
        """
        Extract entities from text using GLiNER.
        
        Args:
            text: Input text
            
        Returns:
            List of entities with name, type, start, end positions
        """
        if not self.model:
            logger.warning("gliner_model_not_loaded")
            return []
        
        try:
            raw_entities = self.model.predict_entities(text, self.entity_types)
            return self._post_process(raw_entities, text)
        except Exception as e:
            logger.error("gliner_extraction_failed", error=str(e))
            return []

    def _post_process(
        self, 
        raw_entities: List[Dict[str, Any]], 
        text: str
    ) -> List[Dict[str, Any]]:
        """
        Post-process raw entities: deduplicate, clean types, validate.
        
        1. Deduplicate by lowercase name
        2. Map inconsistent types to canonical types
        3. Validate entity exists in text
        """
        seen = {}
        type_map = {
            "tech": "technology",
            "product": "technology",
            "org": "organization",
            "company": "organization",
            "per": "person",
            "loc": "location",
        }
        
        for e in raw_entities:
            name = e.get("text", "").strip()
            if not name or len(name) < 2:
                continue
            
            # Validate existence in text
            if name.lower() not in text.lower():
                continue
            
            key = name.lower()
            if key not in seen:
                # Clean type
                raw_type = e.get("label", "concept").lower()
                clean_type = type_map.get(raw_type, raw_type)
                
                seen[key] = {
                    "name": name,
                    "type": clean_type,
                    "start": e.get("start", 0),
                    "end": e.get("end", 0),
                }
        
        return list(seen.values())
```

**Fichiers** :
- Créer : `api/services/gliner_service.py`

---

### Story 32.2: Update EntityExtractionService

**Objectif** : Remplacer `OllamaClient` par `GLiNERService`.

**Modifications** :
- `EntityExtractionService` utilise maintenant `GLiNERService`.
- Suppression de la dépendance à `OllamaClient`.
- Mise à jour des tests.

**Fichiers** :
- Modifier : `api/services/entity_extraction_service.py`
- Supprimer : `api/services/ollama_client.py`
- Supprimer : `api/services/lm_studio_client.py`

---

### Story 32.3: Remove LLM Dependencies

**Objectif** : Nettoyer le codebase des clients LLM inutiles.

**Modifications** :
- Supprimer `OllamaClient` et `LMStudioClient`.
- Retirer les variables d'environnement `OLLAMA_*` et `LM_STUDIO_*`.
- Mettre à jour `docker-compose.yml` (retirer Ollama, ajouter GLiNER model path).
- Mettre à jour `Dockerfile` (copier le modèle GLiNER, installer `gliner`).

**Fichiers** :
- Supprimer : `api/services/ollama_client.py`
- Supprimer : `api/services/lm_studio_client.py`
- Modifier : `docker-compose.yml`
- Modifier : `api/Dockerfile`
- Modifier : `api/requirements.txt` (ajouter `gliner`, retirer `json-repair` si non utilisé ailleurs)

---

### Story 32.4: Query Understanding Fallback

**Objectif** : Remplacer `QueryUnderstandingService` (LLM) par une méthode déterministe.

**Approche** :
- Utiliser une extraction de mots-clés simple (TF-IDF ou regex) pour les HL/LL keywords.
- Ou désactiver temporairement la feature si la qualité n'est pas suffisante.

**Fichiers** :
- Modifier : `api/services/query_understanding_service.py` (fallback déterministe)

---

### Story 32.5: Tests TDD

**Objectif** : Tester le nouveau service GLiNER.

**Tests** :
- `test_gliner_service.py` — Extraction, post-processing, déduplication.
- `test_entity_extraction_gliner.py` — Intégration avec `EntityExtractionService`.

**Fichiers** :
- Créer : `tests/services/test_gliner_service.py`
- Créer : `tests/services/test_entity_extraction_gliner.py`

---

## 4. Ordre d'implémentation

1. **Story 32.1** — GLiNER Service
2. **Story 32.2** — Update EntityExtractionService
3. **Story 32.3** — Remove LLM Dependencies
4. **Story 32.4** — Query Understanding Fallback
5. **Story 32.5** — Tests TDD

---

## 5. Métriques de succès

| Métrique | Cible | Mesure |
|----------|-------|--------|
| Hallucinations | **0%** | Vérification manuelle sur 50 mémoires |
| Latence extraction | <200ms | P95 response time |
| RAM supplémentaire | ~1.2 GB | `docker stats` |
| Qualité entités | >85% | Précision manuelle vs entités attendues |

---

## 6. Dépendances

- **Modèle GLiNER** : `gliner_multi-v2.1` (déjà téléchargé, ~1.2 GB)
- **Bibliothèque** : `pip install gliner`
- **Aucune dépendance externe** (Ollama/LM Studio supprimés)
