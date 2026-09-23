import math
import threading
from typing import List, Optional

from core.config import RERANKER_ENABLED, RERANKER_MODEL
from core.utils import logger

_model = None
_failed = False
_lock = threading.Lock()


def _get_model():
    global _model, _failed
    if not RERANKER_ENABLED or _failed:
        return None
    if _model is None:
        with _lock:
            if _model is None and not _failed:
                try:
                    from sentence_transformers import CrossEncoder
                    _model = CrossEncoder(RERANKER_MODEL, max_length=512)
                except Exception as e:
                    logger.warning(f"Cross-encoder unavailable ({e}); search will use first-stage scores only")
                    _failed = True
    return _model


def is_available() -> bool:
    return _get_model() is not None


def score_pairs(query: str, documents: List[str]) -> Optional[List[float]]:
    """Cross-encoder relevance in 0-1 (sigmoid of the raw logit), one per
    document, or None when the reranker is disabled or could not be loaded."""
    model = _get_model()
    if model is None or not documents:
        return None
    try:
        raw = model.predict([(query, doc) for doc in documents], batch_size=16, show_progress_bar=False)
        return [1.0 / (1.0 + math.exp(-float(x))) for x in raw]
    except Exception as e:
        logger.error(f"Reranking failed: {e}")
        return None
