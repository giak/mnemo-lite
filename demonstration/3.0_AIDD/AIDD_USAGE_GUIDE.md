# MnemoLite - Guide d'Utilisation Présentation AIDD

**Fichier**: `index_aidd_v1.0.html`
**Format**: 30 minutes | 21 slides | Reveal.js
**Date**: 2025-10-31

---

## 🚀 Démarrage Rapide

### Ouvrir la Présentation

```bash
# Option 1: Ouvrir directement dans le navigateur
open demonstration/3.0_AIDD/index_aidd_v1.0.html

# Option 2: Serveur local (recommandé pour les démos)
cd demonstration/3.0_AIDD
python3 -m http.server 8080
# Puis ouvrir: http://localhost:8080/index_aidd_v1.0.html
```

### Contrôles Reveal.js

- **Flèches** : Navigation entre slides
- **F** : Mode plein écran
- **S** : Mode speaker (notes + timer)
- **O** : Vue d'ensemble (toutes les slides)
- **ESC** : Quitter mode plein écran/vue d'ensemble

---

## ✏️ Personnalisations OBLIGATOIRES

Avant le live, remplacez les placeholders suivants dans `index_aidd_v1.0.html`:

### Slide 1: Introduction
```html
<!-- Chercher et remplacer: -->
[Votre Nom] → Jacques Dupont (ou votre nom)
```

### Slide 18: Open Source + Liens
```html
<!-- Chercher et remplacer: -->
github.com/[username]/mnemolite → github.com/votre-username/mnemolite
[current count] → 42 stars (ou chiffre actuel)
@[username] → @votre_discord_handle
[email] → votre.email@example.com
@[handle] → @votre_twitter
```

### Slide 20: Q&A
```html
<!-- Chercher et remplacer (même chose que Slide 18): -->
github.com/[username]/mnemolite
@[username]
[email]
```

### Commande de Remplacement Global

```bash
# Dans le fichier index_aidd_v1.0.html
sed -i 's/\[Votre Nom\]/Jacques Dupont/g' index_aidd_v1.0.html
sed -i 's/\[username\]/votre-username/g' index_aidd_v1.0.html
sed -i 's/\[current count\]/42 stars/g' index_aidd_v1.0.html
sed -i 's/@\[username\]/@votre_discord/g' index_aidd_v1.0.html
sed -i 's/\[email\]/votre.email@example.com/g' index_aidd_v1.0.html
sed -i 's/@\[handle\]/@votre_twitter/g' index_aidd_v1.0.html
```

---

## 🎬 Préparation des Démos

### Démo 1: Assistant qui se Souvient (Slide 7)

**À préparer:**
1. **Vidéo/Screenshot** montrant:
   - Claude Desktop interface
   - Conversation "Lundi" avec question sur PostgreSQL 18
   - Conversation "Vendredi" avec search_conversations() appelé
   - Contexte restauré avec référence à la conversation précédente

2. **Fichier à créer**:
   - `demonstration/3.0_AIDD/assets/demo1_mcp_action.mp4` (ou .png)
   - Durée max: 60 secondes

3. **Insertion dans HTML**:
```html
<!-- Remplacer Slide 7 .demo-placeholder par: -->
<div style="text-align: center;">
    <video width="80%" controls>
        <source src="assets/demo1_mcp_action.mp4" type="video/mp4">
    </video>
    <p style="font-size: 0.7em; color: #42affa;">
        💡 Temps de recherche: 8-12ms | Précision: ~85%
    </p>
</div>
```

### Démo 2: Knowledge Base Auto-Growing (Slide 11)

**À préparer:**
1. **Screenshot dashboard** montrant:
   - URL: http://localhost:8001/ui/autosave
   - Liste des 7,972 conversations
   - Barre de recherche avec query "postgres 18"
   - Résultats en 8-12ms

2. **Fichier à créer**:
   - `demonstration/3.0_AIDD/assets/demo2_dashboard.png`

3. **Insertion dans HTML**:
```html
<!-- Remplacer Slide 11 .demo-placeholder par: -->
<div style="text-align: center;">
    <img src="assets/demo2_dashboard.png" alt="Dashboard" style="width: 85%; border: 2px solid #42affa; border-radius: 8px;">
    <p style="font-size: 0.75em; color: #42affa;">
        💡 Recherche: "pourquoi postgres 18" → 12 résultats en 10ms
    </p>
</div>
```

### Démo 3: Code Intelligence avec Graph (Slide 15)

**À préparer:**
1. **Screenshot graph** montrant:
   - URL: http://localhost:8001/ui/code_graph
   - Query: "dependencies of services/code_indexing_service.py"
   - Visualisation D3.js du graph avec nodes/edges
   - Résultat: routes → dependencies → main

