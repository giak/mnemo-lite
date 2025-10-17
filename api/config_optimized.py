"""
Optimized configuration for MnemoLite API.
Performance-tuned settings for production workloads.
"""

import os
from typing import Dict, Any


def get_optimized_db_config(environment: str = "production") -> Dict[str, Any]:
    """
    Get optimized database configuration based on environment.

    Args:
        environment: Current environment (development/test/production)

    Returns:
        Dictionary with SQLAlchemy engine configuration
    """
    # Base configuration
    base_config = {
        "future": True,
        "pool_recycle": 3600,  # Recycle connections after 1 hour
        "echo": False,  # Never log SQL in production
    }

    # Environment-specific configurations
    if environment == "production":
        return {
            **base_config,
            "pool_size": 20,  # Increased for production load
            "max_overflow": 10,  # Allow more overflow connections
            "pool_pre_ping": True,  # Check connections before use
            "pool_timeout": 30,  # Wait up to 30s for connection
            "connect_args": {
                "server_settings": {
                    "application_name": "mnemolite_prod",
                    "jit": "off",  # Disable JIT for consistent performance
                    "statement_timeout": "30s",  # Kill long queries
                    "idle_in_transaction_session_timeout": "60s",
                },
                "command_timeout": 30,
                "prepared_statement_cache_size": 0,  # Avoid pgbouncer issues
                "tcp_keepalives_idle": "120",
                "tcp_keepalives_interval": "30",
                "tcp_keepalives_count": "3",
            }
        }

    elif environment == "test":
        return {
            **base_config,
            "pool_size": 5,  # Smaller pool for tests
            "max_overflow": 2,
            "pool_pre_ping": False,  # Not needed for tests
            "connect_args": {
                "server_settings": {
                    "application_name": "mnemolite_test",
                    "jit": "off",
                },
                "command_timeout": 10,
            }
        }

    else:  # development
        return {
            **base_config,
            "pool_size": 10,  # Moderate pool for development
            "max_overflow": 5,
            "pool_pre_ping": False,
            "echo": os.getenv("DEBUG", "False").lower() == "true",
            "connect_args": {
                "server_settings": {
                    "application_name": "mnemolite_dev",
                    "jit": "off",
                },
                "command_timeout": 60,
            }
        }


def get_cache_config(environment: str = "production") -> Dict[str, Any]:
    """
    Get cache configuration based on environment.

    Args:
        environment: Current environment

    Returns:
        Dictionary with cache configuration
    """
    if environment == "production":
        return {
            "event_cache": {
                "ttl_seconds": 60,
                "max_items": 1000,
            },
            "search_cache": {
                "ttl_seconds": 30,
                "max_items": 500,
            },
            "graph_cache": {
                "ttl_seconds": 120,
                "max_items": 200,
            }
        }
    else:
        # Shorter TTL for development/test
        return {
            "event_cache": {
                "ttl_seconds": 10,
                "max_items": 100,
            },
            "search_cache": {
                "ttl_seconds": 5,
                "max_items": 50,
            },
            "graph_cache": {
                "ttl_seconds": 20,
                "max_items": 20,
            }
        }


def get_performance_config(environment: str = "production") -> Dict[str, Any]:
    """
    Get performance-related configuration.

    Args:
        environment: Current environment

    Returns:
        Dictionary with performance settings
    """
    return {
        "batch_size": 100 if environment == "production" else 10,
        "max_concurrent_requests": 100 if environment == "production" else 20,
        "request_timeout": 30 if environment == "production" else 60,
        "enable_profiling": environment == "development",
        "enable_metrics": environment in ["production", "test"],
    }