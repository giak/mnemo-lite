# 🏷️ EPIC-60 : Registre central des conventions de tags (schéma forensique unifié)

> **Status:** BACKLOG (proposé le 2026-08-07)
> **Priority:** P2 : documentation d'abord, validation douce ensuite (après EPIC-56/57, base stable)
> **Date:** 2026-08-07
> **Effort:** 1 h

## Problem Statement

Les mémoires réelles du corpus truth-engine portent **4 variantes qui coexistent déjà** (vérifié en base le 2026-08-07) :

- `status:CONFIRME` (majuscule, imposé par le skill global et le KERNEL)
- `status:confirme` (minuscule, mémoires parrainages/ARCOM écrites en session)
- `fact:verifie` (variante du KERNEL)
- `kernel` (tag non documenté dans le skill, posé par le KERNEL)

Conséquence : une recherche par tag (`tags=["status:CONFIRME"]`) rate les mémoires taguées en minuscule ; le statut forensique d'une mémoire n'est pas fiablement requêtable. Aucun registre central n'existe côté serveur (grep `known_tags`/`TAG_REGISTRY`/`valid_tags` dans `api/` : vide).

## Cause racine (vérifiée)

- Le skill global et le KERNEL imposent chacun leurs conventions ; le serveur **n'enforce rien** (aucune validation des tags au write).
- Les écrivains (KERNEL, skills, sessions manuelles) sont libres dans la casse et le vocabulaire.

## Stories / Tasks

| Story | Task | Statut |
|---|---|---|
| S1. Documentation | T1.1 Ajouter un registre des tags dans `MCP_SETUP.md` (racine du repo) : casse canonique (`status:CONFIRME`), familles (status, project, fact, kind, sys, memory), liste autorisée | ⬜ |
| | T1.2 Documenter le tag `kernel` (KERNEL) et les tags `fact:verifie` → normalisés en `fact:verifie` (si retenu) ou `status:CONFIRME` | ⬜ |
| S2. Validation douce au write | T2.1 `warning` (non bloquant) si tag hors liste autorisée OU si une mémoire forensique n'a pas de tag `status:*` | ⬜ |
| | T2.2 Normalisation douce de la casse : `status:confirme` → `status:CONFIRME` au write (décision produit à valider) | ⬜ |
| S3. Tests | T3.1 `test_write_warns_on_missing_status_tag` : write sans `status:*` → warning dans la réponse, pas d'erreur | ⬜ |
| | T3.2 `test_write_warns_on_unknown_tag` | ⬜ |
| | T3.3 `test_status_case_normalized` : si T2.2 retenu, `status:confirme` → `status:CONFIRME` | ⬜ |

## Fichiers

- `MCP_SETUP.md` (racine) : registre des tags.
- `api/mnemo_mcp/tools/memory_tools.py` (WriteMemoryTool) : warning + normalisation douce.
- `tests/mnemo_mcp/test_memory_tools.py` : +3 tests.

## Validation

- `search_memory(tags=["status:CONFIRME"])` retrouve les mémoires vérifiées (qu'elles aient été écrites en minuscule ou majuscule, après normalisation rétroactive ou au write).
- Aucune écriture existante n'est cassée (warning non bloquant).

## Régressions

- La validation est **douce** (warning) : aucun write existant ne devient bloquant.
- La normalisation de casse au write est un changement de contrat de données : vérifier les requêtes par tag en minuscule existantes (elles continueront à matcher si la recherche est insensible à la casse, sinon documenter).
- Dépendance externe : mise à jour du skill `mnemolite-mem-first` et du KERNEL pour référencer le registre (après EPIC-56/57, comme convenu).
