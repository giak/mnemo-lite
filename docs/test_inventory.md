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
- `test_build_search_vector_query_no_criteria`: Teste la construction de la requête de recherche vectorielle sans aucun critère (devrait probablement lever une erreur ou retourner une requête simple).
- `test_build_search_vector_query_invalid_dimension`: Teste la construction de la requête de recherche vectorielle avec un vecteur de dimension invalide (devrait lever une erreur).

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

## tests/test_event_routes.py

- `test_get_event_success_with_patch`: Teste la récupération réussie via l'API en patchant `EventRepository.get_by_id` (Skipped: Problème de mocking/patch).
- `test_get_event_not_found_with_patch`: Teste le cas 404 via l'API en patchant `EventRepository.get_by_id` (Skipped: Problème de mocking/patch).

## tests/test_search_routes.py

- `test_direct_db_connection`: Teste la connexion directe à la base de données de test en utilisant `TEST_DATABASE_URL`.
- `test_search_by_metadata_not_found`: Teste la recherche par métadonnées via l'API quand aucun événement ne correspond.
- `test_search_by_metadata_found_simple`: Teste la recherche par métadonnées simple (niveau 1) via l'API.
- `test_search_by_metadata_found_nested`: Teste la recherche par métadonnées imbriquées via l'API.
- `test_search_by_metadata_invalid_json`: Teste la recherche par métadonnées avec un JSON invalide dans la requête.
- `test_search_vector_only_found`: Teste la recherche vectorielle seule via l'API.
- `test_search_hybrid_found`: Teste la recherche hybride (vecteur + métadonnées) via l'API.
- `test_search_invalid_vector_query`: Teste la recherche vectorielle avec un vecteur invalide dans la requête.
- `test_search_invalid_vector_content`: Teste la recherche vectorielle avec un contenu de vecteur invalide (ex: mauvaise dimension).
- `test_search_metadata_with_time_filter`: Teste la recherche par métadonnées avec un filtre temporel ajouté via l'API.
- `test_search_hybrid_with_time_filter`: Teste la recherche hybride avec un filtre temporel ajouté via l'API.
- `test_search_pagination`: Teste la pagination (limit et offset) pour les résultats de recherche via l'API.

## api/tests/test_dependency_injection.py

- `test_db_engine_injection`: Teste l'injection correcte du moteur de base de données.
- `test_event_repository_injection`: Teste l'injection correcte du repository d'événements.
- `test_memory_repository_injection`: Teste l'injection correcte du repository de mémoires.
- `test_embedding_service_injection`: Teste l'injection correcte du service d'embedding.
- `test_memory_search_service_injection`: Teste l'injection correcte du service de recherche de mémoires.
- `test_event_processor_injection`: Teste l'injection correcte du processeur d'événements.
- `test_notification_service_injection`: Teste l'injection correcte du service de notification.
- `test_dependency_error_handling`: Teste la gestion des erreurs lorsqu'une dépendance requise n'est pas disponible.

## api/tests/test_event_processor.py

- `test_process_event`: Teste le traitement d'un événement, vérifiant l'enrichissement des métadonnées et la génération d'embedding.
- `test_generate_memory_from_event`: Teste la génération d'une mémoire à partir d'un événement.
- `test_process_event_with_error`: Teste le comportement du processeur lors d'une erreur pendant la génération d'embedding.

## api/tests/test_notification_service.py

- `test_send_notification`: Teste l'envoi d'une notification individuelle.
- `test_broadcast_notification`: Teste la diffusion d'une notification à plusieurs utilisateurs.
- `test_broadcast_notification_without_recipients`: Teste le comportement lorsqu'aucun destinataire n'est spécifié.
- `test_send_notification_with_smtp`: Teste l'envoi d'une notification avec un serveur SMTP configuré.
- `test_send_notification_with_error`: Teste la gestion des erreurs lors de l'envoi d'une notification.

## api/tests/test_new_services.py

- `test_event_processor_injection`: Teste l'injection du processeur d'événements dans une application FastAPI.
- `test_notification_service_injection`: Teste l'injection du service de notification avec configuration SMTP.

## api/tests/test_memory_search_service.py

- `test_search_by_content`: Teste la recherche de mémoires par contenu textuel.
- `test_search_by_metadata`: Teste la recherche de mémoires par métadonnées.
- `test_search_by_similarity`: Teste la recherche de mémoires par similarité sémantique. 