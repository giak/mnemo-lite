# EPIC-35: Search UX & Intelligence

**Status**: DRAFT | **Created**: 2026-04-02 | **Effort**: ~8 points | **Stories**: 5

---

## Context

La recherche fonctionne maintenant (EPIC-32) mais manque de fonctionnalités UX
qui amélioreraient significativement l'expérience utilisateur.

### État actuel

| Feature | Status | Notes |
|---------|--------|-------|
| Recherche hybride (lexical + vectoriel) | ✅ | Fonctionnel |
| BM25 reranking | ✅ | Activé par défaut |
| Tag-only search | ✅ | Skip embedding |
| Cache search results | ✅ | Redis L2 |
| **Highlighting** | ❌ | Termes non surlignés |
| **Deduplication** | ❌ | Mêmes fichiers multiples |
| **Query rewriting** | ❌ | Pas de synonymes |
| **Search analytics UI** | ❌ | Endpoints existent, pas d'UI |
| **Search suggestions** | ❌ | Pas d'autocomplete |

---

## Stories

### Story 35.1: Search result highlighting
**Priority**: P1 | **Effort**: 2 pts | **Value**: High

**Problème** : Les résultats de recherche ne montrent pas où les termes
correspondants apparaissent dans le contenu.

**Solution** : Surligner les termes de la query dans les extraits de résultats.

**Implémentation** :
```python
# api/services/highlight_service.py
def highlight_matches(text: str, query: str, max_snippets: int = 3) -> list[dict]:
    """Find matching spans and return highlighted snippets."""
    tokens = re.findall(r'\w+', query.lower())
    # Find best matching snippets with <mark> tags
    # Return list of { snippet, highlighted_text, score }
```

**Frontend** :
```vue
<!-- Dans les résultats de search -->
<span v-html="highlightedContent"></span>

<!-- CSS -->
::v-deep mark {
  background: rgba(6, 182, 212, 0.3);
  color: white;
  border-radius: 2px;
  padding: 0 2px;
}
```

**Fichiers** :
- `api/services/highlight_service.py` (nouveau)
- `api/mnemo_mcp/tools/search_tool.py` — Ajouter `highlights` dans la réponse
- `api/mnemo_mcp/tools/memory_tools.py` — Ajouter `highlights` dans la réponse
- `frontend/src/components/SearchResultItem.vue` (nouveau)

**Critères de complétion** :
- [ ] Termes de la query surlignés dans les snippets
- [ ] Max 3 snippets par résultat
- [ ] Fonctionne pour code search et memory search
- [ ] Performance: <5ms overhead par résultat

---

### Story 35.2: Search result deduplication
**Priority**: P1 | **Effort**: 1.5 pts | **Value**: High

**Problème** : Un même fichier peut apparaître plusieurs fois dans les résultats
(chunks différents du même fichier).

**Solution** : Option de déduplication par fichier, gardant le meilleur chunk.

**Implémentation** :
```python
def deduplicate_by_file(results: list[dict], keep_best: bool = True) -> list[dict]:
    """Remove duplicate file paths, keeping the best-scoring chunk."""
    seen = {}
    for r in results:
        fp = r.get("file_path") or r.get("metadata", {}).get("file_path")
        if fp not in seen or r.get("score", 0) > seen[fp].get("score", 0):
            seen[fp] = r
    return list(seen.values())
```

**API** : Ajouter paramètre `deduplicate=true` (default: false)

**Fichiers** :
- `api/services/hybrid_code_search_service.py` — Ajouter `deduplicate` param
- `api/mnemo_mcp/tools/search_tool.py` — Exposer `deduplicate` parameter

**Critères de complétion** :
- [ ] Paramètre `deduplicate` dans search_code
- [ ] Par défaut: désactivé (backward compatible)
- [ ] Tests vérifient la déduplication

---

### Story 35.3: Query rewriting & synonyms
**Priority**: P2 | **Effort**: 2 pts | **Value**: Medium

**Problème** : "auth" ne trouve pas "authentication", "db" ne trouve pas "database".

**Solution** : Dictionnaire de synonymes + expansion de query optionnelle.

