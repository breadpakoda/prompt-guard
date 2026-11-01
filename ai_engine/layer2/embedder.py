"""
Embedding generation module for Layer 2.
Loads and caches the SentenceTransformer model (all-MiniLM-L12-v2),
ensuring embeddings are generated identically to the precomputed dataset embeddings.
"""
from typing import Optional, List, Union
import numpy as np
from sentence_transformers import SentenceTransformer
from .config import EMBEDDING_MODEL_NAME

_model_instance: Optional[SentenceTransformer] = None


def get_embedding_model(model_name: str = EMBEDDING_MODEL_NAME) -> SentenceTransformer:
    """
    Returns the cached SentenceTransformer singleton instance.
    Loads from disk/cache on the first invocation.
    """
    global _model_instance
    if _model_instance is None:
        _model_instance = SentenceTransformer(model_name)
    return _model_instance


def generate_embedding(
    text: Union[str, List[str]],
    normalize: bool = True
) -> np.ndarray:
    """
    Generates normalized float32 embedding(s) for input text(s).

    Args:
        text: A single string prompt or a list of prompt strings.
        normalize: Whether to L2-normalize vectors (required for cosine similarity).

    Returns:
        np.ndarray of shape (N, 384) with dtype float32.
    """
    model = get_embedding_model()
    if isinstance(text, str):
        text = [text]

    embeddings = model.encode(text, normalize_embeddings=normalize)
    return np.asarray(embeddings, dtype=np.float32)

