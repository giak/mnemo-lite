"""
Runs KNN benchmark queries against the partitioned 'events' table.
"""

import asyncio
import asyncpg
import os
import argparse
import numpy as np
import time
from datetime import datetime, timedelta, timezone
from pgvector.utils import from_db, to_db
import statistics
from pathlib import Path
import sys

# Ajout du chemin racine du projet au PYTHONPATH pour trouver 'api'
# Ceci est nécessaire si on exécute le script directement et pas comme module
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# Importation relative depuis la structure attendue
try:
    # Les imports sont relatifs au PYTHONPATH (/app dans le conteneur)
    from db.repositories.event_repository import EventRepository
    from db.database import Database  # Pour le pool
except ImportError as e:
    print(f"Erreur d'importation: {e}")
    print(
        "Assurez-vous que le script est exécuté dans un environnement où 'db' et 'db.repositories' sont accessibles depuis PYTHONPATH=/app (ex: conteneur api)"
    )
    sys.exit(1)

# --- Configuration ---
DB_URL = os.getenv("DATABASE_URL", "postgresql://mnemo:mnemo@localhost:5432/mnemolite")
TABLE_NAME = "public.events"
EMBEDDING_DIMENSION = 1536  # Assuming OpenAI embeddings
DEFAULT_DB_DSN = os.environ.get(
    "DATABASE_URL", "postgresql://user:password@localhost:5432/mnemolite_db"
)
DEFAULT_EMBEDDING_DIM = 1536  # Doit correspondre au schéma et aux données
DEFAULT_NUM_RUNS = 20  # Nombre d'exécutions par scénario
DEFAULT_TOP_K = 10
DEFAULT_LIMIT = 10  # Limite finale retournée par l'API (via search_vector)

# --- Functions ---


async def fetch_sample_vectors(pool, count=100):
    """Fetches a few existing vectors from the DB to use as query vectors."""
    # Select embedding directly, pgvector handles parsing
    query = f"SELECT embedding FROM {TABLE_NAME} TABLESAMPLE SYSTEM (1) LIMIT {count};"
    # TABLESAMPLE SYSTEM(1) gets approx 1% of rows, then LIMIT
    # Adjust sampling percentage if needed for performance/representativeness
    print(f"Fetching up to {count} sample vectors for queries...")
    async with pool.acquire() as conn:
        rows = await conn.fetch(query)
        if not rows:
            print("Warning: Could not fetch sample vectors. Falling back to random.")
            # Generate random vectors if table is empty or sampling failed
            return [
                np.random.rand(EMBEDDING_DIMENSION).astype(np.float32)
                for _ in range(count)
            ]
        print(f"Fetched {len(rows)} sample vectors.")
        # Placeholder: return random if conversion logic is complex
        # TODO: Implement proper conversion from memoryview/bytea if needed
        # Use pgvector.utils.from_db to parse the string representation
        return [from_db(row["embedding"]) for row in rows]
        # return [np.random.rand(EMBEDDING_DIMENSION).astype(np.float32) for _ in range(len(rows))]


async def run_knn_query(pool, query_vector, k, ef_search=None):
    """Runs a single KNN query and returns the latency."""
    query = f"""
    SELECT id, timestamp 
    FROM {TABLE_NAME} 
    ORDER BY embedding <=> $1::vector -- Ensure type casting
    LIMIT $2;
    """

    start_time = time.monotonic()
    async with pool.acquire() as conn:
        # Set ef_search for this transaction if provided
        if ef_search:
            await conn.execute(f"SET LOCAL hnsw.ef_search = {ef_search};")

        # Prepare statement might be beneficial if running many queries
        # stmt = await conn.prepare(query)
        # results = await stmt.fetch(query_vector, k)
        # Convert numpy array back to string format for query parameter
        results = await conn.fetch(query, to_db(query_vector), k)

        # Optionally reset local setting if needed, but connection release handles it
        # if ef_search:
        #     await conn.execute("RESET hnsw.ef_search;")

    end_time = time.monotonic()
    return end_time - start_time, results  # Return latency and results (optional)


