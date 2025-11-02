#!/usr/bin/env python3
"""
Clean up test repositories from database.

Usage:
    # List test repositories
    python scripts/cleanup_test_repos.py --list

    # Clean all test repositories (interactive)
    python scripts/cleanup_test_repos.py --clean

    # Clean all test repositories (no confirmation)
    python scripts/cleanup_test_repos.py --clean --force

    # Keep specific repositories
    python scripts/cleanup_test_repos.py --clean --keep code_test_clean,MnemoLite
"""

import asyncio
import argparse
import os
import sys
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# Add api to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'api'))


async def list_repositories(db_url: str):
    """List all repositories in database."""
    engine = create_async_engine(db_url)

    async with engine.begin() as conn:
        # Get repositories from chunks
        chunks = await conn.execute(text('''
            SELECT repository, COUNT(*) as chunk_count
            FROM code_chunks
            GROUP BY repository
            ORDER BY repository
        '''))

        repos_chunks = {row.repository: row.chunk_count for row in chunks}

        # Get repositories from nodes
        nodes = await conn.execute(text('''
            SELECT properties->>'repository' as repo, COUNT(*) as node_count
            FROM nodes
            WHERE properties->>'repository' IS NOT NULL
            GROUP BY properties->>'repository'
            ORDER BY properties->>'repository'
        '''))

        repos_nodes = {row.repo: row.node_count for row in nodes}

    await engine.dispose()

    # Merge both lists
    all_repos = set(repos_chunks.keys()) | set(repos_nodes.keys())

    return {
        repo: {
            'chunks': repos_chunks.get(repo, 0),
            'nodes': repos_nodes.get(repo, 0)
        }
        for repo in all_repos
    }


def identify_test_repos(repos: dict, keep: set = None) -> list:
    """Identify test repositories based on naming patterns."""
    keep = keep or set()

    test_patterns = [
        'test_',
        'parallel_test_',
        'embeddings-test',
        'epic18-stress-test',
        'semantic-search-demo',
        'realistic_typescript_test',
    ]

    test_repos = []
    for repo in repos.keys():
        # Skip if in keep list
        if repo in keep:
            continue

        # Check if matches test pattern
        if any(repo.startswith(pattern) for pattern in test_patterns):
            test_repos.append(repo)
        elif 'test' in repo.lower() and repo not in keep:
            test_repos.append(repo)

    return sorted(test_repos)


async def clean_repository(repository: str, db_url: str):
    """Remove all data for a repository."""
    engine = create_async_engine(db_url)

    async with engine.begin() as conn:
        # Delete chunks
        result = await conn.execute(
            text("DELETE FROM code_chunks WHERE repository = :repo"),
            {"repo": repository}
        )
        chunks_deleted = result.rowcount

        # Delete nodes (edges cascade delete automatically)
        result = await conn.execute(
            text("DELETE FROM nodes WHERE properties->>'repository' = :repo"),
            {"repo": repository}
        )
        nodes_deleted = result.rowcount

    await engine.dispose()

    return chunks_deleted, nodes_deleted


async def clean_test_repositories(db_url: str, keep: set, force: bool = False):
    """Clean all test repositories."""
    # List all repositories
    repos = await list_repositories(db_url)

    # Identify test repos
    test_repos = identify_test_repos(repos, keep)

    if not test_repos:
        print("✅ No test repositories found to clean.")
        return

    # Show what will be deleted
    print(f"\n🗑️  Found {len(test_repos)} test repositories to clean:\n")
    total_chunks = 0
    total_nodes = 0

    for repo in test_repos:
        chunks = repos[repo]['chunks']
        nodes = repos[repo]['nodes']
        total_chunks += chunks
        total_nodes += nodes
        print(f"  • {repo}: {chunks} chunks, {nodes} nodes")

    print(f"\n📊 Total: {total_chunks} chunks, {total_nodes} nodes")

    # Confirm deletion
    if not force:
        response = input(f"\n⚠️  Delete all {len(test_repos)} test repositories? (yes/no): ")
        if response.lower() != 'yes':
            print("❌ Cancelled.")
            return

    # Delete repositories
    print("\n🧹 Cleaning repositories...")
    deleted_chunks = 0
    deleted_nodes = 0

    for repo in test_repos:
        chunks, nodes = await clean_repository(repo, db_url)
        deleted_chunks += chunks
        deleted_nodes += nodes
        print(f"  ✓ {repo}: deleted {chunks} chunks, {nodes} nodes")

    print(f"\n✅ Cleanup complete!")
    print(f"   Deleted {deleted_chunks} chunks")
    print(f"   Deleted {deleted_nodes} nodes")
    print(f"   Cleaned {len(test_repos)} repositories")


async def list_command(db_url: str):
    """List all repositories."""
    repos = await list_repositories(db_url)

    print("\n=== ALL REPOSITORIES ===\n")

    for repo in sorted(repos.keys()):
        chunks = repos[repo]['chunks']
        nodes = repos[repo]['nodes']
        marker = "🧪" if any(p in repo.lower() for p in ['test', 'demo']) else "📦"
        print(f"{marker} {repo}: {chunks} chunks, {nodes} nodes")

    print(f"\n📊 Total: {len(repos)} repositories")


def main():
    parser = argparse.ArgumentParser(
        description="Clean up test repositories from database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all repositories
  python scripts/cleanup_test_repos.py --list

  # Clean test repositories interactively
  python scripts/cleanup_test_repos.py --clean

  # Clean without confirmation
  python scripts/cleanup_test_repos.py --clean --force

  # Keep specific repositories
  python scripts/cleanup_test_repos.py --clean --keep code_test_clean,MnemoLite
        """
    )

    parser.add_argument("--list", action="store_true", help="List all repositories")
    parser.add_argument("--clean", action="store_true", help="Clean test repositories")
    parser.add_argument("--force", action="store_true", help="Clean without confirmation")
    parser.add_argument("--keep", help="Comma-separated list of repositories to keep")
    parser.add_argument("--db-url", help="Database URL (default: from env)")

    args = parser.parse_args()

    db_url = args.db_url or os.getenv("DATABASE_URL")
    if not db_url:
        print("❌ ERROR: DATABASE_URL not set")
        sys.exit(1)

    # Parse keep list
    keep = set()
    if args.keep:
        keep = set(args.keep.split(','))

    # Default keep list (important repositories)
    keep.update(['code_test_clean', 'MnemoLite'])

    # Execute command
    if args.list:
        asyncio.run(list_command(db_url))
    elif args.clean:
        asyncio.run(clean_test_repositories(db_url, keep, args.force))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
