# EPIC-09: Advanced File Upload & Batch Processing

**Version**: 1.0.0
**Date**: 2025-10-17
**Status**: 🚧 **PROPOSED** (0/35 pts)
**Dependencies**: ✅ EPIC-07 (UI Infrastructure)

---

## 📚 Documentation Structure

```
EPIC-09/
├─ EPIC-09_Advanced_File_Upload_README.md  ← VOUS ÊTES ICI (point d'entrée)
├─ STORIES_EPIC-09_Upload.md               (Detailed user stories)
└─ EPIC-09_COMPLETION_REPORT.md            (Future: implementation results)
```

---

## 🎯 Executive Summary (2 min)

### Le Problème Actuel

L'interface actuelle ne supporte que l'upload **fichier par fichier**. Pour indexer un projet entier, l'utilisateur doit :
- Sélectionner manuellement chaque fichier 😱
- Pas de support pour les dossiers avec parcours récursif
- Pas de support pour les archives ZIP contenant des codebases complètes
- Pas de support pour git clone
- Processus fastidieux et error-prone

**Cas d'usage critiques non supportés** :
1. **Glisser-déposer un dossier projet complet** → Parcours récursif de TOUS les sous-dossiers
2. **Upload d'un ZIP de projet** → Extraction avec préservation de la structure complète

**Impact** : Pour un projet de 1000+ fichiers → Impossible actuellement !

### Vision

Transformer l'upload en un système **intelligent et efficace** capable de traiter :
- 📁 **Dossiers entiers** (récursif avec filtres)
- 🗜️ **Archives ZIP/TAR**
- 🔗 **Git repositories** (clone direct)
- 📦 **Batch processing** optimisé
- 🎯 **Smart filtering** (.gitignore aware)

### Principe Fondamental

> "One click to index an entire codebase"

### Valeur Métier Immédiate

| Avant | Après | Gain |
|-------|-------|------|
| 100 fichiers = 100 clics | 1 dossier = 1 clic | **100x plus rapide** |
| Pas de ZIP | ZIP upload direct | **Convenience** |
| Pas de git | Git clone URL | **Integration** |
| Manuel uniquement | Automation ready | **Scalability** |

---

## 🏗️ Architecture Overview

### Current State (Limitation)
```html
<input type="file" multiple accept=".py,.js,...">
<!-- Ne supporte que des fichiers individuels -->
```

### Target State
```html
<!-- Multiple input modes -->
<input type="file" webkitdirectory>  <!-- Folders -->
<input type="file" accept=".zip,.tar.gz">  <!-- Archives -->
<input type="url" placeholder="https://github.com/...">  <!-- Git -->
```

### Processing Pipeline
```
Upload Sources → Filter & Validate → Extract & Parse → Batch Process → Index
      ↓              ↓                   ↓                ↓            ↓
   Folder         .gitignore          Unzip/Clone      Queue       Database
   ZIP/TAR        Extensions          Tree-walk        Chunking    Storage
   Git URL        Size limits         Encoding         Progress    Graph
```

---

## 🔄 Architecture Unifiée: Convergence Folder & ZIP

Les deux modes principaux (Dossier Récursif et ZIP) convergent vers le même pipeline de traitement :

### Pipeline Convergent
```
[Dossier Récursif] ──┐
                      ├──→ [Structure Tree] → [Smart Filter] → [Preview UI] → [Batch Process] → [Index]
[ZIP Upload] ─────────┘
```

### Structure de Données Unifiée
```typescript
interface ProjectStructure {
  name: string;
  type: 'root' | 'folder' | 'file';
  path: string;  // Chemin relatif préservé depuis la racine
  children?: Map<string, ProjectStructure>;

  // Pour les fichiers
  content?: string | ArrayBuffer | LazyLoader;
  size?: number;
  language?: string;
  selected?: boolean;

  // Métadonnées projet
  stats?: {
    totalFiles: number;
    totalSize: number;
    selectedFiles: number;
    selectedSize: number;
    languages: Set<string>;
    depth: number;  // Profondeur max de l'arbre
    projectType?: 'node' | 'python' | 'java' | 'unknown';
  };
}
```

