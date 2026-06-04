import os
import json
import numpy as np
from redis import Redis
from sentence_transformers import SentenceTransformer
from typing import Optional

class PrivacyAwareCache:
    def __init__(self, redis_host="localhost", redis_port=6379, threshold=0.75):
        # Initialize connection to local Redis Stack
        self.redis_client = Redis(host=redis_host, port=redis_port, decode_responses=False)
        self.threshold = threshold
        
        # Load a local model so confidential data never leaves the VPC for embedding
        print("Loading local embedding model...")
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        self.vector_dim = 384 

    def _generate_embedding(self, text: str) -> np.ndarray:
        """Generates embeddings strictly on local hardware."""
        return self.encoder.encode(text).astype(np.float32)

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculates mathematical similarity between two vectors."""
        dot_product = np.dot(vec1, vec2)
        norm_a = np.linalg.norm(vec1)
        norm_b = np.linalg.norm(vec2)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)

    def check_cache(self, user_prompt: str) -> Optional[str]:
        """
        Scans local Redis for a semantically similar query.
        Returns the cached response if similarity exceeds the threshold.
        """
        query_vector = self._generate_embedding(user_prompt)
        
        # In a production environment, this uses RediSearch. 
        # For this MVP, we do a raw key scan for demonstration.
        keys = self.redis_client.keys("aegis:cache:*")
        
        best_match = None
        highest_score = 0.0
        
        for key in keys:
            cached_data = json.loads(self.redis_client.get(key).decode('utf-8'))
            cached_vector = np.array(cached_data['embedding'], dtype=np.float32)
            
            score = self._cosine_similarity(query_vector, cached_vector)

            print(f"  [DEBUG] Compared against '{cached_data['prompt']}' | Score: {score:.2f}")
            
            if score > highest_score and score >= self.threshold:
                highest_score = score
                best_match = cached_data['response']
                
        if best_match:
            print(f"[CACHE HIT] Similarity Score: {highest_score:.2f} - Preventing external API call.")
        return best_match

    def store_cache(self, user_prompt: str, llm_response: str):
        """Stores the local embedding and response to prevent future external calls."""
        query_vector = self._generate_embedding(user_prompt)
        cache_id = f"aegis:cache:{os.urandom(4).hex()}"
        
        payload = {
            "prompt": user_prompt,
            "embedding": query_vector.tolist(),
            "response": llm_response
        }
        
        self.redis_client.set(cache_id, json.dumps(payload))
        print(f"[CACHE STORED] Saved to {cache_id}")