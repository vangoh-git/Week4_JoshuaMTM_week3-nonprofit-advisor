"""
Response Cache — reduces redundant API calls and KB lookups.
Week 4 Production Addition, Lonely Octopus AI Agent Bootcamp

Implements two levels of caching:
1. KB search cache — stores knowledge base query results
2. Synthesis cache — stores full advisory responses for repeated questions

This demonstrates the cost optimization principle from the Week 4
production journey (analogous to OpenAI's Batch API / prompt caching).
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field


@dataclass
class CacheEntry:
    """A cached result with metadata."""
    key: str
    value: object
    created_at: float
    ttl_seconds: int
    hits: int = 0


class ResponseCache:
    """Simple in-memory cache with TTL and hit tracking."""

    def __init__(self, default_ttl: int = 300):
        self._store: dict[str, CacheEntry] = {}
        self.default_ttl = default_ttl
        self.total_hits = 0
        self.total_misses = 0

    def _make_key(self, prefix: str, *parts: str) -> str:
        """Create a deterministic cache key."""
        raw = f"{prefix}:" + "|".join(str(p) for p in parts)
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, key: str) -> object | None:
        """Get a cached value, or None if expired/missing."""
        entry = self._store.get(key)
        if entry is None:
            self.total_misses += 1
            return None

        if time.time() - entry.created_at > entry.ttl_seconds:
            del self._store[key]
            self.total_misses += 1
            return None

        entry.hits += 1
        self.total_hits += 1
        return entry.value

    def set(self, key: str, value: object, ttl: int | None = None):
        """Store a value in the cache."""
        self._store[key] = CacheEntry(
            key=key,
            value=value,
            created_at=time.time(),
            ttl_seconds=ttl or self.default_ttl,
        )

    def kb_key(self, domain: str, query: str, budget_tier: str = "all") -> str:
        """Generate a cache key for knowledge base searches."""
        return self._make_key("kb", domain, query.lower().strip(), budget_tier)

    def synthesis_key(self, question: str, org_name: str) -> str:
        """Generate a cache key for synthesis responses."""
        return self._make_key("synthesis", question.lower().strip(), org_name.lower().strip())

    def get_stats(self) -> dict:
        """Return cache statistics."""
        active = sum(
            1 for e in self._store.values()
            if time.time() - e.created_at <= e.ttl_seconds
        )
        total_requests = self.total_hits + self.total_misses
        hit_rate = (self.total_hits / total_requests * 100) if total_requests > 0 else 0

        return {
            "active_entries": active,
            "total_entries": len(self._store),
            "hits": self.total_hits,
            "misses": self.total_misses,
            "hit_rate": round(hit_rate, 1),
        }

    def clear(self):
        """Clear all cached entries."""
        self._store.clear()
        self.total_hits = 0
        self.total_misses = 0


# Module-level singleton
cache = ResponseCache(default_ttl=300)  # 5-minute default TTL
