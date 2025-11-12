#!/usr/bin/env python3
"""
One-time import of historical conversations from Claude Code transcripts.
Runs inside Docker container with access to mounted .claude/projects.

EPIC-24 Task 6: AUTOIMPORT One-Time Historical Import
"""
import requests
import sys
from datetime import datetime


def import_historical():
    """Run one-time import via API."""
    print("=" * 70)
    print("         HISTORICAL CONVERSATIONS IMPORT")
    print("=" * 70)
    print()
    print("⚠️  This is a ONE-TIME import of historical Claude Code conversations")
    print("   Future conversations will be saved automatically via auto-save queue")
    print()
    print("Starting import from /host/.claude/projects...")
    print()

    # Call import endpoint
    try:
        response = requests.post(
            "http://localhost:8000/v1/conversations/import",
            json={"projects_dir": "/host/.claude/projects"},
            timeout=600  # 10 minutes (536 transcripts may take a while)
        )

        if response.status_code == 200:
            data = response.json()
            print()
            print("=" * 70)
            print("✅ IMPORT COMPLETED SUCCESSFULLY")
            print("=" * 70)
            print()
            print(f"   📥 Imported:  {data.get('imported', 0)} conversations")
            print(f"   ⏭️  Skipped:   {data.get('skipped', 0)} (duplicates)")
            print()
            if 'message' in data:
                print(f"   📝 Message: {data['message']}")
                print()
            print("=" * 70)
            print()
            print("✨ Historical data is now available in MnemoLite!")
            print("   Future conversations will be saved automatically via auto-save queue.")
            print("   This import endpoint is now DEPRECATED and will be removed in v2.0.")
            print()
            return 0
        else:
            print()
            print("=" * 70)
            print(f"❌ IMPORT FAILED: HTTP {response.status_code}")
            print("=" * 70)
            print()
            print("Response:")
            print(response.text)
            print()
            return 1

    except requests.exceptions.Timeout:
        print()
        print("=" * 70)
        print("❌ IMPORT TIMEOUT")
        print("=" * 70)
        print()
        print("The import took too long (>10 minutes).")
        print("This may happen with very large transcript collections.")
        print("Try running the import again or check API logs for errors.")
        print()
        return 1

    except requests.exceptions.ConnectionError:
        print()
        print("=" * 70)
        print("❌ CONNECTION ERROR")
        print("=" * 70)
        print()
        print("Could not connect to API at http://localhost:8000")
        print("Make sure the API container is running:")
        print("  docker compose ps api")
        print()
        return 1

    except Exception as e:
        print()
        print("=" * 70)
        print(f"❌ UNEXPECTED ERROR")
        print("=" * 70)
        print()
        print(f"Error: {e}")
        print()
        return 1


if __name__ == "__main__":
    sys.exit(import_historical())
