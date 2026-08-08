"""
Explorer Routes — API endpoints for the Knowledge Explorer (EPIC-78).

Endpoints pour consulter le socle Truth Engine : agrégats, arborescence
par sujet, et relations par proxy de tags partagés.

Toutes les requêtes sont en SQL direct (pattern cohérent avec
memory_graph_routes.py), sans service dédié : KISS, robuste, zéro
pipeline d'extraction à réparer.
"""
import logging
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.sql import text

from dependencies import get_db_engine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/memories", tags=["explorer"])

@router.get("/explorer/stats")
async def get_explorer_stats(
    project_id: Optional[str] = Query(None, description="Project_id optionnel. Par défaut : tout le socle (tous projets, conversations exclues)."),
    include_conversations: bool = Query(False, description="Inclure les conversations (bruit) dans les compteurs"),
    engine: AsyncEngine = Depends(get_db_engine),
) -> Dict[str, Any]:
    """Agrégats du socle : distribution par type, top sujets, statuts, timeline.

    Le socle par défaut = tout sauf conversation (les 33k conversations
    sont du bruit). Les faits vérifiés récents (status:CONFIRME) sont
    écrits sans project_id : on les capture donc par défaut.
    """
    try:
        def _scope(alias: str = "m") -> str:
            conds = [f"{alias}.deleted_at IS NULL"]
            if project_id:
                conds.append(f"{alias}.project_id = :pid")
            if not include_conversations:
                conds.append(f"{alias}.memory_type != 'conversation'")
            return " AND ".join(conds)

        params = {"pid": project_id} if project_id else {}

        type_query = text(f"""
            SELECT memory_type, count(*) AS n
            FROM memories m
            WHERE {_scope()}
            GROUP BY memory_type
            ORDER BY n DESC
        """)
        status_query = text(f"""
            SELECT
                count(*) FILTER (WHERE 'status:CONFIRME' = ANY(tags)) AS confirmed,
                count(*) FILTER (WHERE 'fact-check' = ANY(tags)) AS fact_checked,
                count(*) AS total
            FROM memories m
            WHERE {_scope()}
        """)
        # Top sujets : tags porteurs de sens, hors bruit technique (tags de
        # version t1-t9/v7-v8/v15..., tags de session/date/source, artefacts
        # de corpus livre). Les exclusions sont PRÉCISES (regex), pas des
        # préfixes larges : 't%' exclurait truth-engine/trump, 'v%' exclurait
        # viginum/verifie-*.
        subjects_query = text(f"""
            SELECT tag, count(*) AS n
            FROM memories m, unnest(m.tags) AS tag
            WHERE {_scope()}
              AND tag NOT LIKE 'session:%%'
              AND tag NOT LIKE 'date:%%'
              AND tag NOT LIKE 'source-%%'
              AND tag NOT LIKE 'auto-%%'
              AND tag NOT LIKE 'claude%%'
              AND tag NOT LIKE 'livre-%%'
              AND tag NOT LIKE 'chapter-%%'
              AND tag NOT LIKE 'chapitre-%%'
              AND tag NOT LIKE 'article-web%%'
              AND tag NOT LIKE 'fichier-%%'
              AND tag NOT LIKE '%%-corpus-%%'
              AND tag NOT LIKE 'discriminant-%%'
              AND tag NOT LIKE 'polarite-%%'
              AND tag NOT LIKE 'synthese-%%'
              AND tag NOT LIKE 'verifie-%%'
              AND tag NOT LIKE 'status:%%'
              AND tag NOT LIKE 'project:%%'
              AND tag NOT LIKE 'memory:%%'
              AND tag NOT LIKE 'trace:%%'
              AND tag !~* '^(t[0-9]+|v[0-9]+)$'
              AND tag NOT IN ('test', 'kernel', 'investigation', 'fact',
                              'fact-check', 'truth-engine', 'article', 'rapport')
            GROUP BY tag
            ORDER BY n DESC
            LIMIT 25
        """)
        timeline_query = text(f"""
            SELECT to_char(date_trunc('month', created_at), 'YYYY-MM') AS month,
                   count(*) AS n
            FROM memories m
            WHERE {_scope()}
              AND memory_type IN ('investigation', 'article', 'quintessence')
            GROUP BY month
            ORDER BY month
        """)

        async with engine.begin() as conn:
            types_rows = (await conn.execute(type_query, params)).fetchall()
            status_row = (await conn.execute(status_query, params)).fetchone()
            subjects_rows = (await conn.execute(subjects_query, params)).fetchall()
            timeline_rows = (await conn.execute(timeline_query, params)).fetchall()

        return {
            "by_type": {row[0]: row[1] for row in types_rows},
            "status": {
                "confirmed": status_row[0] if status_row else 0,
                "fact_checked": status_row[1] if status_row else 0,
                "total": status_row[2] if status_row else 0,
            },
            "top_subjects": [{"tag": row[0], "count": row[1]} for row in subjects_rows],
            "timeline": [{"month": row[0], "count": row[1]} for row in timeline_rows],
        }

    except Exception as e:
        logger.error(f"Failed to get explorer stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get explorer stats: {e}")


