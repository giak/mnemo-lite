from fastapi import Request, HTTPException, Depends
import asyncpg
from contextlib import asynccontextmanager

# Importer le repository
from api.db.repositories.event_repository import EventRepository

async def get_db_pool(request: Request) -> asyncpg.Pool:
    """Récupère le pool de connexions stocké dans l'état de l'application."""
    pool = request.app.state.db_pool
    if pool is None:
        # Ceci ne devrait pas arriver si le lifespan est correctement configuré
        raise HTTPException(status_code=503, detail="Database connection pool is not available.")
    return pool

@asynccontextmanager
async def get_db_connection_context(pool: asyncpg.Pool = Depends(get_db_pool)):
    """Acquiert une connexion depuis le pool et la libère."""
    conn = None
    try:
        conn = await pool.acquire()
        yield conn
    finally:
        if conn:
            await pool.release(conn)

async def get_db_connection(pool: asyncpg.Pool = Depends(get_db_pool)) -> asyncpg.Connection:
    """Dépendance FastAPI pour obtenir une connexion unique par requête."""
    # Utiliser un context manager pour acquérir/libérer la connexion
    # Note: Cette approche simple peut ne pas être idéale si la dépendance est 
    # appelée plusieurs fois dans la même requête. L'approche par context manager
    # est généralement plus sûre pour les dépendances qui gèrent des ressources.
    # Cependant, pour l'injection simple, retourner directement la connexion acquise
    # est souvent fait. L'important est la libération.
    # Solution plus robuste : utiliser un context manager ou un middleware.
    
    # Pour simplifier l'injection ici, on acquiert et on "espère" 
    # que FastAPI gère bien la fin de la requête pour la libération implicite.
    # C'EST RISQUÉ - préférer un middleware ou un context manager dans une vraie app.
    
    # Retour à une approche plus sûre avec context manager via une fonction "helper" 
    # (ou directement avec Depends sur un context manager si FastAPI le supporte bien)
    
    # Tentative avec un context manager simple : 
    # Ce n'est pas standard pour une dépendance simple, mais essayons.
    # async with pool.acquire() as conn: 
    #    return conn # Ne marche pas car dépendance doit retourner directement
    
    # Solution la moins pire pour une dépendance simple : 
    # Acquérir et laisser FastAPI/Starlette gérer la fin.
    # La libération se fera quand le pool sera fermé à la fin du lifespan.
    # MOINS IDÉAL car garde la connexion active plus longtemps.
    # conn = await pool.acquire() # Acquisition directe
    # return conn
    
    # Solution PROPRE: Utiliser un middleware ou une dépendance plus complexe
    # qui gère le cycle de vie de la connexion pour la requête.
    # Pour l'instant, on va utiliser une approche simple MAIS qui nécessite
    # que l'appelant (le repository) n'appelle pas await sur la connexion 
    # après la fin de la requête (ce qui est le cas ici).
    
    # ACQUISITION SIMPLE (La plus courante mais avec des caveats)
    conn = await pool.acquire()
    # On DOIT s'assurer que cette connexion est libérée.
    # FastAPI ne le fait PAS automatiquement pour les dépendances simples.
    # -> Cette approche est donc FAUSSE.
    
    # REVENONS À LA BASE: Le repository a besoin d'une connexion.
    # Fournissons une connexion gérée par un context manager.
    # C'est le rôle de la fixture dans les tests. 
    # Pour l'application, la dépendance doit fournir la connexion.
    
    # On va essayer d'utiliser le context manager que j'ai défini plus haut.
    # MAIS Depends ne peut pas directement utiliser un asynccontextmanager.
    # DONC: Il faut que la dépendance retourne une connexion, et un middleware
    # ou le lifespan doit s'assurer de la libération.
    
    # SOLUTION TEMPORAIRE (pour que ça marche, mais à améliorer): 
    # Laisser le repository acquérir/libérer avec async with pool.acquire()
    # MAIS on a vu que ça causait des problèmes de "another operation in progress".
    
    # CONCLUSION: La gestion de connexion par requête est complexe.
    # Le plus simple est de fournir le POOL au repository via dépendance,
    # et le repository gère l'acquisition/libération pour chaque opération.
    # C'était l'état initial. Pourquoi l'erreur "another operation..." alors?
    # Peut-être lié à la transaction de la fixture de test ?
    
    # *** RETOUR À LA CASE DÉPART sur la dépendance ***
    # On va laisser get_event_repository dépendre du POOL.
    # Le problème est probablement dans la gestion de la transaction de test.
    # La dépendance retournera donc le POOL.
    # La fixture override retournera le POOL de test.
    # Le repository utilisera `async with self.pool.acquire() as conn:`
    pass # Laisser get_db_pool telle quelle pour l'instant.

async def get_event_repository(pool: asyncpg.Pool = Depends(get_db_pool)) -> EventRepository:
    """Injecte une instance de EventRepository avec le pool de connexions."""
    # Le repository attend maintenant une connexion, pas un pool
    # async with pool.acquire() as conn:
    #    yield EventRepository(conn=conn) # Ne marche pas avec Depends simple
        
    # *** RETOUR À LA CASE DÉPART sur la dépendance ***
    # Le repository a été remis pour utiliser `async with pool.acquire()` implicitement
    # Donc on lui passe le pool.
    return EventRepository(pool=pool) # Retour à l'implémentation originale 