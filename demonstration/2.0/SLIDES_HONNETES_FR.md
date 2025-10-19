# MnemoLite v2.0 - Présentation Honnête
## Un Projet Personnel d'Exploration Technique

---

## [Slide 1] 🏛️ **MnemoLite v2.0**

```
     ╔═══════════════════════════════════╗
     ║                                   ║
     ║         MnemoLite v2.0            ║
     ║   Un projet personnel             ║
     ║   d'embedding sur CPU             ║
     ║                                   ║
     ╚═══════════════════════════════════╝

    📝 Projet perso (~1 semaine de dev)
    💻 Tourne sur CPU standard
    🔧 PostgreSQL + Python
```

**À dire** : "C'est un side project pour explorer les embeddings CPU"

---

## [Slide 2] 🎯 **L'Idée de Départ**

```
    Question Simple :

    "Peut-on faire de l'embedding et
     de la recherche sémantique sans GPU ?"

    Contexte :
    • Les GPUs coûtent cher (2000€+)
    • Les APIs cloud aussi (300€/mois)
    • Pour un usage perso/PME, c'est overkill

    Hypothèse :
    • Les modèles CPU récents sont pas mal
    • PostgreSQL a pgvector maintenant
    • Voyons ce qu'on peut faire...
```

**À dire** : "J'ai voulu tester si c'était faisable pour un usage modeste"

---

## [Slide 3] 🔬 **Ce Que J'ai Construit**

```
    MnemoLite = 2 modules :

    1. Agent Memory
       • Stocke des conversations
       • Recherche sémantique basique
       • Utilise pgvector

    2. Code Intelligence
       • Parse du code Python (surtout)
       • Construit un graphe de dépendances
       • Recherche dans le code

    Stack : FastAPI + PostgreSQL 18
    Temps : ~1 semaine (soirs et weekends)
```

**À dire** : "Rien de révolutionnaire, juste de l'assemblage intelligent"

---

## [Slide 4] 💡 **Les Choix Techniques**

```
    Modèle : nomic-embed-text-v1.5
    • 137M paramètres (petit)
    • Optimisé CPU (ONNX)
    • 768 dimensions
    • Gratuit et open source

    Base : PostgreSQL 18
    • pgvector pour les embeddings
    • pg_trgm pour le texte
    • CTEs pour les graphes

    Pas de magie, juste des outils existants
```

**À dire** : "J'ai pris des briques qui existent et je les ai assemblées"

---

## [Slide 5] 📊 **Les Résultats (Honnêtes)**

```
    Ce qui marche bien :
    ✓ Recherche sémantique : ~11ms
    ✓ Embeddings : 50-100/sec sur mon laptop
    ✓ Graphe de code : 0.155ms*
    ✓ Pas besoin de GPU

    * Le 0.155ms c'est parce que :
    - Le graphe est petit (14 fichiers)
    - Tout est en cache PostgreSQL
    - La requête est simple

    C'est pas un "record", c'est normal
```

**À dire** : "Les perfs sont correctes pour un usage léger"

---

## [Slide 6] ⚠️ **Les Vraies Limitations**

```
    Soyons clairs :

    ❌ Pas "production ready" (1 semaine de dev!)
    ❌ Single-instance only (pas de Redis)
    ❌ Python bien supporté, le reste bof
    ❌ 4GB RAM minimum quand même
    ❌ Testé sur quelques milliers d'items max
    ❌ Pas comparable à OpenAI/Claude

    C'est un POC qui fonctionne,
    pas un produit fini
```

**À dire** : "C'est un projet perso, pas une solution entreprise"

---

## [Slide 7] 🎯 **Pour Qui C'est Utile ?**

```
    Cas d'usage réalistes :

    ✓ Side projects personnels
    ✓ PME avec <1000 docs
    ✓ Prototypes/POCs
    ✓ Apprentissage/Expérimentation

    PAS pour :
    ✗ Production critique
    ✗ Millions de documents
    ✗ Multi-utilisateurs intensif
    ✗ Remplacement d'OpenAI
```

**À dire** : "Si vous avez un petit projet, ça peut servir"

---

## [Slide 8] 💻 **Démo Rapide**

```
    Ce que ça fait concrètement :

    1. Stocke du texte
    2. Le transforme en vecteurs (CPU)
    3. Cherche par similarité
    4. Retourne des résultats

    [Montrer l'interface]

    C'est basique mais ça marche
```

**À dire** : "Voilà, pas de magie"

---

## [Slide 9] 🔧 **Le Code (Simple)**

```python
# C'est vraiment pas compliqué
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('nomic-embed-text-v1.5')
embedding = model.encode("votre texte")

# PostgreSQL fait le reste
SELECT * FROM events
WHERE embedding <-> %s < 0.8
ORDER BY embedding <-> %s
LIMIT 10;
```

**À dire** : "200 lignes de Python, le reste c'est PostgreSQL"

---

## [Slide 10] 📈 **Ce Que J'ai Appris**

```
    Leçons du projet :

    1. Les modèles CPU sont utilisables
       (pour des usages modestes)

    2. PostgreSQL + pgvector = combo solide

    3. Pas besoin de GPU pour explorer

    4. HTMX c'est vraiment simple

    5. 1 semaine = POC fonctionnel
```

**À dire** : "C'était surtout pour apprendre"

---

## [Slide 11] 🤔 **Comparaison Réaliste**

