# Inventaire des Tests MnemoLite

**Version:** 2.0.0
**Dernière mise à jour:** 2025-10-17
**Statut:** 245 tests passing (102 Agent Memory + 126 Code Intelligence + 17 Integration)

Ce document recense les tests automatisés du projet MnemoLite, collectés via `pytest --collect-only`.

## ⚠️ Notes EPIC-06 (v2.0.0) - Code Intelligence

MnemoLite v2.0.0 introduit **126 nouveaux tests Code Intelligence** pour valider :
- **Indexation** : 7-step pipeline (language detection → AST parsing → chunking → metadata → dual embedding → graph → storage)
- **Recherche hybride** : Lexical (pg_trgm) + Vector (HNSW) + RRF fusion
- **Graphe de dépendances** : Construction et traversée (recursive CTEs, ≤3 hops, 0.155ms)
- **Dual embeddings** : TEXT (768D) + CODE (768D) pour recherche sémantique
- **API** : 12 nouveaux endpoints `/v1/code/*`

**Nouveaux fichiers de tests Code Intelligence** :
- `test_code_chunk_repository.py` (20 tests) - CRUD + recherche vectorielle/lexicale
- `test_graph_construction_service.py` (11 tests) - Construction graphe de dépendances
- `test_graph_traversal_service.py` (9 tests) - Traversée recursive CTEs
- `test_code_metadata_service.py` (15 tests) - Extraction metadata AST
- `test_ast_parser_service.py` (18 tests) - Parsing tree-sitter multi-langages
- `test_code_search_routes.py` (22 tests) - API endpoints code search
- `test_lexical_search_service.py` (8 tests) - Recherche pg_trgm
- `test_vector_search_service.py` (10 tests) - Recherche HNSW
- `test_rrf_fusion_service.py` (6 tests) - Fusion RRF
- `test_hybrid_code_search_service.py` (7 tests) - Orchestration hybride

## ⚠️ Notes Phase 3.4 (v1.3.0)

Suite à la consolidation de l'architecture autour d'EventRepository, **3 fichiers de tests obsolètes ont été supprimés** :
- `test_memory_repository.py` - MemoryRepository n'existe plus
- `test_memory_protocols.py` - MemoryRepositoryProtocol supprimé
- `test_memory_routes.py` - Routes `/v0/memories` retirées

**Nouveau fichier ajouté** :
- `test_search_fallback.py` - Tests pour le mécanisme de fallback automatique des recherches vectorielles

---

## tests/db/repositories/test_event_repository.py

- `test_event_repository_instantiation`: Teste si EventRepository peut être instancié avec un moteur mocké.
- `test_add_event_success`: Teste l'ajout réussi d'un événement.
- `test_get_event_by_id_success`: Teste la récupération réussie d'un événement par ID.
- `test_get_event_by_id_not_found`: Teste le cas où l'événement n'est pas trouvé par ID.
- `test_delete_event_success`: Teste la suppression réussie d'un événement.
- `test_delete_event_not_found`: Teste la suppression quand l'ID n'existe pas.
- `test_filter_by_metadata_found`: Teste le filtrage par métadonnées quand des événements correspondent.
- `test_filter_by_metadata_not_found`: Teste le filtrage par métadonnées quand aucun événement ne correspond.
- `test_search_vector_metadata_only`: Teste la recherche vectorielle en utilisant uniquement des filtres de métadonnées (pas de vecteur de requête).
- `test_search_vector_vector_only`: Teste la recherche vectorielle en utilisant uniquement un vecteur de requête (pas de filtres de métadonnées).
- `test_search_vector_hybrid`: Teste la recherche vectorielle combinant un vecteur de requête et des filtres de métadonnées.
- `test_build_add_query`: Teste la construction de la requête SQL pour ajouter un événement.
- `test_build_get_by_id_query`: Teste la construction de la requête SQL pour récupérer un événement par ID.
- `test_build_update_metadata_query`: Teste la construction de la requête SQL pour mettre à jour les métadonnées d'un événement.
- `test_build_delete_query`: Teste la construction de la requête SQL pour supprimer un événement.
- `test_build_filter_by_metadata_query`: Teste la construction de la requête SQL pour filtrer par métadonnées.
- `test_build_search_vector_query_vector_only`: Teste la construction de la requête de recherche vectorielle avec seulement un vecteur.
- `test_build_search_vector_query_metadata_only`: Teste la construction de la requête de recherche vectorielle avec seulement des métadonnées.
- `test_build_search_vector_query_time_only`: Teste la construction de la requête de recherche vectorielle avec seulement un filtre temporel.
- `test_build_search_vector_query_hybrid`: Teste la construction de la requête de recherche vectorielle hybride (vecteur + métadonnées + temps).
- `test_build_search_vector_query_no_criteria`: Teste la construction de la requête de recherche vectorielle sans aucun critère.
- `test_build_search_vector_query_invalid_dimension`: Teste la construction de la requête de recherche vectorielle avec un vecteur de dimension invalide.