### Points de Convergence
| Aspect | Dossier Récursif | ZIP Upload | Résultat Unifié |
|--------|------------------|------------|-----------------|
| **Structure** | Parcours récursif complet | Extraction avec hiérarchie | Arbre identique |
| **Filtrage** | .gitignore + smart filter | Même filtres dans ZIP | Fichiers pertinents |
| **Preview** | Tree view interactive | Tree view identique | UX cohérente |
| **Performance** | Chunking + Workers | Streaming + Workers | Scalable |
| **Mémoire** | IndexedDB cache | Extraction lazy | Optimisé |

---

## 📊 Stories Overview (35 points total)

### Phase 1: Core Upload Capabilities (15 pts)

#### Story 1: Recursive Folder Upload with Complete Structure (8 pts) ⭐ CRITICAL
**Goal**: Support récursif COMPLET des dossiers avec préservation de la structure

**Use Case Principal**:
```bash
# User glisse son projet entier
my-project/
├── src/
│   ├── components/    # 234 fichiers
│   ├── services/      # 156 fichiers
│   └── utils/         # 89 fichiers
├── tests/             # 456 fichiers
└── docs/              # 234 fichiers
# → TOUT est parcouru récursivement et indexé avec structure préservée
```

**Acceptance Criteria**:
- [ ] Upload de dossiers entiers via drag & drop
- [ ] Parcours récursif COMPLET de TOUS les sous-dossiers
- [ ] Conservation intégrale de la structure des chemins
- [ ] Filtrage intelligent automatique (.gitignore, node_modules, etc.)
- [ ] Progress bar avec détails par dossier
- [ ] Support jusqu'à 10,000+ fichiers avec chunking
- [ ] Preview en arbre avant validation
- [ ] Web Workers pour ne pas bloquer l'UI

**Technical Implementation Avancée**:
```javascript
// Parcours récursif COMPLET avec Web Workers
async function traverseDirectoryRecursive(dirHandle, basePath = '') {
  const files = [];

  for await (const entry of dirHandle.values()) {
    const path = basePath ? `${basePath}/${entry.name}` : entry.name;

    if (entry.kind === 'file') {
      const file = await entry.getFile();
      // Préserver le chemin complet
      files.push({
        path: path,
        file: file,
        size: file.size,
        modified: file.lastModified,
        relativePath: path  // Critique pour reconstruction
      });
    } else if (entry.kind === 'directory') {
      // RÉCURSIF - descendre dans TOUS les sous-dossiers
      const subFiles = await traverseDirectoryRecursive(entry, path);
      files.push(...subFiles);
    }
  }

  return files;
}

// Smart filtering intégré
const smartFilter = {
  autoExclude: [
    'node_modules/**',
    '.git/**',
    '**/.DS_Store',
    '**/__pycache__/**',
    'dist/**',
    'build/**',
    '.env*'
  ],
  maxFileSize: 10 * 1024 * 1024, // 10MB par fichier
  includeOnly: ['.py', '.js', '.ts', '.jsx', '.tsx', '.java', '.go', '.rs']
};

// Chunked processing pour gros projets
class ChunkedProcessor {
  async processLargeProject(files) {
    const CHUNK_SIZE = 100;
    const chunks = [];

    for (let i = 0; i < files.length; i += CHUNK_SIZE) {
      chunks.push(files.slice(i, i + CHUNK_SIZE));
    }

    for (const chunk of chunks) {
      await this.processChunk(chunk);
      this.updateProgress(chunks.indexOf(chunk) / chunks.length * 100);
    }
  }
}
```

**Défis & Solutions**:
| Défi | Solution |
|------|----------|
| WebKit API limitée | Fallback pour autres browsers |
| 10k+ fichiers | Streaming + chunking |
| Performance | Web Workers + virtual scrolling |
| Mémoire | IndexedDB pour cache temporaire |

---

#### Story 2: Complete Codebase ZIP Upload with Structure Preservation (7 pts) ⭐ CRITICAL
**Goal**: Upload et extraction d'archives ZIP contenant des codebases complètes