**Implémentation** :
```python
# api/services/query_rewriter.py
SYNONYMS = {
    "auth": ["authentication", "authorization", "login"],
    "db": ["database", "postgres", "postgresql"],
    "cache": ["cache", "redis", "memcached"],
    "api": ["api", "endpoint", "route", "handler"],
    "func": ["function", "def", "method"],
    "class": ["class", "type", "struct"],
    "err": ["error", "exception", "fail"],
    "req": ["request", "req", "http"],
    "resp": ["response", "resp", "return"],
    "config": ["config", "setting", "option", "env"],
}

def rewrite_query(query: str, expand: bool = True) -> str:
    """Expand query with synonyms for better recall."""
    if not expand:
        return query
    tokens = query.lower().split()
    expanded = []
    for token in tokens:
        expanded.append(token)
        expanded.extend(SYNONYMS.get(token, []))
    return " ".join(expanded)
```

**API** : Ajouter paramètre `rewrite=true` (default: false)

**Fichiers** :
- `api/services/query_rewriter.py` (nouveau)
- `api/services/hybrid_code_search_service.py` — Intégrer query rewriting
- `api/mnemo_mcp/tools/search_tool.py` — Exposer `rewrite` parameter

**Critères de complétion** :
- [ ] Dictionnaire de 20+ synonymes
- [ ] Paramètre `rewrite` dans search_code
- [ ] Tests vérifient l'expansion de query

---

### Story 35.4: Search analytics dashboard UI
**Priority**: P2 | **Effort**: 1.5 pts | **Value**: Medium

**Problème** : Les endpoints analytics existent mais pas d'interface visuelle.

**Solution** : Page `/search-analytics` avec graphiques et statistiques.

**Fonctionnalités** :
- Top 10 queries les plus fréquentes
- Queries sans résultats (zero-result)
- Queries lentes (>500ms)
- Cache hit rate over time
- Distribution des scores de recherche

**Fichiers à créer** :
- `frontend/src/pages/SearchAnalytics.vue`
- `frontend/src/composables/useSearchAnalytics.ts`

**Fichiers à modifier** :
- `frontend/src/router.ts` — Ajouter route `/search-analytics`
- `frontend/src/components/Navbar.vue` — Lien vers analytics

**Critères de complétion** :
- [ ] Page `/search-analytics` fonctionnelle
- [ ] Graphiques avec Chart.js
- [ ] Auto-refresh 60s
- [ ] Export des données

---

### Story 35.5: Search suggestions / autocomplete
**Priority**: P3 | **Effort**: 1 pt | **Value**: Medium

**Problème** : Pas de suggestions pendant la saisie de la query.

**Solution** : Autocomplete basé sur les queries passées et les termes du codebase.

**Implémentation** :
- Utiliser les queries récentes du cache Redis comme suggestions
- Compléter avec les noms de fonctions/classes du codebase (via graph)
- Debounce 200ms pour éviter trop d'appels

**Fichiers** :
- `api/routes/search_suggestions_routes.py` (nouveau)
- `frontend/src/components/SearchAutocomplete.vue` (nouveau)
- `frontend/src/composables/useSearchSuggestions.ts` (nouveau)

**Critères de complétion** :
- [ ] Suggestions apparaissent après 2 caractères
- [ ] Debounce 200ms
- [ ] Max 5 suggestions
- [ ] Navigation clavier (flèches haut/bas, Enter)

---

## Ordre d'exécution

```
Phase 1 (Quick Wins, ~3.5h)
  35.1 → Search result highlighting
  35.2 → Search result deduplication

Phase 2 (Intelligence, ~4h)
  35.3 → Query rewriting & synonyms
  35.4 → Search analytics dashboard UI

Phase 3 (UX Polish, ~1h)
  35.5 → Search suggestions / autocomplete
```

---

## Critères de complétion

- [ ] Termes de recherche surlignés dans les résultats
- [ ] Déduplication par fichier optionnelle
- [ ] Query rewriting avec 20+ synonymes
- [ ] Dashboard analytics fonctionnel
- [ ] Autocomplete avec suggestions
- [ ] 358+ tests MCP passing
- [ ] Performance: <10ms overhead total pour toutes les features

---

## Métriques de succès

| Métrique | Avant | Après | Cible |
|----------|-------|-------|-------|
| Highlighting | ❌ | ✅ | ✅ |
| Deduplication | ❌ | ✅ | ✅ |
| Synonymes | 0 | 20+ | 20+ |
| Analytics UI | ❌ | ✅ | ✅ |
| Autocomplete | ❌ | ✅ | ✅ |
| Search overhead | 0ms | <10ms | <10ms |
