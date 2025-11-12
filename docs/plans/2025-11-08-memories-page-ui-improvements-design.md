# Memories Page UI Improvements - Design Document

**Date:** 2025-11-08
**Status:** Validated
**Page:** http://localhost:3000/memories

## Objectifs

1. Augmenter la hauteur des 3 colonnes pour qu'elles prennent 100% de la hauteur disponible
2. Rendre la colonne "Recent Conversations" plus intelligible avec des informations claires

## Contexte Actuel

La page Memories affiche 3 colonnes:
- **Recent Conversations** (gauche)
- **Code Indexing Activity** (centre)
- **Embeddings Status** (droite)

**Problèmes identifiés:**
- Les colonnes n'utilisent pas efficacement l'espace vertical
- Les informations des conversations sont cryptiques (temps relatif non intuitif)
- Informations importantes manquantes (date complète, projet, type de mémoire)

## Solution 1: Structure de Layout et Hauteur des Colonnes

### Approche: Hauteur Flexible avec Max-Height

**Layout structure:**
```
┌─────────────────────────────────────────┐
│ Header (Memories Monitor + Refresh)    │ Fixe
├─────────────────────────────────────────┤
│ Stats Bar (Total, Embeddings, etc)     │ Fixe
├─────────────────────────────────────────┤
│ ┌─────────┬─────────┬─────────┐        │
│ │ Recent  │  Code   │Embedding│        │ Flexible
│ │ Convs   │ Chunks  │ Status  │        │ avec
│ │         │         │         │        │ max-height
│ │ [scroll]│ [scroll]│ [scroll]│        │
│ └─────────┴─────────┴─────────┘        │
└─────────────────────────────────────────┘
```

**Implémentation:**
- Container des colonnes: `max-height: calc(100vh - 280px)`
  - 280px = navbar (64px) + header (80px) + stats bar (100px) + padding (36px)
- Chaque widget: `overflow-y: auto` pour scroll individuel
- Les colonnes s'adaptent au contenu jusqu'à la max-height
- Au-delà, scroll apparaît dans chaque colonne

**Avantages:**
- Les 3 en-têtes de colonnes restent toujours visibles
- Pas de scroll global de la page
- Les colonnes courtes ne sont pas artificiellement étirées
- Responsive: la hauteur s'adapte à la taille de l'écran

## Solution 2: Affichage Détaillé des Conversations

### Structure d'une Carte de Conversation

```
┌─────────────────────────────────────────┐
│ 8 novembre 2025 07:18:03  │  Claude    │ ← Date + Auteur
├─────────────────────────────────────────┤
│ Conv: Use and follow the brainstorming  │ ← Titre + Type
│      skill exactly as written           │
├─────────────────────────────────────────┤
│ 📁 mnemolite                            │ ← Projet (si disponible)
├─────────────────────────────────────────┤
│ [auto-saved] [session:6699d37b] [+2]   │ ← Tags + Session
├─────────────────────────────────────────┤
│ ● EMBEDDED                    [VIEW]    │ ← Status + Action
└─────────────────────────────────────────┘
```

### Détails de Chaque Section

**Ligne 1 - En-tête (Date + Auteur):**
- Date complète en français: `formatFullDate(created_at)`
  - Format: "8 novembre 2025 07:18:03"
- Auteur à droite (ou "Unknown" si null)
- Style: Police mono, text-xs, text-gray-400

**Ligne 2 - Titre avec Type:**
- Préfixe selon `memory_type`:
  - conversation → "Conv:"
  - note → "Note:"
  - decision → "Dec:"
  - task → "Task:"
  - reference → "Ref:"
- Titre tronqué sur 2 lignes max avec ellipsis
- Style: Police normale, text-sm, text-gray-200

**Ligne 3 - Projet (conditionnelle):**
- Affiché uniquement si `project_id` existe
- Format: `📁 {project_name}`
- Style: text-xs, text-cyan-400 (cohérence SCADA)

**Ligne 4 - Tags et Session:**
- 3 premiers tags visibles
- Compteur si plus de 3 tags: `+N`
- Session ID toujours visible (8 premiers caractères)
- Style: Badges avec bg-slate-600, font-mono

**Ligne 5 - Footer (Status + Action):**
- LED colorée (vert = embedded, jaune = no embedding)
- Texte status: "EMBEDDED" / "NO EMBEDDING"
- Bouton "VIEW" (style SCADA)

### Fonctions de Formatage

**Date complète en français:**
```typescript
function formatFullDate(isoString: string): string {
  const date = new Date(isoString)
  const months = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin',
                  'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
  const day = date.getDate()
  const month = months[date.getMonth()]
  const year = date.getFullYear()
  const time = date.toLocaleTimeString('fr-FR')
  return `${day} ${month} ${year} ${time}`
}
```

**Label de type de mémoire:**
```typescript
function getMemoryTypeLabel(type: string): string {
  const labels = {
    conversation: 'Conv:',
    note: 'Note:',
    decision: 'Dec:',
    task: 'Task:',
    reference: 'Ref:'
  }
  return labels[type] || 'Conv:'
}
```

## Fichiers à Modifier

### 1. `/frontend/src/pages/Memories.vue`

**Changements:**
- Modifier le grid container pour ajouter max-height:
  ```html
  <div class="grid grid-cols-1 lg:grid-cols-3 gap-6 max-h-[calc(100vh-280px)]">
  ```

### 2. `/frontend/src/components/ConversationsWidget.vue`

**Changements:**
- Ajouter fonction `formatFullDate()`
- Ajouter fonction `getMemoryTypeLabel()`
- Modifier le template pour afficher:
  - En-tête: Date complète + Auteur
  - Titre avec préfixe type
  - Projet (si disponible)
  - Tags + Session ID
  - Footer: Status + bouton VIEW
- Ajouter `overflow-y-auto` au container de la liste

### 3. Ajustements CSS

**Style SCADA maintenu:**
- LEDs colorées (cyan, vert, jaune, rouge)
- Police monospace pour données techniques
- Couleurs cyber (slate, cyan, gray)
- Bordures et effets industriels

**Nouveaux styles:**
- Couleur projet: text-cyan-400
- Titre: max 2 lignes avec line-clamp
- Espacement cohérent entre sections

## Gestion des Données Manquantes

- `project_id` null → Ne pas afficher la ligne projet
- `author` null → Afficher "Unknown" ou "System"
- `tags` vide → Ne pas afficher la section tags

## Résultat Attendu

Une page Memories avec:
1. ✅ Colonnes utilisant efficacement la hauteur disponible (max-height + scroll individuel)
2. ✅ Conversations lisibles avec toutes les informations importantes visibles
3. ✅ Date complète en français (8 novembre 2025 07:18:03)
4. ✅ Type de mémoire clairement identifié (Conv:, Note:, etc.)
5. ✅ Projet visible quand disponible
6. ✅ Style SCADA industriel maintenu
7. ✅ Scroll fluide dans chaque colonne indépendamment

## Notes d'Implémentation

- Conserver le style SCADA existant (LEDs, monospace, couleurs cyber)
- Tester avec différentes hauteurs de viewport
- Vérifier le comportement sur mobile (responsive)
- S'assurer que le scroll fonctionne bien sur toutes les colonnes
- Maintenir la performance (pas de lag avec beaucoup de conversations)
