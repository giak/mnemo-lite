# MnemoLite v1.3.0 - Démonstration Interactive

Présentation Reveal.js professionnelle pour démonstration publique de MnemoLite.

---

## 🚀 Quick Start

### Mode Développement
```bash
# Lancer MnemoLite d'abord
cd /home/giak/Work/MnemoLite
make up
make db-fill-test  # Populate avec données de démo

# Ouvrir la présentation
cd demonstration
open index.html  # ou firefox index.html
```

### Mode Production
```bash
# 1. Minifier CSS
./scripts/build.sh

# 2. Déployer
# Upload: index.html + css/ + assets/ + SCENARIO.md
```

---

## 📚 Documentation

### Guides Principaux

1. **[SCENARIO.md](SCENARIO.md)** - Scénario de Présentation Complet
   - 20 slides organisées en 5 actes
   - Speaker notes détaillées
   - Timing et scénarios alternatifs
   - Checklist pré-démonstration

2. **[IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)** - Plan d'Implémentation (TODO)
   - Étapes de création
   - Technologies utilisées
   - Ressources nécessaires

3. **[DESIGN_GUIDE.md](DESIGN_GUIDE.md)** - Guide de Design (TODO)
   - Palette SCADA
   - Typographie
   - Composants visuels

---

## 🛠️ Structure du Projet

```
demonstration/
├── index.html              # Présentation Reveal.js (TODO - à créer)
├── README.md               # Ce fichier
├── SCENARIO.md             # Scénario détaillé ✅
├── IMPLEMENTATION_PLAN.md  # Plan d'implémentation (TODO)
├── DESIGN_GUIDE.md         # Guide de design (TODO)
│
├── css/
│   ├── custom.css          # Styles custom MnemoLite (TODO)
│   ├── reveal-overrides.css # Overrides Reveal.js (TODO)
│   └── scada-theme.css     # Thème SCADA industriel (TODO)
│
├── assets/
│   ├── images/
│   │   ├── logo_mnemolite.jpg  # Logo principal
│   │   ├── architecture.svg    # Diagramme architecture (TODO)
│   │   ├── screenshots/        # Screenshots UI (TODO)
│   │   │   ├── dashboard.png
│   │   │   ├── search.png
│   │   │   ├── graph.png
│   │   │   └── monitoring.png
│   │   └── benchmarks/         # Graphiques performance (TODO)
│   │       ├── latency.png
│   │       └── comparison.png
│   │
│   └── videos/
│       └── ui-demo.mp4         # Screencast UI (TODO - optionnel)
│
└── scripts/
    ├── build.sh                # Minification CSS (TODO)
    ├── capture-screenshots.sh  # Auto-capture UI (TODO)
    └── generate-diagrams.sh    # Génération SVG (TODO)
```

---

## 🎨 Thème Visuel

### Palette SCADA Industrial

**Couleurs Principales**:
```css
--color-bg-primary: #0d1117;      /* Ultra dark background */
--color-bg-secondary: #161b22;    /* Secondary background */
--color-accent-blue: #4a90e2;     /* Primary accent */
--color-accent-gold: #fbbf24;     /* Gold highlights */
--color-success: #10b981;         /* Green success */
--color-danger: #f43f5e;          /* Red danger */
--color-text: #e6edf3;            /* Light text */
```

**Typographie**:
- **Titres**: Inter, bold, sans-serif
- **Corps**: Inter, regular, 18px
- **Code**: JetBrains Mono, 16px

**Principes**:
- Zero border-radius (strict industrial)
- Compact spacing (8px, 16px, 24px)
- Fast transitions (80ms)
- Border-left accents (2px) pour status
- High contrast (WCAG AAA)

---

## 📖 Navigation Reveal.js

