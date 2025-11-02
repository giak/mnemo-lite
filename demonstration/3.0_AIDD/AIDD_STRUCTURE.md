# MnemoLite - Live AIDD Structure
## Format 30 Minutes | Vendredi 13h30

**Date création**: 2025-10-31
**Cible**: Communauté AIDD (tech/IA francophones)
**Format**: Discord + Slides Canva
**Durée**: 30 minutes max

---

## 📊 Contraintes AIDD vs Présentation Technique

| Aspect | Présentation Technique | Live AIDD |
|--------|----------------------|-----------|
| **Durée** | 50-60 min | **30 min MAX** ✅ |
| **Focus** | 8 décisions techniques | **Use cases + Démos** ✅ |
| **Audience** | Meetup technique | **Communauté IA** ✅ |
| **Tone** | Professionnel, honnête | **Énergique, communautaire** ✅ |
| **Call-to-action** | Inspiration | **Collaboration + Open-source** ✅ |
| **Démos** | Optionnel | **OBLIGATOIRE** ✅ |

---

## 🎯 Structure AIDD Imposée (30 min)

### 1️⃣ **Début de Live (5 min)** — Introduction + Mise en avant

**Objectifs**:
- Me présenter rapidement
- Établir le problème (LLMs sans mémoire)
- Montrer la solution (MnemoLite)
- Annoncer les 3 use cases
- Préciser où est l'IA

**Slides (4 slides)** :
1. **Slide 1**: Titre + Qui je suis (30 sec)
2. **Slide 2**: Le Problème - LLMs oublient tout (90 sec)
3. **Slide 3**: MnemoLite = Mémoire Persistante (2 min)
4. **Slide 4**: 3 Use Cases du jour + Où est l'IA (60 sec)

---

### 2️⃣ **Milieu de Live (15 min)** — 3 Use Cases avec Démos

**Objectifs**:
- Montrer MnemoLite EN ACTION
- Expliquer le flow IA utilisé
- Démontrer la valeur concrète
- Montrer l'intégration MCP

**Use Case 1: Assistant qui se Souvient (5 min)** - **4 slides**
- **Problème**: Claude oublie entre sessions
- **Démo LIVE**: Conversation Lundi → Vendredi avec MCP
- **Flow IA**: Claude Desktop → MCP → MnemoLite → PostgreSQL
- **Résultat**: Contexte restauré automatiquement

**Use Case 2: Knowledge Base Auto-Growing (5 min)** - **4 slides**
- **Problème**: Documenter manuellement = pénible
- **Démo LIVE**: 7,972 conversations auto-indexées, recherche sémantique
- **Flow IA**: Auto-save daemon → Embeddings → pgvector HNSW
- **Résultat**: Recherche en 8-12ms, 0 effort de doc

**Use Case 3: Code Intelligence avec Graph (5 min)** - **4 slides**
- **Problème**: Comprendre dépendances code = difficile
- **Démo LIVE**: Graph traversal sur codebase MnemoLite
- **Flow IA**: AST parsing → Dependency graph → Claude queries
- **Résultat**: "Montre-moi tous les fichiers qui dépendent de X"

---

### 3️⃣ **Fin de Live (10 min)** — Q&A + Call-to-Action

**Objectifs**:
- Montrer l'open-source
- Indiquer la roadmap
- Appeler à la collaboration
- Répondre aux questions

**Slides (4 slides)** :
1. **Slide 13**: Métriques Impact (2 min)
2. **Slide 14**: Open Source + Liens (2 min)
3. **Slide 15**: Roadmap + Besoin de Collaborateurs (3 min)
4. **Slide 16**: Q&A + Merci (3 min)

---

## 📝 Timing Détaillé (30 min)

| Section | Slides | Minutes | Cumul |
|---------|--------|---------|-------|
| **🎬 Intro + Setup** | 1-4 | 5 min | 5 min |
| **🔥 Use Case 1** | 5-8 | 5 min | 10 min |
| **🔥 Use Case 2** | 9-12 | 5 min | 15 min |
| **🔥 Use Case 3** | 13-16 | 5 min | 20 min |
| **💬 Impact + Open Source** | 17-18 | 3 min | 23 min |
| **🚀 Roadmap + Collab** | 19 | 2 min | 25 min |
| **❓ Q&A** | 20 | 5 min | 30 min |

**Total**: 20 slides pour 30 minutes = **1.5 min/slide** (rythme soutenu)

---

## 🎨 Adaptation du Contenu Existant

### ✅ **À Réutiliser** (Présentation v3.1.0)

1. **Slides "A quoi ça sert?" (4-11)** → Adapter pour Intro AIDD
   - Slide 5 (Problème LLMs) → AIDD Slide 2
   - Slide 7 (MnemoLite = Mémoire) → AIDD Slide 3
   - Slide 10 (Métriques impact) → AIDD Slide 17

