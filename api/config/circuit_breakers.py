"""
Circuit breaker configuration.

Centralized configuration for all circuit breakers in the application.

Author: Claude Code
Created: 2025-10-21
Epic: EPIC-12 Story 12.3
"""

from dataclasses import dataclass

from api.core.settings import get_settings


@dataclass
class ServiceCircuitConfig:
    """Configuration for a specific service's circuit breaker."""
    failure_threshold: int
    recovery_timeout: int
    half_open_max_calls: int = 1


def _load_circuit_configs() -> tuple:
    """Load circuit breaker configs from AppSettings (centralized config)."""
    s = get_settings()
    return (
        ServiceCircuitConfig(
            failure_threshold=s.REDIS_CIRCUIT_FAILURE_THRESHOLD,
            recovery_timeout=s.REDIS_CIRCUIT_RECOVERY_TIMEOUT,
            half_open_max_calls=s.REDIS_CIRCUIT_HALF_OPEN_CALLS,
        ),
        ServiceCircuitConfig(
            failure_threshold=s.EMBEDDING_CIRCUIT_FAILURE_THRESHOLD,
            recovery_timeout=s.EMBEDDING_CIRCUIT_RECOVERY_TIMEOUT,
            half_open_max_calls=s.EMBEDDING_CIRCUIT_HALF_OPEN_CALLS,
        ),
        ServiceCircuitConfig(
            failure_threshold=s.DATABASE_CIRCUIT_FAILURE_THRESHOLD,
            recovery_timeout=s.DATABASE_CIRCUIT_RECOVERY_TIMEOUT,
            half_open_max_calls=s.DATABASE_CIRCUIT_HALF_OPEN_CALLS,
        ),
    )


REDIS_CIRCUIT_CONFIG, EMBEDDING_CIRCUIT_CONFIG, DATABASE_CIRCUIT_CONFIG = _load_circuit_configs()