2. **Fichier à créer**:
   - `demonstration/3.0_AIDD/assets/demo3_code_graph.png`

3. **Insertion dans HTML**:
```html
<!-- Remplacer Slide 15 .demo-placeholder par: -->
<div style="text-align: center;">
    <img src="assets/demo3_code_graph.png" alt="Code Graph" style="width: 85%; border: 2px solid #42affa; border-radius: 8px;">
    <p style="font-size: 0.7em; color: #42affa;">
        💡 Graph stocké en PostgreSQL, queries via API REST
    </p>
</div>
```

### Création du Dossier Assets

```bash
mkdir -p demonstration/3.0_AIDD/assets
# Puis copier vos screenshots/vidéos dans ce dossier
```

---

## ⏱️ Timing Détaillé (30 min)

| Slides | Section | Temps | Cumul |
|--------|---------|-------|-------|
| 1-4 | **Intro + Setup** | 5 min | 5 min |
| 5-8 | **Use Case 1: Assistant qui se Souvient** | 5 min | 10 min |
| 9-12 | **Use Case 2: Knowledge Base Auto-Growing** | 5 min | 15 min |
| 13-16 | **Use Case 3: Code Intelligence** | 5 min | 20 min |
| 17-18 | **Impact + Open Source** | 3 min | 23 min |
| 19-19bis | **Roadmap + Collaboration** | 2 min | 25 min |
| 20 | **Q&A** | 5 min | 30 min |

**Rythme**: 1.4 min/slide (soutenu, énergique)

---

## 📋 Checklist Pré-Live (15 jours avant)

### Technique ✅

- [ ] Personnalisation complète (nom, liens, email)
- [ ] 3 démos préparées (vidéos/screenshots)
- [ ] Assets copiés dans `demonstration/3.0_AIDD/assets/`
- [ ] HTML mis à jour avec vrais médias (pas de placeholders)
- [ ] Dashboard accessible (localhost:8001)
- [ ] Claude Desktop configuré avec MCP
- [ ] Internet stable pour démo live
- [ ] Backup slides si démo fail (screenshots statiques)

### Contenu ✅

- [ ] Slides finalisées (21 slides)
- [ ] Timing validé (30 min max)
- [ ] Script verbal répété (voir AIDD_STRUCTURE.md lignes 178-191)
- [ ] Transitions fluides
- [ ] Q&A anticipées (liste ci-dessous)

### Communautaire ✅

- [ ] Liens GitHub préparés et publics
- [ ] Discord/contact partagés
- [ ] Issues GitHub organisées (good first issue)
- [ ] Roadmap publique visible (docs/agile/ROADMAP.md)
- [ ] Contributing guide à jour (CONTRIBUTING.md)
- [ ] README principal mis à jour

---

## 🎤 Script Verbal Suggéré

### Intro (Slide 1-2) - 2 min
> "Salut la commu AIDD! Moi c'est [nom], développeur solo qui aime expérimenter avec l'IA. Aujourd'hui je vais vous montrer MnemoLite, un projet qui résout un problème qu'on a TOUS vécu : les LLMs qui oublient tout entre les sessions. Vous savez, ce moment où vous dites à Claude 'je t'avais déjà expliqué ça la semaine dernière' et il répond 'euh... non?' — Frustrant, non?"

### Transition Use Cases (Slide 4) - 1 min
> "Alors aujourd'hui, 3 démos concrètes pour vous montrer comment MnemoLite change ça. Use case 1: un assistant qui SE SOUVIENT. Use case 2: une knowledge base qui grandit toute seule. Use case 3: du code intelligence avec graph. Et spoiler: tout tourne sur CPU, 0€ budget, 100% open-source. Let's go!"

### Use Case 1 Intro (Slide 5) - 30 sec
> "Premier use case: imaginez que lundi, vous expliquez à Claude pourquoi vous avez choisi PostgreSQL. Vendredi, vous lui reposez la question. Sans MnemoLite, il a tout oublié. Avec MnemoLite... [DEMO LIVE]"

### Use Case 2 Intro (Slide 9) - 30 sec
> "Deuxième use case: documenter manuellement, c'est pénible. Et si vos conversations créaient automatiquement une knowledge base vivante? Regardez ces 7,972 conversations auto-indexées..."

### Use Case 3 Intro (Slide 13) - 30 sec
> "Troisième use case: comprendre les dépendances code, c'est compliqué. MnemoLite parse votre codebase et vous montre visuellement 'qui dépend de quoi'. Regardez..."

### Closing (Slide 19) - 1 min
> "Voilà! 3 use cases, 7,972 conversations indexées, 4 mois de dev solo. Mais c'est là que VOUS entrez en jeu. Le projet est open-source, j'ai besoin de collaborateurs pour tester en production, améliorer le frontend, faire du load testing. Qui est chaud pour rejoindre l'aventure?"