## tests/db/repositories/test_memory_repository.py

**[OBSOLETE - Phase 3.4]** Ce fichier de test a été supprimé lors de la consolidation autour d'EventRepository. MemoryRepository n'existe plus dans la codebase.

## tests/test_dependency_injection.py

- `test_injection_in_event_routes`
- `test_injection_in_memory_routes`
- `test_chain_of_dependencies`
- `test_dependency_error_handling`: Teste la gestion des erreurs lorsqu'une dépendance requise n'est pas disponible.

## tests/test_embedding_service.py

- `test_generate_embedding`
- `test_generate_embedding_with_protocol_mock`
- `test_compute_similarity_with_protocol_mock`
- `test_generate_embedding_empty_text`
- `test_dimension_property`
- `test_cosine_similarity`
- `test_batch_embedding`
- `test_normalize_embedding`
- `test_error_handling`
- `test_similarity_method`

## tests/test_event_processor.py

- `test_process_event`: Teste le traitement d'un événement, vérifiant l'enrichissement des métadonnées et la génération d'embedding.
- `test_process_event_with_existing_embedding`
- `test_process_event_update_failure`
- `test_generate_memory_from_event`: Teste la génération d'une mémoire à partir d'un événement.
- `test_process_event_with_error`: Teste le comportement du processeur lors d'une erreur pendant la génération d'embedding.
- `test_generate_memory_from_event_with_error`
- `test_process_event_with_uncaught_error`
- `test_process_event_different_embedding_dimensions`
- `test_process_event_null_metadata`
- `test_generate_memory_from_event_with_embedding`
- `test_process_event_specific_update_exception`
- `test_event_processor_initialization`

## tests/test_event_routes.py

- `test_get_event_success_with_mock`
- `test_get_event_not_found_with_mock`
- `test_create_event_success`
- `test_update_event_metadata_success`
- `test_update_event_metadata_not_found`
- `test_delete_event_success`
- `test_delete_event_not_found`
- `test_filter_events_by_metadata`
- `test_search_events_by_embedding`
- `test_get_event_success_with_patch`: Teste la récupération réussie via l'API en patchant `EventRepository.get_by_id`.
- `test_get_event_not_found_with_patch`: Teste le cas 404 via l'API en patchant `EventRepository.get_by_id`.

## tests/test_health_routes.py

- `test_readiness_success`
- `test_readiness_failure`
- `test_health_check_unexpected_error`
- `test_health_check_success`
- `test_health_check_degraded`
- `test_metrics_endpoint`
- `test_check_postgres_no_database_url`
- `test_check_postgres_connection_error`
- `test_check_postgres_success`
- `test_health_check_metrics_calls`
- `test_health_check_metric_error_handling`

## tests/test_memory_protocols.py

**[OBSOLETE - Phase 3.4]** Ce fichier de test a été supprimé. MemoryRepositoryProtocol n'existe plus suite à la consolidation vers EventRepository.

## tests/test_memory_routes.py

**[OBSOLETE - Phase 3.4]** Ce fichier de test a été supprimé. Les routes `/v0/memories` ont été retirées de l'API lors du nettoyage Phase 2.

## tests/test_memory_search_service.py

- `test_search_by_content`: Teste la recherche de mémoires par contenu textuel.
- `test_search_by_metadata`: Teste la recherche de mémoires par métadonnées.
- `test_search_by_similarity`: Teste la recherche de mémoires par similarité sémantique.
- `test_search_by_vector`
- `test_search_hybrid`
- `test_search_hybrid_with_empty_results`
- `test_search_hybrid_with_none_query`
- `test_search_hybrid_with_none_metadata`