**Use Case Principal**:
```bash
# Développeur crée un ZIP de son projet
cd my-awesome-project/
zip -r project.zip . -x "node_modules/*" ".git/*" "*.pyc"
# Taille: 98MB, 2847 fichiers, structure complète préservée
# → Upload ce ZIP → MnemoLite extrait et indexe TOUT avec structure
```

**Acceptance Criteria**:
- [ ] Support ZIP contenant des projets complets (jusqu'à 500MB)
- [ ] Extraction côté client avec préservation COMPLÈTE de la structure
- [ ] Preview en arbre du contenu ENTIER avant import
- [ ] Reconnaissance automatique de la structure (package.json, requirements.txt, etc.)
- [ ] Filtrage intelligent même dans le ZIP
- [ ] Gestion des encodages (UTF-8, Latin-1, etc.)
- [ ] Support streaming pour gros ZIP
- [ ] Validation CRC32 pour intégrité

**Technical Implementation - ZIP avec Structure Complète**:
```javascript
async function processZipWithFullStructure(zipFile) {
  const zip = new JSZip();

  // Load avec streaming pour gros fichiers
  const contents = await zip.loadAsync(zipFile, {
    streamFiles: true,
    onProgress: (metadata) => updateProgress(metadata.percent)
  });

  // Construire l'arbre COMPLET du projet
  const projectStructure = {
    name: zipFile.name.replace('.zip', ''),
    type: 'root',
    children: {},
    stats: {
      totalFiles: 0,
      totalSize: 0,
      languages: new Set(),
      depth: 0
    }
  };

  // Parcourir TOUS les fichiers du ZIP
  for (let [fullPath, zipEntry] of Object.entries(contents.files)) {
    if (!zipEntry.dir) {
      // Reconstituer la hiérarchie complète
      const pathParts = fullPath.split('/');
      let currentLevel = projectStructure.children;

      // Créer tous les dossiers parents
      for (let i = 0; i < pathParts.length - 1; i++) {
        const folderName = pathParts[i];
        if (!currentLevel[folderName]) {
          currentLevel[folderName] = {
            name: folderName,
            type: 'folder',
            children: {},
            selected: true,
            path: pathParts.slice(0, i + 1).join('/')
          };
        }
        currentLevel = currentLevel[folderName].children;
      }

      // Ajouter le fichier avec métadonnées
      const fileName = pathParts[pathParts.length - 1];
      const language = detectLanguage(fileName);
      const shouldInclude = smartFilter.shouldInclude(fullPath);

      currentLevel[fileName] = {
        name: fileName,
        type: 'file',
        path: fullPath,
        size: zipEntry._data?.uncompressedSize || 0,
        compressed: zipEntry._data?.compressedSize || 0,
        language: language,
        selected: shouldInclude,
        zipEntry: zipEntry  // Pour extraction lazy
      };

      // Stats globales
      projectStructure.stats.totalFiles++;
      projectStructure.stats.totalSize += currentLevel[fileName].size;
      if (language) projectStructure.stats.languages.add(language);
      projectStructure.stats.depth = Math.max(projectStructure.stats.depth, pathParts.length);
    }
  }

  return projectStructure;
}

// Extraction sélective avec progress
async function extractSelectedFiles(projectStructure, selectedPaths) {
  const extractedFiles = [];
  const total = selectedPaths.length;
  let processed = 0;

  for (const path of selectedPaths) {
    const file = findFileInStructure(projectStructure, path);
    if (file?.zipEntry) {
      const content = await file.zipEntry.async('string');
      extractedFiles.push({
        path: file.path,
        content: content,
        language: file.language,
        size: file.size
      });

      processed++;
      updateProgress((processed / total) * 100);
    }
  }

  return extractedFiles;
}
```

**Preview UI pour ZIP de Projet Complet**:
```
┌──────────────────────────────────────────────────┐
│ 📦 project.zip (2,847 files, 98.5 MB)            │
│ Detected: Node.js project (package.json found)    │
├──────────────────────────────────────────────────┤
│ Project Structure:                                │
│                                                   │
│ ▼ 📁 my-awesome-project/          [✓] 2.8k files │
│   ▼ 📁 src/                       [✓] 1.2k      │
│     ▼ 📁 components/              [✓] 234       │
│       📄 Button.tsx               [✓] 12KB      │
│       📄 Modal.tsx                [✓] 8KB       │
│     ▶ 📁 services/               [✓] 156       │
│     ▶ 📁 utils/                  [✓] 89        │
│   ▼ 📁 tests/                    [?] 456       │
│   ▶ 📁 docs/                     [✓] 234       │
│   📄 package.json                [✓] 2KB       │
│   📄 README.md                   [✓] 15KB      │
│   📄 tsconfig.json               [✓] 1KB       │
│                                                   │
│ Auto-excluded (in ZIP but filtered):             │
│ ❌ node_modules/ (would be 35k files)            │
│ ❌ .git/ (would be 1.2k files)                   │
│ ❌ dist/ (would be 456 files)                    │
│                                                   │
│ Languages detected: TypeScript, JavaScript, JSON  │
│ Selected: 1,847 / 2,847 files (45.3 MB)          │
├──────────────────────────────────────────────────┤
│ [❌ Cancel]                   [🚀 Start Import]   │
└──────────────────────────────────────────────────┘
```

**Défis Spécifiques ZIP & Solutions**:
| Défi | Impact | Solution |
|------|--------|----------|
| ZIP de 500MB+ | Out of memory | Streaming extraction avec JSZip |
| Structure complexe | Perte hiérarchie | Reconstruction complète de l'arbre |
| Encodage mixte | Caractères cassés | Détection auto + conversion UTF-8 |
| ZIP corrompu | Crash | Validation CRC32 avant extraction |
| Gros fichiers dans ZIP | Blocage UI | Extraction lazy + Web Workers |

---

### Phase 2: Advanced Features (12 pts)

#### Story 3: Git Repository Import (5 pts)
**Goal**: Clone et import depuis URL Git

**Acceptance Criteria**:
- [ ] Support GitHub/GitLab/Bitbucket URLs
- [ ] Clone shallow (--depth=1)
- [ ] Branch selection
- [ ] Private repos avec token
- [ ] .gitignore respect

**API Endpoint**:
```python
POST /v1/code/import/git
{
  "url": "https://github.com/user/repo.git",
  "branch": "main",
  "token": "optional_for_private",
  "shallow": true
}
```

---

#### Story 4: Smart Filtering System (4 pts)
**Goal**: Filtrage intelligent des fichiers

**Features**:
- [ ] .gitignore parsing et respect
- [ ] Custom ignore patterns
- [ ] File size limits
- [ ] Binary file detection
- [ ] Duplicate detection
- [ ] Language auto-detection

**Configuration**:
```javascript
const filterConfig = {
  respectGitignore: true,
  maxFileSize: "10MB",
  excludePatterns: ["node_modules/**", "*.min.js"],
  includeOnly: [".py", ".js", ".ts"],
  excludeBinary: true,
  detectDuplicates: true
};
```

---

#### Story 5: Batch Processing Optimization (3 pts)
**Goal**: Traitement optimisé par batch

**Acceptance Criteria**:
- [ ] Queue de traitement avec priorités
- [ ] Chunking adaptatif (10-100 fichiers/batch)
- [ ] Parallel processing (Web Workers)
- [ ] Retry mechanism
- [ ] Partial failure handling

---

### Phase 3: UI/UX Enhancements (8 pts)

#### Story 6: Enhanced Upload UI (4 pts)
**Goal**: Interface améliorée multi-mode

**Features**:
- [ ] Tabs pour modes (Files/Folder/ZIP/Git)
- [ ] Drag & drop zone intelligente
- [ ] File tree preview
- [ ] Sélection/désélection en masse
- [ ] Search/filter dans la preview

**Mockup**:
```
┌─────────────────────────────────────┐
│ 📤 Upload Code                       │
├─────────────────────────────────────┤
│ [Files] [Folder] [ZIP] [Git] [URL]  │
├─────────────────────────────────────┤
│                                     │
│     📁 Drop folder or click         │
│        to browse                    │
│                                     │
│   ✓ Include subfolders             │
│   ✓ Respect .gitignore             │
│   □ Include tests                  │
├─────────────────────────────────────┤
│ Files to upload (247 found):       │
│ ▼ src/                   [✓]       │
│   ▼ components/          [✓]       │
│     ■ Button.tsx         [✓]       │
│     ■ Modal.tsx          [✓]       │
│   ▶ utils/              [✓]       │
│ ▶ tests/                [□]       │
└─────────────────────────────────────┘
```

---

#### Story 7: Progress & Monitoring (2 pts)
**Goal**: Feedback détaillé du progress

**Features**:
- [ ] Real-time progress par fichier
- [ ] ETA calculation
- [ ] Pause/Resume capability
- [ ] Error reporting inline
- [ ] Success/failure summary

---

#### Story 8: Bulk Operations (2 pts)
**Goal**: Opérations en masse post-upload

**Features**:
- [ ] Select all/none
- [ ] Filter by status
- [ ] Bulk retry failed
- [ ] Bulk delete
- [ ] Export results

---

## 🎯 Technical Implementation Details

### Frontend Changes

#### 1. Multi-mode Upload Component
```typescript
interface UploadMode {
  files: FileUploadHandler;
  folder: FolderUploadHandler;
  archive: ArchiveUploadHandler;
  git: GitImportHandler;
  url: URLFetchHandler;
}

class AdvancedUploader {
  private mode: keyof UploadMode;
  private filters: FilterConfig;
  private queue: UploadQueue;

  async processUpload(input: UploadInput): Promise<UploadResult> {
    const files = await this.extractFiles(input);
    const filtered = await this.applyFilters(files);
    const batches = this.createBatches(filtered);
    return await this.processBatches(batches);
  }
}
```

#### 2. File Tree Component
```typescript
interface FileTreeNode {
  name: string;
  path: string;
  type: 'file' | 'folder';
  selected: boolean;
  children?: FileTreeNode[];
  size?: number;
  language?: string;
}
```

### Backend Changes

#### 1. New Endpoints
```python
# Folder upload
POST /v1/code/upload/folder
Content-Type: multipart/form-data

# Archive upload
POST /v1/code/upload/archive
Content-Type: multipart/form-data

# Git import
POST /v1/code/import/git
{
  "url": "...",
  "branch": "main"
}

# Batch status
GET /v1/code/upload/batch/{batch_id}/status
```

#### 2. Batch Processing Service
```python
class BatchProcessingService:
    def __init__(self, concurrency: int = 5):
        self.queue = asyncio.Queue()
        self.workers = []
        self.concurrency = concurrency

    async def process_batch(
        self,
        files: List[FileInput],
        options: BatchOptions
    ) -> BatchResult:
        # Chunking
        chunks = self.create_chunks(files, options.chunk_size)

        # Queue processing
        tasks = []
        for chunk in chunks:
            task = self.queue.put(chunk)
            tasks.append(task)

        # Wait for completion
        results = await asyncio.gather(*tasks)
        return self.merge_results(results)
```

### Database Schema

```sql
-- Batch tracking
CREATE TABLE upload_batches (
    id UUID PRIMARY KEY,
    user_id UUID,
    upload_type VARCHAR(20), -- 'folder', 'archive', 'git'
    total_files INT,
    processed_files INT,
    failed_files INT,
    status VARCHAR(20), -- 'pending', 'processing', 'completed', 'failed'
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    metadata JSONB
);

-- File processing queue
CREATE TABLE file_queue (
    id UUID PRIMARY KEY,
    batch_id UUID REFERENCES upload_batches(id),
    file_path TEXT,
    status VARCHAR(20),
    error_message TEXT,
    retry_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 📈 Expected Outcomes

### Performance Metrics

| Metric | Current | Target | Improvement |
|--------|---------|--------|-------------|
| **Files per operation** | 1-10 | **10,000+** | **1000x** |
| **Time to index project** | Impossible (>1000 files) | **< 2 min** | **∞** |
| **User clicks required** | 1000+ (1 per file) | **1** | **99.9% reduction** |
| **Structure preservation** | None | **100%** | **Complete** |
| **ZIP support** | 0 | **500MB projects** | **Game changer** |
| **Folder recursion** | 0 | **Unlimited depth** | **Critical** |
| **Success rate** | 95% | **99.9%** | **Near perfect** |

### User Experience Transformation

| Scenario | Before | After |
|----------|--------|-------|
| **Upload React project (2000 files)** | "Impossible, j'abandonne" | "Glisser-déposer → 30s → Done!" |
| **Import from ZIP backup** | "Pas supporté" | "Upload ZIP → Preview → Import" |
| **Preserve folder structure** | "Tout aplati" | "Structure complète préservée" |
| **Filter unwanted files** | "Manuel file by file" | "Auto-filter + preview" |

---

## ⚠️ Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Browser memory limits | HIGH | Streaming processing, chunking |
| Large archives | MEDIUM | Size limits, server-side processing option |
| Git rate limits | LOW | Caching, token rotation |
| Network failures | MEDIUM | Resume capability, retry logic |

---

## 🚀 Implementation Roadmap

### Week 1: Foundation
- [ ] Folder upload (Story 1)
- [ ] Basic filtering (Story 4 partial)

### Week 2: Archives & Git
- [ ] ZIP support (Story 2)
- [ ] Git import (Story 3)

### Week 3: Optimization
- [ ] Batch processing (Story 5)
- [ ] Advanced filtering (Story 4 complete)

### Week 4: Polish
- [ ] Enhanced UI (Story 6)
- [ ] Progress monitoring (Story 7)
- [ ] Bulk operations (Story 8)

---

## 📊 Story Points Summary

| Phase | Stories | Points | Priority |
|-------|---------|--------|----------|
| **Phase 1** | Core Upload (2 stories) | 15 pts | CRITICAL |
| **Phase 2** | Advanced Features (3 stories) | 12 pts | HIGH |
| **Phase 3** | UI/UX (3 stories) | 8 pts | MEDIUM |
| **TOTAL** | **8 stories** | **35 pts** | **HIGH** |

---

## 🎓 Success Criteria

- [ ] Support folder upload with 1000+ files
- [ ] Support ZIP files up to 500MB
- [ ] Git import functional
- [ ] Processing time <30s for 100 files
- [ ] UI intuitive (user test score >4/5)
- [ ] 99% success rate
- [ ] Documentation complete

---

## 📝 Notes

Cette EPIC répond à un besoin **CRITIQUE** et **BLOQUANT** : sans la capacité d'uploader des projets complets (dossiers récursifs ou ZIP), MnemoLite est **inutilisable pour des vrais projets**.

### Pourquoi c'est CRITIQUE

| Sans cette EPIC | Avec cette EPIC |
|-----------------|-----------------|
| ❌ Max 10-20 fichiers réaliste | ✅ 10,000+ fichiers possible |
| ❌ Perte de structure des dossiers | ✅ Structure complète préservée |
| ❌ Import manuel fastidieux | ✅ Un clic = projet entier |
| ❌ Pas de ZIP support | ✅ ZIP de projets complets |
| ❌ Adoption limitée | ✅ Production-ready |

### Impact Business Direct

- **De 0 à Hero**: Passe de "gadget" à "outil professionnel"
- **Adoption x100**: Les développeurs peuvent VRAIMENT l'utiliser
- **Time to Value**: 30 minutes → 30 secondes pour indexer un projet

**Slogan**: "From files to forests - upload ENTIRE codebases at once!"

⚡ **Cette EPIC est LA fonctionnalité qui rend MnemoLite utilisable en production**

---

**Date**: 2025-10-17
**Version**: 1.0.0
**Status**: 🚧 **PROPOSED**
**Author**: MnemoLite Team
**Estimated Duration**: 4 weeks
**Business Value**: CRITICAL
**Technical Complexity**: MEDIUM

**Approval**: _Pending_