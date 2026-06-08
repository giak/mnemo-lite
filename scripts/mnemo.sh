#!/usr/bin/env bash
# ============================================================================
# mnemo — CLI wrapper for Mnemolite REST API (port 8001)
# Usage: mnemo <command> [options]
#
# Commands:
#   search <query>       Recherche hybride vectorielle dans les mémoires
#   memories [--limit N] Liste les mémoires récentes
#   write --title "..." --content "..." [--tags "a,b"] [--type note]
#                        Écrire une nouvelle mémoire
#   read <id>            Lire une mémoire par son ID
#   projects             Lister les projets indexés
#   status               État du serveur + statistiques
#   health               Health check rapide
#   code <query>         Recherche dans le code indexé (hybride)
#   events [--limit N]   Liste les événements récents
#   help                 Affiche cette aide
# ============================================================================

set -euo pipefail

API_BASE="http://localhost:8001"
CURL_OPTS="-s --connect-timeout 5 --max-time 30"

# ── Couleurs ────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

die() { echo -e "${RED}✗${NC} $*" >&2; exit 1; }
ok()  { echo -e "${GREEN}✓${NC} $*"; }
warn(){ echo -e "${YELLOW}⚠${NC} $*"; }

# ── Help ────────────────────────────────────────────────────────────────────
show_help() {
    cat <<'HELPEOF'
mnemo — CLI pour Mnemolite (REST API port 8001)

USAGE:
  mnemo <commande> [options]

COMMANDES:
  search <query>          Recherche hybride vectorielle
    --limit N               Nombre de résultats (défaut: 10)
    --type TYPE             Filtrer par type (investigation, note, etc.)
    --tag TAG               Filtrer par tag

  memories                Liste les mémoires récentes
    --limit N               Nombre max (défaut: 10)

  write                   Écrire une mémoire
    --title "..."           Titre (obligatoire)
    --content "..."         Contenu (obligatoire)
    --tags "a,b,c"          Tags séparés par des virgules
    --type TYPE             Type: note, decision, investigation (défaut: note)
    --author "..."          Auteur (défaut: freebuff)

  read <id>               Lire une mémoire par son UUID

  code <query>            Recherche dans le code indexé
    --limit N               Nombre de résultats (défaut: 10)
    --repo REPO             Filtrer par dépôt

  projects                Lister les projets indexés

  events                  Lister les événements
    --limit N               Nombre max (défaut: 10)

  status                  Statistiques du serveur + mémoires

  health                  Health check rapide

  help                    Affiche cette aide

EXEMPLES:
  mnemo search "immigration France politique"
  mnemo search "dette publique BCE" --limit 20 --type investigation
  mnemo write --title "S7 Immigration" --content "..." --tags "immigration,politique"
  mnemo code "def search_memory" --repo MnemoLite
  mnemo status
HELPEOF
}

# ── API helpers ─────────────────────────────────────────────────────────────
api_get() {
    local url="${API_BASE}$1"
    curl $CURL_OPTS "$url" 2>/dev/null || die "API inaccessible sur $API_BASE"
}

api_post() {
    local url="${API_BASE}$1"
    local data="$2"
    curl $CURL_OPTS -X POST -H 'Content-Type: application/json' -d "$data" "$url" 2>/dev/null \
        || die "API inaccessible sur $API_BASE"
}