def generate_random_embedding(dim):
    """Génère un vecteur embedding aléatoire normalisé."""
    vec = np.random.rand(dim).astype(np.float32)
    norm = np.linalg.norm(vec)
    if norm == 0:
        return np.zeros(dim).tolist()
    return (vec / norm).tolist()


async def run_query_scenario(
    db_pool: asyncpg.Pool,
    scenario_name: str,
    vector: list[float] | None,
    metadata_filter: dict | None,
    top_k: int,
    limit: int,
    num_runs: int,
    ts_start: datetime | None = None,
    ts_end: datetime | None = None,
) -> tuple[float, float]:
    """Exécute un scénario de recherche plusieurs fois et calcule les latences P50/P95."""
    latencies_ms = []
    repo = EventRepository(db_pool)
    print(f"--- Démarrage Scénario: {scenario_name} ({num_runs} runs) ---")
    print(
        f"    Vector: {'Oui' if vector else 'Non'}, Metadata: {metadata_filter}, TopK: {top_k}, Limit: {limit}, Start: {ts_start}, End: {ts_end}"
    )

    # Préchauffage (une exécution pour initialiser les caches potentiels)
    try:
        _ = await repo.search_vector(
            vector=vector,
            metadata=metadata_filter,
            ts_start=ts_start,
            ts_end=ts_end,
            top_k=top_k,
            limit=limit,
            offset=0,
        )
    except Exception as e:
        print(f"Erreur lors du préchauffage: {e}")
        # On continue quand même pour voir si les runs suivants marchent

    # Exécutions mesurées
    for i in range(num_runs):
        start_time = time.perf_counter_ns()
        try:
            results = await repo.search_vector(
                vector=vector,
                metadata=metadata_filter,
                ts_start=ts_start,
                ts_end=ts_end,
                top_k=top_k,
                limit=limit,
                offset=0,  # Garder offset 0 pour la mesure pure
            )
            end_time = time.perf_counter_ns()
            latencies_ms.append(
                (end_time - start_time) / 1_000_000
            )  # Convertir ns en ms
            print(
                f"  Run {i+1}/{num_runs}: {latencies_ms[-1]:.2f} ms, {len(results)} résultats",
                end="\r",
            )
        except Exception as e:
            print(f"\nErreur pendant le run {i+1}: {e}")
            # On pourrait choisir d'arrêter ou de continuer
            # Pour l'instant, on logue et on continue si possible
            continue  # Passer au run suivant

    print("\n" + "-" * 20)  # Nouvelle ligne après les runs

    if not latencies_ms:
        print("Aucune exécution réussie, impossible de calculer les statistiques.")
        return (0.0, 0.0)

    # Calcul P50 (Médiane) et P95
    p50 = statistics.median(latencies_ms)
    p95 = np.percentile(latencies_ms, 95)

    print(f"Latences pour '{scenario_name}':")
    print(f"  P50 (Median): {p50:.2f} ms")
    print(f"  P95:          {p95:.2f} ms")
    print("-" * (len(scenario_name) + 20))
    return p50, p95


# --- Main Execution ---