@router.get("/explorer/tree")
async def get_explorer_tree(
    subject: str = Query(..., min_length=1, description="Tag de sujet (ex. 14-juillet-2026)"),
    project_id: Optional[str] = Query(None, description="Project_id optionnel (par défaut : tout le socle)"),
    engine: AsyncEngine = Depends(get_db_engine),
) -> Dict[str, Any]:
    """Arborescence sujet -> enquêtes -> faits vérifiés -> notes/sources.

    Match insensible à la casse (aligné sur related-by-tags) : la base a des
    tags mixtes, un sélecteur utilisateur peut introduire une autre casse.
    """
    try:
        where = ("deleted_at IS NULL AND EXISTS "
                 "(SELECT 1 FROM unnest(tags) AS t WHERE lower(t) = lower(:subject))")
        params: Dict[str, Any] = {"subject": subject}
        if project_id:
            where += " AND project_id = :pid"
            params["pid"] = project_id

        query = text(f"""
            SELECT id::text, title, memory_type, tags, created_at
            FROM memories
            WHERE {where}
            ORDER BY memory_type, created_at DESC
        """)

        async with engine.begin() as conn:
            rows = (await conn.execute(query, params)).fetchall()

        investigations = []
        facts = []
        others = []

        for row in rows:
            item = {
                "id": row[0],
                "title": row[1],
                "memory_type": row[2],
                "tags": row[3] or [],
                "created_at": row[4].isoformat() if row[4] else None,
            }
            if row[2] == "investigation":
                investigations.append(item)
            elif row[2] == "quintessence" or "fact-check" in (row[3] or []):
                facts.append(item)
            else:
                others.append(item)

        return {
            "subject": subject,
            "total": len(rows),
            "investigations": investigations,
            "facts": facts,
            "others": others,
        }

    except Exception as e:
        logger.error(f"Failed to get explorer tree: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get explorer tree: {e}")


@router.get("/{memory_id}/related-by-tags")
async def get_related_by_tags(
    memory_id: str,
    limit: int = Query(10, ge=1, le=50),
    min_shared: int = Query(1, ge=1, le=10),
    engine: AsyncEngine = Depends(get_db_engine),
) -> Dict[str, Any]:
    """
    Mémoires liées par proxy de tags partagés.

    Score = nombre de tags de sujet communs (pondération : les tags
    porteurs de sens valent 2, les tags techniques valent 1). Fonctionne
    immédiatement sur les mémoires déjà taggées, sans pipeline d'extraction.
    """
    try:
        # Tags de la mémoire source
        source_query = text("""
            SELECT tags FROM memories WHERE id = :mid AND deleted_at IS NULL
        """)
        async with engine.begin() as conn:
            source_row = (await conn.execute(source_query, {"mid": memory_id})).fetchone()

        if source_row is None:
            raise HTTPException(status_code=404, detail="Memory not found")

        source_tags = [t.lower() for t in (source_row[0] or [])]
        if not source_tags:
            return {"memory_id": memory_id, "related": [], "total": 0}

        # Mémoires candidates partageant au moins un tag avec la source
        # (hors elle-même), score calculé en Python (pondération par tag).
        candidates_query = text("""
            SELECT id::text, title, memory_type, tags
            FROM memories
            WHERE id != :mid AND deleted_at IS NULL
              AND EXISTS (
                  SELECT 1 FROM unnest(tags) AS t
                  WHERE lower(t) = ANY(CAST(:tags AS text[]))
              )
            ORDER BY updated_at DESC
            LIMIT 200
        """)

        # Poids des tags : sujets = 2, techniques = 1
        def _tag_weight(tag: str) -> int:
            if tag.startswith(("session:", "date:", "source-", "auto-", "claude")):
                return 1
            return 2

        async with engine.begin() as conn:
            rows = (await conn.execute(
                candidates_query, {"mid": memory_id, "tags": source_tags}
            )).fetchall()

        related = []
        for row in rows:
            cand_tags = [t.lower() for t in (row[3] or [])]
            shared = set(source_tags) & set(cand_tags)
            score = sum(_tag_weight(t) for t in shared)
            if score >= min_shared:
                related.append({
                    "id": row[0],
                    "title": row[1],
                    "memory_type": row[2],
                    "shared_tags": sorted(shared),
                    "score": score,
                })

        related.sort(key=lambda r: r["score"], reverse=True)
        related = related[:limit]

        return {"memory_id": memory_id, "related": related, "total": len(related)}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get related by tags for {memory_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get related by tags: {e}")