## tests/test_notification_service.py

- `test_send_notification`: Teste l'envoi d'une notification individuelle.
- `test_broadcast_notification`: Teste la diffusion d'une notification à plusieurs utilisateurs.
- `test_broadcast_notification_without_recipients`: Teste le comportement lorsqu'aucun destinataire n'est spécifié.
- `test_send_notification_with_smtp`: Teste l'envoi d'une notification avec un serveur SMTP configuré.
- `test_send_notification_with_error`: Teste la gestion des erreurs lors de l'envoi d'une notification.
- `test_broadcast_notification_with_global_error`
- `test_broadcast_notification_with_partial_errors`
- `test_send_notification_without_metadata`
- `test_broadcast_notification_with_empty_user_list`
- `test_notification_service_initialization`
- `test_send_notification_with_unhandled_exception`
- `test_broadcast_with_send_errors`

## tests/test_repository_protocols.py

- `test_create_event_with_protocol_mock`
- `test_get_event_success_with_protocol_mock`
- `test_get_event_not_found_with_protocol_mock`
- `test_filter_events_with_protocol_mock`
- `test_update_event_metadata_with_protocol_mock`
- `test_delete_event_with_protocol_mock`

## tests/test_search_routes.py

- `test_direct_db_connection`: Teste la connexion directe à la base de données de test en utilisant `TEST_DATABASE_URL`.
- `test_search_by_metadata_not_found`: Teste la recherche par métadonnées via l'API quand aucun événement ne correspond.
- `test_search_by_metadata_found_simple`: Teste la recherche par métadonnées simple (niveau 1) via l'API.
- `test_search_by_metadata_found_nested`: Teste la recherche par métadonnées imbriquées via l'API.
- `test_search_by_metadata_invalid_json`: Teste la recherche par métadonnées avec un JSON invalide dans la requête.
- `test_search_vector_only_found`: Teste la recherche vectorielle seule via l'API.
- `test_search_hybrid_with_time_filter`: Teste la recherche hybride avec un filtre temporel ajouté via l'API.
- `test_search_invalid_vector_query`: Teste la recherche vectorielle avec un vecteur invalide dans la requête.
- `test_search_invalid_vector_content`: Teste la recherche vectorielle avec un contenu de vecteur invalide (ex: mauvaise dimension).
- `test_search_metadata_with_time_filter`: Teste la recherche par métadonnées avec un filtre temporel ajouté via l'API.
- `test_search_pagination`: Teste la pagination (limit et offset) pour les résultats de recherche via l'API.

## tests/test_search_fallback.py

Tests pour le mécanisme de fallback automatique et les validations de distance_threshold dans les recherches vectorielles.

- `test_fallback_on_strict_threshold_returns_results`: Teste le fallback automatique quand un threshold trop strict (0.3) retourne 0 résultats. Vérifie que le système réessaie automatiquement sans threshold (mode top-K).
- `test_no_fallback_with_metadata_filter`: Teste que le fallback ne se déclenche PAS si un filtre metadata est présent, car le scope de la recherche est intentionnellement restreint.
- `test_no_fallback_with_time_filter`: Teste que le fallback ne se déclenche PAS si un filtre temporel (ts_start/ts_end) est présent.
- `test_fallback_disabled_with_enable_fallback_false`: Teste qu'on peut désactiver explicitement le fallback avec enable_fallback=False.
- `test_warning_on_strict_threshold`: Teste qu'un warning est émis pour threshold < 0.6 (considéré comme très strict).
- `test_warning_on_high_threshold`: Teste qu'un warning est émis pour threshold > 2.0 (inhabituel pour distance L2).
- `test_error_on_negative_threshold`: Teste qu'une ValueError est levée pour threshold < 0.0 (invalide).
- `test_no_fallback_if_threshold_none`: Teste qu'aucun fallback n'est nécessaire si threshold=None (mode top-K par défaut).
- `test_fallback_logs_warning`: Teste que le fallback log un message WARNING quand il se déclenche, indiquant le threshold initial et le passage en mode top-K.

---

# Tests Code Intelligence (EPIC-06/07)

Les sections suivantes documentent les **126 tests Code Intelligence** introduits en v2.0.0, couvrant l'indexation de code, la recherche hybride, et le graphe de dépendances.

