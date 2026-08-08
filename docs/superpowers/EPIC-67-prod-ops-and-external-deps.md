# 🚀 EPIC-67 : Opérations de maintenance prod + dépendances externes (skills, KERNEL)

> **Status:** EN COURS (2026-08-07 : S2 terminé ; S1 backfill relancé après la fin du backfill events EPIC-62, progression saine 0 ERROR)
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
| S1. Backfill prod | T1.1 1re tentative (2026-08-07 ~18 h) : 5 items, 2 OK / 2 ERROR (timeout 30 s sur gros textes sous contention CPU avec le backfill events EPIC-62) → ARRÊTÉ volontairement ; 2e tentative (2026-08-07 ~22 h 50, backfill events terminé 3784/3784) : RELANCÉ en détaché | ✅ |
| | T1.2 TERMINÉ le 2026-08-08 ~00 h 20 : `[856/856] OK (dim=1024)`, 0 ERROR, durée 5877 s ; psql `missing_half = 0` (39667/39667 = 100 %) ; recherche vectorielle d'échantillon : le query « parrainages presentation candidats presidentielle loi departements » remonte en position 1 la mémoire exacte « Asselineau 293, Kuzmanovic 49, Egger 36 » (score 0.0163), puis la mémoire maîtresse 58cc0e69 (0.0161), le cadre RIP (0.0158), l'investigation dilution 2027 (0.0132) ; `search_time_ms=122` | ✅ |
| S2. Skills externes | T2.1 Skill `mnemolite-mem-first` (SKILL.md) : bloc REST MAJ suite EPIC-59 (POST /v1/search/ réécrit et fiable, content/similarity SUPPRIMÉS, GET /api/v1/memories/search voie de référence) + registre EPIC-60 ajouté (casse canonique `status:CONFIRME`, namespaces réservés, `fact:verifie` obsolète, `tag_warnings` non bloquant) | ✅ |
| | T2.2 KERNEL (truth-engine) : ligne 123 `status:confirme` → `status:CONFIRME` (casse canonique) + règle du registre ajoutée (fact:verifie → status:CONFIRME, namespaces) | ✅ |

## Fichiers

- MnemoLite : aucun fichier de code modifié (l'EPIC-67 est documentaire ici).
- Externes modifiés (hors repo MnemoLite, traçabilité via cette EPIC) : `~/.agents/skills/mnemolite-mem-first/SKILL.md`, `truth-engine-v2/KERNEL.md`.
- Logs : `/tmp/bf_memory.log` (backfill memory, relancé 22 h 50), `/tmp/bf_events.log` (backfill events EPIC-62, TERMINÉ : `[3784/3784] updated=3784 failed=0` le 2026-08-07 ~22 h 20, durée 5764 s).

## Validation

- S2 : SKILL.md documente le registre EPIC-60 (casse canonique, namespaces, fact:verifie obsolète, tag_warnings) et la voie REST à jour (EPIC-59) ; KERNEL ligne 123 conforme (`status:CONFIRME`).
- S1 : backfill events EPIC-62 **terminé** (`[3784/3784] updated=3784 skipped_no_text=0 failed=0`). Backfill memory relancé à CPU libre (load ~1,5) : **TERMINÉ le 2026-08-08 ~00 h 20 : `[856/856] OK (dim=1024)`, 0 ERROR, durée 5877 s, `RESULT : 856 traités, 0 en échec`** (contre 50 % d'échec sous contention à la 1re tentative). psql : `missing_half = 0` (total et non-deleted), `39667 / 39667` = **100 % de couverture**. Relance idempotente confirmée (856 = 861 moins les 2 déjà écrites + skips).
- S1 : **recherche vectorielle d'échantillon (épreuve fonctionnelle, ~00 h 20)** : `GET /api/v1/memories/search?query=parrainages presentation candidats presidentielle loi departements&limit=4` → 200 en **122 ms** ; position 1 = mémoire exacte « Parrainages présidentielle 2022 : divergence résolue, Asselineau 293, Kuzmanovic 49, Egger 36 » (score 0.0163), position 2 = mémoire maîtresse consolidée 58cc0e69 (0.0161), position 3 = cadre juridique RIP (0.0158), position 4 = investigation dilution 2027 (0.0132). Les mémoires backfillées (dim 1024) sont bien retrouvées par recherche vectorielle sémantique.
- `search_memory(tags=["status:CONFIRME"])` (via MCP) retrouve les mémoires vérifiées (déjà le cas depuis EPIC-60 : 153 `status:CONFIRME` en base).

## Régressions

- Le backfill est idempotent (WHERE embedding_half IS NULL) : l'arrêt prématuré ne perd rien (2 mémoires écrites, les autres relançables). Relance à CPU libre (après fin du backfill events) pour éviter les timeouts 30 s sur gros textes.
- Les skills sont des dépendances externes : la MAJ est documentée ici pour traçabilité, le repo MnemoLite n'est pas modifié.
- Le KERNEL modifié (truth-engine) : changement d'une ligne de tags + ajout d'une règle, sans effet sur le pipeline (le modèle normalise la casse à l'écriture, la source est désormais conforme).
