import os

# Base directory for layer2
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Data and index paths
CSV_PATH = os.path.join(BASE_DIR, "forbidden_question_set_df.csv")
INDEX_DIR = os.path.join(BASE_DIR, "index_storage")
FAISS_INDEX_PATH = os.path.join(INDEX_DIR, "forbidden_prompts.index")
METADATA_PATH = os.path.join(INDEX_DIR, "prompts_metadata.json")

# Embedding model verified against precomputed dataset embeddings
EMBEDDING_MODEL_NAME = "all-MiniLM-L12-v2"
EMBEDDING_DIM = 384

# Default threshold for cosine similarity detection
# Benign queries typically exhibit similarity <= 0.25 - 0.30
# Adversarial, jailbreak, and instruction overrides exhibit similarity >= 0.45
DEFAULT_SIMILARITY_THRESHOLD = 0.45
DEFAULT_TOP_K = 3
