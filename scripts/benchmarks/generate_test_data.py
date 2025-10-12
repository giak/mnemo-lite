"""
Generates and inserts a large volume of test data into the 'events' table
for performance benchmarking (STORY-03.4 PoC).
"""

import asyncio
import asyncpg
import argparse
import numpy as np
import json
import uuid
import os
import random
from datetime import datetime, timedelta, timezone
import time

# --- Configuration ---
DEFAULT_NUM_EVENTS = 30000  # Nombre d'événements à générer
DEFAULT_DB_DSN = os.environ.get(
    "DATABASE_URL", "postgresql://user:password@localhost:5432/mnemolite_db"
)
DEFAULT_EMBEDDING_DIM = 768  # Ajusté selon le schéma DB (01-init.sql) - nomic-embed-text-v1.5
BATCH_SIZE = 1000  # Taille des lots pour l'insertion

# Période pour les timestamps (3 mois)
END_DATE = datetime.now(timezone.utc)
START_DATE = END_DATE - timedelta(days=90)

METADATA_TYPES = ["log", "metric", "trace", "audit"]
METADATA_SOURCES = ["app-web", "app-mobile", "api-gateway", "db-worker", "infra-node"]
METADATA_STATUS_CODES = [200, 201, 204, 400, 401, 403, 404, 500, 503]

# --- Helper Functions ---


def generate_random_timestamp(start, end):
    """Génère un timestamp aléatoire entre start et end."""
    delta = end - start
    random_seconds = random.uniform(0, delta.total_seconds())
    return start + timedelta(seconds=random_seconds)


def generate_random_embedding(dim):
    """Génère un vecteur embedding aléatoire normalisé."""
    vec = np.random.rand(dim).astype(np.float32)
    norm = np.linalg.norm(vec)
    if norm == 0:
        return np.zeros(dim).tolist()  # Éviter division par zéro
    return (vec / norm).tolist()


def generate_random_event(embedding_dim):
    """Génère un enregistrement d'événement aléatoire."""
    event_type = random.choice(METADATA_TYPES)
    metadata = {
        "type": event_type,
        "source": random.choice(METADATA_SOURCES),
        "tenant_id": random.randint(1, 10),
    }
    if event_type in ["log", "trace"]:
        # Ajout conditionnel de status_code
        if random.random() > 0.3:  # 70% de chance d'avoir un status_code
            metadata["status_code"] = random.choice(METADATA_STATUS_CODES)

    return (
        uuid.uuid4(),  # id (au lieu de event_id)
        generate_random_timestamp(START_DATE, END_DATE),  # timestamp
        generate_random_embedding(embedding_dim),  # embedding (list)
        json.dumps(metadata),  # metadata (json string)
        json.dumps({}),  # content (au lieu de raw_event)
    )


async def main(num_events, db_dsn, embedding_dim):
    """Fonction principale pour générer et insérer les données."""
    print(f"Connexion à la base de données : {db_dsn}")
    conn = None
    try:
        conn = await asyncpg.connect(db_dsn)
        print(
            f"Connexion réussie. Génération de {num_events} événements (dim={embedding_dim})..."
        )

        start_time = time.time()
        total_inserted = 0
        records_batch = []

        for i in range(num_events):
            records_batch.append(generate_random_event(embedding_dim))

            if len(records_batch) >= BATCH_SIZE or i == num_events - 1:
                try:
                    # Utilisation de copy_records_to_table pour l'efficacité
                    await conn.copy_records_to_table(
                        "events",
                        records=records_batch,
                        columns=["id", "timestamp", "embedding", "metadata", "content"],
                        timeout=60,  # Augmenter le timeout pour les gros lots
                    )
                    total_inserted += len(records_batch)
                    elapsed_time = time.time() - start_time
                    print(
                        f"  -> Inséré {total_inserted}/{num_events} événements ({len(records_batch)} ce lot). Temps écoulé: {elapsed_time:.2f}s",
                        end="\r",
                    )
                    records_batch = []  # Vider le lot

                except Exception as e:
                    print(f"\nErreur lors de l'insertion du lot: {e}")
                    print("Tentative d'insertion ligne par ligne (plus lent)...")
                    # Mode dégradé: insertion ligne par ligne en cas d'échec du lot
                    for record in records_batch:
                        # Convertir l'embedding (liste) en string pour INSERT
                        record_list = list(
                            record
                        )  # Convertir le tuple en liste pour modification
                        record_list[2] = str(
                            record_list[2]
                        )  # Convertir l'embedding (index 2) en string '[...]'
                        record_tuple = tuple(record_list)

                        try:
                            await conn.execute(
                                """
                                 INSERT INTO events (id, timestamp, embedding, metadata, content)
                                 VALUES ($1, $2, $3, $4, $5)
                             """,
                                *record_tuple,
                            )  # Utiliser le tuple modifié
                            total_inserted += 1
                            elapsed_time = time.time() - start_time
                            print(
                                f"  -> Inséré {total_inserted}/{num_events} événements (ligne par ligne). Temps écoulé: {elapsed_time:.2f}s",
                                end="\r",
                            )
                        except Exception as inner_e:
                            print(
                                f"\nErreur lors de l'insertion de l'enregistrement {record[0]}: {inner_e}"
                            )
                            # Décider quoi faire ici: skipper, logger, arrêter ? Pour l'instant, on logue et continue.
                    records_batch = []  # Vider le lot même en cas d'erreur partielle

        print(
            f"\nInsertion terminée. {total_inserted} événements insérés en {time.time() - start_time:.2f} secondes."
        )

    except Exception as e:
        print(f"Erreur générale : {e}")
    finally:
        if conn:
            await conn.close()
            print("Connexion à la base de données fermée.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Génère des données de test pour MnemoLite."
    )
    parser.add_argument(
        "-n",
        "--num-events",
        type=int,
        default=DEFAULT_NUM_EVENTS,
        help=f"Nombre d'événements à générer (défaut: {DEFAULT_NUM_EVENTS})",
    )
    parser.add_argument(
        "--db-dsn",
        type=str,
        default=DEFAULT_DB_DSN,
        help=f"DSN de la base de données PostgreSQL (défaut: {DEFAULT_DB_DSN} ou variable d'env DATABASE_URL)",
    )
    parser.add_argument(
        "--dim",
        type=int,
        default=DEFAULT_EMBEDDING_DIM,
        help=f"Dimension des embeddings (défaut: {DEFAULT_EMBEDDING_DIM})",
    )

    args = parser.parse_args()

    asyncio.run(main(args.num_events, args.db_dsn, args.dim))
