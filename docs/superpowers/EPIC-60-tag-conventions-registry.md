# 🏷️ EPIC-60 : Registre central des conventions de tags (schéma forensique unifié)

> **Status:** ✅ DONE (implémenté et validé le 2026-08-07)
> **Priority:** P2 : documentation d'abord, validation douce ensuite (après EPIC-56/57, base stable)
> **Date:** 2026-08-07
> **Effort:** ~2 h

## Problem Statement

Les mémoires réelles portaient 4 variantes coexistantes (vérifié en base le 2026-08-07) :

- `status:confirme` (minuscule, 152 occurrences) : forme dominante en base.
- `fact:verifie` (1 occurrence, variante du KERNEL).
- `kernel` (189 + variantes kernel-v2/v3/apex) : tag posé par le KERNEL, non documenté.
- `status:CONFIRME` (majuscule) : **zéro occurrence** en base, alors que c'est la casse canonique imposée par le skill global et le KERNEL.

Conséquence : une recherche `tags=["status:CONFIRME"]` ne trouvait rien ; le statut forensique n'était pas fiablement requêtable.

## Cause racine (prouvée forensiquement le 2026-08-07)

**Le validateur pydantic `_normalize_tags` (api/mnemo_mcp/models/memory_models.py) lowercaisait tous les tags** (`.strip().lower()`), annulant toute majuscule à l'écriture. Les 152 `status:confirme` existaient non pas par négligence des écrivains mais par construction : le modèle forçait la minuscule, en conflit direct avec la convention `status:CONFIRME`.

Preuve : debug dans le conteneur (process réel) : `MemoryCreate(tags=["status:confirme", "Kernel", "Status:DOUTE", "  Foo "])` → `['status:CONFIRME', 'kernel', 'status:DOUTE', 'foo']`.

## Décisions (KISS / DRY / YAGNI)

| Story | Task | Décision | Statut |
|---|---|---|---|
| S1. Documentation | T1.1 Registre des tags dans `MCP_SETUP.md` (section 8) : casse canonique, familles, namespaces réservés (status, fact, project, sys, session, date, source), tags documentés (kernel*, tags d'import) | ✅ |
| | T1.2 `kernel` documenté ; `fact:verifie` = obsolète, remplacé au write par `status:CONFIRME` (warning informatif) | ✅ |
| S2. Validation douce | T2.1 `tag_warnings` non bloquant : namespace inconnu, statut inconnu, mémoire `kernel*` sans `status:*`, casse normalisée | ✅ |
| | T2.2 Normalisation de casse `status:*` → MAJUSCULE, garantie au niveau du **modèle** (`_normalize_tags`) + au niveau du tool (`process_tags`) | ✅ |
| S3. Tests | T3.1 `test_write_warns_on_missing_status_tag` (kernel sans status -> warning) | ✅ |
| | T3.2 `test_write_warns_on_unknown_tag` (foo:bar -> warning, tag conservé) | ✅ |
| | T3.3 `test_status_case_normalized` (status:confirme -> status:CONFIRME au write) | ✅ |
| | + `test_fact_verifie_obsolete_replaced` (fact:verifie -> status:CONFIRME + warning) | ✅ |

### Architecture (DRY)

- `api/mnemo_mcp/tag_registry.py` (nouveau) : registre `TAG_NAMESPACES`, `OBSOLETE_TAGS`, fonction pure `process_tags(tags) -> (normalized, warnings)`.
- **Namespaces réservés mais non standardisés** (`kind`, `memory`, mentionnés dans l'EPIC d'origine) : absents du registre volontairement (non observés en base, non standardisés) ; un tag `kind:*`/`memory:*` déclenche un warning « namespace inconnu » jusqu'à leur standardisation.
- `WriteMemoryTool` et `UpdateMemoryTool` : appellent `process_tags` avant le write, ajoutent `tag_warnings` à la réponse (champ optionnel, comme `duplicate_warning`).
- `memory_models._normalize_tags` : **cause racine corrigée** : préserve la casse MAJ du namespace `status`, lowercase le reste, et remplace `fact:verifie` -> `status:CONFIRME` (DRY : le modèle est la garantie pour TOUS les points d'écriture, MCP, REST, repo, consolidation). Le warning « obsolète » reste émis par le tool `process_tags` (exécuté avant le write).

### Migration rétroactive (exécutée, base prod)

```
UPDATE memories SET tags = (SELECT array_agg(CASE
    WHEN lower(t) = 'fact:verifie' THEN 'status:CONFIRME'
    WHEN lower(t) LIKE 'status:%' THEN 'status:' || upper(split_part(t, ':', 2))
    ELSE t END) FROM unnest(tags) t)
WHERE deleted_at IS NULL AND EXISTS (SELECT 1 FROM unnest(tags) t
      WHERE lower(t) LIKE 'status:%' OR lower(t) = 'fact:verifie');
```
- Avant : 152 `status:confirme` + 1 `fact:verifie`, 0 `status:CONFIRME`.
- Après : **153 `status:CONFIRME`, 0 minuscule, 0 fact:verifie** (UPDATE 152 lignes ; la mémoire fact:verifie portait aussi status:confirme).

## Validation

| Vérification | Résultat |
|---|---|
| `tests/mnemo_mcp/test_memory_tools.py` (+4 tests EPIC-60) | 6/6 sur les tests ciblés, suite complète verte |
| `tests/mnemo_mcp/test_memory_models.py` | 33/34 (1 échec préexistant : `test_memory_type_count` attend 6 types, l'enum en a 8 (ARTICLE/QUINTESSENCE ajoutés sans MAJ du test) ; prouvé préexistant par stash HEAD) |
| Collecte complète | 1655 tests (+4), 0 erreur |
| Preuve prod (process réel) | `MemoryCreate(tags=["status:confirme","Kernel","Status:DOUTE","  Foo "])` → `['status:CONFIRME','kernel','status:DOUTE','foo']` |
| Migration base | 153 `status:CONFIRME`, zéro écart |

## Régressions

- Validation douce : aucun write existant ne devient bloquant.
- Changement de contrat de données : la casse des tags `status:*` stockés change (minuscule -> MAJUSCULE). Les recherches par tag `status:confirme` (minuscule) ne matcheront plus : c'est l'objectif (casse canonique). Documenté dans MCP_SETUP.md section 8.
- Préexistant hors périmètre : `test_memory_type_count` (count d'enum périmé).
- Dépendance externe : mise à jour du skill `mnemolite-mem-first` et du KERNEL pour référencer le registre (à faire côté skill, hors repo MnemoLite).
