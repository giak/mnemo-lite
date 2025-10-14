<p align="center">
  <img src="static/img/logo_mnemolite.jpg" alt="MnemoLite Logo" width="200" style="border-radius: 50%;">
</p>

# 🧠 MnemoLite v1.3.0 - Guide de Démarrage

> **Pour qui ?** Ce guide est fait pour vous si vous voulez installer et utiliser MnemoLite, même sans être expert en bases de données ou en Docker. On vous prend par la main, étape par étape.

---

## 📖 Introduction : Votre bibliothèque personnelle intelligente

Imaginez une **bibliothèque immense** où chaque livre représente un souvenir, une conversation, un événement. Mais contrairement à une bibliothèque classique où vous devez connaître le titre exact pour trouver un livre, **MnemoLite** est comme une bibliothèque magique :

- 🔍 **Vous cherchez par sens, pas par mot exact** : "Je cherche quelque chose sur les chats" trouvera aussi "félin domestique" ou "mon minou"
- ⏰ **Vous pouvez filtrer par époque** : "Montre-moi tout ce qui s'est passé en janvier"
- 🏷️ **Vous pouvez classer par catégories** : "Tous les souvenirs liés au projet Expanse"

**Le secret ?** MnemoLite utilise **PostgreSQL** comme bibliothécaire ultra-compétent et des **embeddings locaux** (des "empreintes digitales sémantiques") pour comprendre le sens de vos données, sans jamais envoyer quoi que ce soit sur Internet.

### 🎯 Ce que vous obtiendrez

À la fin de ce guide, vous aurez :
- ✅ MnemoLite v1.3.0 installé et opérationnel sur votre machine
- ✅ Compris comment stocker des événements (vos "livres")
- ✅ Appris à rechercher dans vos données avec différentes stratégies
- ✅ Une API prête à connecter à vos projets
- ✅ Un système stable et performant (102 tests passent, architecture consolidée)

**Temps estimé** : 15-20 minutes pour l'installation ⏱️

**🎉 Nouveauté v1.3.0** : Architecture simplifiée avec EventRepository comme source unique de vérité (-1,909 lignes de code, zéro régression détectée)

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
  "timestamp": "2025-10-14T20:00:00Z"
}
```

🎉 **Ça marche ?** Félicitations ! MnemoLite est opérationnel !

---

## 🎮 Premiers pas : Utiliser MnemoLite

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

## 🎨 Interface Web v4.0 - Design SCADA Industriel

MnemoLite inclut une **interface Web moderne** (HTMX 2.0) avec un design **SCADA industriel** pour explorer visuellement vos données.

Ouvrez simplement votre navigateur : **http://localhost:8001/ui/**

### 🖥️ Pages disponibles

**Dashboard** (`/ui/`)
- Vue d'ensemble des événements récents
- Filtres par période (24h, 7j, 30j, tout)
- Filtres par projet et catégorie
- Cartes de statistiques en temps réel

**Recherche Sémantique** (`/ui/search`)
- Recherche vectorielle par sens (pas par mots-clés)
- Recherche hybride (vecteur + métadonnées + temps)
- Ajustement du seuil de similarité
- Résultats avec scores de pertinence

**Graphe de Connaissances** (`/ui/graph`)
- Visualisation interactive des relations (Cytoscape.js)
- 5 algorithmes de layout (cose, circle, grid, breadthfirst, concentric)
- Filtres par type de nœud (event, entity, concept)
- Détails des nœuds et arêtes au clic
- Minimap pour navigation

**Monitoring** (`/ui/monitoring`)
- Graphiques ECharts en temps réel
- Timeline d'activité des événements
- Distribution par type et projet
- Événements critiques récents
- Auto-refresh toutes les 30 secondes

### ✨ Fonctionnalités UI v4.0

**🎨 Design System SCADA Industriel**
- Ultra dark palette (#0d1117 à #2d333b)
- Zéro border-radius (aesthetic industrielle)
- Compact spacing (haute densité d'information)
- Transitions ultra-rapides (80ms)
- Couleurs vives pour les statuts (critical, warning, ok)

**⚡ Performance & UX**
- Architecture CSS modulaire (16 modules + variables)
- JavaScript organisé (3 core + 3 composants)
- Composants réutilisables (event_card, filters, modal)
- Gestion d'erreurs globale avec retry automatique
- Patterns HTMX standardisés (data-attributes)

**♿ Accessibilité**
- ARIA attributes pour lecteurs d'écran
- Navigation clavier complète
- Focus trapping dans les modaux
- Indicateurs de chargement accessibles

**Documentation API interactive** :
- **Swagger UI** : http://localhost:8001/docs
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

## 📊 Nouveautés v1.3.0

La version 1.3.0 apporte des **améliorations majeures** :

### ✨ Changements principaux

**🏗️ Architecture consolidée**
- **Avant** : 2 repositories (EventRepository + MemoryRepository) accédant à la même table
- **Maintenant** : 1 seul repository (EventRepository) comme **source unique de vérité**
- **Résultat** : -1,909 lignes de code supprimées, plus de duplication !

**✅ Tests renforcés**
- **102 tests unitaires passent** (11 skipped, 1 xfailed)
- **16 tests d'intégration** pour la similarité sémantique
- **Durée** : ~13 secondes pour la suite complète
- **Couverture** : ~87% du code

**🚀 Performance maintenue**
- Recherche vectorielle (HNSW) : **~12ms P95**
- Recherche hybride (vecteur + métadonnées + temps) : **~11ms P95**
- Recherche métadonnées + temps : **~3ms P95**
- Génération d'embeddings : **~30ms moyenne** (100% local)

**🔍 Validation exhaustive**
- ✅ Zéro régression détectée
- ✅ Tous les services fonctionnels
- ✅ Architecture plus claire et maintenable
- 📖 Rapport complet : [`docs/VALIDATION_FINALE_PHASE3.md`](docs/VALIDATION_FINALE_PHASE3.md)

**🎨 Interface Web v4.0 (UI Refactoring)**
- Interface complète avec 4 pages : Dashboard, Search, Graph, Monitoring
- Design SCADA industriel (ultra dark, compact, haute densité)
- CSS modulaire : 16 modules organisés (base, layout, components, utils)
- JavaScript structuré : 6 modules (error-handler, modal, htmx-helpers, filters, graph, monitoring)
- Composants réutilisables : event_card, filters, modal
- HTMX 2.0 standardisé avec data-attributes patterns
- Accessibilité ARIA complète + navigation clavier
- Gestion d'erreurs globale avec retry automatique
- Visualisation graphe avec Cytoscape.js (5 layouts)
- Monitoring temps réel avec ECharts

### 💡 Ce que ça change pour vous

**En tant qu'utilisateur** :
- ✅ API REST inchangée (rétrocompatibilité totale)
- ✅ Nouvelle interface Web complète et moderne
- ✅ Système plus stable (moins de code = moins de bugs)
- ✅ Meilleures performances (requêtes optimisées)
- ✅ Base solide pour les futures fonctionnalités

**En tant que développeur** : Tout est simplifié :
- 1 seul repository à maintenir au lieu de 2
- Injection de dépendances plus claire
- Tests plus simples et fiables
- Documentation à jour

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

**Bienvenue dans l'univers MnemoLite !** 🧠✨

Vous avez maintenant votre propre bibliothèque cognitive locale, prête à alimenter vos agents IA. Explorez, expérimentez, et amusez-vous !

*Guide rédigé avec ❤️ pour rendre MnemoLite accessible à tous.*

---

**Version** : 1.3.0
**Dernière mise à jour** : 2025-10-14
**Auteur** : Giak
