"""
Routes pour le monitoring de l'auto-save des conversations.
EPIC-24: Auto-Save Conversations - UI/UX Monitoring
"""

import logging
from datetime import datetime
from typing import Dict, Any, List
from pathlib import Path
import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy import text

from dependencies import get_db_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/autosave", tags=["autosave-monitoring"])


@router.get("/stats")
async def get_autosave_stats(
    engine: AsyncEngine = Depends(get_db_engine)
) -> Dict[str, Any]:
    """Statistiques globales de l'auto-save."""
    try:
        async with engine.begin() as conn:
            # Total
            result = await conn.execute(text("SELECT COUNT(*) FROM memories WHERE author = 'AutoImport'"))
            total = result.scalar() or 0

            # 24h
            result = await conn.execute(text("SELECT COUNT(*) FROM memories WHERE author = 'AutoImport' AND created_at > NOW() - INTERVAL '24 hours'"))
            last_24h = result.scalar() or 0

            # 7d
            result = await conn.execute(text("SELECT COUNT(*) FROM memories WHERE author = 'AutoImport' AND created_at > NOW() - INTERVAL '7 days'"))
            last_7d = result.scalar() or 0

            # 30d
            result = await conn.execute(text("SELECT COUNT(*) FROM memories WHERE author = 'AutoImport' AND created_at > NOW() - INTERVAL '30 days'"))
            last_30d = result.scalar() or 0

            # Embeddings
            result = await conn.execute(text("SELECT COUNT(*) FROM memories WHERE author = 'AutoImport' AND embedding IS NOT NULL"))
            with_embeddings = result.scalar() or 0

            # Last import
            result = await conn.execute(text("SELECT MAX(created_at) FROM memories WHERE author = 'AutoImport'"))
            last_import = result.scalar()

        return {
            "total_conversations": total,
            "last_24_hours": last_24h,
            "last_7_days": last_7d,
            "last_30_days": last_30d,
            "with_embeddings": with_embeddings,
            "embedding_coverage_pct": round((with_embeddings / total * 100) if total > 0 else 0, 1),
            "unique_sessions": 0,  # Simplified
            "last_import_at": last_import.isoformat() if last_import else None,
            "last_import_ago": str(datetime.now() - last_import.replace(tzinfo=None)) if last_import else None,
        }
    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        raise


@router.get("/timeline")
async def get_import_timeline(
    days: int = 7,
    engine: AsyncEngine = Depends(get_db_engine)
) -> List[Dict[str, Any]]:
    """Timeline des importations par jour."""
    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text(f"""
                    SELECT DATE(created_at) as import_date, COUNT(*) as count
                    FROM memories
                    WHERE author = 'AutoImport' AND created_at > NOW() - INTERVAL '{days} days'
                    GROUP BY DATE(created_at)
                    ORDER BY import_date DESC
                """)
            )

            return [{"date": str(row.import_date), "count": row.count} for row in result]
    except Exception as e:
        logger.error(f"Error fetching timeline: {e}")
        raise


@router.get("/recent")
async def get_recent_conversations(
    limit: int = 10,
    engine: AsyncEngine = Depends(get_db_engine)
) -> List[Dict[str, Any]]:
    """Conversations récemment importées."""
    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT id, title, LEFT(content, 200) as preview, tags, created_at
                    FROM memories
                    WHERE author = 'AutoImport'
                    ORDER BY created_at DESC
                    LIMIT :limit
                """),
                {"limit": limit}
            )

            conversations = []
            for row in result:
                conversations.append({
                    "id": str(row.id),
                    "title": row.title,
                    "preview": row.preview + "..." if len(row.preview) == 200 else row.preview,
                    "tags": row.tags,
                    "created_at": row.created_at.isoformat(),
                    "created_ago": str(datetime.now() - row.created_at.replace(tzinfo=None))
                })

            return conversations
    except Exception as e:
        logger.error(f"Error fetching recent: {e}")
        raise


@router.get("/daemon-status")
async def get_daemon_status() -> Dict[str, Any]:
    """Statut du daemon d'auto-import."""
    try:
        state_file = Path("/tmp/mnemo-conversations-state.json")

        if state_file.exists():
            stat = state_file.stat()
            last_activity = datetime.fromtimestamp(stat.st_mtime)
            state = json.loads(state_file.read_text())

            return {
                "status": "running",
                "state_file_exists": True,
                "last_activity": last_activity.isoformat(),
                "last_activity_ago": str(datetime.now() - last_activity),
                "saved_hashes_count": len(state.get("saved_hashes", [])),
                "last_import": state.get("last_import"),
            }
        else:
            return {
                "status": "unknown",
                "state_file_exists": False,
                "message": "State file not found"
            }
    except Exception as e:
        logger.error(f"Error checking daemon: {e}")
        return {"status": "error", "error": str(e)}


