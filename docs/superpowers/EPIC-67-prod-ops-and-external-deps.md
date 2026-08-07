# 🚀 EPIC-67 : Opérations de maintenance prod + dépendances externes (skills, KERNEL)

> **Status:** BACKLOG (créé le 2026-08-07, issu de la revue des EPIC 55-61)
> **Priority:** P1 (backfill) / P2 (skills)
> **Date:** 2026-08-07
> **Effort:** variable (backfill : heures de calcul ; skills : 1 h)

## Problem Statement

Deux actions restantes, hors code nouveau, documentées dans les EPIC 58 et 60 :

1. **Backfill des embeddings jamais exécuté** : 861 mémoires sur 39 564 (2,2 %) sans `embedding_half` (vérifié en base le 2026-08-07) : invisibles de toute recherche vectorielle et du RRF hybride. Le script `scripts/backfill_memory_embeddings.py` est prêt et validé en dry-run (EPIC-58 DONE) ; l'exécution complète n'a jamais été lancée.
2. **Dépendances externes non mises à jour** : le skill global `mnemolite-mem-first` (~/.agents/skills/) et le KERNEL (projet truth-engine) ne référencent pas encore le registre des tags (EPIC-60) ni la règle « ne pas utiliser POST /v1/search/ » désormais obsolète (EPIC-59).

## Stories / Tasks

| Story | Task | Statut |
|---|---|---|
| S1. Backfill prod | T1.1 Lancer `docker compose exec api python scripts/backfill_memory_embeddings.py` (--dry-run d'abord, puis complet) | ⬜ |
| | T1.2 Vérifier `missing_half = 0` (ou rapport restant) et un échantillon de mémoires retrouvées par recherche vectorielle | ⬜ |
| S2. Skills externes | T2.1 Skill `mnemolite-mem-first` : référencer le registre EPIC-60 (casse canonique `status:CONFIRME`, namespaces, warning `tag_warnings`), retirer la règle « ne pas utiliser POST /v1/search/ » (remplacée par le POST unifié) | ⬜ |
| | T2.2 KERNEL (truth-engine) : aligner les tags posés sur le registre (status:CONFIRME, kernel, fact:verifie → status:CONFIRME) | ⬜ |

## Fichiers

- MnemoLite : aucun (opération de données + scripts existants).
- Externes : `~/.agents/skills/mnemolite-mem-first/SKILL.md`, KERNEL de truth-engine.

## Validation

- `SELECT count(*) FROM memories WHERE embedding_half IS NULL AND deleted_at IS NULL` → 0.
- `search_memory(tags=["status:CONFIRME"])` (via MCP) retrouve les mémoires vérifiées.
- Le skill documente le registre EPIC-60 et le POST /v1/search/ unifié.

## Régressions

- Le backfill est idempotent (WHERE embedding_half IS NULL) : relance sans danger, à heure creuse (opération longue, ~0,04 m/s après chargement du modèle selon EPIC-58).
- Les skills sont des dépendances externes : la MAJ est documentée ici pour traçabilité, le repo MnemoLite n'est pas modifié.
