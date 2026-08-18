import time
import math
from typing import Any, Dict, List, Optional, Tuple
import structlog

from backend.core.config import settings

logger = structlog.get_logger(__name__)

# Global in-memory cache fallback store for high-similarity vector lookups
_CACHE_STORE: List[Dict[str, Any]] = []


SYNONYMS = {
    "corp": "corporation",
    "inc": "incorporated",
    "ltd": "limited",
    "co": "company",
    "&": "and",
}


def _text_to_vector(text: str) -> Dict[str, float]:
    """Term-frequency vector representation with synonym normalization for high-precision similarity matching."""
    raw_words = [w.lower().strip(".,!?\"'()") for w in text.split() if len(w) > 0]
    words = [SYNONYMS.get(w, w) for w in raw_words if len(SYNONYMS.get(w, w)) > 1]
    vec: Dict[str, float] = {}
    for w in words:
        vec[w] = vec.get(w, 0.0) + 1.0
    norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
    return {k: v / norm for k, v in vec.items()}


def _cosine_similarity(vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
    """Compute cosine similarity between two vector representations (0.0 to 1.0 scale)."""
    dot_product = sum(v * vec2.get(k, 0.0) for k, v in vec1.items())
    return round(dot_product, 4)


class SemanticCacheManager:
    """
    High-Similarity Redis & In-Memory Vector Semantic Cache Manager
    Caches LLM and query responses, bypassing redundant executions for queries with similarity > 0.98.
    """

    def __init__(self, default_ttl: int = 3600, default_threshold: float = 0.98):
        self.default_ttl = default_ttl
        self.default_threshold = default_threshold
        self.redis_url = getattr(settings, "REDIS_URL", None)

    @classmethod
    def get_cached_query(
        cls,
        query: str,
        threshold: float = 0.98,
        ttl_seconds: int = 3600,
    ) -> Optional[Dict[str, Any]]:
        """
        Check semantic cache for a historical query with cosine similarity > threshold.
        Returns cached payload if found and TTL has not expired.
        """
        current_time = time.time()
        query_vec = _text_to_vector(query)

        best_match: Optional[Dict[str, Any]] = None
        best_similarity = 0.0

        for entry in _CACHE_STORE:
            # Check TTL expiration
            if current_time - entry["timestamp"] > entry.get("ttl", ttl_seconds):
                continue

            sim = _cosine_similarity(query_vec, entry["vector"])
            if sim > best_similarity:
                best_similarity = sim
                best_match = entry

        if best_match and best_similarity >= threshold:
            logger.info(
                "semantic_cache_hit",
                query=query,
                matched_query=best_match["query"],
                similarity=best_similarity,
                threshold=threshold,
            )
            return best_match["payload"]

        logger.info("semantic_cache_miss", query=query, highest_similarity=best_similarity)
        return None

    @classmethod
    def set_cached_query(
        cls,
        query: str,
        payload: Dict[str, Any],
        ttl_seconds: int = 3600,
    ):
        """Store query vector and payload in semantic cache with specified TTL."""
        query_vec = _text_to_vector(query)

        _CACHE_STORE.append(
            {
                "query": query,
                "vector": query_vec,
                "payload": payload,
                "timestamp": time.time(),
                "ttl": ttl_seconds,
            }
        )
        logger.info("semantic_cache_entry_stored", query=query, ttl=ttl_seconds)

    @classmethod
    def clear_cache(cls):
        """Clear cached entries for testing."""
        global _CACHE_STORE
        _CACHE_STORE.clear()
