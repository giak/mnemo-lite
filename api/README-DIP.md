# Principe d'Inversion de Dépendances dans MnemoLite

Ce document explique l'implémentation du Principe d'Inversion de Dépendances (DIP) dans l'API MnemoLite, un des principes SOLID pour la conception de logiciels.

## Qu'est-ce que le DIP ?

Le Principe d'Inversion de Dépendances (DIP) stipule que :

1. Les modules de haut niveau ne devraient pas dépendre des modules de bas niveau. Les deux devraient dépendre d'abstractions.
2. Les abstractions ne devraient pas dépendre des détails. Les détails devraient dépendre des abstractions.

En termes concrets, cela signifie que notre code métier (contrôleurs, services) ne devrait pas dépendre directement des implémentations spécifiques (comme un repository SQLAlchemy), mais plutôt d'interfaces ou de protocoles.

## Architecture de l'Injection de Dépendances

L'implémentation du DIP dans MnemoLite comprend plusieurs composants clés :

### 1. Protocoles (Interfaces)

Les protocoles définissent les contrats que les implémentations concrètes doivent respecter. Ils sont situés dans le package `api/interfaces/` :

- `repositories.py` : Définit les protocoles pour les opérations de persistance
- `services.py` : Définit les protocoles pour les services métier

Ces interfaces sont utilisées par les couches supérieures plutôt que des implémentations concrètes.

### 2. Système d'Injection de Dépendances

Le fichier `api/dependencies.py` fournit des fonctions factory qui :

- Créent et configurent les implémentations concrètes
- Gèrent les dépendances entre les différents composants
- Facilitent le remplacement des implémentations pour les tests

### 3. Implémentations Concrètes

Les implémentations concrètes réalisent les contrats définis par les protocoles :

- `api/db/repositories/` : Implémentations des repository basées sur SQLAlchemy
- `api/services/` : Implémentations des services métier

## Avantages de cette Approche

1. **Découplage** : Les composants de haut niveau ne dépendent pas des détails d'implémentation.
2. **Testabilité** : Les dépendances peuvent être facilement mockées pour les tests.
3. **Flexibilité** : Les implémentations peuvent être remplacées sans modifier le code client.
4. **Évolution** : Le système peut évoluer plus facilement, par exemple en changeant la source de données.

## Exemple d'Utilisation dans les Routes

```python
@router.get("/{memory_id}", response_model=Memory)
async def get_memory(
    memory_id: UUID,
    repo: Annotated[MemoryRepositoryProtocol, Depends(get_memory_repository)]
) -> Memory:
    """Récupère une mémoire par son ID."""
    memory = await repo.get_by_id(memory_id)
    if memory is None:
        raise HTTPException(status_code=404, detail=f"Mémoire avec ID {memory_id} non trouvée")
    return memory
```

Dans cet exemple, le contrôleur dépend du protocole `MemoryRepositoryProtocol`, pas de l'implémentation concrète `MemoryRepository`.

## Tests avec Injection de Dépendances

L'un des avantages majeurs de cette approche est la facilité à remplacer les dépendances pendant les tests, comme illustré dans `api/tests/test_memory_routes.py` :

```python
# Fixture pour l'application FastAPI avec dépendances remplacées
@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(memory_router)
    
    # Créer une instance de notre mock repository
    mock_repo = MockMemoryRepository()
    
    # Remplacer la dépendance avec notre mock
    app.dependency_overrides[get_memory_repository] = lambda: mock_repo
    
    return app, mock_repo
```

Ici, nous remplaçons l'implémentation concrète du repository par un mock pour les tests, ce qui nous permet de tester les routes sans dépendre d'une base de données réelle.

## Conclusion

L'application du Principe d'Inversion de Dépendances dans MnemoLite nous permet de créer une architecture plus modulaire, testable et évolutive. Les composants sont découplés, ce qui facilite les changements et l'évolution du système au fil du temps. 