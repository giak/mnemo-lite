# Inventaire des Tests MnemoLite

Ce document recense les tests automatisés du projet MnemoLite, collectés via `pytest --collect-only`.

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

- `test_add_memory_success`: Teste l'ajout réussi d'une nouvelle mémoire.
- `test_get_memory_by_id_success`: Teste la récupération réussie d'une mémoire existante par son ID.
- `test_get_memory_by_id_not_found`: Teste que la récupération d'une mémoire non existante par ID retourne None.
- `test_update_memory_success`: Teste la mise à jour réussie d'une mémoire existante.
- `test_update_memory_partial`: Teste la mise à jour partielle d'une mémoire (seulement un champ).
- `test_update_memory_not_found`: Teste que la mise à jour d'une mémoire non existante retourne None.
- `test_update_memory_empty_data`: Teste que l'appel à update sans données réelles ne change pas la mémoire.
- `test_update_memory_merge_only_content`: Teste que la mise à jour du contenu uniquement fusionne correctement.
- `test_update_memory_merge_only_metadata`: Teste que la mise à jour des métadonnées uniquement fusionne correctement.
- `test_update_memory_overwrite_content_key`: Teste que la mise à jour du contenu écrase les clés existantes.
- `test_update_memory_overwrite_metadata_key`: Teste que la mise à jour des métadonnées écrase les clés existantes.
- `test_delete_memory_success`: Teste la suppression réussie d'une mémoire existante.
- `test_delete_memory_not_found`: Teste que la suppression d'une mémoire non existante retourne False.
- `test_list_memories_no_filters_default_limit`: Teste la liste des mémoires sans filtres et avec la limite par défaut (10).
- `test_list_memories_custom_limit`: Teste la liste des mémoires avec une limite personnalisée.
- `test_list_memories_offset`: Teste la liste des mémoires avec un offset.
- `test_list_memories_filter_memory_type`: Teste le filtrage par memory_type.
- `test_list_memories_filter_event_type`: Teste le filtrage par event_type.
- `test_list_memories_filter_role_id`: Teste le filtrage par role_id.
- `test_list_memories_filter_session_id`: Teste le filtrage par session_id (stocké dans les métadonnées).
- `test_list_memories_combined_filters_pagination`: Teste la combinaison de filtres avec limite et offset.
- `test_list_memories_filter_no_results`: Teste que les filtres ne donnant aucun résultat retournent une liste vide.
- `test_list_memories_limit_zero`: Teste que la liste des mémoires avec limit=0 retourne une liste vide.
- `test_list_memories_offset_too_large`: Teste que la liste des mémoires avec offset >= total retourne une liste vide.
- `test_list_memories_three_filters`: Teste la combinaison de trois filtres (memory_type, event_type, role_id).
- `test_get_memory_with_null_json_fields`: Teste la récupération et le mapping d'un enregistrement avec des champs JSON vides mais valides.

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

- `test_list_memories`
- `test_create_memory_with_protocol_mock`
- `test_get_memory_success_with_protocol_mock`
- `test_get_memory_not_found_with_protocol_mock`
- `test_update_memory_with_protocol_mock`
- `test_delete_memory_with_protocol_mock`
- `test_list_memories_with_protocol_mock`

## tests/test_memory_routes.py

- `test_get_memory_success_with_mock`
- `test_get_memory_not_found_with_mock`
- `test_get_memory_with_exception`
- `test_create_memory_success`
- `test_create_memory_error`
- `test_update_memory_success`
- `test_update_memory_not_found`
- `test_update_memory_error`
- `test_delete_memory_success`
- `test_delete_memory_not_found`
- `test_delete_memory_error`
- `test_list_memories`
- `test_list_memories_empty_result`
- `test_list_memories_with_filters`
- `test_list_memories_error`
- `test_invalid_path_for_memories`

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