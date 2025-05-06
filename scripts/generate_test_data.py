#!/usr/bin/env python3
"""
Script pour générer des données de test dans la base de données MnemoLite Test.
Ce script crée des événements fictifs avec différents contenus, métadonnées et embeddings.
"""

import os
import uuid
import json
import random
import datetime
import asyncio
import asyncpg
from datetime import timezone, timedelta
import numpy as np

# Configuration
DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", "postgresql://mnemo:mnemopass@db:5432/mnemolite_test"
).replace(
    "+asyncpg", ""
)  # Conversion pour asyncpg natif

# Constantes
VECTOR_DIM = 1536  # Dimension des vecteurs d'embedding
NUM_EVENTS = 100  # Nombre d'événements à générer

# Catégories de test
CATEGORIES = [
    "note",
    "email",
    "message",
    "document",
    "image",
    "code",
    "meeting",
    "task",
    "idea",
    "reference",
]

# Sources de test
SOURCES = [
    "web",
    "api",
    "manual",
    "system",
    "import",
    "query",
    "search",
    "feed",
    "notification",
]

# Tags de test
TAGS = [
    "important",
    "urgent",
    "follow-up",
    "archived",
    "draft",
    "personal",
    "work",
    "project",
    "reference",
    "learning",
    "high-priority",
    "low-priority",
    "team",
    "private",
]


async def generate_random_embedding():
    """Génère un vecteur d'embedding aléatoire."""
    # Générer un vecteur aléatoire
    embedding = np.random.normal(0, 0.1, VECTOR_DIM)
    # Normaliser le vecteur (comme le font souvent les modèles d'embedding)
    embedding = embedding / np.linalg.norm(embedding)
    return embedding.tolist()


def format_embedding_for_pgvector(embedding_list):
    """Formate une liste de flottants pour pgvector."""
    if embedding_list is None:
        return None
    return "[" + ",".join(map(str, embedding_list)) + "]"


async def generate_event_content(category):
    """Génère un contenu aléatoire basé sur la catégorie."""
    base_content = {
        "category": category,
        "created_at": datetime.datetime.now(timezone.utc).isoformat(),
    }

    if category == "note":
        base_content.update(
            {
                "title": f"Note sur {random.choice(['le projet', 'la réunion', 'l\'idée', 'le concept'])}",
                "text": f"Contenu détaillé de la note avec des points importants à retenir pour {random.randint(1, 5)} jours.",
            }
        )
    elif category == "email":
        base_content.update(
            {
                "subject": f"RE: {random.choice(['Discussion', 'Projet', 'Mise à jour', 'Question'])}",
                "from": f"user{random.randint(1, 20)}@example.com",
                "to": [f"contact{random.randint(1, 50)}@example.com"],
                "body": f"Contenu de l'email avec {random.randint(1, 10)} paragraphes.",
            }
        )
    elif category == "message":
        base_content.update(
            {
                "channel": f"#{random.choice(['general', 'random', 'projet', 'equipe', 'support'])}",
                "sender": f"user{random.randint(1, 30)}",
                "text": f"Message dans le canal avec {random.randint(1, 3)} mentions.",
            }
        )
    elif category == "document":
        base_content.update(
            {
                "title": f"Document {random.choice(['technique', 'marketing', 'légal', 'financier'])}",
                "summary": f"Résumé du document en {random.randint(1, 5)} lignes.",
                "pages": random.randint(1, 50),
            }
        )
    elif category == "code":
        languages = ["python", "javascript", "rust", "golang", "typescript"]
        base_content.update(
            {
                "language": random.choice(languages),
                "filename": f"example_{random.randint(1, 100)}.{random.choice(['py', 'js', 'rs', 'go', 'ts'])}",
                "snippet": f"function example{random.randint(1, 20)}() {{ /* code snippet */ }}",
            }
        )
    else:
        # Catégorie générique
        base_content.update(
            {
                "title": f"{category.capitalize()} #{random.randint(1, 100)}",
                "description": f"Description du {category} avec détails variés et {random.randint(1, 5)} points clés.",
            }
        )

    return base_content


async def generate_event_metadata(category, source):
    """Génère des métadonnées aléatoires."""
    # Métadonnées de base
    metadata = {
        "source": source,
        "category": category,
        "version": f"1.{random.randint(0, 9)}",
    }

    # Ajouter des tags aléatoires (0 à 5)
    num_tags = random.randint(0, 5)
    if num_tags > 0:
        random_tags = random.sample(TAGS, num_tags)
        metadata["tags"] = random_tags

    # Ajouter d'autres métadonnées selon la catégorie
    if category in ["note", "document", "code"]:
        metadata["author"] = f"user{random.randint(1, 20)}"

    if category in ["email", "message"]:
        metadata["thread_id"] = str(uuid.uuid4())

    # Ajouter une priorité aléatoire pour certaines catégories
    if category in ["task", "email", "document"]:
        metadata["priority"] = random.randint(1, 5)

    # Ajouter un statut pour certaines catégories
    if category == "task":
        metadata["status"] = random.choice(
            ["pending", "in-progress", "completed", "blocked"]
        )

    return metadata


