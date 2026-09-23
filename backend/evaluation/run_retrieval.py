"""Compares ranking strategies on a labelled set of (job, resume, relevance) triples.

    python -m evaluation.run_retrieval [path/to/dataset.json]

Strategies:
  bi_encoder        MiniLM cosine (best chunk)          first stage only
  bi_plus_rerank    MiniLM blended with cross-encoder   what the search endpoint uses for semantic
  hybrid            deterministic 40/40/20 score using the bi-encoder semantic score
  hybrid_rerank     the same score with the blended semantic score (the production pipeline)

Needs sentence-transformers and the two models (downloaded on first run). No database."""
import json
import os
import sys

import numpy as np

from services import embedding_service
from ai import reranker
from ai.chunking import build_job_text, chunk_resume
from evaluation.metrics import mean, ndcg_at_k, recall_at_k, reciprocal_rank
from ai.extraction import parse_resume
from services.scoring_service import ScoringService
from services.search_service import blend_semantic

DEFAULT = os.path.join(os.path.dirname(__file__), "datasets", "retrieval_sample.json")


def run(path: str = DEFAULT, k: int = 5) -> dict:
    data = json.load(open(path, encoding="utf-8"))
    resumes = {}
    for r in data["resumes"]:
        parsed = parse_resume(r["text"])
        chunks = chunk_resume(parsed["skills"], parsed["experience_years"], r["text"])
        resumes[r["id"]] = {"parsed": parsed, "vectors": embedding_service.encode(chunks), "doc": " ".join(chunks[:2])[:1800]}

    strategies = {"bi_encoder": [], "bi_plus_rerank": [], "hybrid": [], "hybrid_rerank": []}
    rr_available = reranker.is_available()
    detail = {}
    for job in data["jobs"]:
        job_text = build_job_text(job["text"], job["required_skills"])
        jvec = embedding_service.encode_one(job_text)
        ids = list(resumes)
        bi = {rid: float(np.max(resumes[rid]["vectors"] @ jvec)) for rid in ids}
        ce_raw = reranker.score_pairs(job_text, [resumes[rid]["doc"] for rid in ids]) if rr_available else None
        ce = dict(zip(ids, ce_raw)) if ce_raw else {}

        def hybrid(rid, semantic):
            return ScoringService.score_candidate(
                semantic_similarity=semantic, candidate_skills=resumes[rid]["parsed"]["skills"],
                required_skills=job["required_skills"], candidate_experience=resumes[rid]["parsed"]["experience_years"],
                required_min_experience=job.get("min_experience"),
            )["final_score"]

        scores = {
            "bi_encoder": {rid: bi[rid] for rid in ids},
            "bi_plus_rerank": {rid: blend_semantic(bi[rid], ce.get(rid)) for rid in ids},
            "hybrid": {rid: hybrid(rid, bi[rid]) for rid in ids},
            "hybrid_rerank": {rid: hybrid(rid, blend_semantic(bi[rid], ce.get(rid))) for rid in ids},
        }
        gains = data["relevance"].get(job["id"], {})
        relevant = {rid for rid, g in gains.items() if g > 0}
        for name, s in scores.items():
            ranked = sorted(ids, key=lambda rid: s[rid], reverse=True)
            strategies[name].append({
                f"recall@{k}": recall_at_k(ranked, relevant, k),
                "mrr": reciprocal_rank(ranked, relevant),
                f"ndcg@{k}": ndcg_at_k(ranked, gains, k),
            })
            detail.setdefault(job["id"], {})[name] = ranked

    summary = {name: {m: round(mean([row[m] for row in rows]), 3) for m in rows[0]} for name, rows in strategies.items()}
    return {"reranker_available": rr_available, "jobs": len(data["jobs"]), "summary": summary, "rankings": detail}


if __name__ == "__main__":
    print(json.dumps(run(sys.argv[1] if len(sys.argv) > 1 else DEFAULT), indent=2))
