import math
from typing import Dict, Iterable, List, Sequence, Set


def precision_recall_f1(predicted: Iterable[str], expected: Iterable[str]) -> Dict[str, float]:
    p, e = set(predicted), set(expected)
    tp = len(p & e)
    precision = tp / len(p) if p else (1.0 if not e else 0.0)
    recall = tp / len(e) if e else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def recall_at_k(ranked: Sequence, relevant: Set, k: int) -> float:
    if not relevant:
        return 0.0
    return len(set(ranked[:k]) & set(relevant)) / len(relevant)


def reciprocal_rank(ranked: Sequence, relevant: Set) -> float:
    for i, item in enumerate(ranked, 1):
        if item in relevant:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked: Sequence, gains: Dict, k: int) -> float:
    """gains maps item -> graded relevance (0 = irrelevant)."""
    dcg = sum(gains.get(item, 0) / math.log2(i + 1) for i, item in enumerate(ranked[:k], 1))
    ideal = sorted(gains.values(), reverse=True)[:k]
    idcg = sum(g / math.log2(i + 1) for i, g in enumerate(ideal, 1))
    return dcg / idcg if idcg else 0.0


def mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0
