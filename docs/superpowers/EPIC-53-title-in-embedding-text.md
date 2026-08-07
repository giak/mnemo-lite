# 📌 EPIC-53 : Titre inclus dans le texte vectorisé (P4-c)

> **Status:** DONE
> **Priority:** P1 : Améliore la retrouvabilité vectorielle immédiatement
> **Date:** 2026-08-07
> **Effort:** 10 min + test

## Problem Statement

L'embedding était calculé sur `embedding_source or content` : si l'appelant fournit un résumé (`embedding_source`, cas du write-back KERNEL), le contenu complet n'était jamais vectorisé, et le **titre** n'était jamais vectorisé du tout. Les faits présents seulement dans le contenu ou le titre étaient invisibles du vectoriel.

## Cause racine (vérifiée)

- `memory_tools.py` `_trigger_async_embedding` : `text = embedding_source or content`.
- Une seule occurrence du pattern (pas de duplication ailleurs).

## Stories / Tasks

| Story | Task | Statut |
|---|---|---|
| S1. Inclure le titre | T1.1 `text = f"{title}. {embedding_source or content}"` si titre non vide | ✅ |
| S2. Test | T2.1 `test_async_embedding_text_includes_title` : titre présent dans les 2 cas (avec et sans embedding_source) | ✅ |

## Fichiers

- `api/mnemo_mcp/tools/memory_tools.py` : +2 lignes.
- `tests/mnemo_mcp/test_memory_tools.py` : +1 test.

## Validation

- Test vert : `texts[0]` commence par le titre + contient le résumé ; `texts[1]` commence par le titre + contient le contenu complet.

## Portée documentée (non bloquant)

- Ne s'applique qu'aux futurs writes. Les mémoires existantes (dont `58cc0e69`) gardent leur ancien embedding jusqu'à un backfill/update (P7 reporté, YAGNI).
- Le chemin de régénération d'`update_memory` n'utilise pas ce builder (incohérence write/update documentée, à harmoniser lors du backfill).