## tests/db/repositories/test_code_chunk_repository.py

**20 tests** - Tests CRUD et recherches (vectorielle/lexicale) pour CodeChunkRepository.

- `test_add_code_chunk_success`: Teste l'ajout réussi d'un chunk de code avec dual embeddings.
- `test_get_code_chunk_by_id_success`: Teste la récupération d'un chunk par chunk_id.
- `test_get_code_chunk_by_id_not_found`: Teste le cas où le chunk n'existe pas.
- `test_update_code_chunk_success`: Teste la mise à jour d'un chunk existant (code_text, metadata, embeddings).
- `test_delete_code_chunk_success`: Teste la suppression d'un chunk.
- `test_delete_code_chunk_not_found`: Teste la suppression d'un chunk inexistant.
- `test_filter_by_repository`: Teste le filtrage par repository.
- `test_filter_by_file_path`: Teste le filtrage par file_path.
- `test_filter_by_language`: Teste le filtrage par language.
- `test_filter_by_chunk_type`: Teste le filtrage par chunk_type (function, class, method, file).
- `test_filter_by_metadata`: Teste le filtrage par métadonnées JSONB (ex: metadata->>'name' = 'foo').
- `test_search_vector_text_mode`: Teste la recherche vectorielle sur embedding_text (recherche par description).
- `test_search_vector_code_mode`: Teste la recherche vectorielle sur embedding_code (recherche par similarité de code).
- `test_search_lexical_code_text`: Teste la recherche lexicale (pg_trgm) sur code_text.
- `test_search_lexical_metadata`: Teste la recherche lexicale sur metadata (name, signature).
- `test_search_hybrid_vector_lexical`: Teste la recherche hybride combinant vector + lexical.
- `test_list_repositories`: Teste la récupération de la liste des repositories indexés.
- `test_get_repository_stats`: Teste les statistiques d'un repository (total chunks, par langage, par type).
- `test_batch_add_code_chunks`: Teste l'ajout en batch de plusieurs chunks.
- `test_count_chunks_by_repository`: Teste le comptage de chunks par repository.

## tests/services/test_ast_parser_service.py

**18 tests** - Tests pour ASTParserService (parsing tree-sitter multi-langages).

- `test_parse_python_function`: Teste le parsing d'une fonction Python.
- `test_parse_python_class`: Teste le parsing d'une classe Python avec méthodes.
- `test_parse_python_method`: Teste le parsing d'une méthode dans une classe Python.
- `test_parse_javascript_function`: Teste le parsing d'une fonction JavaScript.
- `test_parse_javascript_class`: Teste le parsing d'une classe JavaScript (ES6).
- `test_parse_typescript_interface`: Teste le parsing d'une interface TypeScript.
- `test_parse_typescript_function`: Teste le parsing d'une fonction TypeScript avec types.
- `test_parse_go_function`: Teste le parsing d'une fonction Go.
- `test_parse_go_struct`: Teste le parsing d'une struct Go.
- `test_parse_rust_function`: Teste le parsing d'une fonction Rust.
- `test_parse_rust_struct`: Teste le parsing d'une struct Rust.
- `test_parse_invalid_syntax`: Teste le comportement lors d'une erreur de syntaxe.
- `test_parse_unsupported_language`: Teste le comportement pour un langage non supporté.
- `test_extract_imports_python`: Teste l'extraction des imports Python (import, from...import).
- `test_extract_calls_python`: Teste l'extraction des appels de fonctions Python.
- `test_extract_docstring_python`: Teste l'extraction de docstring Python.
- `test_calculate_complexity`: Teste le calcul de complexité cyclomatique.
- `test_parse_empty_file`: Teste le parsing d'un fichier vide.

## tests/services/test_code_metadata_service.py

