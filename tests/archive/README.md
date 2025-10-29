# Tests Archivés - EPIC-24

**Date**: 2025-10-28
**Raison**: Tests obsolètes remplacés par suite MCP complète

## Fichiers Archivés

### main_obsolete.py
**Date Originale**: 2025-10-14
**Remplacé Par**: `api/main.py` (2025-10-24)
**Raison**: Point d'entrée FastAPI obsolète, remplacé par version plus récente dans `api/`

### Tests - Remplacés par `tests/mcp/test_mcp_phase1_unit.py` & `test_mcp_phase2_integration.py`

| Fichier Original | Taille | Remplacé Par | Raison |
|------------------|--------|--------------|--------|
| `test_double_check.py` | 4.0K | Phase 1 & 2 | Tests end-to-end incomplets |
| `test_memory_integration.py` | 4.1K | Phase 2 test 2.1 | Write→Read cycle |
| `test_memory_search.py` | 3.4K | Phase 2 test 2.2 | Semantic search |
| `test_memory_service_injection.py` | 2.4K | Phase 1 (all) | Service injection validation |
| `test_search_conversations.py` | 3.7K | Phase 2 test 2.2 | Conversation search |
| `test_write_memory_fix.py` | 7.8K | Phase 1 test 1.1-1.5 | write_memory validation |

## Tests MCP Actuels (100% Pass Rate)

### tests/mcp/test_mcp_phase1_unit.py (5/5 PASS)
- ✅ 1.1: write_memory simple conversation
- ✅ 1.2: write_memory complex (code blocks)
- ✅ 1.3: write_memory special chars (UTF-8, emoji)
- ✅ 1.4: write_memory long content (10K)
- ✅ 1.5: write_memory multiple tags (7 tags)

### tests/mcp/test_mcp_phase2_integration.py (5/5 PASS)
- ✅ 2.1: Write → Read cycle
- ✅ 2.2: Write → Search → Verify (semantic)
- ✅ 2.3: Write Multiple → List Filtered (tags)
- ✅ 2.4: Write → Read Performance (<100ms avg)
- ✅ 2.5: Concurrent Writes (5 parallel, no races)

## Avantages de la Nouvelle Suite

1. **MCP-Only Testing**: Teste via interface publique (pas de shortcuts SQL)
2. **Bug Discovery**: A révélé 2 bugs critiques (MemoryResponse, MemoryFilters)
3. **Comprehensive**: Couvre unit + integration + performance
4. **Documented**: 60K de documentation (EPIC-24_*.md)
5. **Validated**: 10/10 tests PASS (100% success rate)

## Documentation

Voir: `docs/agile/serena-evolution/03_EPICS/EPIC-24_MCP_TESTING_BUGS_FOUND.md`

---

**Note**: Ces tests peuvent être restaurés depuis l'archive si nécessaire, mais la suite MCP est maintenant la référence.