2. **Démo MCP (Slide 37-42)** → Adapter pour Use Case 1

3. **Métriques finales** → AIDD Slide 17

### ❌ **À Supprimer** (Trop technique pour AIDD)

- ❌ 8 Critical Decisions (trop long)
- ❌ Technical Deep Dives détaillés (code)
- ❌ Benchmarks CPU vs GPU (hors scope)
- ❌ Cache strategy triple-layer (trop technique)
- ❌ Async architecture (pas pertinent pour use cases)

### ➕ **À Créer de Nouveau**

1. **Slide "Où est l'IA?"** (AIDD Slide 4)
   - Claude Desktop (LLM)
   - MCP Protocol (interface)
   - Embeddings (sentence-transformers)
   - pgvector HNSW (search)

2. **Démos LIVE préparées** (screenshots/vidéos)
   - Use Case 1: Claude Desktop + MCP en action
   - Use Case 2: Dashboard 7,972 conversations
   - Use Case 3: Code graph visualization

3. **Slide "Besoin de Collaborateurs"** (AIDD Slide 19)
   - Frontend/UI contributors
   - Load testing help
   - Documentation writers
   - Multi-user testing

---

## 🎭 Tone & Énergie AIDD

### Différences vs Présentation Technique

**Présentation Technique** :
- Tone: Professionnel, honnête, humble
- Pace: Modéré (1 min/slide)
- Focus: HOW (comment c'est construit)
- Closing: "C'est un experiment"

**Live AIDD** :
- Tone: **Énergique, passionné, communautaire** ⚡
- Pace: **Rapide** (1.5 min/slide, soutenu)
- Focus: **WHAT + WHY** (use cases concrets)
- Closing: **"Rejoignez-moi pour construire ça ensemble!"**

### Do's AIDD ✅
- ✅ "Regardez ce que ça permet de faire!"
- ✅ "C'est open-source, vous pouvez contribuer!"
- ✅ "J'ai besoin de vous pour tester ça en production"
- ✅ "Qui veut collaborer sur X?"
- ✅ Montrer l'enthousiasme du projet
- ✅ Démos visuelles impactantes

### Don'ts AIDD ❌
- ❌ Trop de détails techniques
- ❌ Code deep dives
- ❌ Limitations trop insistantes
- ❌ "C'est juste un POC modeste"
- ❌ Ton trop humble/défensif

---

## 🎬 Script Verbal Suggéré

### Intro (Slide 1-2)
> "Salut la commu AIDD! Moi c'est [nom], développeur solo qui aime expérimenter avec l'IA. Aujourd'hui je vais vous montrer MnemoLite, un projet qui résout un problème qu'on a TOUS vécu : les LLMs qui oublient tout entre les sessions. Vous savez, ce moment où vous dites à Claude 'je t'avais déjà expliqué ça la semaine dernière' et il répond 'euh... non?' — Frustrant, non?"

### Transition Use Cases (Slide 4)
> "Alors aujourd'hui, 3 démos concrètes pour vous montrer comment MnemoLite change ça. Use case 1: un assistant qui SE SOUVIENT. Use case 2: une knowledge base qui grandit toute seule. Use case 3: du code intelligence avec graph. Et spoiler: tout tourne sur CPU, 0€ budget, 100% open-source. Let's go!"

### Use Case 1 Intro (Slide 5)
> "Premier use case: imaginez que lundi, vous expliquez à Claude pourquoi vous avez choisi PostgreSQL. Vendredi, vous lui reposez la question. Sans MnemoLite, il a tout oublié. Avec MnemoLite... [DEMO LIVE]"

### Closing (Slide 19)
> "Voilà! 3 use cases, 7,972 conversations indexées, 4 mois de dev solo. Mais c'est là que VOUS entrez en jeu. Le projet est open-source, j'ai besoin de collaborateurs pour tester en production, améliorer le frontend, faire du load testing. Qui est chaud pour rejoindre l'aventure?"

---

## 🔗 Liens à Préparer

### Slide "Open Source" (Slide 18)

**GitHub** :
- Repo: `github.com/[username]/mnemolite`
- Stars: [current count]
- License: MIT

**Documentation** :
- README: Installation guide
- MCP Guide: `docs/MCP_INTEGRATION_GUIDE.md`
- 46 Completion Reports: `docs/agile/serena-evolution/03_EPICS/`

**Démo Live** :
- Dashboard: `http://localhost:8001/ui/code_search`
- Monitoring: `http://localhost:8001/ui/monitoring/advanced`
- Graph: `http://localhost:8001/ui/code_graph`

**Contact** :
- Discord: @[username]
- Email: [email]
- Twitter/X: @[handle]

---

## 🎥 Démos à Préparer (Screenshots/Vidéos)

### Use Case 1: MCP en Action
**Préparation** :
1. Enregistrer conversation Lundi avec Claude Desktop
2. Enregistrer conversation Vendredi avec search_conversations()
3. Montrer le contexte restauré
4. **Durée vidéo**: 60 secondes max

### Use Case 2: Auto-Save Dashboard
**Préparation** :
1. Screenshot dashboard `/ui/autosave` montrant 7,972 conversations
2. Demo recherche sémantique live
3. Montrer résultats en 8-12ms
4. **Durée vidéo**: 60 secondes max

### Use Case 3: Code Graph
**Préparation** :
1. Screenshot graph visualization
2. Demo traversal "Show dependencies of X"
3. Montrer résultat avec liens
4. **Durée vidéo**: 60 secondes max

---

## 📊 Métriques à Mettre en Avant (AIDD Style)

### Slide 17: Impact Mesuré

**Métriques "Wow" pour l'audience** :
- ✅ **7,972 conversations** auto-saved (KB vivante)
- ✅ **8-12ms** search time (rapide!)
- ✅ **+30% productivité** (quantifié)
- ✅ **32h économisées** sur 4 mois (ROI clair)
- ✅ **0€ budget** (accessible à tous)
- ✅ **355/355 tests** MCP passing (qualité)

**Présentation visuelle** :
```
┌─────────────────────────────────┐
│  7,972 conversations indexées   │  ← Big number
│  Search en 8-12ms               │  ← Performance
│  +30% productivité              │  ← Business value
│  0€ budget (CPU only)           │  ← Accessibility
└─────────────────────────────────┘
```

---

## 🚀 Appel à l'Action Communautaire

### Slide 19: Besoin de Collaborateurs

**Message clé** :
> "MnemoLite fonctionne en solo/duo. Mais pour aller plus loin, j'ai besoin de VOUS!"

**Contributions recherchées** :
1. **Frontend/UX Devs** 🎨
   - Améliorer dashboard
   - Mobile responsive
   - Dark mode natif

2. **Backend/Infra** ⚙️
   - Load testing (>100 users)
   - Multi-tenant architecture
   - Kubernetes deployment

3. **Documentation** 📝
   - User guides FR/EN
   - Video tutorials
   - API documentation

4. **Testing** 🧪
   - Production validation
   - Multi-user scenarios
   - Bug hunting

**Call-to-action** :
- ✅ "Rejoignez le Discord du projet"
- ✅ "Forkez le repo et proposez des PRs"
- ✅ "Testez en local et donnez du feedback"
- ✅ "Partagez vos use cases!"

---

## ✅ Checklist Pré-Live

### Technique
- [ ] Démos préparées (vidéos/screenshots)
- [ ] Dashboard accessible (localhost:8001)
- [ ] Claude Desktop configuré avec MCP
- [ ] Internet stable pour démo live
- [ ] Backup slides si démo fail

### Contenu
- [ ] Slides finalisées (20 slides)
- [ ] Timing validé (30 min max)
- [ ] Script verbal répété
- [ ] Transitions fluides
- [ ] Q&A anticipées

### Communautaire
- [ ] Liens GitHub préparés
- [ ] Discord/contact partagés
- [ ] Issues GitHub organisées (good first issue)
- [ ] Roadmap publique visible
- [ ] Contributing guide à jour

---

## 📅 Roadmap à Présenter (Slide 19)

### Court Terme (Q4 2025)
- ✅ **Phase 1 MCP**: Complete (355/355 tests)
- ⏳ **Phase 2**: Multi-user support (en cours)
- ⏳ **Load testing**: Valider 100+ users

### Moyen Terme (Q1 2026)
- 🔜 **Mobile app**: React Native
- 🔜 **Cloud deployment**: AWS/GCP guides
- 🔜 **Plugin ecosystem**: Custom tools

### Long Terme (Q2 2026+)
- 💡 **Multi-LLM support**: GPT-4, Gemini, etc.
- 💡 **Team features**: Shared knowledge bases
- 💡 **Enterprise tier**: SLA, support, SSO

**Message** :
> "Seul, je peux faire Phase 1. Ensemble, on peut faire Phase 2-3!"

---

## 🎯 Success Metrics (Post-Live)

**Objectifs Live AIDD** :
- 🎯 **Engagement**: >20 personnes présentes
- 🎯 **GitHub Stars**: +10-20 stars
- 🎯 **Contributors**: 2-3 nouveaux contributeurs
- 🎯 **Discord**: 5-10 nouveaux membres
- 🎯 **Feedback**: Issues/suggestions concrètes

**Follow-up** :
- Post-live debrief avec Ben
- Potential ambassadeur AIDD
- Suivi live dans 2-3 mois (Phase 2 results)

---

**Prochaine étape**: Créer les 20 slides optimisées pour AIDD (format Canva/Reveal.js)
