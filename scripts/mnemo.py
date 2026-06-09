#!/usr/bin/env python3
"""MnemoLite CLI — Python rewrite. Zero quoting bugs."""
import argparse
import json
import sys
import urllib.parse

try:
    import requests
except ImportError:
    print("Erreur: pip install requests")
    sys.exit(1)

BASE_URL = "http://localhost:8001"
TIMEOUT = 120


def api_get(path, params=None):
    """GET request, return JSON or die."""
    try:
        resp = requests.get(f"{BASE_URL}{path}", params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        die(f"API inaccessible sur {BASE_URL}")
    except requests.exceptions.Timeout:
        die("API timeout")
    except Exception as e:
        die(f"API error: {e}")


def api_request(method, path, data=None):
    """HTTP request, return JSON or die."""
    try:
        func = getattr(requests, method)
        kwargs = {"timeout": TIMEOUT}
        if data is not None:
            kwargs["json"] = data
        resp = func(f"{BASE_URL}{path}", **kwargs)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        die(f"API inaccessible sur {BASE_URL}")
    except Exception as e:
        die(f"API error: {e}")


def api_post(path, data):
    return api_request("post", path, data)


def api_put(path, data):
    return api_request("put", path, data)




def die(msg):
    print(f"❌ {msg}", file=sys.stderr)
    sys.exit(1)


def ok(msg):
    print(f"✅ {msg}")


def cmd_health(args):
    data = api_get("/readiness")
    status = data.get("status", "unknown")
    if status and status not in ("offline", "error", "down"):
        ok(f"API UP — {BASE_URL}")
        # Show DB status if available
        checks = data.get("checks", {})
        db = checks.get("database", False)
        print(f"   BDD: {'✅' if db else '❌'}")
    else:
        die(f"API status: {status}")


def cmd_search(args):
    body = {"query": args.query, "limit": args.limit}
    if args.memory_type:
        body["memory_type"] = args.memory_type
    data = api_post("/api/v1/memories/search", body)
    results = data.get("results", [])
    total = data.get("total", len(results))
    elapsed = data.get("search_time_ms", 0)

    if not results:
        print("Aucun résultat.")
        return

    print(f"\n{'═' * 60}")
    print(f"📊 {total} résultat(s) (affichés: {len(results)}) · {elapsed:.0f} ms")
    print(f"{'═' * 60}")

    for r in results:
        rid = r.get("id", "")[:8]
        ts = r.get("created_at", "")[:19]
        title = r.get("title", "(sans titre)")
        memory_type = r.get("memory_type", "?")
        score = r.get("score", 0)
        preview = (r.get("content_preview") or "")[:100]
        tags = r.get("tags", [])
        print(f"\n  [{rid}] {ts}")
        print(f"  {title}")
        print(f"  type={memory_type}  score={score:.3f}")
        if preview:
            print(f"  {preview}")
        if tags:
            tag_str = tags if isinstance(tags, str) else ", ".join(tags)
            print(f"  tags: {tag_str}")
    print()
def cmd_write(args):
    if not args.content:
        die("Usage: mnemo write --title '...' --content '...' [--tags 'a,b'] [--type note]")

    tags_list = [t.strip() for t in args.tags.split(",")] if args.tags else []

    payload = {
        "title": args.title or "(sans titre)",
        "content": args.content,
        "memory_type": args.type or "note",
        "tags": tags_list,
    }

    result = api_post("/api/v1/memories", payload)
    mid = result.get("id", "")[:8]
    ok(f"Mémoire créée: [{mid}] « {args.title or args.content[:40]}... »")

def cmd_update(args):
    payload = {}
    if args.title is not None:
        payload["title"] = args.title
    if args.content is not None:
        payload["content"] = args.content
    if args.tags is not None:
        payload["tags"] = [t.strip() for t in args.tags.split(",")] if args.tags else []
    if args.type is not None:
        payload["memory_type"] = args.type

    if not payload:
        die("Au moins un champ à modifier (--title, --content, --tags, --type)")

    result = api_put(f"/api/v1/memories/{args.id}", payload)
    mid = result.get("id", args.id)[:8]
    ok(f"Mémoire mise à jour: [{mid}]")



def cmd_memories(args):
    data = api_get("/api/v1/memories/recent", params={"limit": args.limit})
    memories = data.get("data", data.get("memories", []))
    if not memories:
        print("Aucune mémoire.")
        return
    print(f"\n{'═' * 60}")
    print(f"📋 {len(memories)} mémoires récentes")
    print(f"{'═' * 60}")
    for m in memories:
        mid = m.get("id", "")[:8]
        ts = m.get("timestamp", m.get("created_at", ""))[:19]
        title = m.get("title", m.get("content", {}).get("title", "(sans titre)"))
        mtype = m.get("memory_type", m.get("type", "?"))
        print(f"  [{mid}] {ts}  [{mtype}] {title}")
    print()


def cmd_status(args):
    print()
    ok(f"API: {BASE_URL}")

    # Health
    health = api_get("/readiness")
    checks = health.get("checks", {})
    db_ok = checks.get("database", False)
    print(f"   BDD: {'✅' if db_ok else '❌'}")

    # Stats
    try:
        resp = requests.get(f"{BASE_URL}/api/v1/memories/stats", timeout=5)
        if resp.ok:
            stats = resp.json()
            total = stats.get("total", "?")
            today = stats.get("today", "?")
            last = stats.get("last_activity", "")[:19] if stats.get("last_activity") else "?"
            print(f"   Mémoires: {total} total, {today} aujourd'hui")
            print(f"   Dernière activité: {last}")
    except Exception:
        pass

    # Projects
    try:
        resp = requests.get(f"{BASE_URL}/api/v1/projects", timeout=5)
        if resp.ok:
            projs = resp.json()
            repos = projs.get("repositories", projs.get("data", []))
            print(f"   Projets: {len(repos)}")
            for r in repos[:5]:
                name = r.get("repository", r.get("name", "?"))
                files = r.get("files_count", r.get("file_count", 0))
                print(f"     └ {name} ({files} fichiers)")
    except Exception:
        pass
    print()


def main():
    parser = argparse.ArgumentParser(description="MnemoLite CLI")
    sub = parser.add_subparsers(dest="command")

    p_health = sub.add_parser("health", help="Vérifier l'état de l'API")

    p_search = sub.add_parser("search", help="Rechercher dans les mémoires")
    p_search.add_argument("query", help="Texte à rechercher")
    p_search.add_argument("--limit", "-l", type=int, default=10, help="Nombre de résultats")
    p_search.add_argument("--type", "-t", dest="memory_type", default=None,
                       help="Filtrer par type de mémoire (note, investigation, article, quintessence, etc.)")

    p_write = sub.add_parser("write", help="Créer une mémoire")
    p_write.add_argument("--title", "-t", help="Titre")
    p_write.add_argument("--content", "-c", help="Contenu")
    p_write.add_argument("--tags", help="Tags (séparés par des virgules)")
    p_write.add_argument("--type", default="note", help="Type de mémoire (note, investigation, article, quintessence)")

    p_update = sub.add_parser("update", help="Mettre à jour une mémoire")
    p_update.add_argument("id", help="ID de la mémoire")
    p_update.add_argument("--title", "-t", help="Nouveau titre")
    p_update.add_argument("--content", "-c", help="Nouveau contenu")
    p_update.add_argument("--tags", help="Nouveaux tags (séparés par des virgules)")
    p_update.add_argument("--type", help="Nouveau type")


    p_mem = sub.add_parser("memories", help="Lister les mémoires récentes")
    p_mem.add_argument("--limit", "-l", type=int, default=10, help="Nombre")

    p_status = sub.add_parser("status", help="Statut détaillé")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "health": cmd_health,
        "search": cmd_search,
        "write": cmd_write,
        "update": cmd_update,
        "memories": cmd_memories,
        "status": cmd_status,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
