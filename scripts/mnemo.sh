#!/bin/bash
# mnemo — CLI for MnemoLite REST API
# Usage: mnemo <command> [options]
#
# Commands:
#   search <query>       Search memories (semantic hybrid)
#   write  <title> <content>  Create a new memory
#   get    <id>          Get memory by ID
#   stats                Show memory statistics
#
# Environment:
#   MNEMO_API  Base URL (default: http://127.0.0.1:8001)

set -euo pipefail

API="${MNEMO_API:-http://127.0.0.1:8001}"

usage() {
    cat <<EOF
mnemo — CLI for MnemoLite

Usage:
  mnemo search <query> [--type TYPE] [--tags t1,t2] [--limit N] [--format json|table]
  mnemo write  <title> <content> [--type TYPE] [--tags t1,t2] [--author NAME]
  mnemo get    <memory_id> [--format json|table]
  mnemo update <id> [--title T] [--content C] [--type TYPE] [--tags t1,t2]
  mnemo delete <id> [--permanent]
  mnemo stats

Commands:
  search   Semantic search on memories (hybrid lexical + vector)
  write    Create a new memory with auto-generated embedding
  get      Retrieve a memory by UUID
  update   Update an existing memory (partial)
  delete   Delete a memory (soft by default, hard with --permanent)
  stats    Show memory statistics

Options:
  --type       Memory type: note, decision, task, reference, conversation, investigation
  --limit      Max results (default: 10)
  --tags       Comma-separated tags (AND filter for search, replace for update/write)
  --author     Author name
  --format     Output format: json or table (default: table)
  --permanent  Hard delete (irreversible)

Environment:
  MNEMO_API  Base URL (default: http://127.0.0.1:8001)
EOF
    exit 1
}

die() { echo "Error: $*" >&2; exit 1; }

check_deps() {
    command -v curl >/dev/null 2>&1 || die "curl is required"
    command -v jq   >/dev/null 2>&1 || die "jq is required"
}

# ── search ──────────────────────────────────────────────────────────────────
cmd_search() {
    local query="" type="" tags="" limit=10 fmt="table"
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --type)   type="$2";   shift 2 ;;
            --tags)   tags="$2";   shift 2 ;;
            --limit)  limit="$2";  shift 2 ;;
            --format) fmt="$2";    shift 2 ;;
            *)        query="$1";  shift ;;
        esac
    done
    [[ -z "$query" ]] && die "Usage: mnemo search <query> [--type TYPE] [--tags t1,t2] [--limit N]"

    local tags_json="[]"
    if [[ -n "$tags" ]]; then
        tags_json=$(echo "$tags" | tr ',' '\n' | jq -R . | jq -s .)
    fi

    local body
    body=$(jq -n \
        --arg q "$query" \
        --arg t "$type" \
        --argjson l "$limit" \
        --argjson tags "$tags_json" \
        '{query: $q, limit: $l, tags: $tags} + (if $t != "" then {memory_type: $t} else {} end)')

    local resp
    resp=$(curl -s -X POST "${API}/api/v1/memories/search" \
        -H "Content-Type: application/json" \
        -d "$body")

    if [[ "$fmt" == "json" ]]; then
        echo "$resp" | jq -c '.'
    else
        echo "$resp" | jq -r '
            .results[] |
            [
                .score,
                .memory_type,
                .title,
                (.content_preview // "" | .[0:80]),
                .id
            ] | @tsv
        ' | column -t -s $'\t' | head -n "$limit"
        echo "---"
        echo "$resp" | jq -r '"\(.total) results in \(.search_time_ms)ms"'
    fi
}

# ── write ───────────────────────────────────────────────────────────────────
cmd_write() {
    local title="" content="" type="note" tags="" author="" fmt="table"
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --type)   type="$2";   shift 2 ;;
            --tags)   tags="$2";   shift 2 ;;
            --author) author="$2"; shift 2 ;;
            --format) fmt="$2";    shift 2 ;;
            *)
                if [[ -z "$title" ]]; then
                    title="$1"
                elif [[ -z "$content" ]]; then
                    content="$1"
                else
                    content="$content $1"
                fi
                shift
                ;;
        esac
    done
    [[ -z "$title" ]]   && die "Usage: mnemo write <title> <content> [--type TYPE] [--tags t1,t2]"
    [[ -z "$content" ]] && die "Usage: mnemo write <title> <content> [--type TYPE] [--tags t1,t2]"

    # Build tags array
    local tags_json="[]"
    if [[ -n "$tags" ]]; then
        tags_json=$(echo "$tags" | tr ',' '\n' | jq -R . | jq -s .)
    fi

    local body
    body=$(jq -n \
        --arg title "$title" \
        --arg content "$content" \
        --arg type "$type" \
        --arg author "$author" \
        --argjson tags "$tags_json" \
        '{
            title: $title,
            content: $content,
            memory_type: $type,
            tags: $tags
        } + (if $author != "" then {author: $author} else {} end)')

    local resp
    resp=$(curl -s -X POST "${API}/api/v1/memories" \
        -H "Content-Type: application/json" \
        -d "$body")

    if echo "$resp" | jq -e '.id' >/dev/null 2>&1; then
        if [[ "$fmt" == "json" ]]; then
            echo "$resp" | jq -c '.'
        else
            echo "✓ Created: $(echo "$resp" | jq -r '.id')"
            echo "  Title:   $(echo "$resp" | jq -r '.title')"
            echo "  Type:    $(echo "$resp" | jq -r '.memory_type')"
        fi
    else
        echo "$resp" | jq . >&2
        exit 1
    fi
}