async def insert_events(conn, num_events):
    """Insère un nombre spécifié d'événements aléatoires dans la base de données."""
    print(f"Génération de {num_events} événements de test...")

    for i in range(num_events):
        # Générer des données aléatoires
        category = random.choice(CATEGORIES)
        source = random.choice(SOURCES)

        # Timestamp avec une distribution sur les derniers 30 jours
        days_ago = random.randint(0, 30)
        hours_ago = random.randint(0, 23)
        timestamp = datetime.datetime.now(timezone.utc) - timedelta(
            days=days_ago, hours=hours_ago
        )

        # Génération de contenu, métadonnées et embedding
        content = await generate_event_content(category)
        metadata = await generate_event_metadata(category, source)

        # 80% des événements ont un embedding, 20% n'en ont pas
        embedding_list = (
            await generate_random_embedding() if random.random() < 0.8 else None
        )
        embedding_formatted = format_embedding_for_pgvector(embedding_list)

        # Insérer l'événement
        await conn.execute(
            """
            INSERT INTO events (id, timestamp, content, metadata, embedding)
            VALUES ($1, $2, $3, $4, $5)
        """,
            uuid.uuid4(),
            timestamp,
            json.dumps(content),
            json.dumps(metadata),
            embedding_formatted,
        )

        if (i + 1) % 10 == 0:
            print(f"  {i + 1} événements générés...")

    print("Génération des données de test terminée.")


async def create_test_nodes_and_edges(conn):
    """Crée des noeuds et des arêtes de test pour le graphe conceptuel."""
    print("Création de noeuds et d'arêtes de test pour le graphe...")

    # Récupérer quelques IDs d'événements existants
    event_ids = await conn.fetch(
        """
        SELECT id FROM events LIMIT 20
    """
    )

    # Créer des noeuds basés sur les événements
    print("Création de noeuds de test...")
    for i, row in enumerate(event_ids):
        event_id = row["id"]
        node_type = "event" if i < 10 else "concept"
        label = f"Node-{i+1}"
        properties = {
            "description": f"Description du noeud {i+1}",
            "importance": random.randint(1, 10),
            "related_event_id": str(event_id) if node_type == "concept" else None,
        }

        await conn.execute(
            """
            INSERT INTO nodes (node_id, node_type, label, properties)
            VALUES ($1, $2, $3, $4)
        """,
            event_id,
            node_type,
            label,
            json.dumps(properties),
        )

    # Créer des arêtes entre les noeuds
    print("Création d'arêtes de test...")
    node_ids = [row["id"] for row in event_ids]

    # Créer environ 30 arêtes de test
    for _ in range(30):
        # Sélectionner deux noeuds aléatoires différents
        source_node = random.choice(node_ids)
        target_node = random.choice([n for n in node_ids if n != source_node])

        # Sélectionner un type de relation aléatoire
        relation_type = random.choice(
            ["references", "follows", "precedes", "mentions", "related_to"]
        )

        # Propriétés de l'arête
        properties = {
            "weight": random.uniform(0.1, 1.0),
            "created_by": f"script-{random.randint(1, 5)}",
            "confidence": random.uniform(0.5, 0.99),
        }

        await conn.execute(
            """
            INSERT INTO edges (source_node_id, target_node_id, relation_type, properties)
            VALUES ($1, $2, $3, $4)
        """,
            source_node,
            target_node,
            relation_type,
            json.dumps(properties),
        )

    print("Création du graphe de test terminée.")


async def main():
    """Fonction principale."""
    print(f"Connexion à la base de données: {DATABASE_URL}")
    try:
        conn = await asyncpg.connect(DATABASE_URL)
        print("Connexion réussie!")

        # Vérifier si la table 'events' est vide
        count = await conn.fetchval("SELECT COUNT(*) FROM events")
        if count > 0:
            print(f"La table 'events' contient déjà {count} événements.")
            proceed = input(
                "Voulez-vous ajouter plus d'événements de test? (o/n): "
            ).lower()
            if proceed != "o":
                print("Opération annulée.")
                await conn.close()
                return

        # Insérer les événements
        await insert_events(conn, NUM_EVENTS)

        # Créer le graphe de test
        await create_test_nodes_and_edges(conn)

        # Obtenir des statistiques
        event_count = await conn.fetchval("SELECT COUNT(*) FROM events")
        node_count = await conn.fetchval("SELECT COUNT(*) FROM nodes")
        edge_count = await conn.fetchval("SELECT COUNT(*) FROM edges")

        print(f"\nStatistiques finales de la base de test:")
        print(f"- {event_count} événements dans la table 'events'")
        print(f"- {node_count} noeuds dans la table 'nodes'")
        print(f"- {edge_count} arêtes dans la table 'edges'")

        await conn.close()
        print("Connexion fermée.")

    except Exception as e:
        print(f"Erreur lors de la génération des données: {e}")


if __name__ == "__main__":
    asyncio.run(main())