@router.get("/health")
async def daemon_health_check(
    engine: AsyncEngine = Depends(get_db_engine)
) -> Dict[str, Any]:
    """
    Health check complet du système auto-save.
    Multi-step validation pour Docker healthcheck.
    Returns 200 si OK, 503 si critical.
    """
    import time

    issues = []
    status = "healthy"

    # 1. Check daemon heartbeat
    heartbeat_file = Path("/tmp/daemon-heartbeat.txt")
    heartbeat_age = None

    if heartbeat_file.exists():
        try:
            last_beat = int(heartbeat_file.read_text().strip())
            heartbeat_age = int(time.time() - last_beat)

            if heartbeat_age > 120:  # 2 minutes
                issues.append(f"Daemon heartbeat stale ({heartbeat_age}s)")
                status = "unhealthy"
            elif heartbeat_age > 60:  # 1 minute
                issues.append(f"Daemon heartbeat old ({heartbeat_age}s)")
                status = "degraded"
        except Exception as e:
            issues.append(f"Failed to read heartbeat: {e}")
            status = "critical"
    else:
        issues.append("Daemon heartbeat file missing")
        status = "critical"

    # 2. Check daemon metrics
    metrics_file = Path("/tmp/daemon-metrics.json")
    metrics = None

    if metrics_file.exists():
        try:
            metrics = json.loads(metrics_file.read_text())

            if metrics.get("consecutive_failures", 0) >= 5:
                issues.append(f"High failure rate: {metrics['consecutive_failures']}")
                status = "degraded" if status == "healthy" else status

            if metrics.get("status") == "critical":
                issues.append("Daemon reports critical status")
                status = "critical"
        except Exception as e:
            issues.append(f"Failed to read metrics: {e}")

    # 3. Check recent imports (last 10 minutes)
    last_import_age = None

    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("""
                SELECT MAX(created_at) FROM memories WHERE author = 'AutoImport'
            """))
            last_import = result.scalar()

            if last_import:
                last_import_age = int((datetime.now() - last_import.replace(tzinfo=None)).total_seconds())

                if last_import_age > 600:  # 10 minutes
                    issues.append(f"No imports in last {last_import_age}s")
                    status = "degraded" if status == "healthy" else status
    except Exception as e:
        issues.append(f"Database check failed: {e}")
        status = "critical"

    # 4. Build response
    response = {
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "daemon": {
            "heartbeat_age_seconds": heartbeat_age,
            "metrics": metrics,
            "last_import_age_seconds": last_import_age
        },
        "issues": issues
    }

    # Return 503 if critical (triggers Docker unhealthy)
    if status == "critical":
        raise HTTPException(status_code=503, detail=response)

    return response


@router.get("/conversation/{conversation_id}")
async def get_conversation_content(
    conversation_id: str,
    engine: AsyncEngine = Depends(get_db_engine)
) -> Dict[str, Any]:
    """Récupère le contenu complet d'une conversation."""
    try:
        async with engine.begin() as conn:
            result = await conn.execute(
                text("""
                    SELECT id, title, content, tags, created_at
                    FROM memories
                    WHERE id = :id AND author = 'AutoImport'
                """),
                {"id": conversation_id}
            )

            row = result.first()
            if not row:
                return {"error": "Conversation not found"}

            return {
                "id": str(row.id),
                "title": row.title,
                "content": row.content,
                "tags": row.tags,
                "created_at": row.created_at.isoformat(),
            }
    except Exception as e:
        logger.error(f"Error fetching conversation {conversation_id}: {e}")
        raise