# ── get ─────────────────────────────────────────────────────────────────────
cmd_get() {
    local id="" fmt="table"
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --format) fmt="$2"; shift 2 ;;
            *)        id="$1";  shift ;;
        esac
    done
    [[ -z "$id" ]] && die "Usage: mnemo get <memory_id> [--format json|table]"

    local resp
    resp=$(curl -s "${API}/api/v1/memories/${id}")

    if echo "$resp" | jq -e '.id' >/dev/null 2>&1; then
        if [[ "$fmt" == "json" ]]; then
            echo "$resp" | jq -c '.'
        else
            echo "ID:      $(echo "$resp" | jq -r '.id')"
            echo "Title:   $(echo "$resp" | jq -r '.title')"
            echo "Type:    $(echo "$resp" | jq -r '.memory_type')"
            echo "Author:  $(echo "$resp" | jq -r '.author // "—"')"
            echo "Created: $(echo "$resp" | jq -r '.created_at')"
            echo "Tags:    $(echo "$resp" | jq -r '.tags | join(", ")')"
            echo "---"
            echo "$resp" | jq -r '.content'
        fi
    else
        echo "$resp" | jq . >&2
        exit 1
    fi
}

# ── stats ───────────────────────────────────────────────────────────────────
cmd_stats() {
    local resp
    resp=$(curl -s "${API}/api/v1/memories/stats")
    echo "$resp" | jq .
}

# ── update ──────────────────────────────────────────────────────────────────
cmd_update() {
    local id="" title="" content="" type="" tags="" author=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --title)   title="$2";   shift 2 ;;
            --content) content="$2"; shift 2 ;;
            --type)    type="$2";    shift 2 ;;
            --tags)    tags="$2";    shift 2 ;;
            --author)  author="$2";  shift 2 ;;
            *)         id="$1";     shift ;;
        esac
    done
    [[ -z "$id" ]] && die "Usage: mnemo update <id> [--title T] [--content C] [--type TYPE] [--tags t1,t2]"

    local body="{}"
    [[ -n "$title" ]]   && body=$(echo "$body" | jq --arg v "$title"   '. + {title: $v}')
    [[ -n "$content" ]] && body=$(echo "$body" | jq --arg v "$content" '. + {content: $v}')
    [[ -n "$type" ]]    && body=$(echo "$body" | jq --arg v "$type"    '. + {memory_type: $v}')
    [[ -n "$author" ]]  && body=$(echo "$body" | jq --arg v "$author"  '. + {author: $v}')
    if [[ -n "$tags" ]]; then
        local tags_json
        tags_json=$(echo "$tags" | tr ',' '\n' | jq -R . | jq -s .)
        body=$(echo "$body" | jq --argjson v "$tags_json" '. + {tags: $v}')
    fi

    local resp
    resp=$(curl -s -X PUT "${API}/api/v1/memories/${id}" \
        -H "Content-Type: application/json" \
        -d "$body")

    if echo "$resp" | jq -e '.id' >/dev/null 2>&1; then
        echo "✓ Updated: $(echo "$resp" | jq -r '.id')"
    else
        echo "$resp" | jq . >&2
        exit 1
    fi
}

# ── delete ──────────────────────────────────────────────────────────────────
cmd_delete() {
    local id="" permanent=false
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --permanent) permanent=true; shift ;;
            *)           id="$1";       shift ;;
        esac
    done
    [[ -z "$id" ]] && die "Usage: mnemo delete <id> [--permanent]"

    local url="${API}/api/v1/memories/${id}"
    [[ "$permanent" == "true" ]] && url="${url}?permanent=true"

    local resp
    resp=$(curl -s -X DELETE "$url")

    if echo "$resp" | jq -e '.deleted' >/dev/null 2>&1; then
        echo "✓ Deleted: $(echo "$resp" | jq -r '.id')"
        echo "$resp" | jq -r 'if .permanent then "  (permanent)" else "  (soft, can restore)" end'
    else
        echo "$resp" | jq . >&2
        exit 1
    fi
}

# ── main ────────────────────────────────────────────────────────────────────
main() {
    check_deps

    [[ $# -lt 1 ]] && usage
    local cmd="$1"; shift

    case "$cmd" in
        search) cmd_search "$@" ;;
        write)  cmd_write  "$@" ;;
        get)    cmd_get    "$@" ;;
        update) cmd_update "$@" ;;
        delete) cmd_delete "$@" ;;
        stats)  cmd_stats  "$@" ;;
        -h|--help|help) usage ;;
        *) die "Unknown command: $cmd (try: mnemo --help)" ;;
    esac
}

main "$@"
