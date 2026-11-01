"""
Vector Index creation, local persistence, and loading using FAISS.
Uses precomputed embeddings from forbidden_question_set_df.csv and deduplicates prompts.
"""
import os
import json
from typing import Tuple, List, Dict, Any
import numpy as np
import pandas as pd
import faiss

from .config import (
    CSV_PATH,
    FAISS_INDEX_PATH,
    METADATA_PATH,
    EMBEDDING_DIM
)


def build_index_from_csv(
    csv_path: str = CSV_PATH,
    index_path: str = FAISS_INDEX_PATH,
    metadata_path: str = METADATA_PATH,
    dim: int = EMBEDDING_DIM
) -> Tuple[faiss.IndexFlatIP, List[Dict[str, Any]]]:
    """
    Builds a FAISS IndexFlatIP (cosine similarity) from the precomputed embeddings
    in forbidden_question_set_df.csv, deduplicating exact prompts, and persists
    both the FAISS index and metadata to local disk.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Source dataset not found at: {csv_path}")

    os.makedirs(os.path.dirname(index_path), exist_ok=True)
    os.makedirs(os.path.dirname(metadata_path), exist_ok=True)

    print(f"[Layer2 Indexer] Reading precomputed embeddings from {csv_path}...")
    df = pd.read_csv(csv_path, usecols=["Prompt", "embedding", "Length", "Perplexity"])

    # Remove exact duplicate prompts and null rows
    dedup = df.dropna(subset=["Prompt", "embedding"]).drop_duplicates(subset=["Prompt"]).copy()
    print(f"[Layer2 Indexer] Extracted {len(dedup)} unique malicious prompts from {len(df)} total rows.")

    vectors: List[np.ndarray] = []
    metadata: List[Dict[str, Any]] = []

    for idx, row in dedup.iterrows():
        raw_emb = str(row["embedding"])
        clean_str = raw_emb.replace("[", " ").replace("]", " ")
        arr = np.fromstring(clean_str, sep=" ", dtype=np.float32)

        if arr.shape != (dim,):
            print(f"[Layer2 Indexer] Skipping invalid embedding shape: {arr.shape}")
            continue

        # Ensure unit L2 norm for exact cosine similarity
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr = arr / norm

        vectors.append(arr)
        metadata.append({
            "id": len(metadata),
            "prompt": str(row["Prompt"]),
            "length": float(row["Length"]) if pd.notna(row.get("Length")) else len(str(row["Prompt"])),
            "perplexity": float(row["Perplexity"]) if pd.notna(row.get("Perplexity")) else None
        })

    if not vectors:
        raise ValueError("No valid precomputed embeddings found in dataset to index.")

    vector_matrix = np.vstack(vectors).astype(np.float32)

    # IndexFlatIP calculates inner products. For unit-norm vectors, inner product == cosine similarity.
    index = faiss.IndexFlatIP(dim)
    index.add(vector_matrix)

    # Persist locally so rebuilding is not needed on subsequent app launches
    faiss.write_index(index, index_path)
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    print(f"[Layer2 Indexer] FAISS index saved to {index_path} ({index.ntotal} vectors).")
    print(f"[Layer2 Indexer] Metadata saved to {metadata_path}.")
    return index, metadata


def load_or_create_index(
    index_path: str = FAISS_INDEX_PATH,
    metadata_path: str = METADATA_PATH,
    csv_path: str = CSV_PATH,
    force_rebuild: bool = False
) -> Tuple[faiss.IndexFlatIP, List[Dict[str, Any]]]:
    """
    Loads the persistent FAISS index and metadata from disk.
    If the index files do not exist or force_rebuild=True, automatically builds
    and persists them from the CSV.
    """
    if not force_rebuild and os.path.exists(index_path) and os.path.exists(metadata_path):
        try:
            index = faiss.read_index(index_path)
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            return index, metadata
        except Exception as e:
            print(f"[Layer2 Indexer] Failed to load cached index: {e}. Rebuilding from source CSV...")

    return build_index_from_csv(csv_path=csv_path, index_path=index_path, metadata_path=metadata_path)

