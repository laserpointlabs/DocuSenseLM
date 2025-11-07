from __future__ import annotations

from typing import List
import hashlib


class DeterministicEmbedder:
    """
    Lightweight embedder for tests.
    Encodes text into fixed-length vectors using hashed token counts.
    """

    def __init__(self, dimension: int = 32):
        self.dimension = dimension

    def embed_text(self, text: str) -> List[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        vectors: List[List[float]] = []
        for text in texts:
            vector = [0.0] * self.dimension
            if text:
                for token in text.split():
                    token = token.lower()
                    digest = hashlib.sha256(token.encode("utf-8")).digest()
                    idx = digest[0] % self.dimension
                    vector[idx] += 1.0
            length = sum(x * x for x in vector) ** 0.5 or 1.0
            vectors.append([x / length for x in vector])
        return vectors

    def get_dimension(self) -> int:
        return self.dimension

