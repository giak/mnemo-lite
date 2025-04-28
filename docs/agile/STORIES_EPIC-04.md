# EPIC-04 : Refactoring et Amélioration des Bonnes Pratiques

## Description générale

Cette epic vise à améliorer la qualité globale, la maintenabilité, la testabilité et la robustesse du code base de MnemoLite en appliquant de manière systématique les principes de conception logicielle reconnus (SOLID, SoC) et les bonnes pratiques de développement (Clean Code, KISS, YAGNI).

## Objectifs

- Augmenter la modularité et réduire le couplage entre les composants.
- Améliorer la lisibilité et la compréhension du code.
- Renforcer la couverture de tests et la qualité des tests existants.
- Simplifier les composants complexes.
- Assurer une gestion propre et sécurisée de la configuration.
- Supprimer le code inutile ou mort.

## User Stories

### US-04.1 : Appliquer le Principe de Responsabilité Unique (SRP)

**En tant que** développeur
**Je veux** refactoriser les classes et modules clés (ex: Repositories, Services) pour qu'ils aient une seule responsabilité bien définie
**Afin de** réduire le couplage, faciliter les tests unitaires et améliorer la compréhension du code.

**État:** Terminé

**Tâches:**
- [x] Identifier les classes/modules violant le SRP (ex: `EventRepository` initial, `memory_routes.py`).
- [x] Créer de nouvelles classes/modules pour séparer les responsabilités (ex: `EventQueryBuilder`).
- [x] Examiner les routes (`memory_routes.py`, `event_routes.py`, `health_routes.py`, `search_routes.py`) pour appliquer le SRP.
- [x] Créer `MemoryRepository` (et potentiellement `MemoryQueryBuilder`) pour encapsuler la logique DB de `memory_routes.py`.
- [x] Adapter le code appelant (routes) pour utiliser les nouvelles structures.
- [x] Exécuter les tests `make api-test` pour vérifier la non-régression.
- [x] Mettre à jour les tests existants / Créer des tests pour le nouveau Repository.

**Critères d'acceptation:**
- [x] Les classes refactorisées ont une seule raison de changer.
- [x] La séparation des responsabilités est claire (ex: construction de requête vs exécution).
- [x] Le code est plus facile à tester isolément.
- [x] Aucune régression fonctionnelle introduite.

**Complexité estimée:** Moyenne (par composant)
**Priorité:** Haute
**Assigné à:** Non assigné

### US-04.2 : Mettre en place l'Injection de Dépendances (DIP)

**En tant que** développeur
**Je veux** que les composants de haut niveau (ex: routes API, tâches worker) reçoivent leurs dépendances (ex: Repositories, Services) via injection plutôt que de les créer directement
**Afin de** respecter le Principe d'Inversion de Dépendance (DIP), découpler les composants et faciliter le remplacement des dépendances (notamment pour les tests).

**Tâches:**
- [ ] Choisir et mettre en place un mécanisme/librairie d'injection de dépendances (si nécessaire, ex: FastAPI Depends, `dependency-injector`).
- [ ] Identifier les endroits où les dépendances sont créées directement.
- [ ] Refactoriser les constructeurs ou points d'entrée pour recevoir les dépendances injectées.
- [ ] Configurer le conteneur d'injection ou le système de dépendances.
- [ ] Adapter les tests pour fournir des mocks/doublures via l'injection.

**Critères d'acceptation:**
- [ ] Les composants clés dépendent d'abstractions (interfaces/protocoles) plutôt que de classes concrètes lorsque c'est pertinent.
- [ ] Les dépendances sont injectées de l'extérieur.
- [ ] Il est facile de remplacer une dépendance par une autre (ex: un mock pour les tests).
- [ ] Le couplage entre les modules est réduit.

