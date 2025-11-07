"""
768-dim embedding generation using sentence-transformers/all-mpnet-base-v2
"""
from typing import List
import os

from sentence_transformers import SentenceTransformer
import torch

from api.services.service_registry import (
    get_embedder_service,
    register_embedder_service,
)


class Embedder:
    """Generate 768-dimensional embeddings for text chunks"""

    def __init__(self, model_name: str = "sentence-transformers/all-mpnet-base-v2"):
        """
        Initialize embedder with specified model

        Args:
            model_name: Name of the sentence transformer model
        """
        self.model_name = model_name
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'

        print(f"Loading embedding model: {model_name} on {self.device}")
        self.model = SentenceTransformer(model_name, device=self.device)

        # Verify dimension
        test_embedding = self.model.encode("test", convert_to_numpy=True)
        self.dimension = len(test_embedding)
        print(f"Embedding dimension: {self.dimension}")

        if self.dimension != 768:
            print(f"Warning: Expected 768 dimensions, got {self.dimension}")

    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text

        Args:
            text: Text to embed

        Returns:
            List of 768 float values
        """
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_batch(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        Generate embeddings for a batch of texts

        Args:
            texts: List of texts to embed
            batch_size: Batch size for processing

        Returns:
            List of embeddings (each is a list of 768 floats)
        """
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            show_progress_bar=len(texts) > 100
        )
        return embeddings.tolist()

    def get_dimension(self) -> int:
        """Get embedding dimension"""
        return self.dimension


# Singleton embedder instance
_embedder_instance = None

def _embedder_factory() -> Embedder:
    global _embedder_instance
    if _embedder_instance is None:
        model_name = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-mpnet-base-v2")
        _embedder_instance = Embedder(model_name)
    return _embedder_instance


register_embedder_service(_embedder_factory)


def get_embedder() -> Embedder:
    """Resolve the active embedder implementation through the service registry."""
    return get_embedder_service()
