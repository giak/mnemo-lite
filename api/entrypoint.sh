#!/bin/sh
set -e

# Default to development environment if ENVIRONMENT is not set
: ${ENVIRONMENT:=development}
# Use default DB URL if not test environment
DEFAULT_DATABASE_URL="postgresql://${POSTGRES_USER:-mnemo}:${POSTGRES_PASSWORD:-changeme}@db:5432/${POSTGRES_DB:-mnemolite}"

echo "Starting application in $ENVIRONMENT environment"

if [ "$ENVIRONMENT" = "test" ]; then
  echo "Using TEST_DATABASE_URL: $TEST_DATABASE_URL"
  export DATABASE_URL="$TEST_DATABASE_URL"
elif [ -z "$DATABASE_URL" ]; then
  # Only set default if DATABASE_URL isn't already set (e.g., from docker compose env)
  echo "Using default DATABASE_URL: $DEFAULT_DATABASE_URL"
  export DATABASE_URL="$DEFAULT_DATABASE_URL"
else
  echo "Using provided DATABASE_URL: $DATABASE_URL"
  # If DATABASE_URL is already set (e.g. via docker-compose environment), keep it.
fi

# Execute the command passed to the entrypoint (e.g., uvicorn...)
exec "$@" 