**Complexité estimée:** Moyenne à Élevée (selon l'ampleur)
**Priorité:** Moyenne
**Assigné à:** Non assigné

### US-04.3 : Améliorer la Couverture et la Qualité des Tests

**En tant que** développeur
**Je veux** augmenter la couverture de tests et améliorer la qualité des tests existants
**Afin de** garantir la fiabilité du code, détecter les régressions rapidement et faciliter les refactorisations futures.

**Tâches:**
- [x] Mettre en place une base de données de test dédiée (`db-test-reset`).
- [ ] Mesurer la couverture de code actuelle.
- [ ] Identifier les zones critiques ou complexes avec une faible couverture.
- [ ] Écrire de nouveaux tests (unitaires, intégration) pour combler les manques.
- [ ] Refactoriser les tests existants pour améliorer leur lisibilité (ex: structure Given-When-Then, noms clairs).
- [ ] S'assurer que les tests sont rapides et fiables (pas de tests "flaky").
- [ ] Intégrer la mesure de couverture dans le pipeline CI (si existant).

**Critères d'acceptation:**
- [ ] La couverture de code globale a augmenté de manière significative (objectif à définir).
- [ ] Les nouvelles fonctionnalités incluent des tests adéquats.
- [ ] Les tests sont clairs, concis et faciles à maintenir.
- [ ] Les tests s'exécutent de manière fiable dans l'environnement de test.

**Complexité estimée:** Élevée (continu)
**Priorité:** Haute
**Assigné à:** Non assigné

### US-04.4 : Nettoyage et Lisibilité du Code (Clean Code)

**En tant que** développeur
**Je veux** améliorer la qualité intrinsèque du code en appliquant les principes du Clean Code
**Afin de** rendre le code plus facile à lire, comprendre, maintenir et faire évoluer.

**Tâches:**
- [ ] Examiner les modules clés (`api/`, `workers/`, `db/`).
- [ ] Renommer les variables, fonctions, classes de manière claire et cohérente.
- [ ] Simplifier les fonctions/méthodes trop longues ou complexes (extraire des méthodes).
- [ ] Supprimer le code mort ou commenté inutile.
- [ ] Assurer une indentation et un formatage cohérents (utiliser `black`, `ruff format`).
- [ ] Ajouter des commentaires uniquement là où c'est nécessaire pour expliquer le "pourquoi" et non le "comment".
- [ ] Réduire la duplication de code (DRY).

**Critères d'acceptation:**
- [ ] Le code respecte les conventions de style (PEP 8, via linters/formatters).
- [ ] Les noms sont explicites et non ambigus.
- [ ] La complexité cyclomatique des fonctions/méthodes est maîtrisée.
- [ ] Le code inutile a été supprimé.
- [ ] Le code est globalement plus facile à lire et à comprendre pour un nouveau développeur.

**Complexité estimée:** Moyenne (continu)
**Priorité:** Moyenne
**Assigné à:** Non assigné

### US-04.5 : Simplification des Composants (KISS & YAGNI)

**En tant que** développeur
**Je veux** identifier et simplifier les composants ou logiques inutilement complexes et supprimer les fonctionnalités non utilisées
**Afin de** réduire la charge cognitive, faciliter la maintenance et éviter la sur-ingénierie.

**Tâches:**
- [ ] Identifier les parties du code qui semblent trop complexes pour ce qu'elles font (KISS).
- [ ] Refactoriser pour simplifier la logique, réduire les abstractions inutiles.
- [ ] Rechercher les fonctionnalités ou options qui ne sont pas actuellement utilisées (YAGNI).
- [ ] Supprimer prudemment le code correspondant à ces fonctionnalités non nécessaires.
- [ ] S'assurer que la suppression n'introduit pas de régressions.

**Critères d'acceptation:**
- [ ] La complexité de certaines parties du code a été réduite.
- [ ] Le code mort ou non utilisé a été supprimé.
- [ ] Le code restant est justifié par les besoins actuels.

**Complexité estimée:** Moyenne
**Priorité:** Faible
**Assigné à:** Non assigné

### US-04.6 : Amélioration de la Gestion de la Configuration

**En tant que** développeur
**Je veux** une gestion centralisée, claire et sécurisée de la configuration de l'application
**Afin de** faciliter le déploiement dans différents environnements et éviter les erreurs de configuration ou les fuites d'informations sensibles.

**Tâches:**
- [x] Supprimer les informations sensibles en clair des fichiers sources (ex: Makefile).
- [ ] Centraliser la lecture de la configuration (ex: variables d'env, fichiers `.env`) en utilisant potentiellement une librairie comme Pydantic Settings.
- [ ] Définir clairement les variables de configuration nécessaires pour chaque environnement (dev, test, prod).
- [ ] Documenter le processus de configuration.
- [ ] Valider les types et la présence des variables de configuration au démarrage.

**Critères d'acceptation:**
- [x] Aucune information sensible en clair dans le code versionné.
- [ ] La configuration est chargée depuis des sources externes (variables d'env, fichiers `.env`).
- [ ] La configuration est validée au démarrage de l'application/worker.
- [ ] La documentation explique clairement comment configurer l'application.

**Complexité estimée:** Moyenne
**Priorité:** Haute
**Assigné à:** Non assigné

## Bénéfices

L'application de ces bonnes pratiques rendra le code base de MnemoLite :
- **Plus Maintenable:** Modifications et évolutions futures plus faciles et moins risquées.
- **Plus Robuste:** Moins de bugs grâce à une meilleure conception et des tests renforcés.
- **Plus Compréhensible:** Intégration de nouveaux développeurs facilitée.
- **Plus Performant:** Simplification et suppression de l'inutile pouvant améliorer les performances.
- **Plus Sécurisé:** Meilleure gestion des configurations et des secrets. 