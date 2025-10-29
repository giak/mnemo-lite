# Archive: EPIC-20 Observability

**Archived**: 2025-10-23
**Status**: Obsolète, non implémenté
**Reason**: Epic conceptuel qui n'a jamais été validé pour implémentation

---

## Contexte

EPIC-20 était un brainstorming sur l'observabilité de MnemoLite (logs, Redis, PostgreSQL, API monitoring).

Deux documents ont été créés:
1. `EPIC-20_OBSERVABILITY_ULTRATHINK.md` (~1400 lignes) - Brainstorming complet
2. `EPIC-20_MVP_PHASE1_IMPLEMENTATION.md` (~2400 lignes) - Plan d'implémentation détaillé

---

## Pourquoi Archivé

1. **Jamais validé**: L'EPIC n'a jamais été approuvé pour implémentation
2. **Priorités changées**: D'autres EPICs plus critiques ont pris le dessus (EPIC-19, EPIC-21-LITE)
3. **Spéculatif**: Proposait des features sans validation du besoin réel (YAGNI)
4. **Over-engineering**: Trop de features pour un MVP

---

## Contenu Archivé

### `ARCHIVE_2025-10-23_EPIC-20_OBSERVABILITY_ULTRATHINK.md`

**Contenu**: Brainstorming complet sur observabilité
- API monitoring (latency, throughput, errors)
- Redis monitoring (hit rate, memory, keys)
- PostgreSQL monitoring (connections, queries, slow queries)
- Logs streaming (SSE)
- System metrics (CPU, RAM, disk)

**Points proposés**: 21 pts (MVP: 5pts, Standard: 8pts, Nice-to-have: 8pts)

**Architecture**: PostgreSQL pour métriques, structlog, Chart.js, SSE

### `ARCHIVE_2025-10-23_EPIC-20_MVP_PHASE1_IMPLEMENTATION.md`

**Contenu**: Plan d'implémentation détaillé MVP Phase 1
- Schemas PostgreSQL (table metrics)
- Services (MetricsRecorder, MetricsCollector)
- API endpoints design
- UI templates (HTMX + Chart.js)
- JavaScript SSE implementation
- 5-day implementation plan

**Estimation**: 5 jours

---

## Leçons Apprises

1. **Valider avant d'ultrathink**: Ne pas créer 4000 lignes de docs sans validation du besoin
2. **YAGNI**: Pas besoin de monitoring tant que pas de problème de performance identifié
3. **KISS**: Si besoin de monitoring, commencer simple (logs + quelques KPIs basiques)

---

## Utilité Future

Ces documents peuvent être utiles **si et seulement si**:
- Un problème de performance est identifié en production
- Le besoin de monitoring est explicitement validé
- Les métriques critiques sont définies

Dans ce cas:
1. Reprendre `ARCHIVE_2025-10-23_EPIC-20_OBSERVABILITY_ULTRATHINK.md`
2. Filtrer ce qui est vraiment nécessaire (KISS)
3. Créer un nouvel EPIC avec scope réduit

---

## Références

- Archived from: `docs/agile/serena-evolution/`
- Date: 2025-10-23
- Author: Claude Code + User
- Skills consulted: `document-lifecycle`, `epic-workflow`

---

**Ne pas réimplémenter sans validation explicite du besoin.**
