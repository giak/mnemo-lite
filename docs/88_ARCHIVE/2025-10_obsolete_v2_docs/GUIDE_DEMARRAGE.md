<p align="center">
  <img src="static/img/logo_mnemolite.jpg" alt="MnemoLite Logo" width="200" style="border-radius: 50%;">
</p>

# 🧠 MnemoLite v2.0.0 - Guide de Démarrage

> **Pour qui ?** Ce guide est fait pour vous si vous voulez installer et utiliser MnemoLite, même sans être expert en bases de données ou en Docker. On vous prend par la main, étape par étape.
>
> **🎉 Nouveau v2.0.0** : MnemoLite est maintenant **dual-purpose** - Agent Memory (conversations) + Code Intelligence (analyse de code) !

---

## 📖 Introduction : Votre Système Intelligent Dual-Purpose

MnemoLite v2.0.0, c'est comme avoir **deux bibliothécaires experts** qui collaborent dans la même bibliothèque :

### 🧠 Le Bibliothécaire de Mémoire
**Organise vos souvenirs, conversations, événements** :
- 🔍 Recherche par sens (pas par mots exacts) : "Je cherche quelque chose sur les chats" trouvera aussi "félin domestique"
- ⏰ Filtrage temporel intelligent : "Montre-moi tout ce qui s'est passé en janvier"
- 🏷️ Classification par catégories : "Tous les souvenirs liés au projet Expanse"
- 🕸️ Graphe de connaissances pour visualiser les liens

**Pour qui ?** Agents IA, chatbots, assistants personnels, systèmes de mémoire conversationnelle

### 💻 Le Bibliothécaire de Code
**Organise vos fichiers de code, fonctions, dépendances** :
- 🔍 Recherche hybride dans le code : Trouve "calculer une moyenne" même si vous écrivez `calc_avg()`
- 🌳 Analyse AST automatique : Comprend la structure de votre code (15+ langages)
- 🕸️ Graphe de dépendances : Visualise qui appelle quoi, automatiquement
- 📊 Analytics de complexité : Détecte le code "spaghetti"

**Pour qui ?** Développeurs explorant des codebases, refactoring, code review, onboarding

### 🔥 La Magie : Ils Collaborent !
Les deux utilisent le **même langage** (PostgreSQL 18 + embeddings locaux 768D).

**Résultat ?** Vous pouvez créer un **agent IA qui comprend votre code ET se souvient de vos conversations** !

**Le secret ?** 100% local, **zéro données ne sortent** de votre machine. PostgreSQL comme bibliothécaire ultra-compétent, embeddings locaux (Sentence-Transformers) pour comprendre le sens.

---

## 🎯 Choisissez Votre Parcours

MnemoLite v2.0.0 offre **deux capacités majeures**. Choisissez le parcours qui vous intéresse :

### 📍 Parcours A : Agent Memory (20 min) 🧠
**Pour qui ?** Développeurs d'agents IA, chatbots, assistants conversationnels

**Ce que vous apprendrez** :
- ✅ Stocker et rechercher des événements/conversations
- ✅ Recherche sémantique (par le sens, pas par mots-clés)
- ✅ Filtrer par métadonnées et périodes temporelles
- ✅ Visualiser un graphe de connaissances
- ✅ Interface web pour explorer vos données

**Résultat** : Une API de mémoire cognitive prête pour votre agent IA

**Sections du guide** : 1, 2, 3, 4, 5, 7.1, 8

---

### 📍 Parcours B : Code Intelligence (25 min) 💻
**Pour qui ?** Développeurs cherchant un moteur de recherche de code local et intelligent

**Ce que vous apprendrez** :
- ✅ Indexer des repositories de code (Python, JS, TS, Go, Rust, Java, etc.)
- ✅ Recherche hybride : lexicale (mots-clés) + sémantique (par le sens)
- ✅ Explorer les graphes de dépendances (qui appelle quoi)
- ✅ Analyser la complexité cyclomatique
- ✅ Interface web pour naviguer dans votre codebase

**Résultat** : Un moteur de recherche intelligent pour votre code

**Sections du guide** : 1, 2, 3, 4, 6, 7.2, 8

---

### 📍 Parcours C : Full Stack (35 min) 🔥
**Pour qui ?** Architectes, tech leads, power users qui veulent tout exploiter

**Ce que vous apprendrez** :
- ✅ Combiner mémoire conversationnelle + analyse de code
- ✅ Créer un agent IA qui "lit" et comprend votre code
- ✅ Use cases avancés : code review assisté, debugging intelligent
- ✅ Exploiter les synergies entre les deux systèmes

**Résultat** : Un système complet dual-purpose unique

**Sections du guide** : Toutes les sections (1-9)

---

**💡 Conseil** : Si vous hésitez, commencez par le **Parcours A** ou **B** selon vos besoins immédiats. Vous pourrez toujours explorer l'autre capacité plus tard !

**⏱️ Temps d'installation** : 15-20 minutes (commun aux 3 parcours)

---

## 🧰 Avant de commencer : Votre boîte à outils

### Ce dont vous avez besoin

Pensez à Docker comme à une **machine virtuelle légère** qui isole MnemoLite dans sa propre "bulle" sur votre ordinateur. C'est comme avoir plusieurs mini-ordinateurs dans votre ordinateur.

