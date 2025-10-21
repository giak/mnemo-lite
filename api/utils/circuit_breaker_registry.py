"""
Circuit Breaker Registry for health monitoring.

Centralized registry to avoid circular imports.

Author: Claude Code
Created: 2025-10-21
Epic: EPIC-12 Story 12.3
"""

from typing import Dict, Any


# Global registry for circuit breakers
_circuit_breakers: Dict[str, Any] = {}


def register_circuit_breaker(breaker: Any) -> None:
    """
    Register circuit breaker for health monitoring.

    Args:
        breaker: Circuit breaker instance to register
    """
    _circuit_breakers[breaker.name] = breaker


def get_circuit_breaker_metrics() -> Dict[str, Any]:
    """
    Get metrics for all registered circuit breakers.

    Returns:
        Dict mapping service names to circuit breaker metrics
    """
    return {
        name: breaker.get_metrics()
        for name, breaker in _circuit_breakers.items()
    }
