# SPEC: MnemoLite Documentation v2 — Reprise Complète

**Date:** 2026-04-08  
**Status:** Draft  
**Type:** Documentation Rewrite

---

## 1. Objectif

Réécrire entièrement la documentation MnemoLite avec une approche minimaliste et pragmatique. Archiver l'existant, créer 5 fichiers focalisés.

---

## 2. Structure Cible

```
docs/
├── README.md              # Overview + liens rapides
├── QUICKSTART.md          # Setup rapide + test
├── MCP.md                 # Intégration MCP (33 outils)
├── API.md                 # Endpoints REST
├── ARCHITECTURE.md        # Vue technique
└── 88_ARCHIVE/
    └── YYYY-MM-DD_docs_v1 # Ancien docs/ archivé
```

---

## 3. Contenu par Fichier

### README.md (~100 lignes)
- Badges (version, license, postgres, pgvector)
- Features clés (Cognitive Memory, Code Intelligence, MCP)
- Tableau services (URLs)
- Architecture ASCII
- Liens vers les 4 autres fichiers
- Section développement (make commands)

### QUICKSTART.md (~150 lignes)
- Prérequis (Docker, RAM)
- Démarrage Docker Compose
- Configuration MCP (`.mcp.json`)
- Test connexion (`ping`)
- Premier usage (index_project, search_code, write_memory)
- Troubleshooting rapide

### MCP.md (~300 lignes)
- 33 outils MCP documentés (table)
- Protocole (handshake, headers)
- Configuration clients (KiloCode, Claude Desktop)
- Tests MCP
- Paramètres RRF/decay
- Déploiement Docker

### API.md (~200 lignes)
- Endpoints REST principaux
- Schemas Pydantic clés
- Auth (si applicable)
- Exemples curl

### ARCHITECTURE.md (~250 lignes)
- Stack technique
- Pipeline indexation (7 étapes)
- Cache triple-layer (L1/L2/L3)
- Schéma DB (tables principales)
- Architecture services

---

## 4. Règles de Contenu

| Règle | Application |
|-------|-------------|
| **0 HTMX** | Frontend = Vue 3 SPA |
| **Versions exactes** | v5.0.0-dev, 33 MCP tools, pgvector 0.8.1 |
| **Pas de chemins hardcodés** | `<project-root>` |
| **0 lien cassé** | Vérification obligatoire |
| **Pas de redondance** | README = hub, autres = contenu |
| **Tests count** | 1570+ functions |

---

## 5. Processus d'Implémentation

### Phase 1: Archivage
1. Créer `docs/88_ARCHIVE/2026-04-08_docs_v1/`
2. Déplacer TOUT le contenu actuel `docs/` (sauf 88_ARCHIVE)
3. Commit: "docs: archive v1 (2026-04-08)"

### Phase 2: Création
1. Créer `README.md`
2. Créer `QUICKSTART.md`
3. Créer `MCP.md` (basé sur MCP-GUIDE.md existant, mis à jour)
4. Créer `API.md` (basé sur DECISION_api_specification.md)
5. Créer `ARCHITECTURE.md` (basé sur ARCHITECTURE.md existant)

### Phase 3: Validation
1. Vérifier tous les liens résolvent
2. Vérifier versions exactes
3. Vérifier 0 référence HTMX
4. Supprimer `docs/README.md` si créé en double

---

## 6. Critères de Succès

- [ ] 5 fichiers dans `docs/`
- [ ] 0 HTMX dans docs actives
- [ ] Versions exactes (v5.0.0-dev)
- [ ] 33 MCP tools documentés
- [ ] 0 lien cassé
- [ ] Pas de chemins `/home/giak/`
- [ ] README pointe vers les 4 autres fichiers

---

## 7. Métriques

| Avant | Après |
|-------|-------|
| 48 fichiers | 5 fichiers |
| 7.4 MB | < 500 KB |
| 336+ versions incohérentes | 1 version (v5.0.0-dev) |
| 4+ compteurs MCP différents | 33 (exact) |
| Liens cassés | 0 |
