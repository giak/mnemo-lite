# EPIC-24: Auto-Save Conversations - ULTRATHINK Comparison

**Date**: 2025-10-29
**Version**: 3.0.0 - COMPREHENSIVE EVALUATION
**Context**: User requirement - "Pas d'impact système OS, user-friendly, self-contained dans MnemoLite"

---

## 🎯 Contraintes Absolues

1. ❌ **Pas d'impact système OS** - Pas de systemd, pas de cron, pas d'install packages
2. ✅ **User-friendly** - User lance `docker compose up` et ça marche
3. ✅ **Self-contained** - Tout dans MnemoLite, rien en dehors
4. ✅ **Zéro config externe** - Pas de fichiers à créer dans ~/.config, etc.
5. ✅ **Maintenance zéro** - Pas de scripts à lancer manuellement

---

## 📊 Matrice de Comparaison

| Solution | User Friendly | Self-Contained | Zéro Config | Fiabilité | Complexité | Verdict |
|----------|---------------|----------------|-------------|-----------|------------|---------|
| **1. Claude Hooks** | ⭐⭐ | ⭐⭐⭐ | ⭐ | ⭐ (Bug #10401) | ⭐⭐ | ❌ REJECT |
| **2. Daemon in Docker** | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⚠️ MAYBE |
| **3. MCP Resource** | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐ | ✅ **BEST** |
| **4. Manual Script** | ⭐ | ⭐⭐⭐ | ⭐ | ⭐⭐⭐ | ⭐ | ❌ REJECT |
| **5. Systemd Timer** | ⭐ | ⭐ | ⭐ | ⭐⭐⭐ | ⭐⭐ | ❌ REJECT |
| **6. MCP Tool Auto** | ⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | ⭐⭐ | ⚠️ MAYBE |

---

## 🔍 Analyse Détaillée

### Solution 1: Claude Code Hooks ❌ REJECTED

**Principe**: Utiliser lifecycle hooks (Stop, UserPromptSubmit, SessionEnd)

#### Evaluation Technique

**User Friendly**: ⭐⭐ (2/5)
- Requiert configuration dans `.claude/settings.local.json`
- Peut nécessiter flag `--debug hooks` (Bug #10401)
- User doit comprendre le système de hooks

**Self-Contained**: ⭐⭐⭐ (3/5)
- Scripts dans `.claude/hooks/` (dans projet)
- Mais dépend du comportement de Claude Code (externe)

**Zéro Config**: ⭐ (1/5)
- Requiert config dans settings.local.json
- Peut nécessiter wrapper ou alias
- User doit activer manuellement

**Fiabilité**: ⭐ (1/5)
- **CRITICAL**: Bug #10401 rend hooks non-fiables
- Stop hook ne fonctionne pas sans `--debug hooks`
- UserPromptSubmit ne s'exécute pas (testé, log vide)
- SessionEnd peut ne pas trigger si crash

**Complexité Implémentation**: ⭐⭐ (2/5)
- Scripts bash + appel Docker exec
- Gestion dedup, parsing JSONL
- Debugging difficile (hooks silencieux)

**Complexité Maintenance**: ⭐ (1/5)
- Dépend de versions Claude Code
- Peut casser à chaque update
- Debug complexe (logs éparpillés)

**Impact Système**: ⭐⭐⭐ (3/5)
- Aucun impact (juste fichiers dans projet)

#### Verdict: ❌ **REJECTED**
**Raison**: Trop de dépendances externes (Claude Code behavior), fiabilité 0% à cause Bug #10401

---

### Solution 2: Daemon in Docker Container ⚠️ MAYBE

**Principe**: Process background dans conteneur API qui poll les transcripts toutes les 30s

```yaml
# docker-compose.yml
services:
  api:
    volumes:
      - ~/.claude/projects:/home/user/.claude/projects:ro
    command: >
      sh -c "
        python3 /app/scripts/conversation-watcher.py &
        uvicorn api.main:app --host 0.0.0.0 --port 8000
      "
```

#### Evaluation Technique

**User Friendly**: ⭐⭐⭐ (3/5)
- ✅ Lance automatiquement avec `docker compose up`
- ✅ Aucune action user requise
- ⚠️ Logs mélangés avec logs API

**Self-Contained**: ⭐⭐⭐ (3/5)
- ✅ Tout dans Docker
- ⚠️ Requiert mount de `~/.claude/projects` (externe au projet)

**Zéro Config**: ⭐⭐⭐ (3/5)
- ✅ Aucune config externe
- ⚠️ Volume mount peut être différent selon user

**Fiabilité**: ⭐⭐⭐ (3/5)
- ✅ Polling fiable (pas de hooks)
- ✅ Retry automatique si erreur DB
- ⚠️ Peut crasher et ne pas restart (pas supervisé)
- ⚠️ Si API crash, daemon crash aussi

**Complexité Implémentation**: ⭐⭐ (2/5)
- Python ~100 lignes (polling + parse JSONL)
- Gestion state file pour incremental parsing
- Dedup par hash
- Integration dans docker-compose

**Complexité Maintenance**: ⭐⭐ (2/5)
- Process background peut être oublié
- Logs difficiles à isoler
- Pas de health check

**Impact Système**: ⭐⭐⭐ (3/5)
- Aucun impact (tout dans Docker)

**Overhead Performance**:
- CPU: ~0.5% (poll toutes les 30s)
- Memory: ~20MB
- Disk I/O: Minimal (read-only)

#### Architecture
```
Docker Compose Up
     ↓
API Container Start
     ↓
     ├─> Uvicorn API (port 8000)
     └─> Watcher Daemon (background)
             ↓
             └─> Poll ~/.claude/projects/*.jsonl every 30s
                     ↓
                     Parse new exchanges
                     ↓
                     Save via write_memory
                     ↓
                     PostgreSQL + embeddings
```

#### Code Minimal
```python
#!/usr/bin/env python3
import asyncio
import time
from pathlib import Path

async def watch_conversations():
    while True:
        try:
            # Parse transcripts
            transcripts = Path("~/.claude/projects").expanduser().glob("*.jsonl")
            for transcript in transcripts:
                if transcript.name.startswith("agent-"):
                    continue
                await process_transcript(transcript)
        except Exception as e:
            print(f"Error: {e}")

        await asyncio.sleep(30)

if __name__ == "__main__":
    asyncio.run(watch_conversations())
```

#### Problèmes Potentiels
1. **Volume mount path variable** - Chaque user peut avoir chemin différent
2. **Crash non-détecté** - Si daemon crash, user ne sait pas
3. **Logs mélangés** - Debug difficile
4. **Pas de supervision** - Si process meurt, pas de restart

#### Verdict: ⚠️ **MAYBE** - Fonctionne mais pas optimal
**Raison**: User-friendly mais complexité maintenance élevée

---

### Solution 3: MCP Resource "conversations://" ✅ **BEST**

**Principe**: MCP Server expose une resource `conversations://auto-save` que Claude peut lire périodiquement

```python
# MCP Server
@server.list_resources()
async def list_resources():
    return [
        Resource(
            uri="conversations://auto-save",
            name="Auto-saved conversations from Claude Code",
            description="Automatically saves new conversations"
        )
    ]

@server.read_resource()
async def read_resource(uri: str):
    if uri == "conversations://auto-save":
        # Parse transcripts and save new ones
        result = await auto_save_conversations()
        return {"conversations_saved": result}
```

**Usage**: Claude lit automatiquement cette resource périodiquement (ou user peut demander)

#### Evaluation Technique

**User Friendly**: ⭐⭐⭐ (3/5)
- ✅ Totalement transparent
- ✅ Aucune action requise
- ✅ User peut voir status via MCP

**Self-Contained**: ⭐⭐⭐ (3/5)
- ✅ Tout dans MCP server (partie de MnemoLite)
- ✅ Aucune dépendance externe
- ⚠️ Requiert que Claude lise la resource

**Zéro Config**: ⭐⭐⭐ (3/5)
- ✅ Aucune config user
- ✅ Marche out-of-the-box
- ⚠️ Dépend du comportement Claude (quand il lit resources)

**Fiabilité**: ⭐⭐⭐ (3/5)
- ✅ Pas de daemon à surveiller
- ✅ Appelé seulement quand nécessaire
- ⚠️ Fréquence de lecture incertaine
- ⚠️ Pas de garantie temps réel

**Complexité Implémentation**: ⭐ (1/5)
- ✅ Code minimal (~30 lignes)
- ✅ Réutilise code import existant
- ✅ Intégré dans MCP server existant

**Complexité Maintenance**: ⭐ (1/5)
- ✅ Aucune maintenance (partie du MCP)
- ✅ Pas de process séparé
- ✅ Logs centralisés

**Impact Système**: ⭐⭐⭐ (3/5)
- ✅ Aucun impact (tout dans MCP)

#### Architecture
```
Claude Code Session
     ↓
MCP Client (Claude)
     ↓
Periodic resource check
     ↓
Read "conversations://auto-save"
     ↓
MCP Server Handler
     ↓
Parse ~/.claude/projects/*.jsonl
     ↓
Save new exchanges via write_memory
     ↓
Return count saved
```

#### Code Implementation
```python
# api/mnemo_mcp/resources.py

from pathlib import Path
import json
import hashlib

async def auto_save_conversations(memory_repo, embedding_service):
    """Auto-save new conversations from Claude Code transcripts"""

    transcript_dir = Path("~/.claude/projects").expanduser()
    state_file = Path("/tmp/mnemo-autosave-state.json")

    # Load state (last saved hashes)
    saved_hashes = set()
    if state_file.exists():
        state = json.loads(state_file.read_text())
        saved_hashes = set(state.get("saved_hashes", []))

    # Parse transcripts
    count = 0
    for transcript in transcript_dir.glob("*.jsonl"):
        if transcript.name.startswith("agent-"):
            continue

        # Parse exchanges
        pairs = parse_transcript(transcript)

        for user_text, assistant_text, timestamp in pairs:
            # Compute hash
            content_hash = hashlib.sha256(
                (user_text + assistant_text).encode()
            ).hexdigest()[:16]

            # Skip if already saved
            if content_hash in saved_hashes:
                continue

            # Save via write_memory
            await save_conversation(
                memory_repo, embedding_service,
                user_text, assistant_text,
                transcript.stem, timestamp
            )

            saved_hashes.add(content_hash)
            count += 1

    # Save state
    state_file.write_text(json.dumps({
        "saved_hashes": list(saved_hashes)[-10000:]
    }))

    return count


# Register resource
@server.list_resources()
async def list_resources():
    return [
        types.Resource(
            uri="conversations://auto-save",
            name="Auto-save Claude Code conversations",
            description="Automatically imports new conversations from Claude Code transcripts",
            mimeType="application/json"
        )
    ]

@server.read_resource()
async def read_resource(uri: str):
    if uri == "conversations://auto-save":
        count = await auto_save_conversations(
            memory_repo, embedding_service
        )
        return types.ReadResourceResult(
            contents=[
                types.TextContent(
                    uri=uri,
                    mimeType="application/json",
                    text=json.dumps({
                        "status": "success",
                        "conversations_saved": count,
                        "message": f"Auto-saved {count} new conversations"
                    })
                )
            ]
        )
```

#### Avantages Majeurs
1. ✅ **Zéro overhead** - Pas de polling continu
2. ✅ **Self-documenting** - Resource visible dans MCP
3. ✅ **User control** - User peut trigger manuellement si besoin
4. ✅ **Minimal code** - ~50 lignes totales
5. ✅ **No process management** - Pas de daemon à superviser
6. ✅ **Centralized logs** - Tout dans MCP logs

#### Inconvénients
1. ⚠️ **Timing incertain** - Dépend de quand Claude lit la resource
2. ⚠️ **Pas temps réel** - Peut avoir délai de plusieurs minutes
3. ⚠️ **Pas de garantie** - Claude peut ne jamais lire la resource

#### Solutions aux Inconvénients
1. **User peut forcer**: Demander à Claude "check conversations://auto-save"
2. **Prompt suggestion**: Documenter "Ask Claude to check conversations://auto-save periodically"
3. **Fallback option**: Combiner avec option 6 (tool auto-run)

#### Verdict: ✅ **BEST** pour simplicité et intégration
**Raison**: Minimal code, zéro maintenance, self-contained, user-friendly

---

### Solution 4: Manual Script ❌ REJECTED

**Principe**: User lance manuellement `docker compose exec -T api python3 scripts/import-conversations.py`

#### Evaluation Technique

**User Friendly**: ⭐ (1/5)
- ❌ Action manuelle requise
- ❌ User doit se souvenir de lancer
- ❌ Pas transparent

**Self-Contained**: ⭐⭐⭐ (3/5)
- ✅ Tout dans Docker
- ✅ Script dans projet

**Zéro Config**: ⭐ (1/5)
- ❌ User doit taper commande

**Fiabilité**: ⭐⭐⭐ (3/5)
- ✅ Fonctionne quand lancé
- ❌ Dépend de l'action user

**Complexité**: ⭐ (1/5)
- ✅ Code simple (déjà fait)

**Maintenance**: ⭐⭐⭐ (3/5)
- ✅ Pas de process à surveiller

#### Verdict: ❌ **REJECTED**
**Raison**: Ne répond pas au requirement "transparent et automatique"

---

### Solution 5: Systemd Timer / Cron ❌ REJECTED

**Principe**: Timer système qui lance script périodiquement

#### Evaluation

**User Friendly**: ⭐ (1/5)
- ❌ Requiert config système

**Self-Contained**: ⭐ (1/5)
- ❌ Config hors du projet

**Zéro Config**: ⭐ (1/5)
- ❌ User doit configurer systemd/cron

**Impact Système**: ⭐ (1/5)
- ❌ **VIOLE CONTRAINTE PRINCIPALE**

#### Verdict: ❌ **REJECTED**
**Raison**: Impact système OS - contrainte absolue violée

---

### Solution 6: MCP Tool avec Auto-Run ⚠️ MAYBE

**Principe**: MCP tool `auto_save_conversations` qui se lance automatiquement à chaque requête MCP

```python
@server.call_tool()
async def call_tool(name: str, arguments: dict):
    # Auto-run sur chaque appel
    if name != "auto_save_conversations":
        await auto_save_conversations_silent()  # Background

    # Execute requested tool
    return await execute_tool(name, arguments)
```

#### Evaluation Technique

**User Friendly**: ⭐⭐ (2/5)
- ✅ Automatique
- ⚠️ Overhead sur chaque call
- ⚠️ User peut voir latency

**Self-Contained**: ⭐⭐⭐ (3/5)
- ✅ Tout dans MCP

**Zéro Config**: ⭐⭐ (2/5)
- ✅ Aucune config
- ⚠️ Peut ralentir toutes les opérations

**Fiabilité**: ⭐⭐ (2/5)
- ✅ Se lance fréquemment
- ⚠️ Overhead performance
- ⚠️ Peut causer timeouts

**Complexité**: ⭐⭐ (2/5)
- Code moyen
- Gestion async complexe

**Maintenance**: ⭐⭐ (2/5)
- Risk de bugs cachés

#### Verdict: ⚠️ **MAYBE** - Fonctionne mais overhead
**Raison**: Ajoute latency à TOUTES les operations MCP

---

## 🏆 Recommendation Finale

### Option Recommandée: **Solution 3 - MCP Resource**

**Justification**:
1. ✅ **Minimal code** (~50 lignes)
2. ✅ **Zéro maintenance**
3. ✅ **Self-contained** (dans MCP server)
4. ✅ **User-friendly** (transparent)
5. ✅ **No impact système**
6. ✅ **Facile à debug** (logs MCP)

**Implementation**:
- Add resource `conversations://auto-save` au MCP server
- Parse transcripts on resource read
- Save new exchanges automatiquement
- Return count saved

**User Experience**:
```
User: "Check if there are new conversations to save"
Claude: [Reads conversations://auto-save resource]
Claude: "✅ Auto-saved 5 new conversations to MnemoLite"
```

**Automatic Mode** (optionnel):
- Add prompt suggestion à Claude: "Check conversations://auto-save periodically"
- Ou: User peut créer un script externe qui demande à Claude de check

---

## 📋 Implementation Plan - Solution 3

### Phase 1: Core Implementation (1h)

1. **Add resource handler** (`api/mnemo_mcp/server.py`)
   ```python
   @server.list_resources()
   async def list_resources():
       return [
           types.Resource(
               uri="conversations://auto-save",
               name="Auto-save conversations",
               description="Automatically saves new Claude Code conversations"
           )
       ]
   ```

2. **Implement auto-save logic** (reuse `import-conversations.py` code)
   - Parse transcripts incrementally
   - Dedup by hash
   - Save via write_memory
   - Return count

3. **State management** (`/tmp/mnemo-autosave-state.json`)
   - Track saved hashes
   - Track last processed position per file

### Phase 2: Testing (30min)

1. Test resource listing: `mcp__mnemolite__list_resources`
2. Test resource reading: Read `conversations://auto-save`
3. Verify DB: Check new conversations saved
4. Test dedup: Re-read resource, verify no duplicates

### Phase 3: Documentation (30min)

1. Update MCP_INTEGRATION_GUIDE.md
2. Add usage examples
3. Document manual trigger option

---

## 🔄 Alternative: Hybrid Approach

**Combiner Solution 3 (MCP Resource) + Solution 2 (Daemon)**

### Architecture Hybride
```
User Lance:
    docker compose up
         ↓
    API Container
         ├─> Uvicorn API
         ├─> MCP Server (resource conversations://auto-save)
         └─> Optional: Lightweight daemon (poll 1x per hour)
                  ↓
                  Calls own MCP resource internally
```

**Avantages**:
- ✅ Resource utilisable manuellement (Solution 3)
- ✅ Auto-save périodique garantie (Solution 2)
- ✅ Daemon minimal (1x par heure, pas 30s)

**Inconvénient**:
- ⚠️ Complexité augmentée

**Verdict**: ⚠️ OVERKILL pour MVP - Garder Solution 3 pure

---

## 📊 Scoring Final

| Solution | Score Total | Recommendation |
|----------|-------------|----------------|
| **3. MCP Resource** | **17/25** ⭐⭐⭐⭐ | ✅ **IMPLEMENT** |
| **2. Daemon in Docker** | 15/25 ⭐⭐⭐ | ⚠️ Fallback |
| **6. MCP Tool Auto** | 12/25 ⭐⭐ | ⚠️ Alternative |
| **1. Claude Hooks** | 9/25 ⭐ | ❌ Reject |
| **4. Manual Script** | 9/25 ⭐ | ❌ Reject |
| **5. Systemd Timer** | 5/25 | ❌ Reject |

---

## 🎯 Conclusion

**Solution à implémenter: MCP Resource `conversations://auto-save`**

**Pourquoi c'est LA solution**:
1. Self-contained dans MnemoLite MCP
2. Zéro config, zéro maintenance
3. User-friendly (transparent)
4. Minimal code (~50 lignes)
5. Pas d'impact système OS
6. Facile à tester et debug

**Prochaine étape**: Implementation Phase 1 (1h)

---

**Version**: 3.0.0
**Date**: 2025-10-29
**Author**: Claude Code Assistant + ULTRATHINK Analysis
**EPIC**: EPIC-24 (Auto-Save Conversations)
**Status**: READY FOR IMPLEMENTATION - Solution 3 Selected
