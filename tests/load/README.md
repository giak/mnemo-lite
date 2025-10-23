# Load Tests - Performance & Scalability

Tests de charge pour valider la performance et la scalabilité des différents services MnemoLite.

## 📂 Contenu

### `test_embedding_load.py`

Test de charge progressive pour le système d'embeddings (EPIC-18).

**Phases testées** :
- Phase 1: 10 queries (warmup)
- Phase 2: 50 queries (charge légère)
- Phase 3: 100 queries (charge moyenne)
- Phase 4: 500 queries (charge élevée)
- Phase 5: 1000 queries (charge extrême)

**Métriques mesurées** :
- Latence (P50, P95, P99, max)
- Throughput (queries/sec)
- Taux de succès
- Utilisation mémoire

**Usage** :

```bash
# Dans le container Docker
docker exec mnemo-api python /app/tests/load/test_embedding_load.py

# Ou localement (si environnement configuré)
cd /home/giak/Work/MnemoLite
python tests/load/test_embedding_load.py
```

**Mode** :
- Utilise la variable d'environnement `EMBEDDING_MODE` (mock ou real)
- Recommandé : `EMBEDDING_MODE=real` pour tests de performance réels

**Durée** : ~4-5 minutes (1660 queries testées)

**Résultats** :
- Rapport détaillé : `docs/agile/EPIC-18_LOAD_TEST_REPORT.md`
- Performance attendue : P95 < 200ms, throughput ~7 q/s

---

## 🚀 Lancement Rapide

```bash
# Test de charge embeddings
docker exec mnemo-api python /app/tests/load/test_embedding_load.py
```

---

## 📊 Interprétation des Résultats

### Latence

| Métrique | Bon | Acceptable | Problème |
|----------|-----|------------|----------|
| P50 | < 100ms | < 150ms | > 200ms |
| P95 | < 150ms | < 200ms | > 300ms |
| P99 | < 200ms | < 300ms | > 500ms |

### Throughput

| Service | Bon | Acceptable | Problème |
|---------|-----|------------|----------|
| Embeddings | > 5 q/s | > 3 q/s | < 1 q/s |

### Mémoire

- **Warmup** : +500-600 MB (chargement modèles ML) = Normal
- **Runtime** : < 50 MB par 1000 queries = Bon
- **Memory leak** : > 100 MB par 1000 queries = Problème

### Success Rate

- **Excellent** : 100%
- **Bon** : > 99%
- **Acceptable** : > 95%
- **Problème** : < 95%

---

## 🎯 Objectifs de Performance

### Embeddings (EPIC-18)

```
✅ Latence P95 : < 200ms
✅ Latence P99 : < 500ms
✅ Throughput : > 5 q/s
✅ Success Rate : > 95%
✅ Pas de memory leak
✅ Stable sous charge
```

**Status actuel** : ✅ Tous les objectifs atteints (voir rapport détaillé)

---

## 📝 Ajouter de Nouveaux Tests de Charge

Template pour nouveau test :

```python
#!/usr/bin/env python3
"""
Load Test: [Service Name]

Description du test...
"""

import asyncio
import time
import statistics
from typing import List

# Votre code ici...

async def run_load_test_phase(phase_name: str, num_requests: int):
    """Exécute une phase de test."""
    metrics = LoadTestMetrics(phase_name)
    metrics.start()

    for i in range(num_requests):
        try:
            latency = await test_operation()
            metrics.record_latency(latency)
        except Exception as e:
            metrics.record_error(str(e))

    metrics.finish()
    return metrics

async def main():
    phases = [
        ("Phase 1", 10),
        ("Phase 2", 50),
        ("Phase 3", 100),
    ]

    metrics_list = []
    for phase_name, num_requests in phases:
        metrics = await run_load_test_phase(phase_name, num_requests)
        metrics_list.append(metrics)

    # Afficher rapport...

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 🔗 Liens

- **Rapport EPIC-18** : `docs/agile/EPIC-18_LOAD_TEST_REPORT.md`
- **Logs structurés** : `api/utils/search_metrics.py`
- **Guide embeddings** : `docs/examples/embedding_search_guide.md`

---

**Créé** : 2025-10-23 (EPIC-18)
**Version** : 1.0
