import requests
import json
import random
import uuid
import os
import sys

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000") # Utilise le port interne du conteneur par défaut
API_ENDPOINT = "/v1/events/"
API_URL = f"{API_BASE_URL.rstrip('/')}{API_ENDPOINT}"
EMBEDDING_DIM = 1536 # Doit correspondre à la définition VECTOR() dans le SQL

def generate_fake_embedding(dim: int) -> list[float]:
    """Génère une liste de floats aléatoires (entre -1 et 1)."""
    # return [0.0] * dim # Simple version avec des zéros
    return [random.uniform(-1.0, 1.0) for _ in range(dim)]

def create_fake_event(message: str = "Fake event", source: str = "faker_script") -> dict:
    """Crée le payload pour un événement factice."""
    payload = {
        "content": {
            "type": "fake",
            "message": message,
            "uuid": str(uuid.uuid4()) # Ajoute un peu de variété
        },
        "metadata": {
            "source": source,
            "user": "fake_user",
            "random_val": random.randint(1, 100)
        },
        "embedding": generate_fake_embedding(EMBEDDING_DIM)
        # Mettre à None si on veut tester sans embedding:
        # "embedding": None 
    }
    return payload

def post_event(payload: dict):
    """Envoie une requête POST à l'API."""
    headers = {"Content-Type": "application/json"}
    print(f"Attempting to POST to: {API_URL}")
    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        
        print(f"Status Code: {response.status_code}")
        
        # Essayer d'afficher la réponse JSON si possible, sinon le texte brut
        try:
            response_json = response.json()
            print("Response JSON:")
            print(json.dumps(response_json, indent=2))
        except json.JSONDecodeError:
            print("Response Text:")
            print(response.text)

        response.raise_for_status() # Lève une exception pour les codes 4xx/5xx après affichage
        print("Event created successfully!")
        return response.json()
        
    except requests.exceptions.RequestException as e:
        print(f"Error posting event: {e}")
        if e.response is not None:
             # L'erreur a déjà été affichée plus haut
             pass
        return None

if __name__ == "__main__":
    num_events = 1
    if len(sys.argv) > 1:
        try:
            num_events = int(sys.argv[1])
        except ValueError:
            print("Usage: python fake_event_poster.py [number_of_events]")
            sys.exit(1)

    print(f"Posting {num_events} fake event(s) to {API_URL}...")
    
    for i in range(num_events):
        print(f"--- Posting event {i+1}/{num_events} ---")
        fake_payload = create_fake_event(message=f"Event {i+1} from script!")
        post_event(fake_payload)
        print("-" * (20 + len(str(i+1)) + 1 + len(str(num_events)) + 4)) # Ligne de séparation 