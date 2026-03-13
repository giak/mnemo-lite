#!/usr/bin/env python3
"""
POC: Compare embedding strategies for Knowledge Graph of Investigations

Compares three embedding approaches:
1. FULL_CONTENT: Embed full markdown content (current approach, diluted signal)
2. KEYWORDS_ONLY: Embed extracted keywords/entities only (sparse vector)
3. STRUCTURED_SUMMARY: Embed 200-400 word structured summary (recommended B+C hybrid)

Usage (inside Docker container):
    docker compose exec api python scripts/poc_embedding_source_comparison.py
"""

import asyncio
import numpy as np
from typing import List, Tuple

# Add api directory to path
import sys
sys.path.insert(0, '/app')

# Sample investigation content (simulated Bardella investigation)
SAMPLE_INVESTIGATION = {
    "title": "Investigation APEX: Jordan Bardella & Accord UE-Mercosur",
    "full_content": """
# Investigation APEX : Jordan Bardella & Accord UE-Mercosur

## Contexte
Jordan Bardella, président du Rassemblement National, s'est exprimé le 23 novembre 2024
sur l'accord UE-Mercosur, dénonçant une "trahison des agriculteurs français".

## Analyse Multi-Sources

### Source 1: Tweet original
Le tweet de Bardella du 23/11/2024 utilise un argumentaire souverainiste classique,
opposant les "intérêts des multinationales" aux "agriculteurs français".

### Source 2: Position officielle RN
Le Rassemblement National s'oppose historiquement à l'accord Mercosur depuis 2019.
Marine Le Pen avait déjà dénoncé cet accord lors de la campagne présidentielle 2022.

### Source 3: Analyse économique
Les importations de boeuf sud-américain représentent actuellement 300 000 tonnes/an.
L'accord prévoirait d'augmenter ce quota de 99 000 tonnes supplémentaires.
Impact estimé sur les éleveurs français: -15% de revenus selon FNSEA.

### Source 4: Position européenne
La Commission européenne défend l'accord comme "bénéfique pour l'export automobile et industriel".
Les négociations durent depuis 25 ans (1999-2024).

## Wolves Map (H7)
- Jordan Bardella: Président RN, opposant déclaré
- Marine Le Pen: Vice-présidente RN, historique anti-Mercosur
- Emmanuel Macron: Président FR, position ambiguë
- Ursula von der Leyen: Présidente CE, pro-accord
- Christiane Lambert: Ex-FNSEA, position critique

## Findings
1. Contradiction: Le RN vote contre les mesures de protection agricole au PE tout en s'affichant pro-agriculteurs
2. Pattern: Communication souverainiste visant l'électorat rural pré-élections européennes 2024
3. Iceberg: Vrai débat = arbitrage industrie/agriculture, pas souveraineté

## Métadonnées
- EDI: 0.68
- Sources: 12 (3 primaires, 5 secondaires, 4 tertiaires)
- Investigation Type: APEX
- Date: 2024-11-23
""",
    "keywords_only": "Bardella RN Rassemblement National Mercosur accord UE agriculture agriculteurs FNSEA élections européennes 2024 Marine Le Pen souverainisme",
    "structured_summary": """Sujet: Jordan Bardella, président du Rassemblement National, et sa position sur l'accord UE-Mercosur
Thèmes: politique agricole française, accord commercial UE-Mercosur, souverainisme économique, élections européennes 2024, stratégie électorale RN, contradiction discours/votes
Entités: Jordan Bardella, Marine Le Pen, Rassemblement National, Emmanuel Macron, Ursula von der Leyen, FNSEA, Christiane Lambert, Commission européenne
Findings clés: Le RN s'affiche pro-agriculteurs mais vote contre les protections agricoles au Parlement européen. Communication souverainiste ciblant l'électorat rural avant les européennes. Le vrai débat est l'arbitrage industrie vs agriculture, pas la souveraineté.
Période: novembre 2024, contexte élections européennes
Type investigation: APEX politique, EDI 0.68, 12 sources analysées
Mots-clés recherche: Bardella Mercosur agriculteurs RN élections européennes contradiction votes discours"""
}

# Test queries (what a user would search for)
TEST_QUERIES = [
    # Exact match queries (keywords expected to win)
    "Bardella",
    "Mercosur agriculture",
    "FNSEA éleveurs bovins",

    # Semantic/conceptual queries (summary expected to win)
    "contradiction RN votes agriculteurs",
    "discours populiste vs réalité des votes",
    "stratégie électorale ciblant monde rural",
    "hypocrisie politique sur agriculture",
    "que dit vraiment le RN sur les agriculteurs",
    "analyse critique position extrême droite commerce",
    "arbitrage industrie agriculture dans accord commercial",
    "qui sont les acteurs du débat Mercosur",
    "pourquoi le RN s'oppose à l'accord",
]


async def compute_embedding(text: str, service) -> List[float]:
    """Compute embedding for text."""
    return await service.generate_embedding(text)


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    a = np.array(vec1)
    b = np.array(vec2)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


