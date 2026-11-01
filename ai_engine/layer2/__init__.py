"""
Layer 2 - Semantic Similarity-Based Prompt Injection Detection
"""
from .detector import is_danger_l2, Layer2Result, get_detector_resources
from .embedder import generate_embedding, get_embedding_model
from .indexer import load_or_create_index, build_index_from_csv
from .config import DEFAULT_SIMILARITY_THRESHOLD, DEFAULT_TOP_K

__all__ = [
    "is_danger_l2",
    "Layer2Result",
    "get_detector_resources",
    "generate_embedding",
    "get_embedding_model",
    "load_or_create_index",
    "build_index_from_csv",
    "DEFAULT_SIMILARITY_THRESHOLD",
    "DEFAULT_TOP_K",
]

