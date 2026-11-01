"""
Main Layer 2 detection module.
Exposes is_danger_l2(user_prompt) for semantic similarity prompt injection detection.
"""
from typing import Optional, Dict, Any, List, Union
import numpy as np
import faiss

from .config import DEFAULT_SIMILARITY_THRESHOLD, DEFAULT_TOP_K
from .embedder import generate_embedding
from .indexer import load_or_create_index

# Global cache for single-load lifecycle
_cached_index: Optional[faiss.IndexFlatIP] = None
_cached_metadata: Optional[List[Dict[str, Any]]] = None


class Layer2Result(dict):
    """
    Subclass of dict providing easy access to results:
    - Dict key access: res["is_malicious"], res["similarity_score"]
    - Attribute access: res.is_malicious, res.similarity_score
    - Boolean evaluation: `if res: ...` or `if is_danger_l2(p): ...`
    """

    @property
    def is_malicious(self) -> bool:
        """True if similarity score >= threshold, False otherwise."""
        return bool(self.get("is_malicious", False))

    @property
    def similarity_score(self) -> float:
        """Highest cosine similarity score found against known malicious prompts."""
        return float(self.get("similarity_score", 0.0))

    @property
    def matched_prompt(self) -> Optional[str]:
        """Closest matching malicious prompt from the dataset."""
        return self.get("matched_prompt")

    def __bool__(self) -> bool:
        return self.is_malicious

    def __repr__(self) -> str:
        status = "MALICIOUS" if self.is_malicious else "BENIGN"
        return (
            f"Layer2Result(is_malicious={self.is_malicious} [{status}], "
            f"similarity_score={self.similarity_score:.4f}, "
            f"threshold={self.get('threshold', 0.0):.2f})"
        )


def get_detector_resources() -> tuple[faiss.IndexFlatIP, List[Dict[str, Any]]]:
    """
    Retrieves or lazily initializes the cached FAISS index and prompt metadata.
    """
    global _cached_index, _cached_metadata
    if _cached_index is None or _cached_metadata is None:
        _cached_index, _cached_metadata = load_or_create_index()
    return _cached_index, _cached_metadata


def is_danger_l2(
    user_prompt: str,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    top_k: int = DEFAULT_TOP_K
) -> Layer2Result:
    """
    Classify whether a user prompt is an attack / jailbreak by calculating semantic
    cosine similarity against the stored index of known malicious prompts.

    Args:
        user_prompt: The prompt text to inspect.
        threshold: Cosine similarity cutoff (default: 0.50). Prompts with a similarity
                   score >= threshold are flagged as malicious.
        top_k: Number of closest matching malicious prompts to retrieve.

    Returns:
        Layer2Result (dict subclass) containing:
        {
            "is_malicious": bool,
            "similarity_score": float,
            "threshold": float,
            "matched_prompt": Optional[str],
            "top_matches": List[dict]
        }
    """
    # Guard against empty, blank, or non-string inputs
    if not user_prompt or not isinstance(user_prompt, str) or not user_prompt.strip():
        return Layer2Result({
            "is_malicious": False,
            "similarity_score": 0.0,
            "threshold": threshold,
            "matched_prompt": None,
            "top_matches": []
        })

    index, metadata = get_detector_resources()

    # Generate normalized embedding using all-MiniLM-L12-v2
    query_vector = generate_embedding(user_prompt.strip(), normalize=True)

    # Perform top-k vector search
    k = max(1, min(top_k, index.ntotal))
    scores, indices = index.search(query_vector, k)

    best_score = float(scores[0][0])
    best_idx = int(indices[0][0])
    closest_prompt = metadata[best_idx]["prompt"] if 0 <= best_idx < len(metadata) else None

    # Compile top matches for debugging and transparency
    top_matches: List[Dict[str, Any]] = []
    for rank in range(k):
        m_idx = int(indices[0][rank])
        m_score = float(scores[0][rank])
        if 0 <= m_idx < len(metadata):
            top_matches.append({
                "rank": rank + 1,
                "similarity_score": m_score,
                "prompt": metadata[m_idx]["prompt"],
                "length": metadata[m_idx].get("length"),
                "perplexity": metadata[m_idx].get("perplexity")
            })

    is_malicious = bool(best_score >= threshold)

    return Layer2Result({
        "is_malicious": is_malicious,
        "similarity_score": best_score,
        "threshold": threshold,
        "matched_prompt": closest_prompt,
        "top_matches": top_matches
    })

