# MnemoLite - Présentation AIDD Live (30 min)

**Version**: 1.0
**Date**: 2025-10-31
**Format**: Live Discord + Slides
**Durée**: 30 minutes max
**Audience**: Communauté AIDD (tech/IA francophones)

---

## 📁 Contenu du Dossier

| Fichier | Description |
|---------|-------------|
| **`index_aidd_v1.0.html`** | Présentation Reveal.js (21 slides) - **FICHIER PRINCIPAL** |
| **`AIDD_STRUCTURE.md`** | Structure détaillée et contraintes (référence) |
| **`AIDD_USAGE_GUIDE.md`** | Guide d'utilisation complet + checklist |
| **`README.md`** | Ce fichier (vue d'ensemble) |

---

## 🎯 Objectifs de la Présentation

1. **Montrer la valeur de MnemoLite** via 3 use cases concrets
2. **Démontrer l'intégration IA** (Claude + MCP + Embeddings + pgvector)
3. **Appeler à la collaboration** open-source
4. **Recruter des contributeurs** (frontend, backend, docs, testing)

---

## 📊 Structure (30 minutes)

| Section | Slides | Temps | Contenu |
|---------|--------|-------|---------|
| **Intro** | 1-4 | 5 min | Problème LLMs + Solution MnemoLite + 3 use cases |
| **Use Case 1** | 5-8 | 5 min | Assistant qui se Souvient (MCP) |
| **Use Case 2** | 9-12 | 5 min | Knowledge Base Auto-Growing (7,972 conversations) |
| **Use Case 3** | 13-16 | 5 min | Code Intelligence (Graph) |
| **Impact** | 17-18 | 3 min | Métriques + Open Source |
| **Roadmap** | 19-19bis | 2 min | Roadmap + Contributions |
| **Q&A** | 20 | 5 min | Questions + Merci |

**Total**: 21 slides | Rythme: 1.4 min/slide (énergique)

---

## 🚀 Démarrage Rapide

### 1. Ouvrir la Présentation

```bash
# Option simple
open index_aidd_v1.0.html

# Option serveur local (recommandé)
python3 -m http.server 8080
# Puis: http://localhost:8080/index_aidd_v1.0.html
```

### 2. Personnaliser (OBLIGATOIRE)

**Remplacer les placeholders suivants:**
- `[Votre Nom]` → Votre nom
- `[username]` → Votre GitHub username
- `[current count]` → Nombre de stars actuel
- `[email]` → Votre email
- `@[username]` → Votre Discord handle
- `@[handle]` → Votre Twitter/X

**Script de remplacement rapide:**
```bash
sed -i 's/\[Votre Nom\]/Jacques Dupont/g' index_aidd_v1.0.html
sed -i 's/\[username\]/votre-username/g' index_aidd_v1.0.html
sed -i 's/\[current count\]/42 stars/g' index_aidd_v1.0.html
sed -i 's/\[email\]/votre.email@example.com/g' index_aidd_v1.0.html
```

### 3. Préparer les Démos

**À créer dans `demonstration/3.0_AIDD/assets/`:**
1. `demo1_mcp_action.mp4` (ou .png) - Slide 7
2. `demo2_dashboard.png` - Slide 11
3. `demo3_code_graph.png` - Slide 15

**Voir:** `AIDD_USAGE_GUIDE.md` section "Préparation des Démos" pour détails.

---

## 📋 Checklist Pré-Live (15 jours avant)

### Technique ✅
- [ ] Personnalisation complète (nom, liens, email)
- [ ] 3 démos préparées (vidéos/screenshots)
- [ ] Assets copiés dans `assets/`
- [ ] Dashboard accessible (localhost:8001)
- [ ] Internet stable + backup
- [ ] MCP configuré dans Claude Desktop

### Contenu ✅
- [ ] Timing validé (30 min)
- [ ] Script verbal répété
- [ ] Q&A anticipées

### Communautaire ✅
- [ ] GitHub public + issues organisées
- [ ] Discord/contact partagés
- [ ] Roadmap visible
- [ ] Contributing guide à jour

**Checklist complète:** Voir `AIDD_USAGE_GUIDE.md`

---

## 🎯 Différences vs Présentation Technique (v3.1.0)

| Aspect | v3.1.0 (Technique) | v1.0 AIDD (Communauté) |
|--------|-------------------|----------------------|
| **Durée** | 50-60 min | **30 min** |
| **Slides** | 71 slides | **21 slides** |
| **Focus** | 8 Décisions Techniques | **3 Use Cases + Démos** |
| **Tone** | Professionnel, humble | **Énergique, communautaire** |
| **Audience** | Meetup technique | **Communauté IA** |
| **Goal** | Inspiration | **Collaboration + Contributors** |
| **Démos** | Optionnel | **OBLIGATOIRE** |

---

## 🎨 Export vers Canva

Si vous préférez Canva à Reveal.js:

**Option 1**: Screenshots → Import Canva
**Option 2**: Copier contenu texte → Design manuel
**Option 3**: PDF Export (`?print-pdf`) → Import Canva

**Détails:** Voir `AIDD_USAGE_GUIDE.md` section "Export vers Canva"

---

## 📞 Support & Questions

**Documentation:**
- Structure détaillée: `AIDD_STRUCTURE.md`
- Guide utilisation: `AIDD_USAGE_GUIDE.md`
- Présentation technique: `../2.0/index_v3.1.0.html`

**Contact:**
- Discord AIDD: [lien communauté]
- GitHub: github.com/[username]/mnemolite
- Issues: github.com/[username]/mnemolite/issues

---

## 🚨 Important

**À faire AVANT le live:**
1. ✅ Personnaliser les placeholders (nom, liens)
2. ✅ Créer les 3 démos (vidéos/screenshots)
3. ✅ Tester le timing (30 min max)
4. ✅ Préparer backup si démos fail
5. ✅ S'assurer que GitHub est public et organisé

**Deadline soumission AIDD:** 15 jours avant le live

---

## 📊 Métriques de Succès

**Objectifs post-live:**
- 🎯 >20 personnes présentes
- 🎯 +10-20 GitHub stars
- 🎯 2-3 nouveaux contributeurs
- 🎯 5-10 nouveaux membres Discord
- 🎯 Issues/suggestions concrètes

---

**Bon live! 🚀**

*Dernière mise à jour: 2025-10-31*
