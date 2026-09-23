import threading
from typing import List

import numpy as np

from core.config import EMBEDDING_DIM, EMBEDDING_MODEL
from core.utils import logger


class EmbeddingUnavailable(RuntimeError):
    pass


_model = None
_lock = threading.Lock()


def _get_model():
    global _model
    if _model is not None:
        return _model
    with _lock:
        if _model is None:
            try:
                from sentence_transformers import SentenceTransformer
                _model = SentenceTransformer(EMBEDDING_MODEL)
            except Exception as e:
                logger.error(f"Failed to load embedding model {EMBEDDING_MODEL}: {e}")
                raise EmbeddingUnavailable(f"Embedding model unavailable: {e}") from e
    return _model


def warmup() -> bool:
    try:
        _get_model()
        return True
    except EmbeddingUnavailable:
        return False


def encode(texts: List[str]) -> np.ndarray:
    """(n, 384) float32, L2-normalised, so a dot product is cosine similarity.
    Raises EmbeddingUnavailable instead of returning zero vectors: a silent
    zero vector makes every candidate look equally irrelevant."""
    if not texts:
        return np.zeros((0, EMBEDDING_DIM), dtype=np.float32)
    model = _get_model()
    vectors = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True, batch_size=32, show_progress_bar=False)
    return np.asarray(vectors, dtype=np.float32).reshape(len(texts), -1)


def encode_one(text: str) -> np.ndarray:
    return encode([text])[0]
