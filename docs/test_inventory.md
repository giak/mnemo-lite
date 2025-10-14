# Inventaire des Tests MnemoLite

**Version:** 1.3.0
**Dernière mise à jour:** 2025-10-14
**Statut:** 102 tests passing, 11 skipped, 1 xfailed

Ce document recense les tests automatisés du projet MnemoLite, collectés via `pytest --collect-only`.

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