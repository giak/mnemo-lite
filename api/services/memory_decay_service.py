"""
Memory Decay Service — Temporal relevance scoring.

Applies exponential decay to memory search results based on age.
Recent memories score higher, old unused memories fade naturally.

Formula:
    final_score = relevance_score × temporal_decay(age_days, decay_rate)
    temporal_decay = exp(-decay_rate × age_days)

Decay rate presets (Expanse):
    decay_rate=0.001  → sys:core, sys:anchor (months of relevance)
    decay_rate=0.002  → sys:protocol (~1 year, operational rules)
    decay_rate=0.005  → sys:pattern, sys:user:profile (weeks of relevance)
    decay_rate=0.01   → sys:extension, sys:project (default, moderate decay)
    decay_rate=0.02   → sys:drift (35 days)
    decay_rate=0.05   → sys:history (days of relevance)
    decay_rate=0.08   → sys:trace (~9 days, agent execution traces)
    decay_rate=0.1    → ephemeral (hours of relevance)

Usage:
    from services.memory_decay_service import MemoryDecayService

    service = MemoryDecayService()
    decayed_score = service.apply_decay(
        relevance_score=0.85,
        created_at=datetime(2026, 3, 20),
        decay_rate=0.01
    )
"""

import math
import logging
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

# Decay rate presets for Expanse memory types
DECAY_PRESETS = {
    "sys:core": 0.001,       # ~2 years half-life
    "sys:anchor": 0.001,     # ~2 years half-life
    "sys:pattern": 0.005,    # ~140 days half-life
    "sys:protocol": 0.002,   # ~1 year half-life (operational rules)
    "sys:extension": 0.01,   # ~70 days half-life (default)
    "sys:project": 0.01,     # ~70 days half-life
    "sys:user:profile": 0.005,  # ~140 days half-life
    "sys:history": 0.05,     # ~14 days half-life
    "sys:drift": 0.02,       # ~35 days half-life
    "sys:trace": 0.08,       # ~9 days half-life (agent execution traces)
    "ephemeral": 0.1,        # ~7 days half-life
}

DEFAULT_DECAY_RATE = 0.01  # ~70 days half-life


class MemoryDecayService:
    """
    Temporal decay scoring for memory search results.

    Applies exponential decay based on memory age to prioritize
    recent and relevant memories over stale ones.
    """

    def __init__(self, default_decay_rate: float = DEFAULT_DECAY_RATE):
        """
        Initialize decay service.

        Args:
            default_decay_rate: Default decay rate (0.01 = ~70 days half-life)
        """
        self.default_decay_rate = default_decay_rate

    def compute_decay(
        self,
        age_days: float,
        decay_rate: Optional[float] = None,
    ) -> float:
        """
        Compute temporal decay factor.

        Args:
            age_days: Age of the memory in days
            decay_rate: Decay rate override (uses default if None)

        Returns:
            Decay factor between 0.0 and 1.0
            1.0 = just created, approaches 0.0 = very old

        Examples:
            >>> service = MemoryDecayService()
            >>> service.compute_decay(age_days=0)       # Just created
            1.0
            >>> service.compute_decay(age_days=70)      # 70 days (half-life at 0.01)
            0.496...
            >>> service.compute_decay(age_days=365)     # 1 year
            0.025...
        """
        rate = decay_rate if decay_rate is not None else self.default_decay_rate

        if rate <= 0:
            return 1.0  # No decay

        if age_days < 0:
            return 1.0  # Future date, no decay

        return math.exp(-rate * age_days)

    def apply_decay(
        self,
        relevance_score: float,
        created_at: datetime,
        decay_rate: Optional[float] = None,
        now: Optional[datetime] = None,
    ) -> float:
        """
        Apply temporal decay to a relevance score.

        Args:
            relevance_score: Original relevance score (0.0 to 1.0)
            created_at: When the memory was created
            decay_rate: Decay rate override
            now: Current time (defaults to utcnow)

        Returns:
            Decay-adjusted score
        """
        if now is None:
            now = datetime.now(timezone.utc)

        # Ensure both are timezone-aware
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        age_seconds = (now - created_at).total_seconds()
        age_days = max(0, age_seconds / 86400)

        decay = self.compute_decay(age_days, decay_rate)
        return relevance_score * decay

    def apply_decay_to_results(
        self,
        results: list,
        score_field: str = "rrf_score",
        time_field: str = "created_at",
        decay_rate: Optional[float] = None,
        tag_based_decay: bool = True,
    ) -> list:
        """
        Apply decay to a list of search results and re-sort.

        Args:
            results: List of result objects with score and time fields
            score_field: Name of the score attribute
            time_field: Name of the timestamp attribute (string ISO format)
            decay_rate: Fixed decay rate, or None for tag-based
            tag_based_decay: If True, infer decay_rate from tags

        Returns:
            Results sorted by decay-adjusted score (descending)
        """
        now = datetime.now(timezone.utc)

        for result in results:
            score = getattr(result, score_field, 0)
            time_str = getattr(result, time_field, None)

            if not time_str or not score:
                continue

            # Parse timestamp
            try:
                if isinstance(time_str, str):
                    created_at = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                else:
                    created_at = time_str
            except (ValueError, AttributeError):
                continue

            # Determine decay rate
            rate = decay_rate
            if rate is None and tag_based_decay:
                rate = self._get_decay_rate_from_tags(result)

            # Apply decay
            decayed_score = self.apply_decay(score, created_at, decay_rate=rate, now=now)

            # Update score
            setattr(result, score_field, decayed_score)

        # Re-sort by decayed score
        results.sort(key=lambda r: getattr(r, score_field, 0), reverse=True)

        # Update ranks
        for i, result in enumerate(results):
            if hasattr(result, "rank"):
                result.rank = i + 1

        return results

    def _get_decay_rate_from_tags(self, result) -> float:
        """Infer decay rate from memory tags."""
        tags = getattr(result, "tags", [])
        if not tags:
            return self.default_decay_rate

        # Find the most specific decay preset matching any tag
        for tag in tags:
            if tag in DECAY_PRESETS:
                return DECAY_PRESETS[tag]

        return self.default_decay_rate

    @staticmethod
    def half_life(decay_rate: float) -> float:
        """
        Calculate half-life in days for a given decay rate.

        Args:
            decay_rate: Exponential decay rate

        Returns:
            Days until score halves

        Examples:
            >>> MemoryDecayService.half_life(0.01)
            69.3...
            >>> MemoryDecayService.half_life(0.001)
            693.1...
        """
        if decay_rate <= 0:
            return float("inf")
        return math.log(2) / decay_rate