async def main(db_dsn: str, num_runs: int, embedding_dim: int, top_k: int, limit: int):
    """Fonction principale pour exécuter les benchmarks."""
    db = Database(db_dsn)
    db_pool = (
        await db.get_pool()
    )  # Utilise la méthode de la classe Database pour obtenir le pool

    if not db_pool:
        print("Erreur: Impossible de créer le pool de connexion.")
        return

    print(f"Benchmark Latence PoC - {num_runs} runs par scénario")
    print(f"DB DSN: {db_dsn}, Dim: {embedding_dim}, TopK: {top_k}, Limit: {limit}")
    print("=" * 40)

    # Générer un vecteur de requête unique pour tous les scénarios nécessitant un vecteur
    query_vector = generate_random_embedding(embedding_dim)

    all_results = {}

    # --- Scénario 1: Vector Seul ---
    p50, p95 = await run_query_scenario(
        db_pool=db_pool,
        scenario_name="Vector Seul",
        vector=query_vector,
        metadata_filter=None,
        top_k=top_k,
        limit=limit,
        num_runs=num_runs,
    )
    all_results["Vector Seul"] = {"P50": p50, "P95": p95}

    # --- Scénario 2: Hybride Simple (type=log) ---
    p50, p95 = await run_query_scenario(
        db_pool=db_pool,
        scenario_name="Hybride (type=log)",
        vector=query_vector,
        metadata_filter={"type": "log"},  # Filtre commun
        top_k=top_k,
        limit=limit,
        num_runs=num_runs,
    )
    all_results["Hybride (type=log)"] = {"P50": p50, "P95": p95}

    # --- Scénario 3: Metadata Seul (type=log) ---
    # (Pour comparer avec la recherche hybride)
    p50, p95 = await run_query_scenario(
        db_pool=db_pool,
        scenario_name="Metadata Seul (type=log)",
        vector=None,  # Pas de vecteur
        metadata_filter={"type": "log"},  # Filtre commun
        top_k=0,  # top_k non pertinent sans vecteur
        limit=limit,
        num_runs=num_runs,
    )
    all_results["Metadata Seul (type=log)"] = {"P50": p50, "P95": p95}

    # --- Scénario 4: Metadata + Temps (type=log, dernier mois) ---
    end_time_filter = datetime.now(timezone.utc)
    start_time_filter = end_time_filter - timedelta(days=30)

    p50, p95 = await run_query_scenario(
        db_pool=db_pool,
        scenario_name="Metadata+Temps (type=log, 1 mois)",
        vector=None,  # Pas de vecteur
        metadata_filter={"type": "log"},  # Filtre commun
        ts_start=start_time_filter,  # Filtre temporel !
        ts_end=end_time_filter,  # Filtre temporel !
        top_k=0,  # top_k non pertinent sans vecteur
        limit=limit,
        num_runs=num_runs,
    )
    all_results["Metadata+Temps (type=log, 1 mois)"] = {"P50": p50, "P95": p95}

    print("\n" + "=" * 15 + " RÉSUMÉ " + "=" * 15)
    for name, stats in all_results.items():
        print(f"{name:<25} | P50: {stats['P50']:.2f} ms | P95: {stats['P95']:.2f} ms")
    print("=" * 40)

    await db_pool.close()
    print("Pool de connexion fermé.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Lance un benchmark léger sur l'API de recherche MnemoLite."
    )
    parser.add_argument(
        "--db-dsn",
        type=str,
        default=DEFAULT_DB_DSN,
        help=f"DSN de la base de données (défaut: env DATABASE_URL ou '{DEFAULT_DB_DSN}')",
    )
    parser.add_argument(
        "--num-runs",
        type=int,
        default=DEFAULT_NUM_RUNS,
        help=f"Nombre d'exécutions par scénario (défaut: {DEFAULT_NUM_RUNS})",
    )
    parser.add_argument(
        "--dim",
        type=int,
        default=DEFAULT_EMBEDDING_DIM,
        help=f"Dimension des embeddings (défaut: {DEFAULT_EMBEDDING_DIM})",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=DEFAULT_TOP_K,
        help=f"Valeur de top_k pour la recherche vectorielle (défaut: {DEFAULT_TOP_K})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_LIMIT,
        help=f"Limite de résultats finaux (défaut: {DEFAULT_LIMIT})",
    )

    args = parser.parse_args()

    # Vérifier si DATABASE_URL est dans l'environnement si --db-dsn n'est pas explicitement fourni
    # et que la valeur par défaut est utilisée
    db_dsn_to_use = args.db_dsn
    if db_dsn_to_use == DEFAULT_DB_DSN and "DATABASE_URL" in os.environ:
        db_dsn_to_use = os.environ["DATABASE_URL"]
        print(f"Utilisation de DATABASE_URL de l'environnement: {db_dsn_to_use}")

    asyncio.run(main(db_dsn_to_use, args.num_runs, args.dim, args.top_k, args.limit))
