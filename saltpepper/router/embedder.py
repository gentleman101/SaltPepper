"""Local embedding model — all-MiniLM-L6-v2 via sentence-transformers."""
import logging
import warnings
import numpy as np
from sentence_transformers import SentenceTransformer

# Suppress the harmless "embeddings.position_ids UNEXPECTED" warning from
# BertModel when loaded via sentence-transformers for a non-BERT task.
warnings.filterwarnings("ignore", message=".*position_ids.*")
logging.getLogger("transformers").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)

_model: SentenceTransformer | None = None
MODEL_NAME = "all-MiniLM-L6-v2"


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME, show_progress_bar=False)
    return _model


def embed(text: str) -> np.ndarray:
    return _get_model().encode(text, normalize_embeddings=True)


def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b))  # vectors already L2-normalized
