import os
import json
import logging
import numpy as np
from redis import Redis
from redis.exceptions import RedisError
from sentence_transformers import SentenceTransformer
from typing import Optional

logger = logging.getLogger(__name__)

CACHE_PREFIX = "aws:cache:"
CACHE_TTL_SECONDS = 86400


class PrivacyAwareCache:
    def __init__(self, redis_host="localhost", redis_port=6379, threshold=0.75):
        # Bounded timeouts so a slow or unreachable Redis degrades to a cache miss
        # instead of hanging the request path.
        self.redis_client = Redis(
            host=redis_host,
            port=redis_port,
            decode_responses=False,
            socket_timeout=2,
            socket_connect_timeout=2,
        )
        self.threshold = threshold

        # Load a local model so confidential data never leaves the VPC for embedding.
        logger.info("Loading local embedding model...")
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        self.vector_dim = 384

    def _generate_embedding(self, text: str) -> np.ndarray:
        """Generates embeddings strictly on local hardware."""
        return self.encoder.encode(text).astype(np.float32)

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculates cosine similarity between two vectors."""
        norm_a = np.linalg.norm(vec1)
        norm_b = np.linalg.norm(vec2)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(vec1, vec2) / (norm_a * norm_b))

    def check_cache(self, user_prompt: str) -> Optional[str]:
        """
        Scans local Redis for a semantically similar query and returns the cached
        response when similarity exceeds the threshold. On any Redis error this
        returns None so the caller falls back to a live execution.

        Note: this MVP iterates keys with a non-blocking SCAN. A production
        deployment should index the embeddings with RediSearch and issue a
        server-side KNN query instead of pulling every vector to the client.
        """
        try:
            query_vector = self._generate_embedding(user_prompt)

            best_match = None
            highest_score = 0.0

            # SCAN is cursor-based and non-blocking, unlike KEYS which blocks the entire Redis event loop for the duration of the scan.
            for key in self.redis_client.scan_iter(match=f"{CACHE_PREFIX}*", count=100):
                raw = self.redis_client.get(key)
                if raw is None:
                    continue
                cached_data = json.loads(raw.decode('utf-8'))
                cached_vector = np.asarray(cached_data['embedding'], dtype=np.float32)

                score = self._cosine_similarity(query_vector, cached_vector)
                if score > highest_score and score >= self.threshold:
                    highest_score = score
                    best_match = cached_data['response']

            if best_match is not None:
                logger.info(f"[CACHE HIT] Similarity {highest_score:.2f} - skipping the live query.")
            return best_match

        except RedisError as e:
            logger.warning(f"Cache lookup failed, falling back to live execution: {e}")
            return None

    def store_cache(self, user_prompt: str, llm_response: str) -> None:
        """Stores the local embedding and response to prevent re-running the live query."""
        try:
            # Don't store a near-duplicate of something already cached.
            if self.check_cache(user_prompt) is not None:
                return

            query_vector = self._generate_embedding(user_prompt)
            cache_id = f"{CACHE_PREFIX}{os.urandom(4).hex()}"

            payload = {
                "prompt": user_prompt,
                "embedding": query_vector.tolist(),
                "response": llm_response,
            }

            self.redis_client.set(cache_id, json.dumps(payload), ex=CACHE_TTL_SECONDS)
            logger.info(f"[CACHE STORED] Saved to {cache_id}")
        except RedisError as e:
            logger.warning(f"Cache store failed (continuing without caching): {e}")
