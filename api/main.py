import os
import json
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

# Import des routes
from routes import memory_routes, search_routes, health_routes

# Configuration de base
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialisation au démarrage
    print(f"Starting MnemoLite API in {ENVIRONMENT} mode")
    
    # Nettoyage à l'arrêt
    yield
    print("Shutting down MnemoLite API")


# Création de l'application
app = FastAPI(
    title="MnemoLite API",
    description="API pour la gestion de la mémoire vectorielle",
    version="0.1.0",
    debug=DEBUG,
    lifespan=lifespan
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if DEBUG else ["https://app.mnemolite.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Enregistrement des routes
app.include_router(memory_routes.router, prefix="/memories", tags=["memories"])
app.include_router(search_routes.router, prefix="/search", tags=["search"])
app.include_router(health_routes.router, tags=["health"])


@app.get("/")
async def root():
    return {
        "name": "MnemoLite API",
        "version": "0.1.0",
        "status": "operational",
        "environment": ENVIRONMENT
    }


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": str(exc) if DEBUG else "An error occurred processing your request"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=DEBUG) 