# EPIC-24: Auto-Save Conversations - Architecture ULTRATHINK

**Date**: 2025-10-29
**Version**: 2.0.0
**Status**: CRITICAL REDESIGN - Hooks Approach Failed

---

## 🎯 Objectif Final

**Sauvegarder 100% des conversations Claude Code automatiquement et de manière transparente dans MnemoLite PostgreSQL + pgvector.**

### Critères de Succès (Non-Négociables)

✅ **Automatique** - Aucune action manuelle requise
✅ **Transparent** - User ne voit rien, ne fait rien
✅ **Fiable** - 99.9%+ des échanges capturés
✅ **Temps réel** - Sauvegarde dans les secondes qui suivent l'échange
✅ **Pas de dépendances** - Utilise uniquement MnemoLite MCP tools
✅ **Démarrage auto** - Fonctionne dès le boot système

---

## 📊 Comparaison des Architectures

### Option 1: Claude Code Hooks ❌ REJECTED

**Principe**: Utiliser les lifecycle hooks (Stop, UserPromptSubmit) de Claude Code

#### Variante 1.A: Stop Hook
```bash
# .claude/hooks/Stop/auto-save.sh
# S'exécute APRÈS chaque réponse de Claude
```

**Avantages**:
- ✅ Timing parfait (après réponse complète)
- ✅ Accès natif au transcript_path
- ✅ Intégré dans le workflow Claude Code

**Inconvénients**:
- ❌ **BUG #10401**: Requiert `--debug hooks` flag (régression v2.0.27+)
- ❌ Pas fiable si Claude lancé depuis menu/launcher
- ❌ User doit configurer alias/wrapper
- ❌ Peut échouer silencieusement

**Verdict**: ❌ **NON FIABLE** - Dépend d'un bug ouvert, pas de timeline de fix

---

#### Variante 1.B: UserPromptSubmit Hook
```bash
# .claude/hooks/UserPromptSubmit/auto-save-previous.sh
# S'exécute AVANT chaque nouvelle question user
# Sauvegarde l'échange N-1 (précédent)
```

**Avantages**:
- ✅ Fonctionne SANS `--debug hooks` (contrairement à Stop)
- ✅ Accès natif au transcript_path
- ✅ Déjà testé et prouvé fonctionnel (messages "UserPromptSubmit hook success")

**Inconvénients**:
- ❌ Ne sauvegarde PAS le dernier échange (timing N-1)
- ❌ Dépend quand même du mécanisme de hooks (peut casser)
- ❌ Testé manuellement mais ne s'exécute pas automatiquement en session réelle

**Verdict**: ⚠️ **PARTIELLEMENT FIABLE** - Meilleur que Stop, mais incomplet

---

### Option 2: File Watcher (inotify/watchdog) ✅ RECOMMENDED

**Principe**: Daemon qui surveille `~/.claude/projects/*.jsonl` et détecte les modifications en temps réel

```python
# Pseudo-code
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class TranscriptWatcher(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path.endswith('.jsonl'):
            new_exchanges = parse_new_lines(event.src_path)
            for exchange in new_exchanges:
                save_to_mnemolite(exchange)
```

**Architecture**:
```
~/.claude/projects/*.jsonl (append)
        ↓ (inotify IN_MODIFY event)
Python Daemon (background)
        ↓ (parse JSONL)
Extract new user+assistant pairs
        ↓ (hash-based dedup)
MnemoLite write_memory tool
        ↓
PostgreSQL + embeddings 768D
```

**Avantages**:
- ✅ **100% indépendant** des hooks Claude Code
- ✅ **Ne dépend PAS** du Bug #10401
- ✅ **Temps réel** (inotify < 100ms latency)
- ✅ **Capture TOUT** - même le dernier échange
- ✅ **Démarrage auto** (systemd user service)
- ✅ **Robuste** - technologie éprouvée (inotify depuis Linux 2.6)
- ✅ **Logging** complet pour debugging
- ✅ **Redémarrage auto** si crash

**Inconvénients**:
- ⚠️ Besoin d'un daemon background (mais géré par systemd)
- ⚠️ Dépendance: `watchdog` Python package (ou inotify natif)
- ⚠️ Doit parser JSONL (mais déjà fait dans import script)