```
    MnemoLite          vs      Solutions Pro
    ─────────                  ─────────────
    Gratuit                    300€/mois
    11ms (local)               100ms (réseau)
    CPU 65W                    GPU 450W
    1 semaine dev              Équipes entières

    MAIS :

    Capacité limitée    vs     Scale infini
    Single-user         vs     Multi-tenant
    POC                 vs     Production
```

**À dire** : "Comparons ce qui est comparable"

---

## [Slide 12] 🚀 **Si Vous Voulez Essayer**

```bash
# C'est open source
git clone https://github.com/.../mnemolite
cd mnemolite
make up

# 2 minutes et ça tourne

# Mais attention :
# - C'est un projet perso
# - Support limité
# - Bugs probables
```

**À dire** : "C'est dispo si ça intéresse quelqu'un"

---

## [Slide 13] 🛠️ **Stack Technique Détaillé**

```
    Pour les curieux :

    • FastAPI (API REST)
    • PostgreSQL 18 + pgvector
    • SQLAlchemy Core (async)
    • Sentence-Transformers
    • tree-sitter (parsing Python)
    • HTMX 2.0 (interface web)
    • Docker Compose

    Rien d'exotique, que du standard
```

**À dire** : "Technologies mainstream, pas de rocket science"

---

## [Slide 14] 📊 **Les "245 Tests"**

```
    Oui il y a 245 tests MAIS :

    • Écrits en 1 semaine
    • Coverage partiel
    • Pas de tests de charge
    • Pas de tests de sécurité
    • Juste des tests unitaires/intégration

    C'est mieux que rien,
    mais c'est pas une certification
```

**À dire** : "Les tests c'est bien, mais restons modestes"

---

## [Slide 15] 🎓 **Aspects Intéressants**

```
    Ce qui peut vous intéresser :

    1. Comment utiliser pgvector
    2. Embeddings CPU avec ONNX
    3. CTEs récursives pour graphes
    4. HTMX sans JavaScript
    5. Architecture Repository Pattern

    Le code est dispo pour apprendre
```

**À dire** : "Si ça peut aider quelqu'un à apprendre"

---

## [Slide 16] 💭 **Améliorations Possibles**

```
    Si c'était à refaire / continuer :

    • Ajouter Redis pour le cache
    • Support multi-langages correct
    • Interface plus polie
    • Tests de charge sérieux
    • Documentation utilisateur
    • CI/CD propre

    Mais bon, 1 semaine...
```

**À dire** : "Il y a plein de choses à améliorer"

---

## [Slide 17] 🤝 **Contribution**

```
    Si ça intéresse quelqu'un :

    • Le code est sur GitHub
    • MIT License
    • PRs bienvenues
    • Issues aussi

    Pas de promesses de support,
    c'est un projet perso
```

**À dire** : "Si quelqu'un veut forker ou contribuer"

---

## [Slide 18] 📝 **Le Vrai Message**

```
    Ce que je voulais prouver :

    "On peut faire des trucs sympas
     avec un CPU et PostgreSQL"

    Pas besoin de :
    • GPU à 2000€
    • Cloud à 300€/mois
    • Stack complexe

    Pour un usage modeste, ça suffit
```

**À dire** : "L'idée c'était de démystifier"

---

## [Slide 19] 💬 **Questions ?**

```
    Des questions ?

    (Rappel : c'est un projet d'1 semaine,
     soyez indulgents 😅)
```

**À dire** : "N'hésitez pas mais gardez les expectations raisonnables"

---

## [Slide 20] 🙏 **Merci**

```
    MnemoLite v2.0

    Un projet personnel pour explorer
    les embeddings CPU et pgvector

    Pas révolutionnaire,
    mais ça marche

    github.com/.../mnemolite
```

**À dire** : "Merci de votre attention"

---

# Notes pour le Présentateur

## Ton de la Présentation

- **Humble** : C'est un side project
- **Honnête** : Sur les limitations
- **Pédagogique** : Partager l'apprentissage
- **Réaliste** : Sur les cas d'usage

## Messages Clés

1. "C'est faisable sur CPU pour des usages modestes"
2. "PostgreSQL + pgvector = combo intéressant"
3. "1 semaine = POC fonctionnel"
4. "Open source si ça intéresse"

## Réponses aux Questions

**"C'est vraiment production ready ?"**
> "Non, c'est 1 semaine de dev. C'est un POC qui fonctionne."

**"Ça scale ?"**
> "Testé jusqu'à quelques milliers d'items. Au-delà, je ne sais pas."

**"Vs OpenAI ?"**
> "Pas comparable. OpenAI c'est pro, ça c'est un projet perso."

**"Le 0.155ms ?"**
> "C'est sur 14 fichiers en cache. Rien d'extraordinaire."

## Ce qu'il NE FAUT PAS dire

- ❌ "Révolutionnaire"
- ❌ "Production ready"
- ❌ "Remplace OpenAI"
- ❌ "Record de performance"
- ❌ "Solution entreprise"

## Ce qu'il FAUT dire

- ✅ "Projet personnel"
- ✅ "POC fonctionnel"
- ✅ "Pour apprendre"
- ✅ "Usage modeste"
- ✅ "1 semaine de dev"

---

**Le vrai message : "C'est possible de faire des embeddings sur CPU pour des petits projets. Voici comment."**