check_api() {
    local status
    status=$(api_get "/readiness" 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','offline'))" 2>/dev/null)
    if [[ "$status" != "ok" ]]; then
        die "Mnemolite API ne répond pas sur $API_BASE — vérifie que le conteneur tourne"
    fi
}

# ── Formatters ──────────────────────────────────────────────────────────────
fmt_search_results() {
    python3 -c "
import sys, json
data = json.load(sys.stdin)
events = data.get('data', [])
meta = data.get('meta', {})
if not events:
    print('Aucun résultat.')
    sys.exit(0)
print(f'\n{"═"*60}')
print(f'📊 {meta.get("total_hits", 0)} résultat(s) (affichés: {len(events)})')
print(f'{"═"*60}')
for e in events:
    eid = e.get('id','')[:8]
    ts = e.get('timestamp','')[:19]
    content = e.get('content', {})
    title = content.get('title', content.get('text', '(sans titre)')) if isinstance(content, dict) else str(content)[:80]
    meta_tags = e.get('metadata', {})
    tags = meta_tags.get('tags', meta_tags.get('source', ''))
    print(f'\n  [{eid}] {ts}')
    print(f'  {title}')
    if tags:
        print(f'  tags: {tags}' if isinstance(tags, str) else f'  tags: {",".join(tags)}')
    print()
" 2>/dev/null || echo "(erreur de formattage)"
}

fmt_memories() {
    python3 -c "
import sys, json
data = json.load(sys.stdin)
if isinstance(data, list):
    items = data
elif isinstance(data, dict):
    items = data.get('data', data.get('results', data.get('memories', [])))
else:
    items = []
if not items:
    print('Aucune mémoire.')
    sys.exit(0)
print(f'\n{"═"*60}')
print(f'📝 {len(items)} mémoire(s)')
print(f'{"═"*60}')
for m in items:
    mid = m.get('id','')[:8]
    ts = m.get('created_at', m.get('timestamp',''))[:19]
    title = m.get('title', '(sans titre)')
    mtype = m.get('memory_type', m.get('type', '?'))
    tags = m.get('tags', [])
    author = m.get('author', '')
    tag_str = f' [{", ".join(tags)}]' if tags else ''
    auth_str = f' par {author}' if author else ''
    print(f'\n  [{mid}] {ts}  {title}{tag_str} ({mtype}){auth_str}')
    if m.get('content_preview'):
        print(f'  {m["content_preview"][:120]}...')
    print()
" 2>/dev/null || echo "(erreur de formattage)"
}

fmt_projects() {
    python3 -c "
import sys, json
data = json.load(sys.stdin)
repos = data.get('repositories', data.get('data', data if isinstance(data, list) else []))
if not repos:
    print('Aucun projet indexé.')
    sys.exit(0)
print(f'\n{"═"*60}')
print(f'📦 Projets indexés: {len(repos)}')
print(f'{"═"*60}')
for r in repos:
    name = r.get('repository', r.get('name', '?'))
    files = r.get('files_count', r.get('file_count', 0))
    chunks = r.get('chunks_count', r.get('chunk_count', 0))
    lang = r.get('languages', r.get('language', ''))
    last = r.get('last_indexed', 'jamais')[:19]
    print(f'\n  📁 {name}')
    print(f'     fichiers: {files}  |  chunks: {chunks}  |  lang: {lang}')
    print(f'     dernière indexation: {last}')
    print()
" 2>/dev/null || echo "(erreur de formattage)"
}

# ── Commands ────────────────────────────────────────────────────────────────
cmd_search() {
    local query="" limit=10
    while [[ \$# -gt 0 ]]; do
        case "\$1" in
            --limit) shift; limit="\$1" ;;
            --type|--tag) shift ;;
            *) query="\$query \$1" ;;
        esac
        shift
    done
    query="\$(echo "\$query" | xargs)"
    [[ -z "\$query" ]] && die "Usage: mnemo search <query> [--limit N]"
    check_api
    ok "Recherche: « \$query »"
    api_get "/v1/search/?vector_query=\$(python3 -c "import urllib.parse; print(urllib.parse.quote('\$query'))")&limit=\$limit" | fmt_search_results
}

cmd_memories() {
    local limit=10
    [[ "\${1:-}" == "--limit" ]] && limit="\$2"
    check_api
    api_get "/api/v1/memories/recent?limit=\$limit" | fmt_memories
}

cmd_write() {
    local title="" content="" tags="" mtype="note" author="freebuff"
    while [[ \$# -gt 0 ]]; do
        case "\$1" in
            --title) shift; title="\$1" ;;
            --content) shift; content="\$1" ;;
            --tags) shift; tags="\$1" ;;
            --type) shift; mtype="\$1" ;;
            --author) shift; author="\$1" ;;
        esac
        shift
    done
    [[ -z "\$title" ]] && die "Usage: mnemo write --title '...' --content '...' [--tags 'a,b'] [--type note]"
    [[ -z "\$content" ]] && die "Le contenu est obligatoire"
    check_api

    local tag_array="[]"
    [[ -n "\$tags" ]] && tag_array='["'"\$(echo "\$tags" | sed 's/,/" ,"/g')"'"']'

    local payload
    payload=\$(python3 -c "
import json
p = {
    'title': '$title',
    'content': '''$content''',
    'memory_type': '$mtype',
    'tags': $tag_array,
    'author': '$author'
}
print(json.dumps(p))
" 2>/dev/null)

    local result
    result=\$(api_post "/api/v1/memories" "\$payload" 2>/dev/null)
    local mid
    mid=\$(echo "\$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id','')[:8])" 2>/dev/null)
    ok "Mémoire créée: [\$mid] « \$title »"
}