**Complexité**: Medium (1 fichier Python ~200 lignes + 1 fichier systemd)

**Verdict**: ✅ **SOLUTION ROBUSTE ET PÉRENNE** - Architecture recommandée

---

### Option 3: Polling Périodique ⚠️ FALLBACK

**Principe**: Cron/systemd timer qui vérifie les transcripts toutes les N secondes

```bash
# systemd timer: Toutes les 30 secondes
[Timer]
OnBootSec=30s
OnUnitActiveSec=30s
```

**Avantages**:
- ✅ Ultra simple (réutilise import-conversations.py)
- ✅ Pas de dépendance externe (juste cron ou systemd timer)
- ✅ 100% indépendant des hooks

**Inconvénients**:
- ❌ Délai de sauvegarde (30s-60s)
- ❌ Moins performant (parse complet à chaque run)
- ❌ Pas "temps réel"

**Verdict**: ⚠️ **FALLBACK SIMPLE** - Si file watcher trop complexe

---

### Option 4: Hybrid (UserPromptSubmit + File Watcher) ⭐ BEST COVERAGE

**Principe**: Combiner UserPromptSubmit hook (temps réel N-1) + File Watcher (capture 100%)

```
UserPromptSubmit Hook
        ↓
Sauvegarde échange N-1 (temps réel)
        +
File Watcher Daemon
        ↓
Capture TOUS les échanges (including last)
        ↓
Deduplication (hash)
        ↓
Résultat: 100% coverage + temps réel
```

**Avantages**:
- ✅ **Meilleur des deux mondes**
- ✅ 100% coverage (file watcher)
- ✅ Temps réel (hook)
- ✅ Redondance (si hook fail, watcher catch)

**Inconvénients**:
- ⚠️ Plus complexe (2 systèmes)
- ⚠️ Dedup critique (éviter doublons)

**Verdict**: ⭐ **BEST OVERALL** - Si ressources disponibles

---

## 🏆 Décision Finale: File Watcher (Option 2)

### Justification

1. **Indépendance totale** - Ne dépend PAS des bugs Claude Code
2. **Fiabilité prouvée** - inotify/watchdog utilisé en production depuis des années
3. **100% coverage** - Capture même le dernier échange
4. **Simplicité relative** - 1 daemon Python + 1 service systemd
5. **Maintenance** - Code stable, pas de dépendance sur API Claude Code interne

### Upgrade Path vers Hybrid

Si besoin d'optimisation future:
1. Phase 1: File Watcher (MVP - 100% coverage)
2. Phase 2: Add UserPromptSubmit hook (latency optimization)
3. Phase 3: Monitoring metrics (sauvegarde rate, latency, dedup rate)

---

## 🛠️ Implémentation File Watcher

### Architecture Détaillée