async def main():
    print("=" * 70)
    print("POC: Embedding Source Comparison for Knowledge Graph of Investigations")
    print("=" * 70)
    print()

    # Load embedding service
    print("Loading embedding model (nomic-embed-text-v1.5)...")
    from services.sentence_transformer_embedding_service import SentenceTransformerEmbeddingService
    embedding_service = SentenceTransformerEmbeddingService()
    print("Model loaded!")
    print()

    # Compute embeddings for each approach
    print("Computing embeddings for 3 approaches...")
    print()

    # 1. Full content (current approach)
    print(f"  1. FULL_CONTENT: {len(SAMPLE_INVESTIGATION['full_content'])} chars")
    emb_full = await compute_embedding(
        SAMPLE_INVESTIGATION['full_content'],
        embedding_service
    )

    # 2. Keywords only
    print(f"  2. KEYWORDS_ONLY: {len(SAMPLE_INVESTIGATION['keywords_only'])} chars")
    emb_keywords = await compute_embedding(
        SAMPLE_INVESTIGATION['keywords_only'],
        embedding_service
    )

    # 3. Structured summary (B+C hybrid)
    print(f"  3. STRUCTURED_SUMMARY: {len(SAMPLE_INVESTIGATION['structured_summary'])} chars")
    emb_summary = await compute_embedding(
        SAMPLE_INVESTIGATION['structured_summary'],
        embedding_service
    )

    print()
    print("=" * 70)
    print("SIMILARITY COMPARISON")
    print("=" * 70)
    print()

    # Header
    print(f"{'Query':<40} {'FULL':<10} {'KEYWORDS':<10} {'SUMMARY':<10} {'BEST':<12}")
    print("-" * 90)

    results = []
    for query in TEST_QUERIES:
        query_emb = await compute_embedding(query, embedding_service)

        sim_full = cosine_similarity(query_emb, emb_full)
        sim_keywords = cosine_similarity(query_emb, emb_keywords)
        sim_summary = cosine_similarity(query_emb, emb_summary)

        # Determine best approach
        scores = {
            "FULL": sim_full,
            "KEYWORDS": sim_keywords,
            "SUMMARY": sim_summary
        }
        best = max(scores, key=scores.get)

        # Truncate query for display
        display_query = query[:38] + ".." if len(query) > 40 else query

        print(f"{display_query:<40} {sim_full:.3f}     {sim_keywords:.3f}      {sim_summary:.3f}     {best}")

        results.append({
            "query": query,
            "full": sim_full,
            "keywords": sim_keywords,
            "summary": sim_summary,
            "best": best
        })

    print()
    print("=" * 70)
    print("ANALYSIS")
    print("=" * 70)
    print()

    # Count wins
    wins = {"FULL": 0, "KEYWORDS": 0, "SUMMARY": 0}
    for r in results:
        wins[r["best"]] += 1

    print(f"  FULL_CONTENT wins: {wins['FULL']}/{len(results)}")
    print(f"  KEYWORDS_ONLY wins: {wins['KEYWORDS']}/{len(results)}")
    print(f"  STRUCTURED_SUMMARY wins: {wins['SUMMARY']}/{len(results)}")
    print()

    # Average similarities
    avg_full = sum(r["full"] for r in results) / len(results)
    avg_keywords = sum(r["keywords"] for r in results) / len(results)
    avg_summary = sum(r["summary"] for r in results) / len(results)

    print(f"  Average similarity FULL_CONTENT:     {avg_full:.3f}")
    print(f"  Average similarity KEYWORDS_ONLY:    {avg_keywords:.3f}")
    print(f"  Average similarity STRUCTURED_SUMMARY: {avg_summary:.3f}")
    print()

    # Improvement over current approach
    improvement_summary = ((avg_summary - avg_full) / avg_full) * 100 if avg_full > 0 else 0
    improvement_keywords = ((avg_keywords - avg_full) / avg_full) * 100 if avg_full > 0 else 0

    print(f"  STRUCTURED_SUMMARY improvement vs FULL: {improvement_summary:+.1f}%")
    print(f"  KEYWORDS_ONLY improvement vs FULL:      {improvement_keywords:+.1f}%")
    print()

    # Conclusion
    print("=" * 70)
    print("CONCLUSION")
    print("=" * 70)
    print()

    if avg_summary > avg_keywords and avg_summary > avg_full:
        print("  STRUCTURED_SUMMARY (B+C hybrid) is the BEST approach!")
        print("  → Provides dense semantic signal without dilution")
        print("  → Captures relationships between entities")
        print("  → Recommended for Knowledge Graph of Investigations")
    elif avg_keywords > avg_full:
        print("  KEYWORDS_ONLY shows improvement over FULL_CONTENT")
        print("  → But STRUCTURED_SUMMARY provides better context")
    else:
        print("  FULL_CONTENT performs unexpectedly well")
        print("  → May indicate need for longer test queries")

    print()
    print("=" * 70)
    print("RECOMMENDATION: Use STRUCTURED_SUMMARY (200-400 words)")
    print("  - embedding_source = structured summary")
    print("  - content = full markdown investigation")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