cmd_read() {
    local eid="\${1:-}"
    [[ -z "\$eid" ]] && die "Usage: mnemo read <uuid>"
    check_api
    api_get "/v1/events/\$eid" | python3 -m json.tool 2>/dev/null || die "Mémoire introuvable"
}

cmd_code() {
    local query="" limit=10 repo=""
    while [[ \$# -gt 0 ]]; do
        case "\$1" in
            --limit) shift; limit="\$1" ;;
            --repo) shift; repo="\$1" ;;
            *) query="\$query \$1" ;;
        esac
        shift
    done
    query="\$(echo "\$query" | xargs)"
    [[ -z "\$query" ]] && die "Usage: mnemo code <query> [--limit N] [--repo REPO]"
    check_api

    local filters="null"
    [[ -n "\$repo" ]] && filters='{"repository":"'"\$repo"'"}'

    local payload
    payload=\$(python3 -c "
import json
p = {
    'query': '$query',
    'top_k': $limit,
    'enable_lexical': True,
    'enable_vector': True,
    'filters': $filters
}
print(json.dumps(p))
")

    echo -e "\n\${CYAN}🔍 Recherche code: « \$query »\${NC}"
    api_post "/v1/code/search" "\$payload" | python3 -c "
import sys, json
data = json.load(sys.stdin)
results = data.get('results', [])
meta = data.get('metadata', {})
if not results:
    print('Aucun résultat.')
    sys.exit(0)
print(f'\n{"═"*60}')
print(f'📄 {meta.get("total_results", len(results))} résultat(s) en {meta.get("execution_time_ms",0)}ms')
print(f'{"═"*60}')
for r in results[:$limit]:
    f = r.get('file_path','')
    n = r.get('name','')
    s = r.get('source_code','')[:200]
    sc = r.get('rrf_score',0)
    print(f'\n  📍 {f}:{n}  (score: {sc:.3f})')
    print(f'  {s}')
    print()
" 2>/dev/null
}

cmd_projects() {
    check_api
    api_get "/api/v1/projects" | fmt_projects
}

cmd_events() {
    local limit=10
    [[ "\${1:-}" == "--limit" ]] && limit="\$2"
    check_api
    api_get "/v1/search/?limit=\$limit" | fmt_search_results
}

cmd_status() {
    check_api
    echo ""
    ok "API: \$API_BASE"

    local health
    health=\$(api_get "/readiness" 2>/dev/null)
    echo -e "   \$(echo "\$health" | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'BDD: {\"✅\" if d.get(\"checks\",{}).get(\"database\") else \"❌\"}')" 2>/dev/null)"

    local stats
    stats=\$(api_get "/api/v1/memories/stats" 2>/dev/null)
    echo -e "   \$(echo "\$stats" | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(f'Mémoires: {d.get(\"total\",\"?\")} total, {d.get(\"today\",\"?\")} aujourd\'hui')
if d.get('last_activity'):
    print(f'Dernière activité: {d[\"last_activity\"][:19]}')
" 2>/dev/null)"

    local projs
    projs=\$(api_get "/api/v1/projects" 2>/dev/null | python3 -c "
import sys,json; d=json.load(sys.stdin)
repos=d.get('repositories',d.get('data',[]))
print(f'Projets: {len(repos)}')
for r in repos[:5]:
    n=r.get('repository',r.get('name','?'));f=r.get('files_count',r.get('file_count',0))
    print(f'  └ {n} ({f} fichiers)')
" 2>/dev/null)
    echo "   \$projs"
    echo ""
}

# ── Main ────────────────────────────────────────────────────────────────────
main() {
    local cmd="\${1:-help}"
    shift 2>/dev/null || true

    case "\$cmd" in
        search)     cmd_search "\$@" ;;
        memories)   cmd_memories "\$@" ;;
        write)      cmd_write "\$@" ;;
        read)       cmd_read "\$@" ;;
        code)       cmd_code "\$@" ;;
        projects)   cmd_projects "\$@" ;;
        events)     cmd_events "\$@" ;;
        status|stats) cmd_status "\$@" ;;
        health)
            curl \$CURL_OPTS "\${API_BASE}/readiness" 2>/dev/null | python3 -m json.tool 2>/dev/null \
                || die "API inaccessible"
            ;;
        help|--help|-h) show_help ;;
        *) die "Commande inconnue: \$cmd\nUtilise 'mnemo help' pour voir les commandes disponibles." ;;
    esac
}

main "\$@"