```
┌─────────────────────────────────────────────────────────────┐
│                    USER WORKSPACE                            │
│  ~/.claude/projects/-home-giak-Work-MnemoLite/*.jsonl       │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ inotify IN_MODIFY
                         │
┌────────────────────────▼────────────────────────────────────┐
│              DAEMON: conversation-watcher.py                 │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ TranscriptEventHandler                               │  │
│  │  - on_modified(event)                                │  │
│  │  - parse_new_exchanges()                             │  │
│  │  - compute_hash()                                    │  │
│  │  - check_dedup()                                     │  │
│  └──────────────────────┬───────────────────────────────┘  │
│                         │                                    │
│                         ▼                                    │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ MnemoLite Integration                                │  │
│  │  - WriteMemoryTool                                   │  │
│  │  - MemoryRepository                                  │  │
│  │  - MockEmbeddingService (768D)                       │  │
│  └──────────────────────┬───────────────────────────────┘  │
└─────────────────────────┼────────────────────────────────────┘
                         │
                         │ docker exec OR direct psql
                         │
┌────────────────────────▼────────────────────────────────────┐
│              DOCKER: MnemoLite Stack                         │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │ PostgreSQL 18.1 + pgvector                           │  │
│  │  - memories table                                    │  │
│  │  - embedding vector(768)                             │  │
│  └──────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

### Components

#### 1. Daemon Python (`scripts/conversation-watcher.py`)

**Responsabilités**:
- Surveiller `~/.claude/projects/-home-giak-Work-MnemoLite/*.jsonl`
- Détecter modifications (append de nouvelles lignes)
- Parser JSONL pour extraire user+assistant pairs
- Deduplication par hash SHA256
- Sauvegarder via MnemoLite MCP write_memory
- Logging structuré (info, errors, metrics)
- Gestion erreurs et retry logic

**Technologies**:
- `watchdog` library (ou `inotify` via `pyinotify`)
- `asyncio` pour performance
- `structlog` pour logging
- MnemoLite MCP tools (WriteMemoryTool)

**Performance Target**:
- Latency: < 500ms entre écriture et sauvegarde
- CPU: < 1% idle, < 5% pendant parsing
- Memory: < 50MB
- Disk I/O: Minimal (read-only JSONL tail)

#### 2. Systemd User Service (`~/.config/systemd/user/conversation-watcher.service`)

**Responsabilités**:
- Démarrage auto au login
- Redémarrage auto si crash
- Logging via journald
- Contrôle via systemctl --user

**Configuration**:
```ini
[Unit]
Description=MnemoLite Conversation Auto-Saver
After=network.target docker.service

[Service]
Type=simple
ExecStart=/usr/bin/python3 /home/giak/Work/MnemoLite/scripts/conversation-watcher.py
Restart=always
RestartSec=10s
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
```

#### 3. State Management (`/tmp/mnemo-watcher-state.json`)

**Contenu**:
- Last processed position pour chaque transcript file
- Hashes des échanges déjà sauvés (dedup)
- Timestamp last successful save
- Error count & last error message

**Format**:
```json
{
  "transcripts": {
    "5906b2a1-cbd9-4d97-bc2b-81445d816ebe.jsonl": {
      "last_position": 125000,
      "last_saved_hash": "a3f4d89e2c1b5f6a",
      "last_save_timestamp": "2025-10-29T08:30:45Z",
      "exchange_count": 47
    }
  },
  "saved_hashes": ["a3f4d89e...", "b2e8c71f...", ...],
  "stats": {
    "total_saved": 152,
    "total_errors": 0,
    "uptime_seconds": 3600
  }
}
```

---

## 📋 Plan d'Implémentation

### Phase 1: MVP File Watcher (2-3h)

1. ✅ Créer `scripts/conversation-watcher.py` (200 lignes)
   - Watchdog observer pour `~/.claude/projects/*.jsonl`
   - Parser JSONL (réutiliser code de import-conversations.py)
   - Dedup par hash
   - Sauver via write_memory

2. ✅ Créer systemd service
   - `~/.config/systemd/user/conversation-watcher.service`
   - Enable & start
   - Test logging via journalctl

3. ✅ Tests validation
   - Lancer Claude Code
   - Faire 3-5 échanges
   - Vérifier DB: nouveaux records avec author="AutoSave"
   - Vérifier logs: aucun error

### Phase 2: Robustesse (1h)

4. ✅ Gestion erreurs
   - Try/catch sur parse JSONL
   - Retry logic sur DB errors (max 3 attempts)
   - Log errors mais ne crash pas

5. ✅ State persistence
   - Sauver position dans state file
   - Reprendre depuis last position au restart
   - Éviter re-processing de vieux échanges

### Phase 3: Monitoring (1h)

6. ✅ Metrics & health check
   - Endpoint `/health` (ou log periodic stats)
   - Count: exchanges saved per minute
   - Alert si > 5min sans sauvegarde (conversation active mais pas saved)

7. ✅ Documentation
   - README avec installation steps
   - Troubleshooting guide
   - Architecture diagram

---

## 🧪 Plan de Test

### Test 1: Basic Functionality
```bash
# Terminal 1: Watch logs
journalctl --user -u conversation-watcher -f

# Terminal 2: Start daemon
systemctl --user start conversation-watcher

# Terminal 3: Claude Code session
claude
# Faire 3 échanges

# Vérifier DB
docker compose exec -T db psql -U mnemo -d mnemolite -c "
SELECT COUNT(*) FROM memories
WHERE author = 'AutoSave'
AND created_at > NOW() - INTERVAL '5 minutes';"
```

**Expected**: 3 nouveaux records en DB

---

### Test 2: Deduplication
```bash
# Restart daemon (re-parse transcripts)
systemctl --user restart conversation-watcher

# Vérifier DB count unchanged
```

**Expected**: Aucun doublon créé

---

### Test 3: Crash Recovery
```bash
# Kill daemon
systemctl --user stop conversation-watcher

# Faire 2 échanges dans Claude Code

# Restart daemon
systemctl --user start conversation-watcher

# Wait 10s, check DB
```

**Expected**: Les 2 échanges sauvegardés après restart

---

### Test 4: Performance
```bash
# Session avec 20+ échanges rapides
# Mesurer: temps entre échange et sauvegarde DB
```

**Expected**: < 1s latency en moyenne

---

## 📊 Success Metrics

### Objectifs Quantitatifs

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Coverage** | 99.9%+ | Count DB / Count JSONL |
| **Latency** | < 1s p50, < 3s p99 | Timestamp diff |
| **Reliability** | 30 jours uptime | systemd status |
| **CPU Usage** | < 1% idle | top/htop |
| **Memory** | < 50MB | ps aux |
| **Errors** | < 0.1% | Error logs |

### Validation Continue

```bash
# Daily check (cron)
0 9 * * * /home/giak/Work/MnemoLite/scripts/verify-autosave-health.sh
```

Script vérifie:
- ✅ Daemon running
- ✅ Au moins 1 sauvegarde dans dernières 24h
- ✅ Pas d'errors dans logs
- ✅ State file updated récemment

---

## 🚀 Upgrade Path Future

### Phase 4: Hybrid Architecture (Optionnel)

Si besoin d'optimiser latency:

1. Garder file watcher (100% coverage)
2. Ajouter UserPromptSubmit hook (instant save N-1)
3. Dedup automatique évite doublons
4. Résultat: < 100ms latency + 100% coverage

### Phase 5: Semantic Search Integration

Une fois auto-save 100% fiable:

1. MCP tool `search_conversations`
2. Semantic search sur embeddings 768D
3. UI: voir conversations similaires
4. RAG: context injection automatique

---

## 📝 Documentation Users

### Installation (3 commandes)

```bash
# 1. Enable systemd service
systemctl --user enable conversation-watcher.service

# 2. Start service
systemctl --user start conversation-watcher.service

# 3. Verify running
systemctl --user status conversation-watcher.service
```

**That's it!** Toutes les conversations sont maintenant sauvegardées automatiquement.

### Vérification

```bash
# Voir logs en temps réel
journalctl --user -u conversation-watcher -f

# Compter conversations sauvegardées aujourd'hui
docker compose exec -T db psql -U mnemo -d mnemolite -c "
SELECT COUNT(*) FROM memories
WHERE author = 'AutoSave'
AND DATE(created_at) = CURRENT_DATE;"
```

### Troubleshooting

| Problème | Solution |
|----------|----------|
| Service not running | `systemctl --user restart conversation-watcher` |
| Pas de nouvelles sauvegardes | Check logs: `journalctl --user -u conversation-watcher --since "5 minutes ago"` |
| Errors DB connection | Verify Docker: `docker compose ps` |
| High CPU usage | Check file watcher pattern: devrait surveiller seulement `*.jsonl` |

---

## 🎯 Conclusion

**Architecture FILE WATCHER = Solution robuste et pérenne**

### Pourquoi c'est LA solution:

1. ✅ **Indépendant des bugs Claude Code** (pas de dépendance sur hooks)
2. ✅ **100% coverage** (capture même le dernier échange)
3. ✅ **Temps réel** (< 1s latency)
4. ✅ **Auto-start** (systemd)
5. ✅ **Robuste** (technologie éprouvée)
6. ✅ **Simple à maintenir** (1 fichier Python + 1 service systemd)

### Prochaine Étape

Implémenter Phase 1 (MVP) - ETA: 2-3h

---

**Version**: 2.0.0
**Date**: 2025-10-29
**Author**: Claude Code Assistant
**EPIC**: EPIC-24 (Auto-Save Conversations)
**Status**: READY FOR IMPLEMENTATION