### Clavier
- `→` / `←` : Slide suivante/précédente
- `Space` : Slide suivante
- `Esc` : Vue d'ensemble (overview mode)
- `S` : Mode speaker notes (séparateur d'écran)
- `F` : Fullscreen
- `B` : Blackout (pause)

### Souris
- Flèches en bas à droite
- Barre de progression en bas
- Clic n'importe où → suivant

---

## 🎯 Scénarios de Présentation

### Scénario Standard (20 min)
**Public**: Développeurs, Architectes, Product Managers

**Structure** (20 slides):
1. **Acte 1: Problème** (3 slides, 3 min)
   - Défi mémoire IA
   - Solutions existantes (problèmes)
   - Vision MnemoLite

2. **Acte 2: Solution** (5 slides, 6 min)
   - Architecture
   - Technologies clés
   - Modèle de données
   - Embeddings locaux
   - UI v4.0

3. **Acte 3: Démo Live** (6 slides, 8 min)
   - Quick start Docker
   - Dashboard
   - Search hybride
   - Graph visualization
   - Monitoring
   - API REST

4. **Acte 4: Performance** (4 slides, 4 min)
   - Benchmarks
   - Tests & qualité
   - Production deployment
   - Comparaison concurrents

5. **Acte 5: Conclusion** (2 slides, 2 min)
   - Cas d'usage
   - Call to action

---

### Scénario Court (5 min)
**Public**: Pitch rapide, démo éclair

**Slides**:
1. Hero (30s)
2. Architecture (60s)
3. Demo Dashboard (90s)
4. Performance (60s)
5. CTA (60s)

---

### Scénario Technique (30 min)
**Public**: Développeurs avancés, contributeurs

**Additions**:
- SQLAlchemy async patterns
- pgvector HNSW tuning
- JSONB indexing strategies
- EventRepository implementation
- Sentence-Transformers fine-tuning
- Q&A extensive

---

### Scénario Business (15 min)
**Public**: Managers, Investisseurs, C-level

**Focus**:
- ROI et économies de coûts
- Comparaison avec concurrents
- Case studies (Expanse)
- Roadmap et vision
- TCO (Total Cost of Ownership)

---

## 🛠️ Scripts Disponibles

### Build & Optimisation
```bash
./scripts/build.sh                   # Minifie CSS
./scripts/capture-screenshots.sh     # Capture UI screens
./scripts/generate-diagrams.sh       # Génère SVG diagrammes
```

---

## 📦 Dépendances

### CDN (Reveal.js)
Chargés depuis CDN dans index.html:
- Reveal.js 5.0+ (core)
- Reveal.js plugins (notes, highlight, zoom)
- Font Awesome (icons)
- Inter font (typography)

### Local Assets
- Logo MnemoLite (assets/images/logo_mnemolite.jpg)
- Screenshots UI (à capturer)
- Custom CSS (à créer)

---

## 🎬 Préparer la Démo

### Checklist Pré-Présentation

#### Environnement MnemoLite
```bash
# 1. Services running
cd /home/giak/Work/MnemoLite
make up
docker compose ps  # Vérifier mnemo-api, mnemo-postgres

# 2. Populate test data
make db-fill-test

# 3. Vérifier santé
curl http://localhost:8001/health
# Expected: {"status":"healthy",...}

# 4. Tester UI
open http://localhost:8001/ui/
open http://localhost:8001/ui/search
open http://localhost:8001/ui/graph
open http://localhost:8001/ui/monitoring
```

#### Navigateur
- [ ] Ouvrir tous les onglets UI en arrière-plan
- [ ] DevTools ouverts (Network tab)
- [ ] Désactiver extensions qui pourraient interférer
- [ ] Mode plein écran prêt (F11)

#### Présentation
- [ ] index.html chargé en local
- [ ] Mode speaker notes testé (touche S)
- [ ] Transitions fluides vérifiées
- [ ] Screenshots à jour (si demo live échoue)

#### Backup Plan
- [ ] Screenshots haute résolution de toutes les pages UI
- [ ] Vidéo screencast enregistrée (optionnel)
- [ ] Slides PDF exportées (backup si HTML bug)

---

## 🎓 Speaker Tips

### Avant la Présentation
1. **Tester le flow complet** une fois (15-20 min)
2. **Chronométrer** chaque section
3. **Préparer queries de recherche** (copier-coller prêt)
4. **Vérifier son et vidéo** si applicable

### Pendant la Présentation
1. **Respirer et parler lentement**
2. **Pauses intentionnelles** après points clés
3. **Monitoring audience** (questions, confusion, engagement)
4. **Flexibilité** (skipper slides si en retard)

### Gestion des Questions
- **Question durant démo**: "Excellente question, notons-la pour la fin"
- **Question technique pointue**: "Regardons le code ensemble après"
- **Comparaison concurrent**: Rester objectif, citer sources
- **Feature manquante**: "Roadmap future, contribution welcome!"

### En Cas de Problème Technique
- **Docker crash**: Montrer screenshots pré-capturés
- **UI lente**: "Cache froid, première requête, relançons"
- **Network error**: Passer en mode offline (screenshots)
- **Slide bug**: Utiliser PDF backup

---

## 📊 Métriques de Succès

### Pendant Démo
- ✅ Questions engagées
- ✅ Demandes de repo GitHub
- ✅ Requests de one-on-one
- ✅ Feedback positif (verbal/non-verbal)

### Après Démo
- ✅ GitHub stars/clones
- ✅ Issues créées
- ✅ PRs soumises
- ✅ Mentions social media
- ✅ Demandes de déploiement

---

## 🚀 Prochaines Étapes

### Phase 1: Création Présentation (4h)
- [ ] Créer index.html Reveal.js
- [ ] Implémenter les 20 slides
- [ ] Ajouter speaker notes
- [ ] Intégrer screenshots

### Phase 2: Assets Visuels (2h)
- [ ] Capturer screenshots UI (4 pages)
- [ ] Créer diagramme architecture.svg
- [ ] Générer graphiques benchmarks
- [ ] Optimiser images (compression)

### Phase 3: Styling & Polish (2h)
- [ ] CSS custom SCADA theme
- [ ] Animations micro-interactions
- [ ] Transitions slides
- [ ] Responsive mobile (optionnel)

### Phase 4: Testing & Iteration (1h)
- [ ] Dry run complet
- [ ] Timing ajustements
- [ ] Feedback interne
- [ ] Corrections bugs

---

## 🤝 Contribution

Si vous améliorez cette démo:
1. Tester le flow complet
2. Mettre à jour SCENARIO.md si modifications
3. Capturer nouveaux screenshots si UI change
4. Documenter changements dans ce README

---

## 📝 Notes de Version

### v1.0.0 (2025-10-14)
- ✅ Scénario initial créé (SCENARIO.md)
- ✅ Structure dossiers
- ✅ README documentation
- ⏭️ Présentation Reveal.js (TODO)
- ⏭️ Assets visuels (TODO)

---

## 📞 Support

**Questions**: Vérifier [SCENARIO.md](SCENARIO.md) pour détails complets

**Bugs**: Créer issue sur GitHub

**Contributions**: Pull requests bienvenues

---

**Version**: 1.0.0
**Status**: 🔄 In Progress (SCENARIO ✅, Presentation TODO)
**Last Updated**: 2025-10-14
**Estimated Completion**: 8-10 hours total work
