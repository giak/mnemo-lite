# 🧪 EPIC-63 : test_dual_embedding_service en mode mock (8 échecs)

> **Status:** DONE (implémenté le 2026-08-07, option A)
> **Priority:** P1 : la suite complète n'est pas 100 % verte
> **Date:** 2026-08-07
> **Effort:** 1 h

## Problem Statement

Depuis l'optimisation du run complet (EPIC-57, session 3 : `EMBEDDING_MODE=mock` dans `tests/conftest.py`), **8 tests de `tests/services/test_dual_embedding_service.py` échouent** : en mode mock, `DualEmbeddingService` ne charge jamais les modèles (`_text_model`/`_code_model` restent `None`), ce qui casse les tests de chargement/lazy-loading/dimension.

**Preuve forensique** : `git stash` complet (HEAD sans les changements de session) → **8 failed identiques**, reproductibles isolés. Échecs non causés par EPIC-61/62. En mode real (avant EPIC-57 session 3), le fichier passait 26/26.

## Tests en échec (vérifiés 2026-08-07)

- `test_lazy_loading_text_model`
- `test_lazy_loading_code_model`
- `test_lazy_loading_reuses_model`
- `test_ram_usage_after_text_load`
- `test_ram_budget_safeguard_blocks_code_model`
- `test_dimension_mismatch_detection`
- `test_model_loading_failure_text`
- `test_model_loading_failure_code`

## Cause racine

- `tests/conftest.py:21` : `os.environ["EMBEDDING_MODE"] = "mock"` posé au niveau session pour le run complet.
- `api/services/dual_embedding_service.py` (ligne ~120) : le service consulte `EMBEDDING_MODE` ; en mode mock, les modèles ne sont jamais instanciés → les tests qui vérifient le comportement de chargement réel échouent.

## Options de fix (à trancher, KISS)

| Option | Description |
|---|---|
| A. Exempter le fichier du mode mock | Fixture/session qui force `EMBEDDING_MODE=real` (avec modèles mockés) pour ce fichier uniquement, sans charger de vrais modèles |
| B. Adapter les 8 tests au contrat mock | Réécrire les assertions pour le mode mock (le service ne charge rien), ce qui vide ces tests de leur sens (ils testent le chargement réel) |
| C. Mock ciblé des modèles | Patcher `_load_text_model_sync`/`_load_code_model_sync` pour simuler le chargement quel que soit le mode |

La voie A ou C préserve la valeur des tests (vérifier le vrai comportement de chargement) ; la voie B les affaiblit.

## Décision : option A (exempter le fichier du mode mock)

`tests/services/test_dual_embedding_service.py` : fixture **autouse** `_force_real_embedding_mode` qui force `EMBEDDING_MODE=real` + `get_settings.cache_clear()` avant chaque test (restaure après).

- Zéro changement de code prod (contrat de l'EPIC respecté).
- Aucun vrai modèle chargé : `SentenceTransformer` est patché dans tous les tests qui chargent, le fichier reste rapide (5.36 s).
- Point de bascule confirmé : le service lit `get_settings().EMBEDDING_MODE` dans `__init__` (`_mock_mode`), les `_ensure_*_model` font un early-return en mock.
- L'autouse (même scope que `dual_service`) s'exécute avant les fixtures explicites : le service est construit en mode real.

## Stories / Tasks

| Story | Task | Statut |
|---|---|---|
| S1. Diagnostic | T1.1 Confirmer le contrat `EMBEDDING_MODE` dans le service et le point de bascule (`__init__` → `_mock_mode`, early-return des `_ensure_*_model`) | ✅ |
| S2. Fix | T2.1 Option A : autouse fixture `EMBEDDING_MODE=real` + `cache_clear` dans le fichier de test | ✅ |
| S3. Validation | T3.1 `test_dual_embedding_service.py` : 26/26 (avant : 8 F / 18 P) | ✅ |
| | T3.2 Voisins verts : `test_embedding_contract.py` + `test_event_service.py` 32 P, `test_api_flow.py` 18 P ; mock global intact ailleurs (aucune fuite) | ✅ |

## Fichiers

- `tests/services/test_dual_embedding_service.py` (autouse fixture `_force_real_embedding_mode`, +27 lignes)
- `tests/conftest.py` : inchangé (mock global session conservé)
- `api/services/dual_embedding_service.py` : inchangé

## Preuves de validation (2026-08-07)

| Vérification | Résultat |
|---|---|
| `test_dual_embedding_service.py` | **26/26 passed** (5.36 s, avant : 8 F / 18 P) |
| `test_embedding_contract.py` + `test_event_service.py` | **32 passed** |
| `test_api_flow.py` | **18 passed** (identique au baseline 18/0 EPIC-62) |
| Fuite de la fixture autouse | Aucune : os.environ restauré + `cache_clear` au teardown ; le mock global reste actif pour les autres fichiers |

## Validation

- Fichier complet : 26/26.
- Run complet praticable (le fichier reste rapide en mock).
- Aucun changement de code prod (les 8 tests vérifient le contrat réel, pas l'inverse).

## Régressions

- Aucune : les 8 tests sont déjà en échec (préexistants prouvés) ; le fix ne peut que réparer.
- Ne pas dégrader la lenteur du run complet (éviter un vrai chargement bge-m3 dans la suite).