**Requis absolument** :
- **Docker Desktop** (Windows/Mac) ou **Docker Engine** (Linux) - [Télécharger ici](https://docs.docker.com/get-docker/)
  - Version Docker Compose v2+ incluse
- **Git** - Pour télécharger le code - [Télécharger ici](https://git-scm.com/downloads)
- **Un terminal** (Bash, PowerShell, Terminal Mac, etc.)
- **4 GB de RAM disponible** (minimum) - MnemoLite est gourmand mais pas excessif
- **5 GB d'espace disque libre** - Pour les images Docker et les données

**Bonus (optionnel mais pratique)** :
- **curl** - Pour tester l'API facilement (souvent déjà installé)
- **jq** - Pour formater joliment les réponses JSON
- **Un éditeur de texte** - VSCode, Sublime, nano, vim... au choix

### Vérifier que tout est prêt

Ouvrez un terminal et tapez ces commandes pour vérifier :

```bash
# Vérifier Docker
docker --version
# Devrait afficher quelque chose comme : Docker version 24.0.x

# Vérifier Docker Compose
docker compose version
# Devrait afficher : Docker Compose version v2.x.x

# Vérifier Git
git --version
# Devrait afficher : git version 2.x.x
```

✅ **Tout fonctionne ?** Parfait, on peut continuer !
❌ **Quelque chose ne marche pas ?** Installez l'outil manquant avant de continuer.

---

## 🚀 Installation pas à pas

### Étape 1 : Télécharger MnemoLite

Ouvrez un terminal et allez dans le dossier où vous voulez installer MnemoLite (par exemple `~/Projects` ou `C:\Projects`).

```bash
# Télécharger le code
git clone https://github.com/giak/MnemoLite.git
cd MnemoLite
```

**Ce qui se passe** : Git télécharge tous les fichiers du projet dans un nouveau dossier `MnemoLite`.

### Étape 2 : Configuration - Créer votre fichier `.env`

Le fichier `.env` contient tous les paramètres de configuration. Pensez-y comme aux **réglages personnels** de votre bibliothèque.

```bash
# Copier le fichier d'exemple
cp .env.example .env
```

**Ouvrez le fichier `.env`** avec votre éditeur de texte favori. Voici les paramètres importants :

```bash
# === Configuration PostgreSQL (votre bibliothécaire) ===
POSTGRES_USER=mnemo                    # Nom d'utilisateur de la base de données
POSTGRES_PASSWORD=mnemopass            # ⚠️ CHANGEZ ÇA en production !
POSTGRES_DB=mnemolite                  # Nom de votre bibliothèque
POSTGRES_PORT=5432                     # Port interne (laissez par défaut)

# === Configuration API ===
API_PORT=8001                          # Port pour accéder à l'API
                                       # http://localhost:8001

# === Configuration Embeddings (100% local) ===
EMBEDDING_MODEL=nomic-ai/nomic-embed-text-v1.5  # Le modèle d'IA local
EMBEDDING_DIMENSION=768                         # Taille des vecteurs

# === Environnement ===
ENVIRONMENT=development                # development ou production
```

**💡 Conseil** : Pour un premier test, vous pouvez garder les valeurs par défaut. En production, **changez absolument le mot de passe** !

### Étape 3 : Construire et lancer MnemoLite

Deux options : utiliser le **Makefile** (plus simple) ou **Docker Compose directement**.

#### Option A : Avec Make (recommandé)

```bash
# Démarrer tous les services
make up

# Vérifier que tout roule
make ps
```

#### Option B : Sans Make (Docker Compose direct)

```bash
# Construire les images
docker compose build

# Démarrer les services
docker compose up -d
```

**Ce qui se passe** :
1. 🏗️ Docker construit 3 "boîtes" (containers) :
   - **mnemo-postgres** : Votre base de données PostgreSQL avec les extensions magiques (pgvector, pg_partman)
   - **mnemo-api** : L'API FastAPI qui répond à vos requêtes HTTP
   - **mnemo-worker** : Un travailleur en arrière-plan pour les tâches lourdes (optionnel)

2. ⏳ **Première fois = plus long** : Docker télécharge les images de base (Python, PostgreSQL) et installe toutes les dépendances. Comptez 5-10 minutes.

3. 📦 Au premier démarrage, PostgreSQL initialise la base de données avec les scripts dans `db/init/`.

### Étape 4 : Vérifier que tout fonctionne

```bash
# Voir l'état des containers
docker compose ps
# Tous doivent être "Up" ou "Up (healthy)"

# Tester la santé de l'API
curl http://localhost:8001/health
```

**Réponse attendue** :
```json
{
  "status": "healthy",
  "services": {
    "postgres": {
      "status": "ok"
    }
  },
  "timestamp": "2025-10-17T20:00:00Z"
}
```

**Vérifier Code Intelligence (Nouveau v2.0.0)** :
```bash
# Tester le service d'indexation de code
curl http://localhost:8001/v1/code/index/health

# Réponse attendue: {"status":"healthy","message":"Code indexing service operational"}
```

🎉 **Ça marche ?** Félicitations ! MnemoLite v2.0.0 est opérationnel avec Agent Memory + Code Intelligence !

---

## 5. 🎮 Premiers Pas : Agent Memory (Parcours A)

> **Note** : Cette section concerne le **Parcours A** (Agent Memory).
> Si vous suivez le **Parcours B** (Code Intelligence), rendez-vous à la [Section 6](#6-premiers-pas--code-intelligence-parcours-b).
> Pour le **Parcours C**, lisez les deux sections !

Maintenant que votre bibliothèque est ouverte, apprenons à y ajouter des livres (événements) et à les retrouver.

### 1. Ajouter votre premier événement

Un **événement** dans MnemoLite, c'est comme une **fiche dans votre bibliothèque** avec :
- 📝 **content** : Le contenu principal (le texte du livre)
- 🏷️ **metadata** : Des étiquettes pour classer (genre, auteur, projet...)
- 🧬 **embedding** (optionnel) : L'empreinte sémantique (générée automatiquement si vous ne la fournissez pas)

```bash
curl -X POST http://localhost:8001/v1/events \
  -H "Content-Type: application/json" \
  -d '{
    "content": {
      "text": "Réunion de lancement du projet Expanse. Objectif : créer un agent conversationnel intelligent."
    },
    "metadata": {
      "type": "meeting",
      "project": "Expanse",
      "participants": ["Alice", "Bob", "Charlie"]
    }
  }'
```

**Ce qui se passe** :
1. MnemoLite reçoit votre événement
2. Il extrait le texte : "Réunion de lancement..."
3. Il génère automatiquement un **embedding 768-dimensions** avec le modèle local (nomic-embed-text-v1.5)
4. Il stocke tout dans PostgreSQL avec un index vectoriel HNSW pour recherche ultra-rapide

**Réponse** :
```json
{
  "id": "123e4567-e89b-12d3-a456-426614174000",
  "timestamp": "2025-10-12T14:30:00Z",
  "content": { "text": "Réunion de lancement..." },
  "metadata": { "type": "meeting", "project": "Expanse", ... },
  "embedding": [0.123, -0.456, 0.789, ...], // 768 valeurs
  "created_at": "2025-10-12T14:30:00Z"
}
```

### 2. Rechercher par sens (recherche vectorielle)

La **magie des embeddings** : cherchez par le sens, pas par les mots exacts !

```bash
curl -G http://localhost:8001/v1/search/ \
  --data-urlencode "vector_query=agent conversationnel intelligent" \
  --data-urlencode "limit=5" \
  -H "Accept: application/json"
```

**Ce qui se passe** :
1. MnemoLite transforme votre requête "agent conversationnel intelligent" en embedding
2. Il cherche dans la base les événements avec les embeddings **les plus proches** (cosinus similarity)
3. Il retourne les 5 résultats les plus pertinents

**Résultat** : Votre événement "Réunion de lancement du projet Expanse" sera trouvé, même si les mots ne sont pas exactement les mêmes !

### 3. Recherche hybride (vecteur + métadonnées)

Combinez la recherche sémantique avec des filtres précis :

```bash
curl -G http://localhost:8001/v1/search/ \
  --data-urlencode 'vector_query=projet intelligence artificielle' \
  --data-urlencode 'filter_metadata={"project":"Expanse"}' \
  --data-urlencode "limit=10" \
  -H "Accept: application/json"
```

**Ce qui se passe** : "Trouve-moi tout ce qui parle d'IA **ET** qui est lié au projet Expanse"

### 3.5 🎯 Optimiser la précision avec le seuil de distance (distance_threshold)

Le paramètre **`distance_threshold`** contrôle à quel point les résultats doivent être **similaires** à votre requête. C'est comme régler la "sensibilité" de votre recherche.

**Comment ça marche ?**
- MnemoLite utilise la **distance L2** (Euclidienne) entre les embeddings
- Plus la distance est **petite**, plus les résultats sont **proches** sémantiquement
- La plage va de **0 à 2** (pour des vecteurs normalisés)

**Valeurs recommandées** :

| Valeur | Mode | Usage | Résultats attendus |
|--------|------|-------|-------------------|
| **0.8** | Strict | Haute précision | Peu de résultats, très pertinents |
| **1.0** | Équilibré (défaut) | Usage général | Bon compromis précision/rappel |
| **1.2** | Relax | Haute couverture | Plus de résultats, pertinence élargie |
| **None** ou **2.0** | Top-K | Sans filtrage | K résultats les plus proches |

**Exemple - Recherche stricte** :
```bash
curl -G http://localhost:8001/v1/search/ \
  --data-urlencode 'vector_query=erreur critique système' \
  --data-urlencode "distance_threshold=0.8" \
  --data-urlencode "limit=5" \
  -H "Accept: application/json"
```

**Exemple - Recherche large** :
```bash
curl -G http://localhost:8001/v1/search/ \
  --data-urlencode 'vector_query=projet IA' \
  --data-urlencode "distance_threshold=1.2" \
  --data-urlencode "limit=10" \
  -H "Accept: application/json"
```

**🛡️ Protection automatique (Adaptive Fallback)** :

Si votre `distance_threshold` est trop strict et retourne **0 résultats**, MnemoLite active automatiquement le **mode fallback** :
- Il réessaie la recherche **sans threshold** (mode top-K)
- Vous obtenez les K résultats les plus proches, garantis
- Un avertissement est logué pour vous informer

**Conditions du fallback** :
- ✅ Recherche vectorielle pure (pas de filtres metadata ou time)
- ✅ Threshold défini ET 0 résultats obtenus
- ✅ Fallback activé par défaut (`enable_fallback=true`)

**Exemple de log** :
```
WARNING: Vector search with threshold 0.5 returned 0 results.
Falling back to top-K mode (no threshold).
```

**💡 Conseil pratique** :
- **Commencez avec 1.0** (valeur par défaut) et ajustez selon vos besoins
- **0.8 ou moins** : Réservé aux recherches très spécifiques (ex: détection de doublons)
- **1.2 ou plus** : Pour des recherches exploratoires larges

### 4. Recherche par période (time-based)

Grâce au **partitionnement automatique** (pg_partman), les recherches temporelles sont ultra-rapides :

```bash
curl -G http://localhost:8001/v1/search/ \
  --data-urlencode 'filter_metadata={"project":"Expanse"}' \
  --data-urlencode "ts_start=2025-10-01T00:00:00Z" \
  --data-urlencode "ts_end=2025-10-31T23:59:59Z" \
  --data-urlencode "limit=20" \
  -H "Accept: application/json"
```

**Ce qui se passe** : PostgreSQL utilise le **partition pruning** - il ne regarde que les partitions (tables) du mois d'octobre, ignorant le reste. Résultat : recherche en ~3ms !

---

## 6. 💻 Premiers Pas : Code Intelligence (Parcours B)

> **Note** : Cette section concerne le **Parcours B** (Code Intelligence).
> Si vous suivez le **Parcours A** (Agent Memory), vous avez déjà couvert la [Section 5](#5-premiers-pas--agent-memory-parcours-a).
> Pour le **Parcours C**, lisez les deux sections !

Maintenant que votre système est prêt, découvrons comment indexer et analyser votre code avec l'intelligence artificielle.

### 1. Indexer votre premier fichier de code

Le **code chunking** dans MnemoLite, c'est comme **découper un livre en chapitres** automatiquement :
- 🌳 **Analyse AST** : Tree-sitter comprend la structure de votre code (fonctions, classes, méthodes)
- 🧬 **Dual Embeddings** : Deux vecteurs 768D pour chaque chunk (TEXT pour docstrings, CODE pour le code source)
- 📊 **Métadonnées** : Complexité cyclomatique, paramètres, appels de fonctions, imports
- 🕸️ **Graphe** : Construction automatique des dépendances (qui appelle quoi)

**Exemple : Indexer un fichier Python**

```bash
curl -X POST http://localhost:8001/v1/code/index \
  -H "Content-Type: application/json" \
  -d '{
    "repository": "my-project",
    "files": [
      {
        "path": "src/calculator.py",
        "content": "def add(a, b):\n    \"\"\"Adds two numbers.\"\"\"\n    return a + b\n\ndef multiply(a, b):\n    \"\"\"Multiplies two numbers.\"\"\"\n    return a * b"
      }
    ]
  }'
```

**Ce qui se passe** :
1. 🔍 **Détection du langage** : MnemoLite détecte automatiquement que c'est du Python
2. 🌳 **Parsing AST** : Tree-sitter analyse la structure et extrait 2 fonctions (`add`, `multiply`)
3. 📊 **Extraction métadonnées** : Pour chaque fonction :
   - Complexité cyclomatique (ici : 1 pour chaque)
   - Paramètres : `["a", "b"]`
   - Docstring : "Adds two numbers.", "Multiplies two numbers."
4. 🧬 **Génération dual embeddings** :
   - **TEXT embedding** (768D) : Basé sur la docstring
   - **CODE embedding** (768D) : Basé sur le code source
5. 🕸️ **Construction du graphe** : 2 nœuds créés (function:add, function:multiply)
6. 💾 **Stockage** : Tout est indexé dans PostgreSQL avec HNSW vectoriel

**Réponse** :
```json
{
  "repository": "my-project",
  "indexed_files": 1,
  "total_chunks": 2,
  "chunks": [
    {
      "id": "uuid-1",
      "file_path": "src/calculator.py",
      "chunk_type": "function",
      "name": "add",
      "start_line": 1,
      "end_line": 3,
      "language": "python",
      "metadata": {
        "complexity": {"cyclomatic": 1},
        "parameters": ["a", "b"],
        "docstring": "Adds two numbers."
      }
    },
    {
      "id": "uuid-2",
      "file_path": "src/calculator.py",
      "chunk_type": "function",
      "name": "multiply",
      "start_line": 5,
      "end_line": 7,
      "language": "python",
      "metadata": {
        "complexity": {"cyclomatic": 1},
        "parameters": ["a", "b"],
        "docstring": "Multiplies two numbers."
      }
    }
  ],
  "processing_time_ms": 85
}
```

**Langages supportés** : Python, JavaScript, TypeScript, Go, Rust, Java, C++, C#, Ruby, PHP, Swift, Kotlin, Scala, R, Shell... (15+ langages via Tree-sitter)

### 2. Rechercher dans le code (Hybrid Search)

La **recherche hybride** combine 3 techniques complémentaires pour une précision maximale :

**🔹 Recherche Lexicale (BM25)** : Mots-clés exacts avec pg_trgm
**🔹 Recherche Vectorielle (Sémantique)** : Similarité cosinus avec HNSW
**🔹 RRF Fusion (k=60)** : Combine les deux avec Reciprocal Rank Fusion

**Exemple : Recherche hybride**

```bash
curl -X POST http://localhost:8001/v1/code/search/hybrid \
  -H "Content-Type: application/json" \
  -d '{
    "query": "function that adds numbers together",
    "limit": 5,
    "language": "python"
  }'
```

**Ce qui se passe** :
1. 🔍 **Lexical Search** : Recherche BM25 sur le code source + docstrings (trouve "adds", "numbers")
2. 🧬 **Vector Search** : Génère un embedding pour "function that adds numbers together" et cherche les plus proches
3. 🎯 **RRF Fusion** : Combine les scores des deux recherches avec k=60
4. 📊 **Ranking** : Trie par score RRF décroissant
5. ⚡ **Performance** : <200ms P95 (28× plus rapide que l'objectif de 5000ms)

**Réponse** :
```json
{
  "results": [
    {
      "chunk_id": "uuid-1",
      "file_path": "src/calculator.py",
      "name": "add",
      "chunk_type": "function",
      "source_code": "def add(a, b):\n    \"\"\"Adds two numbers.\"\"\"\n    return a + b",
      "rrf_score": 0.95,
      "lexical_rank": 1,
      "vector_rank": 1,
      "metadata": {
        "complexity": {"cyclomatic": 1},
        "parameters": ["a", "b"],
        "docstring": "Adds two numbers."
      }
    }
  ],
  "total_results": 1,
  "search_time_ms": 142
}
```

**💡 Astuce** : La recherche hybride est **ultra-tolérante** :
- ✅ "calculate sum" → Trouvera `add()`
- ✅ "multiply two values" → Trouvera `multiply()`
- ✅ "fonction d'addition" → Trouvera `add()` (multilangue)

**Autres types de recherche disponibles** :

**Recherche lexicale pure (BM25)**
```bash
curl -X POST http://localhost:8001/v1/code/search/lexical \
  -H "Content-Type: application/json" \
  -d '{"query": "add numbers", "limit": 5}'
```

**Recherche vectorielle pure (Sémantique)**
```bash
curl -X POST http://localhost:8001/v1/code/search/vector \
  -H "Content-Type: application/json" \
  -d '{"query": "function that sums values", "limit": 5}'
```

### 3. Explorer le graphe de dépendances

Le **graphe de dépendances** révèle automatiquement **qui appelle quoi** dans votre code.

**3.1 Construire le graphe pour un repository**

```bash
curl -X POST http://localhost:8001/v1/code/graph/build \
  -H "Content-Type: application/json" \
  -d '{"repository": "my-project"}'
```

**Ce qui se passe** :
1. 🔍 **Récupération** : Tous les chunks du repository "my-project"
2. 🌳 **Analyse** : Pour chaque fonction/classe :
   - Extraction des appels de fonctions (`metadata.calls`)
   - Extraction des imports (`metadata.imports`)
3. 🕸️ **Résolution** : Stratégie en 3 étapes :
   - **Local** : Cherche dans le même fichier
   - **Imports** : Cherche dans les imports trackés
   - **Best-effort** : Recherche globale par nom de fonction
4. ⚡ **Construction** : Création des nœuds et arêtes
   - Nœuds : `{node_id, node_type, label, properties}`
   - Arêtes : `{edge_id, source, target, relation_type}` (calls, imports)
5. 🛡️ **Filtrage** : 73 built-ins Python automatiquement exclus (print, len, range, etc.)

**Réponse** :
```json
{
  "repository": "my-project",
  "nodes_created": 15,
  "edges_created": 8,
  "build_time_ms": 245,
  "statistics": {
    "nodes_by_type": {
      "function": 12,
      "class": 2,
      "method": 1
    },
    "edges_by_relation": {
      "calls": 6,
      "imports": 2
    }
  }
}
```

**3.2 Traverser le graphe (Recursive CTEs)**

Une fois le graphe construit, explorez les dépendances avec des **traversées ultra-rapides** (0.155ms - 129× plus rapide que l'objectif de 20ms) :

**Exemple : Qui appelle ma fonction ?** (Inbound - cherche les callers)
```bash
curl -X POST http://localhost:8001/v1/code/graph/traverse \
  -H "Content-Type: application/json" \
  -d '{
    "start_node_id": "uuid-of-add-function",
    "direction": "inbound",
    "relation_type": "calls",
    "max_depth": 3
  }'
```

**Exemple : Qu'appelle ma fonction ?** (Outbound - cherche les callees)
```bash
curl -X POST http://localhost:8001/v1/code/graph/traverse \
  -H "Content-Type: application/json" \
  -d '{
    "start_node_id": "uuid-of-main-function",
    "direction": "outbound",
    "relation_type": "calls",
    "max_depth": 3
  }'
```

**Ce qui se passe** :
1. 🚀 **Recursive CTE** : PostgreSQL utilise `WITH RECURSIVE` pour traverser le graphe
2. 🎯 **Filtrage** : Direction (inbound/outbound), type de relation (calls/imports)
3. 📏 **Profondeur** : Limite à 3 hops maximum (configurable)
4. ⚡ **Performance** : 0.155ms en moyenne (grâce aux indexes B-tree)

**Réponse** :
```json
{
  "start_node": {
    "node_id": "uuid-of-add-function",
    "label": "add",
    "node_type": "function"
  },
  "paths": [
    {
      "depth": 1,
      "nodes": [
        {"node_id": "uuid-main", "label": "main", "node_type": "function"}
      ],
      "edges": [
        {"relation_type": "calls", "source": "uuid-main", "target": "uuid-of-add-function"}
      ]
    }
  ],
  "total_paths": 1,
  "max_depth_reached": 1,
  "traversal_time_ms": 0.155
}
```

**3.3 Trouver le chemin entre deux nœuds**

```bash
curl -X POST http://localhost:8001/v1/code/graph/path \
  -H "Content-Type: application/json" \
  -d '{
    "source_node_id": "uuid-function-A",
    "target_node_id": "uuid-function-B",
    "relation_type": "calls"
  }'
```

**Ce qui se passe** : Algorithme de plus court chemin entre A et B

**Réponse** :
```json
{
  "path_found": true,
  "path": [
    {"label": "functionA", "node_type": "function"},
    {"label": "helperFunction", "node_type": "function"},
    {"label": "functionB", "node_type": "function"}
  ],
  "distance": 2,
  "edges": [
    {"relation_type": "calls", "source": "A", "target": "helper"},
    {"relation_type": "calls", "source": "helper", "target": "B"}
  ]
}
```

### 4. Analytics de code

Analysez la santé et la complexité de votre codebase avec des **statistiques automatiques**.

**Exemple : Statistiques du repository**

```bash
curl -X GET "http://localhost:8001/v1/code/graph/stats?repository=my-project" \
  -H "Accept: application/json"
```

**Ce qui se passe** :
1. 📊 **Agrégation SQL** : Calcul des métriques sur tous les chunks du repository
2. 🎯 **Analyse** :
   - Complexité cyclomatique (moyenne, min, max)
   - Distribution par type de chunk (function, class, method)
   - Nombre de nœuds et arêtes
   - Top 10 fonctions par complexité

**Réponse** :
```json
{
  "repository": "my-project",
  "total_chunks": 127,
  "total_nodes": 115,
  "total_edges": 78,
  "complexity": {
    "average": 3.2,
    "min": 1,
    "max": 15,
    "median": 2
  },
  "distribution": {
    "by_type": {
      "function": 89,
      "class": 18,
      "method": 12,
      "module": 8
    },
    "by_language": {
      "python": 127
    }
  },
  "top_complex_functions": [
    {
      "name": "process_data",
      "file_path": "src/processor.py",
      "complexity": 15,
      "lines": 87
    },
    {
      "name": "validate_input",
      "file_path": "src/validator.py",
      "complexity": 12,
      "lines": 65
    }
  ],
  "graph_metrics": {
    "average_degree": 1.35,
    "max_depth": 5,
    "connected_components": 3
  }
}
```

**💡 Interprétation** :
- **Complexité moyenne 3.2** : Code sain (< 5 est recommandé)
- **Max complexité 15** : `process_data()` mérite probablement un refactoring
- **3 composants connectés** : Votre codebase a 3 groupes de fonctions indépendantes

**Exemple : Lister tous les chunks d'un repository**

```bash
curl -X GET "http://localhost:8001/v1/code/index/list?repository=my-project&limit=20" \
  -H "Accept: application/json"
```

**Exemple : Supprimer un repository**

```bash
curl -X DELETE "http://localhost:8001/v1/code/index/delete?repository=my-project" \
  -H "Accept: application/json"
```

**🎉 Félicitations !** Vous maîtrisez maintenant le Code Intelligence de MnemoLite v2.0.0 !

---

## 7. 🎨 Interface Web v2.0.0 - Design SCADA Industriel

MnemoLite v2.0.0 inclut une **interface Web complète** (HTMX 2.0) avec un design **SCADA industriel** pour explorer visuellement vos données **Agent Memory** ET **Code Intelligence**.

Ouvrez simplement votre navigateur : **http://localhost:8001/ui/**

### 7.1 🧠 Pages Agent Memory (Parcours A)

**Dashboard Agent Memory** (`/ui/`)
- Vue d'ensemble des événements récents
- Filtres par période (24h, 7j, 30j, tout)
- Filtres par projet et catégorie
- Cartes de statistiques en temps réel
- Graphiques de distribution temporelle

**Recherche Sémantique** (`/ui/search`)
- Recherche vectorielle par sens (pas par mots-clés)
- Recherche hybride (vecteur + métadonnées + temps)
- Ajustement du seuil de similarité (distance_threshold)
- Résultats avec scores de pertinence
- Affichage des embeddings (optionnel)

**Graphe de Connaissances** (`/ui/graph`)
- Visualisation interactive des relations (Cytoscape.js)
- 5 algorithmes de layout (cose, circle, grid, breadthfirst, concentric)
- Filtres par type de nœud (event, entity, concept)
- Détails des nœuds et arêtes au clic
- Minimap pour navigation
- Export PNG/JSON

**Monitoring Agent Memory** (`/ui/monitoring`)
- Graphiques Chart.js en temps réel
- Timeline d'activité des événements
- Distribution par type et projet
- Événements critiques récents
- Auto-refresh toutes les 30 secondes
- Métriques de performance (recherche, indexation)

### 7.2 💻 Pages Code Intelligence (Parcours B)

**Dashboard Code Intelligence** (`/ui/code/dashboard`)
- Vue d'ensemble des repositories indexés
- KPIs : Chunks totaux, fonctions, complexité moyenne
- Top 10 fichiers par complexité
- Distribution par langage (pie chart)
- Timeline d'indexation
- Graphiques de santé du code

**Repository Manager** (`/ui/code/repos`)
- Liste des repositories indexés
- Statistiques par repository (chunks, nodes, edges)
- Actions : Rebuild graph, Delete repository
- Filtres par langage et date
- Bouton "Index New Repository"

**Code Search** (`/ui/code/search`)
- Recherche hybride (lexicale + vectorielle + RRF fusion)
- Filtres : repository, langage, type de chunk
- Résultats avec scores RRF + syntaxe highlighting
- Affichage du code source complet
- Liens vers fichiers et graphe de dépendances
- Export des résultats (JSON, CSV)

**Dependency Graph** (`/ui/code/graph`)
- Visualisation interactive Cytoscape.js
- Filtres : repository, relation_type (calls, imports)
- Layouts spécialisés (hierarchical, cose-bilkent)
- Détails des nœuds (fonctions/classes) et arêtes
- Highlight des chemins critiques
- Traversal interactif (inbound/outbound, depth)
- Minimap et zoom
- Export PNG/JSON

**Upload Interface** (`/ui/code/upload`)
- Drag & drop de fichiers ou dossiers
- Sélection du repository cible
- Détection automatique du langage
- Barre de progression en temps réel
- Résumé de l'indexation (chunks créés, graphe construit)
- Historique des uploads

### ✨ Fonctionnalités UI v2.0.0

**🎨 Design System SCADA Industriel Unifié**
- Ultra dark palette (#0a0e27 background, accents blue/green/red/cyan)
- Zéro border-radius (aesthetic industrielle)
- Compact spacing (haute densité d'information)
- Transitions ultra-rapides (80ms)
- Couleurs vives pour les statuts (critical, warning, ok, success)
- **100% cohérence** entre les 9 pages (Agent Memory + Code Intelligence)

**⚡ Performance & UX**
- Architecture CSS modulaire (18 modules + variables)
- JavaScript organisé (6 core + 5 composants spécialisés)
- Composants réutilisables : event_card, code_result, filters, modal, graph_node
- Gestion d'erreurs globale avec retry automatique
- Patterns HTMX standardisés (data-attributes)
- Chargement lazy des graphes (>1000 nœuds)
- Pagination intelligente (infinite scroll)

**♿ Accessibilité**
- ARIA attributes pour lecteurs d'écran
- Navigation clavier complète (Tab, Enter, Esc)
- Focus trapping dans les modaux
- Indicateurs de chargement accessibles
- Couleurs à contraste élevé (WCAG AAA)

**🔥 Philosophie "EXTEND DON'T REBUILD"**
- Code Intelligence UI réutilise 100% des styles Agent Memory
- Composants graph.js → code_graph.js (adaptation minimale)
- Zéro CSS nouveau (réutilisation totale du système SCADA)
- **Résultat** : Développement 8-9× plus rapide (2 jours vs 16-19 estimés)

**Documentation API interactive** :
- **Swagger UI** : http://localhost:8001/docs (Agent Memory + Code Intelligence)
- **ReDoc** : http://localhost:8001/redoc

---

## 🐛 Dépannage : Quand ça ne marche pas

### Problème 1 : "Cannot connect to Docker daemon"

**Symptôme** : `Cannot connect to the Docker daemon at unix:///var/run/docker.sock`

**Solution** :
```bash
# Vérifier que Docker est lancé
docker info

# Si erreur, démarrer Docker Desktop (Mac/Windows)
# ou démarrer le service (Linux)
sudo systemctl start docker
```

### Problème 2 : "Port 8001 already in use"

**Symptôme** : `Bind for 0.0.0.0:8001 failed: port is already allocated`

**Solution** : Changez le port dans `.env`
```bash
# Éditez .env et changez :
API_PORT=8002  # ou n'importe quel port libre
```

Puis relancez :
```bash
docker compose down
docker compose up -d
```

### Problème 3 : Container "mnemo-postgres" en état "Restarting"

**Symptôme** : `docker compose ps` montre que postgres redémarre en boucle

**Solution** : Vérifier les logs
```bash
docker logs mnemo-postgres

# Si problème de mémoire partagée, ajustez shm_size dans docker-compose.yml
# Si problème de permissions, supprimez le volume et recommencez :
docker compose down -v
docker compose up -d
```

### Problème 4 : "ModuleNotFoundError" dans l'API

**Symptôme** : Erreur Python lors du démarrage de l'API

**Solution** : Reconstruire l'image
```bash
# Rebuild complet sans cache
docker compose build --no-cache api
docker compose up -d
```

### Problème 5 : Embeddings lents au premier appel

**Normal** ! Au premier appel, le modèle `nomic-embed-text-v1.5` est téléchargé (~1 GB) et chargé en mémoire. Ensuite, c'est ultra-rapide (~30ms en moyenne).

**Suivre le téléchargement** :
```bash
docker logs -f mnemo-api
# Vous verrez : "Downloading model..."
```

---

## 8. 🔥 Use Cases Avancés : Combiner Agent Memory + Code Intelligence (Parcours C)

> **Note** : Cette section est particulièrement pertinente pour le **Parcours C** (Full Stack).
> Elle montre comment **combiner les deux capacités** de MnemoLite v2.0.0 pour des cas d'usage innovants.

La vraie puissance de MnemoLite v2.0.0, c'est la **synergie** entre Agent Memory et Code Intelligence. Voici des exemples concrets.

### 8.1 🤖 Agent IA qui comprend votre code

**Scénario** : Un assistant conversationnel qui répond à vos questions sur votre codebase.

**Comment ça marche** :
1. **Indexation** : Vous indexez votre repository avec `/v1/code/index`
2. **Conversation** : L'utilisateur demande "Comment fonctionne l'authentification ?"
3. **Code Search** : MnemoLite cherche dans le code avec `/v1/code/search/hybrid?query=authentication`
4. **Contexte** : L'agent récupère les chunks pertinents (fonctions, classes)
5. **Mémorisation** : L'agent stocke la conversation dans `/v1/events` pour se souvenir
6. **Réponse** : L'agent répond avec le contexte du code + mémoire des échanges précédents

**Exemple de workflow** :

```bash
# Étape 1 : Indexer le code
curl -X POST http://localhost:8001/v1/code/index \
  -d '{"repository": "my-app", "files": [...]}'

# Étape 2 : Question utilisateur → Code Search
curl -X POST http://localhost:8001/v1/code/search/hybrid \
  -d '{"query": "authentication login flow", "repository": "my-app"}'

# Étape 3 : Stocker la conversation
curl -X POST http://localhost:8001/v1/events \
  -d '{
    "content": {"text": "User asked about authentication. Provided code from src/auth.py"},
    "metadata": {"type": "conversation", "topic": "authentication"}
  }'

# Étape 4 : Prochaine question → Recherche dans la mémoire
curl -G http://localhost:8001/v1/search/ \
  --data-urlencode 'vector_query=authentication conversation' \
  --data-urlencode 'filter_metadata={"type":"conversation"}'
```

**Résultat** : Un agent qui se souvient de vos conversations ET comprend votre code !

### 8.2 📝 Code Review Assisté par IA

**Scénario** : Vous ouvrez une Pull Request. MnemoLite analyse les changements et suggère des améliorations.

**Workflow** :

1. **Indexation baseline** : Indexez la branche `main` (`repository: "my-app-main"`)
2. **Indexation PR** : Indexez la branche PR (`repository: "my-app-pr-123"`)
3. **Comparaison** : Cherchez les différences de complexité
4. **Graphe de dépendances** : Vérifiez l'impact des changements (qui appelle les nouvelles fonctions ?)
5. **Mémorisation** : Stockez les reviews précédentes pour apprendre les patterns

**Exemple d'analyse** :

```bash
# Comparer la complexité
curl -X GET "http://localhost:8001/v1/code/graph/stats?repository=my-app-main"
curl -X GET "http://localhost:8001/v1/code/graph/stats?repository=my-app-pr-123"

# Analyser l'impact dans le graphe
curl -X POST http://localhost:8001/v1/code/graph/build \
  -d '{"repository": "my-app-pr-123"}'

curl -X POST http://localhost:8001/v1/code/graph/traverse \
  -d '{"start_node_id": "<new-function-uuid>", "direction": "inbound", "max_depth": 3}'

# Stocker la review
curl -X POST http://localhost:8001/v1/events \
  -d '{
    "content": {"text": "PR #123: Added new authentication method. Complexity increased from 3.2 to 4.1. Impact: 7 callers found."},
    "metadata": {"type": "code_review", "pr": 123, "repository": "my-app"}
  }'
```

**Détection automatique** :
- ⚠️ **Complexité élevée** : Nouvelle fonction avec complexité > 10
- 🕸️ **Impact large** : Fonction appelée par >20 autres fonctions
- 🐛 **Code dupliqué** : Recherche vectorielle détecte du code similaire

### 8.3 🔍 Debugging Intelligent avec Mémoire

**Scénario** : Vous debuggez un bug. MnemoLite vous aide en se souvenant des bugs similaires passés.

**Workflow** :

1. **Erreur détectée** : Stockez l'erreur dans Agent Memory
2. **Code Search** : Cherchez les fonctions liées à l'erreur
3. **Graph Traversal** : Trouvez le chemin d'appels qui a causé l'erreur
4. **Recherche de patterns** : Cherchez des bugs similaires dans l'historique
5. **Solution** : Stockez la solution pour référence future

**Exemple** :

```bash
# 1. Stocker l'erreur
curl -X POST http://localhost:8001/v1/events \
  -d '{
    "content": {"text": "NullPointerException in UserService.validateEmail(). Stack trace: ..."},
    "metadata": {"type": "error", "severity": "critical", "service": "UserService"}
  }'

# 2. Chercher le code concerné
curl -X POST http://localhost:8001/v1/code/search/hybrid \
  -d '{"query": "validateEmail null pointer", "repository": "my-app"}'

# 3. Traverser le graphe pour trouver les callers
curl -X POST http://localhost:8001/v1/code/graph/traverse \
  -d '{"start_node_id": "<validateEmail-uuid>", "direction": "inbound", "max_depth": 3}'

# 4. Chercher des erreurs similaires dans l'historique
curl -G http://localhost:8001/v1/search/ \
  --data-urlencode 'vector_query=NullPointerException UserService' \
  --data-urlencode 'filter_metadata={"type":"error"}'

# 5. Stocker la solution
curl -X POST http://localhost:8001/v1/events \
  -d '{
    "content": {"text": "Fixed: Added null check in validateEmail(). Root cause: Missing validation in createUser()."},
    "metadata": {"type": "solution", "related_error_id": "<error-uuid>"}
  }'
```

**Bénéfice** : La prochaine fois qu'une erreur similaire survient, l'agent la détecte instantanément !

### 8.4 🎓 Onboarding Automatique pour Nouveaux Développeurs

**Scénario** : Un nouveau dev rejoint l'équipe. MnemoLite génère une documentation interactive.

**Workflow** :

1. **Analyse du codebase** : Indexez tout le repository
2. **Identification des points d'entrée** : Graphe de dépendances → trouvez les fonctions `main()`, `app.run()`, etc.
3. **Génération de parcours** : Pour chaque module, créez un parcours de lecture
4. **Q&A interactive** : Le nouveau dev pose des questions → MnemoLite répond avec code + contexte
5. **Mémorisation** : Stockez les questions fréquentes pour améliorer la doc

**Exemple** :

```bash
# 1. Analyser le graphe pour trouver les points d'entrée
curl -X GET "http://localhost:8001/v1/code/graph/stats?repository=my-app"

# 2. Chercher les fonctions critiques
curl -X POST http://localhost:8001/v1/code/search/hybrid \
  -d '{"query": "main entry point application startup", "repository": "my-app"}'

# 3. Générer un parcours (exemple : module auth)
curl -X POST http://localhost:8001/v1/code/graph/traverse \
  -d '{"start_node_id": "<auth-module-uuid>", "direction": "outbound", "max_depth": 2}'

# 4. Stocker les questions fréquentes
curl -X POST http://localhost:8001/v1/events \
  -d '{
    "content": {"text": "Q: How does authentication work? A: See src/auth.py, function authenticate(). Uses JWT tokens."},
    "metadata": {"type": "onboarding", "topic": "authentication"}
  }'
```

**Documentation auto-générée** :
- 📊 **Architecture overview** : Graphe visuel des dépendances
- 🔍 **Code search** : Trouvez n'importe quelle fonctionnalité
- 💬 **FAQ contextuelle** : Basée sur l'historique des questions

### 8.5 🚀 CI/CD Intelligence : Prédire l'impact des changements

**Scénario** : Avant de merger une PR, prédisez l'impact sur les performances et la complexité.

**Workflow** :

1. **Baseline** : Indexez `main` et stockez les métriques
2. **PR** : Indexez la branche PR
3. **Comparaison** : Différence de complexité, nombre de fonctions affectées
4. **Prédiction** : Basée sur l'historique, estimez le risque
5. **Décision** : Auto-approve si risque faible, demandez review si risque élevé

**Exemple d'analyse CI/CD** :

```bash
# Pipeline CI/CD

# Step 1: Index PR branch
curl -X POST http://localhost:8001/v1/code/index \
  -d '{"repository": "my-app-pr-456", "files": [...]}'

# Step 2: Compare stats
MAIN_STATS=$(curl -X GET "http://localhost:8001/v1/code/graph/stats?repository=my-app-main")
PR_STATS=$(curl -X GET "http://localhost:8001/v1/code/graph/stats?repository=my-app-pr-456")

# Step 3: Detect regressions
# - Complexity increase > 20%
# - New functions with complexity > 10
# - Impact on >50 existing functions

# Step 4: Store build result
curl -X POST http://localhost:8001/v1/events \
  -d '{
    "content": {"text": "PR #456 CI/CD: Complexity +15%, 2 high-complexity functions, 12 affected functions"},
    "metadata": {"type": "ci_cd", "pr": 456, "status": "warning"}
  }'
```

**Alertes automatiques** :
- 🔴 **Blocage** : Complexité > +50% OU nouvelle fonction complexité > 15
- 🟡 **Warning** : Complexité > +20% OU impact > 50 fonctions
- 🟢 **Auto-approve** : Complexité stable, faible impact

### 8.6 🎯 Patterns Avancés

**Pattern 1 : Dual Search (Code + Memory)**
```bash
# Chercher dans le code ET dans les conversations
CODE_RESULTS=$(curl -X POST http://localhost:8001/v1/code/search/hybrid -d '{"query": "payment processing"}')
MEMORY_RESULTS=$(curl -G http://localhost:8001/v1/search/ --data-urlencode 'vector_query=payment processing')

# Combiner les résultats dans votre agent
```

**Pattern 2 : Graph + Memory pour tracer les décisions**
```bash
# Quand une décision architecturale est prise
curl -X POST http://localhost:8001/v1/events \
  -d '{
    "content": {"text": "Decision: Refactored PaymentService to use async processing"},
    "metadata": {"type": "architecture_decision", "affected_nodes": ["<PaymentService-uuid>"]}
  }'

# Puis lier la décision au graphe de code
```

**Pattern 3 : Time-based Analysis**
```bash
# Analyser l'évolution de la complexité sur 6 mois
# 1. Rechercher les indexations historiques
curl -G http://localhost:8001/v1/search/ \
  --data-urlencode 'filter_metadata={"type":"code_index"}' \
  --data-urlencode "ts_start=2025-04-01T00:00:00Z" \
  --data-urlencode "ts_end=2025-10-01T00:00:00Z"

# 2. Comparer les métriques
```

**🎉 Résultat** : Avec MnemoLite v2.0.0, vous créez des outils d'intelligence de code **sur-mesure** pour vos besoins !

---

## ❓ FAQ : Questions fréquentes

### Q1 : Est-ce que mes données sortent de ma machine ?

**Réponse** : NON ! MnemoLite est **100% local**. Aucune donnée ne sort de votre ordinateur. Les embeddings sont générés localement avec Sentence-Transformers, sans appel API externe.

### Q2 : Combien d'événements puis-je stocker ?

**Réponse** : Des millions ! Grâce au partitionnement automatique (pg_partman), PostgreSQL gère efficacement des volumes massifs. Avec 50 000 événements, les recherches sont déjà à ~12ms P95.

### Q3 : Puis-je utiliser MnemoLite en production ?

**Réponse** : Oui, mais :
1. **Changez les mots de passe** dans `.env`
2. Configurez des sauvegardes régulières (`make db-backup`)
3. Ajustez les ressources Docker (`docker-compose.yml` > `deploy.resources.limits`)
4. Utilisez HTTPS avec un reverse proxy (nginx, traefik)

### Q4 : Comment sauvegarder mes données ?

```bash
# Sauvegarde manuelle
make db-backup

# Ou avec Docker directement
docker exec mnemo-postgres pg_dump -U mnemo mnemolite > backup_$(date +%Y%m%d).sql
```

### Q5 : Puis-je changer le modèle d'embeddings ?

**Réponse** : Oui ! Éditez `.env` :
```bash
EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2  # Plus petit, plus rapide
EMBEDDING_DIMENSION=384  # Adapter selon le modèle
```

**Attention** : Si vous changez de modèle, les embeddings existants deviennent incompatibles. Il faut régénérer tous les embeddings ou repartir d'une base vierge.

### Q6 : Comment arrêter MnemoLite ?

```bash
# Arrêter les containers (données conservées)
docker compose stop

# Arrêter ET supprimer les containers (données dans volumes conservées)
docker compose down

# Tout supprimer (containers + volumes = perte de données !)
docker compose down -v
```

### Q7 : Est-ce que je peux connecter mon agent IA (LangChain, LlamaIndex, etc.) ?

**Absolument !** MnemoLite expose une API REST standard. Exemples :
- **LangChain** : Utilisez `requests` pour appeler `/v1/events` et `/v1/search`
- **LlamaIndex** : Intégrez comme un `VectorStore` custom
- **Expanse** : C'est justement fait pour ça ! 🎯

---

### Q8 : Quels langages de programmation sont supportés par Code Intelligence ?

**Réponse** : MnemoLite supporte **15+ langages** via Tree-sitter :
- ✅ **Web** : JavaScript, TypeScript, HTML, CSS
- ✅ **Backend** : Python, Go, Rust, Java, C++, C#, Ruby, PHP
- ✅ **Mobile** : Swift, Kotlin
- ✅ **Data Science** : R, Scala
- ✅ **Shell** : Bash, Shell

**Détection automatique** : MnemoLite détecte le langage automatiquement via l'extension de fichier (`.py`, `.js`, `.go`, etc.).

**Qualité de l'analyse** :
- 🟢 **Excellent** : Python, JavaScript, TypeScript, Go, Rust
- 🟡 **Bon** : Java, C++, Ruby, PHP, Swift
- 🟠 **Basique** : Shell, R (parsing sans métadonnées avancées)

### Q9 : Quelle est la différence entre recherche lexicale, vectorielle et hybride ?

**Réponse** : Les 3 approches sont complémentaires :

**🔹 Recherche Lexicale (BM25)** :
- **Comment** : Mots-clés exacts avec pg_trgm (trigrams)
- **Bon pour** : Noms de fonctions, identifiants exacts
- **Exemple** : Chercher `calculate_sum` trouve exactement cette fonction
- **Limite** : Ne comprend pas le sens, juste les mots

**🔹 Recherche Vectorielle (Sémantique)** :
- **Comment** : Similarité cosinus entre embeddings 768D
- **Bon pour** : Concepts, descriptions, code similaire
- **Exemple** : "fonction qui additionne" trouve `calculate_sum()` ET `add()`
- **Limite** : Peut manquer des correspondances exactes

**🔹 Recherche Hybride (RRF Fusion)** :
- **Comment** : Combine lexicale + vectorielle avec Reciprocal Rank Fusion (k=60)
- **Bon pour** : Meilleur des deux mondes
- **Exemple** : "calculate sum of numbers" trouve à la fois par mots-clés ET par sens
- **Recommandé** : C'est l'approche par défaut, la plus robuste

**💡 Conseil** : Commencez toujours avec la recherche hybride. Utilisez lexicale/vectorielle uniquement si vous avez un cas d'usage spécifique.

### Q10 : Comment fonctionne la résolution des dépendances dans le graphe ?

**Réponse** : MnemoLite utilise une **stratégie en 3 étapes** pour résoudre les appels de fonctions :

**1. Résolution Locale (même fichier)** :
```python
# Dans src/math.py
def helper():
    pass

def main():
    helper()  # ✅ Résolu localement dans math.py
```

**2. Résolution par Imports (imports trackés)** :
```python
# Dans src/utils.py
from math import helper

def process():
    helper()  # ✅ Résolu via l'import tracké
```

**3. Best-Effort (recherche globale)** :
```python
def unknown_call():
    some_function()  # 🔍 Cherche globalement par nom
```

**Filtrage automatique** :
- ✅ **73 built-ins Python filtrés** : `print`, `len`, `range`, `isinstance`, etc.
- ✅ **Pas de pollution** : Le graphe ne montre que VOS fonctions, pas les built-ins

**Résultats** :
- **100% accuracy** sur les tests MnemoLite (local + imports)
- **Best-effort** pour les cas complexes (imports dynamiques, monkey-patching)

### Q11 : Puis-je indexer un repository entier (GitHub, GitLab) ?

**Réponse** : Oui ! MnemoLite peut indexer n'importe quel repository local.

**Workflow recommandé** :

```bash
# 1. Cloner le repository
git clone https://github.com/user/repo.git
cd repo

# 2. Lire tous les fichiers et les envoyer à MnemoLite
find . -name "*.py" -type f | while read file; do
  content=$(cat "$file")
  curl -X POST http://localhost:8001/v1/code/index \
    -H "Content-Type: application/json" \
    -d "{\"repository\": \"my-repo\", \"files\": [{\"path\": \"$file\", \"content\": $(jq -Rs . <<< "$content")}]}"
done

# 3. Construire le graphe
curl -X POST http://localhost:8001/v1/code/graph/build \
  -d '{"repository": "my-repo"}'
```

**Optimisations** :
- 🚀 **Batch indexing** : Envoyez plusieurs fichiers par requête (max 100 fichiers)
- ⏱️ **Performance** : ~85ms par fichier (7 chunks en moyenne)
- 💾 **Stockage** : ~5-10 KB par chunk (dépend de la taille du code)

**Fonctionnalités à venir** (roadmap) :
- Auto-watch repository (détection automatique des changements)
- Intégration GitHub API (clonage automatique)
- Incremental indexing (ne ré-indexer que les fichiers modifiés)

### Q12 : Comment interpréter la complexité cyclomatique ?

**Réponse** : La **complexité cyclomatique** mesure le nombre de chemins d'exécution indépendants dans une fonction.

**Formule** : `Complexité = Nombre de conditions + 1`

**Exemples** :

```python
# Complexité = 1 (aucune condition)
def simple():
    return 42

# Complexité = 2 (1 condition if)
def with_if(x):
    if x > 0:
        return x
    return 0

# Complexité = 4 (3 conditions)
def complex(x, y):
    if x > 0:         # +1
        if y > 0:     # +1
            return x + y
    elif x < 0:       # +1
        return -x
    return 0
```

**Interprétation** :
- ✅ **1-5** : Fonction simple, facile à tester et maintenir
- 🟡 **6-10** : Complexité modérée, attention à la testabilité
- 🟠 **11-20** : Complexité élevée, envisagez un refactoring
- 🔴 **>20** : Complexité excessive, refactoring **fortement recommandé**

**Dans MnemoLite** :
```bash
# Trouver les fonctions complexes
curl -X GET "http://localhost:8001/v1/code/graph/stats?repository=my-repo"
# Voir "top_complex_functions" dans la réponse
```

**Bonnes pratiques** :
- Maintenez la complexité moyenne du repository < 5
- Refactorisez les fonctions > 10 en fonctions plus petites
- Utilisez le graphe de dépendances pour identifier les "god functions" (fonctions appelées partout)

### Q13 : Puis-je utiliser Agent Memory ET Code Intelligence sur le même projet ?

**Réponse** : **Absolument, c'est recommandé !** C'est la philosophie du **Parcours C** (Full Stack).

**Architecture** : Les deux systèmes utilisent la même base de données PostgreSQL mais avec des **tables séparées** :
- `events` : Agent Memory (conversations, événements)
- `code_chunks`, `nodes`, `edges` : Code Intelligence
- **Zéro interférence** : Les deux cohabitent parfaitement

**Use cases combinés** :
- 🤖 **Agent qui lit le code** : Voir [Section 8.1](#81--agent-ia-qui-comprend-votre-code)
- 📝 **Code review avec mémoire** : Voir [Section 8.2](#82--code-review-assisté-par-ia)
- 🔍 **Debugging intelligent** : Voir [Section 8.3](#83--debugging-intelligent-avec-mémoire)

**Exemple de workflow** :
```bash
# 1. Indexer le code
curl -X POST http://localhost:8001/v1/code/index -d '{"repository": "my-app", "files": [...]}'

# 2. Stocker une conversation
curl -X POST http://localhost:8001/v1/events -d '{"content": {"text": "Discussing authentication flow"}}'

# 3. Chercher dans le code
curl -X POST http://localhost:8001/v1/code/search/hybrid -d '{"query": "authentication"}'

# 4. Chercher dans les conversations
curl -G http://localhost:8001/v1/search/ --data-urlencode 'vector_query=authentication'

# 5. Combiner les résultats dans votre agent IA
```

**Performance** : Aucune dégradation. Les requêtes sont indépendantes et utilisent des indexes séparés.

---

## 📊 Nouveautés v2.0.0 - Major Release (Octobre 2025)

La version 2.0.0 est une **release majeure** qui transforme MnemoLite en un système **dual-purpose** :
- 🧠 **Agent Memory** (existant) : Mémoire cognitive pour agents IA
- 💻 **Code Intelligence** (nouveau) : Analyse et recherche de code intelligente

**Total** : +115 story points (74 EPIC-06 + 41 EPIC-07) livrés en **12 jours** (vs 93-104 jours estimés) ⚡

---

### 🎯 EPIC-06 : Code Intelligence (Backend) - 74 story points

**✨ Fonctionnalités principales**

**🌳 Code Chunking & AST Parsing**
- Tree-sitter pour 15+ langages (Python, JS, TS, Go, Rust, Java, C++, Ruby, etc.)
- Chunking intelligent : fonction, classe, méthode, module
- Extraction automatique : complexité cyclomatique, paramètres, appels, imports
- Pipeline 7 étapes : <100ms par fichier
- Performance : ~7 chunks par fichier en moyenne

**🧬 Dual Embeddings (768D)**
- **TEXT embedding** : docstrings + comments (nomic-embed-text-v1.5)
- **CODE embedding** : source code (nomic-embed-text-v1.5)
- Double indexation HNSW pour précision maximale
- Stockage dans PostgreSQL avec pgvector

**🔍 Hybrid Code Search**
- **Lexical Search** : BM25 avec pg_trgm (trigrams)
- **Vector Search** : Similarité cosinus avec HNSW
- **RRF Fusion** : Reciprocal Rank Fusion (k=60)
- Performance : <200ms P95 (28× plus rapide que l'objectif de 5000ms)

**🕸️ Dependency Graph**
- Construction automatique des nœuds (fonctions, classes) et arêtes (calls, imports)
- Résolution intelligente : Local → Imports → Best-effort
- Filtrage automatique : 73 built-ins Python exclus
- Traversal avec recursive CTEs : 0.155ms (129× plus rapide que l'objectif de 20ms)
- Algorithmes : Inbound/Outbound traversal, shortest path, graph statistics

**📊 Code Analytics**
- Métriques de complexité : moyenne, min, max, médiane
- Distribution par type (function, class, method) et langage
- Top 10 fonctions complexes
- Graph metrics : average degree, max depth, connected components

**🔧 Code Indexing API**
- `/v1/code/index` : Indexer des fichiers (batch support)
- `/v1/code/index/list` : Lister les chunks indexés
- `/v1/code/index/delete` : Supprimer un repository
- `/v1/code/index/health` : Health check du service

**🌐 Code Search API**
- `/v1/code/search/hybrid` : Recherche hybride (recommandé)
- `/v1/code/search/lexical` : Recherche lexicale BM25
- `/v1/code/search/vector` : Recherche vectorielle sémantique

**🕸️ Code Graph API**
- `/v1/code/graph/build` : Construire le graphe pour un repository
- `/v1/code/graph/traverse` : Traverser le graphe (inbound/outbound)
- `/v1/code/graph/path` : Trouver le chemin entre 2 nœuds
- `/v1/code/graph/stats` : Statistiques du repository

**✅ Tests & Qualité**
- **126/126 tests passants** (100%)
- Couverture : 100% sur les nouveaux services
- Audit score : 9.5/10 moyenne (Production Ready)
- Rapport complet : `docs/agile/EPIC-06_PHASE_4_STORY_6_COMPLETION_REPORT.md`

---

### 🎨 EPIC-07 : Code Intelligence UI (Frontend) - 41 story points

**✨ 5 Nouvelles Pages Web**

**💻 Code Dashboard** (`/ui/code/dashboard`)
- KPIs en temps réel : chunks, fonctions, complexité moyenne
- Top 10 fichiers par complexité
- Distribution par langage (pie chart)
- Timeline d'indexation
- Graphiques de santé du code (Chart.js)

**📁 Repository Manager** (`/ui/code/repos`)
- Liste des repositories indexés
- Statistiques par repo : chunks, nodes, edges
- Actions : Rebuild graph, Delete repository
- Filtres par langage et date d'indexation

**🔍 Code Search** (`/ui/code/search`)
- Interface de recherche hybride
- Filtres : repository, langage, type de chunk
- Résultats avec scores RRF + syntax highlighting
- Affichage du code source complet
- Liens vers fichiers et graphe de dépendances

**🕸️ Dependency Graph** (`/ui/code/graph`)
- Visualisation interactive Cytoscape.js
- Filtres : repository, relation_type (calls/imports)
- Layouts spécialisés (hierarchical, cose-bilkent)
- Détails des nœuds et arêtes
- Traversal interactif (inbound/outbound, depth)
- Export PNG/JSON

**📤 Upload Interface** (`/ui/code/upload`)
- Drag & drop de fichiers/dossiers
- Détection automatique du langage
- Barre de progression en temps réel
- Résumé de l'indexation
- Historique des uploads

**🎨 Design System Unifié**
- **100% cohérence** avec les 4 pages Agent Memory existantes
- SCADA industriel : ultra dark palette (#0a0e27), zéro border-radius
- Philosophie **"EXTEND DON'T REBUILD"** : Réutilisation totale du CSS existant
- Performance : Développement 8-9× plus rapide (2 jours vs 16-19 estimés)

**✅ Tests & Qualité**
- **17/17 tests d'intégration passants**
- Validation manuelle complète (9 pages)
- Accessibilité ARIA + navigation clavier
- Rapport complet : `docs/agile/EPIC-07_MVP_COMPLETION_REPORT.md`

---

### 🚀 Performance v2.0.0

**Agent Memory (maintenu)** :
- Recherche vectorielle (HNSW) : ~12ms P95
- Recherche hybride (vecteur + metadata + time) : ~11ms P95
- Génération embeddings : ~30ms moyenne (100% local)

**Code Intelligence (nouveau)** :
- Indexation : <100ms par fichier
- Hybrid Search : <200ms P95 (28× plus rapide que l'objectif)
- Graph Traversal : 0.155ms (129× plus rapide que l'objectif)
- Graph Construction : ~245ms pour 15 nœuds + 8 arêtes
- Analytics Dashboard : <50ms
- UI Page Load : <100ms

---

### 💾 Infrastructure v2.0.0

**PostgreSQL 18** (migré depuis PG17) :
- pgvector 0.8.1 (depuis 0.5.1)
- pg_partman 5.2.1
- tembo-pgmq (infrastructure ready, non utilisé)

**Nouvelles Tables** :
- `code_chunks` : Code indexé avec dual embeddings (TEXT + CODE, 768D chacun)
- `nodes` : Nœuds du graphe de dépendances (fonctions, classes)
- `edges` : Arêtes du graphe (calls, imports)

**Indexes** :
- HNSW sur `embedding_text` et `embedding_code` (m=16, ef_construction=64)
- GIN sur `metadata` (jsonb_path_ops)
- B-tree sur timestamps, repositories, languages

**Tests** :
- 245 tests passants (102 Agent Memory + 126 Code Intelligence + 17 intégration)
- Durée totale : ~25 secondes
- Databases séparées : `mnemolite` (dev) + `mnemolite_test` (tests)

---

### 💡 Ce que ça change pour vous

**En tant qu'utilisateur** :
- 🎉 **Dual-purpose system** : Agent Memory + Code Intelligence dans un seul outil
- 🌐 **9 pages UI** : 4 Agent Memory + 5 Code Intelligence
- 📚 **15+ langages supportés** : Python, JS, TS, Go, Rust, Java, C++, etc.
- 🔍 **Recherche intelligente** : Hybride (lexical + semantic + RRF fusion)
- 🕸️ **Graphe automatique** : Qui appelle quoi, sans configuration manuelle
- 📊 **Analytics de code** : Complexité, top fichiers, santé du code
- ⚡ **Performance folle** : 129× et 28× plus rapide que les objectifs
- 🔒 **100% local** : Aucune donnée ne sort de votre machine

**En tant que développeur** :
- 🏗️ **Architecture propre** : CQRS-inspired, DIP protocols, Repository pattern
- 🧪 **Tests exhaustifs** : 245 tests, 100% couverture sur Code Intelligence
- 📖 **Documentation complète** : EPIC-06 + EPIC-07 READMEs, completion reports
- 🚀 **CI/CD ready** : Rapports d'audit, métriques de qualité
- 🔄 **Rétrocompatibilité** : 0 breaking changes sur Agent Memory

---

### 📖 Documentation v2.0.0

**Guides utilisateur** :
- `GUIDE_DEMARRAGE.md` : Guide complet avec 3 parcours (A/B/C) - **CE DOCUMENT**
- `README.md` : Vue d'ensemble du projet v2.0.0

**Documentation technique** :
- `docs/agile/EPIC-06_README.md` : Point d'entrée EPIC-06
- `docs/agile/EPIC-07_README.md` : Point d'entrée EPIC-07
- `docs/agile/EPIC-06_PHASE_4_STORY_6_COMPLETION_REPORT.md` : Rapport final EPIC-06
- `docs/agile/EPIC-07_MVP_COMPLETION_REPORT.md` : Rapport final EPIC-07

**API** :
- Swagger UI : http://localhost:8001/docs (Agent Memory + Code Intelligence)
- ReDoc : http://localhost:8001/redoc

---

### 🎯 Prochaines Étapes (Roadmap)

**Planifié** :
- 🔄 **Incremental indexing** : Ne ré-indexer que les fichiers modifiés
- 📡 **GitHub integration** : Clonage et auto-watch automatiques
- 🧠 **Code embeddings optimisés** : jina-embeddings-v2-base-code dédié
- 📊 **Advanced analytics** : Code duplication detection, architectural insights
- 🎨 **UI enhancements** : Real-time collaboration, code annotations

**Explorez** :
- Section 8 : Use Cases Avancés (combiner Agent Memory + Code Intelligence)
- FAQ : 13 questions couvrant Agent Memory + Code Intelligence

---

## 🎓 Aller plus loin

Maintenant que vous maîtrisez les bases, explorez :

- 📖 [Architecture Détaillée](docs/Document%20Architecture.md) - Comprendre comment tout fonctionne
- 🔧 [Spécification API Complète](docs/Specification_API.md) - Tous les endpoints en détail
- 🏗️ [Schéma de Base de Données](docs/bdd_schema.md) - Tables, indexes, partitions
- 🐳 [Configuration Docker Avancée](docs/docker_setup.md) - Tuning et optimisations
- 🔬 [Tests et Benchmarks](tests/README.md) - Performance et qualité
- ✅ [Rapport de Validation Phase 3.4](docs/VALIDATION_FINALE_PHASE3.md) - Vérification exhaustive de la v1.3.0
- 🎨 [Design System UI](docs/ui_design_system.md) - Principes SCADA et composants
- 📁 [Architecture CSS](static/css/README.md) - Guide CSS modulaire v4.0

---

## 🤝 Besoin d'aide ?

- 🐛 **Bug ou problème** : Ouvrez une issue sur GitHub
- 💡 **Question** : Consultez les docs ou demandez sur les discussions GitHub
- 🚀 **Contribution** : Les Pull Requests sont bienvenues !

---

**Bienvenue dans l'univers MnemoLite v2.0.0 !** 🧠✨💻

Vous avez maintenant votre propre système **dual-purpose** local :
- 🧠 **Bibliothèque cognitive** pour alimenter vos agents IA
- 💻 **Moteur d'intelligence de code** pour comprendre vos repositories

**Explorez, expérimentez, et créez des outils sur-mesure !**

*Guide rédigé avec ❤️ pour rendre MnemoLite accessible à tous.*

---

**Version** : 2.0.0 (Major Release)
**Dernière mise à jour** : 2025-10-17
**Auteur** : Giak
**Contenu** :
- Section 5 : Agent Memory (Parcours A)
- Section 6 : Code Intelligence (Parcours B)
- Section 7 : Interface Web v2.0.0 (9 pages)
- Section 8 : Use Cases Avancés (Parcours C)
- FAQ : 13 questions (Agent Memory + Code Intelligence)