**15 tests** - Tests pour CodeMetadataService (extraction metadata à partir de l'AST).

- `test_extract_metadata_python_function`: Teste l'extraction de metadata pour une fonction Python (name, signature, parameters, return_type, docstring, complexity).
- `test_extract_metadata_python_class`: Teste l'extraction de metadata pour une classe Python (name, methods, base_classes).
- `test_extract_metadata_python_method`: Teste l'extraction de metadata pour une méthode (class_name, decorators).
- `test_extract_metadata_javascript_function`: Teste l'extraction de metadata pour une fonction JavaScript.
- `test_extract_metadata_typescript_interface`: Teste l'extraction de metadata pour une interface TypeScript.
- `test_extract_metadata_with_imports`: Teste l'extraction des imports dans metadata.
- `test_extract_metadata_with_calls`: Teste l'extraction des appels de fonctions dans metadata.
- `test_extract_metadata_with_decorators`: Teste l'extraction des decorators Python (@property, @staticmethod).
- `test_extract_metadata_complex_function`: Teste l'extraction pour une fonction complexe (haute complexité cyclomatique).
- `test_extract_metadata_async_function`: Teste l'extraction pour une fonction async/await.
- `test_extract_metadata_generator_function`: Teste l'extraction pour une fonction generator (yield).
- `test_extract_metadata_lambda_function`: Teste l'extraction pour une lambda expression.
- `test_extract_metadata_nested_function`: Teste l'extraction pour une fonction imbriquée.
- `test_extract_metadata_with_type_hints`: Teste l'extraction avec type hints Python 3.
- `test_extract_metadata_empty_function`: Teste l'extraction pour une fonction vide (pass).

## tests/services/test_graph_construction_service.py

**11 tests** - Tests pour GraphConstructionService (construction du graphe de dépendances).

- `test_build_graph_from_chunks`: Teste la construction du graphe à partir d'une liste de chunks.
- `test_create_nodes_from_chunks`: Teste la création de nœuds (nodes) à partir de chunks.
- `test_create_edges_from_imports`: Teste la création d'arêtes (edges) de type 'imports' à partir des imports.
- `test_create_edges_from_calls`: Teste la création d'arêtes de type 'calls' à partir des appels de fonctions.
- `test_create_edges_from_inheritance`: Teste la création d'arêtes de type 'inherits' pour l'héritage de classes.
- `test_resolve_import_to_chunk_id`: Teste la résolution d'un import vers un chunk_id (mapping nom → chunk_id).
- `test_resolve_call_to_chunk_id`: Teste la résolution d'un appel de fonction vers un chunk_id.
- `test_handle_circular_imports`: Teste la gestion des imports circulaires (A imports B, B imports A).
- `test_handle_unresolved_imports`: Teste la gestion des imports non résolus (import externe non indexé).
- `test_filter_builtin_calls`: Teste le filtrage des appels de fonctions built-in (print, len, etc.) - 73 built-ins Python filtrés automatiquement.
- `test_build_graph_empty_chunks`: Teste la construction du graphe avec une liste vide de chunks.

## tests/services/test_graph_traversal_service.py

**9 tests** - Tests pour GraphTraversalService (traversée du graphe avec recursive CTEs).

- `test_traverse_forward_1_hop`: Teste la traversée avant (forward) sur 1 saut.
- `test_traverse_forward_3_hops`: Teste la traversée avant sur 3 sauts (limite max).
- `test_traverse_backward_1_hop`: Teste la traversée arrière (backward) depuis un nœud cible.
- `test_traverse_bidirectional`: Teste la traversée bidirectionnelle (forward + backward).
- `test_find_shortest_path`: Teste la recherche du plus court chemin entre deux nœuds.
- `test_get_node_dependencies`: Teste la récupération de toutes les dépendances d'un nœud (imports + calls).
- `test_get_node_dependents`: Teste la récupération de tous les dépendants d'un nœud (qui importe/appelle ce nœud).
- `test_traverse_with_relation_type_filter`: Teste la traversée avec filtre sur relation_type (ex: 'imports' seulement).
- `test_traverse_performance`: Teste la performance de traversée (doit être ≤20ms pour 3 hops, mesuré à 0.155ms).

## tests/services/test_lexical_search_service.py

**8 tests** - Tests pour LexicalSearchService (recherche pg_trgm).

- `test_search_by_code_text`: Teste la recherche lexicale sur code_text (ex: "def authenticate").
- `test_search_by_function_name`: Teste la recherche sur metadata->>'name' (ex: "authenticate_user").
- `test_search_by_signature`: Teste la recherche sur metadata->>'signature'.
- `test_search_with_similarity_threshold`: Teste le filtrage par seuil de similarité trigram (similarity > 0.3).
- `test_search_case_insensitive`: Teste que la recherche est case-insensitive.
- `test_search_partial_match`: Teste la recherche partielle (ex: "auth" trouve "authenticate").
- `test_search_empty_query`: Teste le comportement avec une query vide.
- `test_search_no_results`: Teste le cas où aucun résultat ne correspond.

## tests/services/test_vector_search_service.py

**10 tests** - Tests pour VectorSearchService (recherche HNSW).

- `test_search_by_text_embedding`: Teste la recherche vectorielle sur embedding_text (mode TEXT).
- `test_search_by_code_embedding`: Teste la recherche vectorielle sur embedding_code (mode CODE).
- `test_search_with_distance_threshold`: Teste le filtrage par distance threshold (ex: distance < 0.5).
- `test_search_with_limit`: Teste la limite du nombre de résultats (top-K).
- `test_search_with_metadata_filter`: Teste la recherche vectorielle + filtre metadata.
- `test_search_with_repository_filter`: Teste la recherche vectorielle + filtre repository.
- `test_search_with_language_filter`: Teste la recherche vectorielle + filtre language.
- `test_search_empty_embedding`: Teste le comportement avec un embedding vide.
- `test_search_invalid_dimension`: Teste le comportement avec un embedding de dimension invalide (≠768).
- `test_search_performance`: Teste la performance de recherche vectorielle (doit être ≤20ms, mesuré à ~12ms).

## tests/services/test_rrf_fusion_service.py

**6 tests** - Tests pour RRFFusionService (Reciprocal Rank Fusion).

- `test_fuse_two_result_sets`: Teste la fusion de 2 listes de résultats (lexical + vector).
- `test_fuse_with_different_k_values`: Teste l'impact du paramètre k (default k=60) sur le score RRF.
- `test_fuse_with_overlapping_results`: Teste la fusion avec des résultats communs entre les 2 listes.
- `test_fuse_with_one_empty_list`: Teste la fusion quand une des listes est vide.
- `test_fuse_both_empty_lists`: Teste la fusion quand les deux listes sont vides.
- `test_rrf_score_calculation`: Teste le calcul du score RRF (score = sum(1/(k + rank_i))).

## tests/services/test_hybrid_code_search_service.py

**7 tests** - Tests pour HybridCodeSearchService (orchestration lexical + vector + RRF).

- `test_hybrid_search_with_query`: Teste la recherche hybride complète (lexical + vector + fusion).
- `test_hybrid_search_lexical_only`: Teste le mode lexical seul (pas de vector).
- `test_hybrid_search_vector_only`: Teste le mode vector seul (pas de lexical).
- `test_hybrid_search_with_filters`: Teste la recherche hybride + filtres (repository, language, metadata).
- `test_hybrid_search_with_limit`: Teste la limite de résultats pour la recherche hybride.
- `test_hybrid_search_empty_query`: Teste le comportement avec query vide (retourne tous les chunks filtrés).
- `test_hybrid_search_performance`: Teste la performance globale de recherche hybride (doit être ≤50ms, mesuré à ~11ms).

## tests/routes/test_code_search_routes.py

**22 tests** - Tests pour les API endpoints `/v1/code/search/*` et `/v1/code/index`.

- `test_index_code_repository`: Teste l'endpoint POST /v1/code/index (indexation d'un repository).
- `test_index_code_repository_invalid_path`: Teste l'indexation avec un chemin invalide (404).
- `test_index_code_repository_unsupported_language`: Teste l'indexation avec un langage non supporté.
- `test_search_hybrid_success`: Teste GET /v1/code/search/hybrid avec query + filters.
- `test_search_hybrid_no_query`: Teste /search/hybrid sans query (retourne résultats filtrés).
- `test_search_hybrid_with_repository_filter`: Teste /search/hybrid avec filtre repository.
- `test_search_hybrid_with_language_filter`: Teste /search/hybrid avec filtre language.
- `test_search_hybrid_with_chunk_type_filter`: Teste /search/hybrid avec filtre chunk_type.
- `test_search_hybrid_with_limit`: Teste /search/hybrid avec limit (pagination).
- `test_search_lexical_success`: Teste GET /v1/code/search/lexical.
- `test_search_lexical_empty_query`: Teste /search/lexical avec query vide (400 Bad Request).
- `test_search_vector_text_mode`: Teste GET /v1/code/search/vector avec mode=text.
- `test_search_vector_code_mode`: Teste GET /v1/code/search/vector avec mode=code.
- `test_search_vector_invalid_mode`: Teste /search/vector avec mode invalide (400).
- `test_get_chunk_by_id_success`: Teste GET /v1/code/chunks/{chunk_id}.
- `test_get_chunk_by_id_not_found`: Teste GET /v1/code/chunks/{chunk_id} inexistant (404).
- `test_get_chunk_metadata`: Teste GET /v1/code/metadata/{chunk_id}.
- `test_list_repositories`: Teste GET /v1/code/repositories (liste des repos indexés).
- `test_get_repository_stats`: Teste GET /v1/code/stats?repository=X.
- `test_delete_chunk_success`: Teste DELETE /v1/code/chunks/{chunk_id}.
- `test_delete_chunk_not_found`: Teste DELETE sur un chunk inexistant (404).
- `test_reindex_repository`: Teste POST /v1/code/reindex (réindexation complète d'un repository).

## tests/routes/test_code_graph_routes.py

**11 tests** - Tests pour les API endpoints `/v1/code/graph/*` (graphe de dépendances).

- `test_build_graph_success`: Teste POST /v1/code/graph/build (construction du graphe).
- `test_build_graph_no_chunks`: Teste /graph/build avec repository vide (aucun chunk).
- `test_traverse_graph_forward`: Teste POST /v1/code/graph/traverse avec direction=forward.
- `test_traverse_graph_backward`: Teste /graph/traverse avec direction=backward.
- `test_traverse_graph_bidirectional`: Teste /graph/traverse avec direction=both.
- `test_traverse_graph_with_max_depth`: Teste /graph/traverse avec max_depth=2.
- `test_traverse_graph_node_not_found`: Teste /graph/traverse avec node_id inexistant (404).
- `test_find_path_success`: Teste POST /v1/code/graph/path (plus court chemin entre 2 nœuds).
- `test_find_path_no_path_exists`: Teste /graph/path quand aucun chemin n'existe.
- `test_get_graph_stats`: Teste GET /v1/code/graph/stats (statistiques du graphe: nb nodes, nb edges).
- `test_get_node_info`: Teste GET /v1/code/graph/nodes/{node_id} (informations détaillées d'un nœud).

---

# Tests d'Intégration

## tests/integration/test_end_to_end_indexing.py

**8 tests** - Tests d'intégration end-to-end pour le pipeline complet d'indexation.

- `test_index_python_repository`: Teste l'indexation complète d'un petit repository Python (détection → parsing → chunking → metadata → embedding → graph → storage).
- `test_search_after_indexing`: Teste la recherche hybride après indexation.
- `test_graph_traversal_after_indexing`: Teste la traversée du graphe après indexation.
- `test_reindex_existing_repository`: Teste la réindexation (mise à jour) d'un repository déjà indexé.
- `test_index_multi_language_repository`: Teste l'indexation d'un repository multi-langages (Python + JavaScript).
- `test_index_large_repository`: Teste l'indexation d'un grand repository (>100 fichiers, >1000 chunks).
- `test_concurrent_indexing`: Teste l'indexation concurrente de plusieurs repositories en parallèle.
- `test_indexing_performance`: Teste la performance du pipeline d'indexation (doit être ≤3s par fichier).

## tests/integration/test_code_intelligence_api.py

**9 tests** - Tests d'intégration API pour Code Intelligence.

- `test_full_workflow_index_search_graph`: Teste le workflow complet (index → search → traverse).
- `test_api_error_handling`: Teste la gestion des erreurs API (400, 404, 500).
- `test_api_pagination`: Teste la pagination des résultats de recherche.
- `test_api_filtering`: Teste les filtres combinés (repository + language + chunk_type).
- `test_api_authentication`: Teste l'authentification API (si activée).
- `test_api_rate_limiting`: Teste le rate limiting API (si activé).
- `test_api_concurrent_requests`: Teste les requêtes concurrentes à l'API.
- `test_api_response_format`: Teste le format de réponse JSON (conformité OpenAPI).
- `test_api_performance`: Teste la performance des endpoints API (latence p95 ≤100ms). 