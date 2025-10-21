"""
Circuit breaker configuration.

Centralized configuration for all circuit breakers in the application.

Author: Claude Code
Created: 2025-10-21
Epic: EPIC-12 Story 12.3
"""

from dataclasses import dataclass
import os


@dataclass
class ServiceCircuitConfig:
    """Configuration for a specific service's circuit breaker."""
    failure_threshold: int
    recovery_timeout: int
    half_open_max_calls: int = 1


# Redis Cache Circuit Breaker
REDIS_CIRCUIT_CONFIG = ServiceCircuitConfig(
    failure_threshold=int(os.getenv("REDIS_CIRCUIT_FAILURE_THRESHOLD", "5")),
    recovery_timeout=int(os.getenv("REDIS_CIRCUIT_RECOVERY_TIMEOUT", "30")),
    half_open_max_calls=int(os.getenv("REDIS_CIRCUIT_HALF_OPEN_CALLS", "1"))
)

# Embedding Service Circuit Breaker
EMBEDDING_CIRCUIT_CONFIG = ServiceCircuitConfig(
    failure_threshold=int(os.getenv("EMBEDDING_CIRCUIT_FAILURE_THRESHOLD", "3")),
    recovery_timeout=int(os.getenv("EMBEDDING_CIRCUIT_RECOVERY_TIMEOUT", "60")),
    half_open_max_calls=int(os.getenv("EMBEDDING_CIRCUIT_HALF_OPEN_CALLS", "1"))
)

# PostgreSQL Circuit Breaker (for health checks only)
DATABASE_CIRCUIT_CONFIG = ServiceCircuitConfig(
    failure_threshold=int(os.getenv("DATABASE_CIRCUIT_FAILURE_THRESHOLD", "3")),
    recovery_timeout=int(os.getenv("DATABASE_CIRCUIT_RECOVERY_TIMEOUT", "10")),
    half_open_max_calls=int(os.getenv("DATABASE_CIRCUIT_HALF_OPEN_CALLS", "1"))
)