### Q&A (Slide 20) - 5 min
> "On passe aux questions! N'hésitez pas à me ping sur Discord après le live aussi."

---

## ❓ Q&A Anticipées

### Questions Techniques

**Q: Ça marche avec d'autres LLMs que Claude?**
R: Actuellement optimisé pour Claude Desktop via MCP. GPT-4/Gemini support prévu Q1 2026 (voir roadmap).

**Q: Quelle est la latence de recherche?**
R: 8-12ms pour recherche sémantique avec pgvector HNSW. 355/355 tests passent.

**Q: Ça tourne sur GPU ou CPU?**
R: 100% CPU! sentence-transformers (nomic-embed-text-v1.5). 0€ budget.

**Q: C'est scalable pour combien d'users?**
R: Actuellement testé solo/duo. Load testing >100 users prévu Phase 2. Besoin de collaborateurs pour tester!

**Q: Quelle est la taille de la base de données?**
R: 7,972 conversations = ~500MB. PostgreSQL 18 + pgvector 0.8.1.

### Questions Pratiques

**Q: Comment on installe ça?**
R: `docker compose up` + MCP config. Voir README + MCP_INTEGRATION_GUIDE.md. 15 minutes install.

**Q: C'est open-source vraiment?**
R: Oui, MIT license. Forkez, modifiez, contribuez! github.com/[username]/mnemolite

**Q: Vous cherchez quels types de contributions?**
R: Frontend/UX, backend/infra, docs FR/EN, load testing, bug hunting. Voir Slide 19bis.

**Q: Ça fonctionne en production?**
R: Oui, utilisé quotidiennement par moi depuis 4 mois. Besoin de validation multi-user (aidez-moi!).

### Questions Roadmap

**Q: Prochaine feature?**
R: Multi-user support (Phase 2) + Mobile app React Native (Q1 2026).

**Q: Vous prévoyez une version payante?**
R: Pas à court terme. Peut-être Enterprise tier (SLA, SSO) en Q2 2026 si demande.

**Q: Comment je peux aider?**
R: Rejoignez Discord, testez en local, proposez des PRs, partagez vos use cases!

---

## 🎨 Export vers Canva (Optionnel)

Si vous préférez utiliser Canva plutôt que Reveal.js:

### Option 1: Screenshots HTML → Canva Import
```bash
# Ouvrir présentation en plein écran
# Prendre screenshot de chaque slide (F ou Cmd+Shift+3)
# Importer les 21 images dans Canva
```

### Option 2: Contenu Text → Canva Design
1. Ouvrir `index_aidd_v1.0.html` dans éditeur
2. Copier le texte de chaque `<section>`
3. Créer slides Canva manuellement avec le contenu
4. Appliquer template AIDD (gradient backgrounds, bold fonts)

### Option 3: PDF Export → Canva
```bash
# Ouvrir présentation dans navigateur
# Ajouter ?print-pdf à l'URL:
# http://localhost:8080/index_aidd_v1.0.html?print-pdf
# Print → Save as PDF
# Importer PDF dans Canva
```

---

## 🚨 Troubleshooting

### Problème: Slides trop denses verticalement
**Solution**: Réduire encore la font-size dans CSS (ligne 13):
```css
.reveal {
    font-size: 22px;  /* Au lieu de 24px */
}
```

### Problème: Vidéos ne s'affichent pas
**Solution**: Vérifier chemin relatif `assets/` et format (MP4 H.264 recommandé).

### Problème: Timing trop serré (>30 min)
**Solution**:
- Fusionner Slide 19 + 19bis (roadmap + contributions)
- Réduire Use Case 3 à 4 min (moins de détails sur flow IA)

### Problème: Démos fail en live
**Solution**: Backup screenshots statiques déjà inclus dans HTML (mode dégradé).

---

## 📊 Métriques de Succès Post-Live

**Objectifs**:
- 🎯 **Engagement**: >20 personnes présentes
- 🎯 **GitHub Stars**: +10-20 stars
- 🎯 **Contributors**: 2-3 nouveaux contributeurs
- 🎯 **Discord**: 5-10 nouveaux membres
- 🎯 **Feedback**: Issues/suggestions concrètes

**Follow-up**:
- Post-live debrief avec organisateurs AIDD
- Potential ambassadeur AIDD
- Suivi live dans 2-3 mois (Phase 2 results)

---

## 📞 Support

**Questions sur la présentation?**
- Consulter: `AIDD_STRUCTURE.md` (structure détaillée)
- Discord: @[username]
- GitHub Issues: github.com/[username]/mnemolite/issues

**Bon live! 🚀**
