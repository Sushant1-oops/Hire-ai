import hashlib
from typing import Dict, List, Optional

import numpy as np
from sqlalchemy.orm import Session

from . import embedding_service
from ai import reranker
from ai import vector_store
from .cache_service import Cache
from ai.chunking import build_job_text, chunk_resume
from core.config import RERANK_BLEND, RERANK_KEEP, RETRIEVE_K
from models import Resume
from .scoring_service import ScoringService
from ai.skills_extractor import SkillsExtractor
from core.utils import logger, safe_json_loads

_query_vec_cache = Cache("queryvec", 3600)


def query_vector(text: str) -> np.ndarray:
    key = hashlib.sha256(text.encode("utf-8")).hexdigest()
    cached = _query_vec_cache.get(key)
    if cached is not None:
        return np.asarray(cached, dtype=np.float32)
    vec = embedding_service.encode_one(text)
    _query_vec_cache.set(key, vec.tolist())
    return vec


def blend_semantic(bi: float, ce: Optional[float]) -> float:
    if ce is None:
        return bi
    return (1.0 - RERANK_BLEND) * bi + RERANK_BLEND * ce


def index_resume(db: Session, resume: Resume) -> int:
    """(Re)builds a resume's chunk vectors from its stored text. The caller commits."""
    skills = safe_json_loads(resume.skills, [])
    chunks = chunk_resume(skills, resume.experience_years, resume.extracted_text)
    if not chunks:
        vector_store.delete_resume_chunks(db, resume.id)
        return 0
    embeddings = embedding_service.encode(chunks)
    vector_store.replace_resume_chunks(db, resume, chunks, embeddings)
    return len(chunks)


def reindex_user_resumes(db: Session, user_id: int) -> int:
    """Re-embeds every processed resume for one tenant. Also the migration path
    from the old FAISS index: vectors are derived data, so they are simply rebuilt."""
    resumes = db.query(Resume).filter(Resume.user_id == user_id, Resume.is_processed.is_(True)).all()
    done = 0
    for resume in resumes:
        try:
            index_resume(db, resume)
            db.commit()
            done += 1
        except Exception as e:
            db.rollback()
            logger.error(f"reindex failed for resume {resume.id}: {e}")
    return done


def semantic_scores(
    db: Session,
    query_text: str,
    resume_ids: List[int],
    query_vec: Optional[np.ndarray] = None,
    best_chunk_ids: Optional[Dict[int, int]] = None,
    use_reranker: bool = True,
    bi_scores: Optional[Dict[int, float]] = None,
) -> Dict[int, Dict]:
    """Semantic score per resume: bi-encoder cosine, optionally blended with the
    cross-encoder's judgement of the (query, resume) pair."""
    if not resume_ids:
        return {}
    if bi_scores is None:
        vec = query_vec if query_vec is not None else query_vector(query_text)
        bi_scores = vector_store.similarities(db, resume_ids, vec)

    ce_scores: Dict[int, float] = {}
    if use_reranker and reranker.is_available():
        docs = vector_store.rerank_documents(db, resume_ids, best_chunk_ids)
        ordered = [rid for rid in resume_ids if rid in docs]
        scores = reranker.score_pairs(query_text, [docs[rid] for rid in ordered])
        if scores is not None:
            ce_scores = dict(zip(ordered, scores))

    out = {}
    for rid in resume_ids:
        bi = bi_scores.get(rid, 0.0)
        ce = ce_scores.get(rid)
        out[rid] = {"bi": bi, "ce": ce, "semantic": blend_semantic(bi, ce)}
    return out


def semantic_for_job(db: Session, job, resume_ids: List[int]) -> Dict[int, Dict]:
    """Semantic scores for a job's applicants. The cross-encoder is skipped for
    very large applicant pools to keep the dashboard responsive."""
    job_text = build_job_text(job.description, safe_json_loads(job.required_skills, []))
    return semantic_scores(db, job_text, resume_ids, use_reranker=len(resume_ids) <= 100)


def search_with_scoring(
    db: Session,
    user_id: int,
    query: str,
    required_skills: Optional[List[str]] = None,
    top_k: int = 10,
    min_experience: Optional[float] = None,
    nice_to_have_skills: Optional[List[str]] = None,
    nice_to_have_experience: Optional[float] = None,
    min_score: Optional[float] = None,
    hard_min_experience: Optional[float] = None,
    must_have_skills: Optional[List[str]] = None,
) -> Dict:
    """retrieve (pgvector, tenant + metadata filtered) -> cross-encoder rerank ->
    deterministic hybrid score. The LLM is not involved in ranking."""
    threshold = min_score if min_score is not None else ScoringService.MIN_SCORE_THRESHOLD
    pool = db.query(Resume).filter(Resume.user_id == user_id, Resume.is_processed.is_(True)).count()
    empty_summary = {"total_in_pool": pool, "total_retrieved": 0, "total_scored": 0,
                     "total_above_threshold": 0, "filtered_out": 0, "score_threshold": threshold, "reranker_used": False}
    if pool == 0:
        return {"results": [], "summary": empty_summary}

    qvec = query_vector(query)
    retrieve_k = min(max(RETRIEVE_K, top_k * 3), 200)
    candidates = vector_store.search(db, user_id, qvec, retrieve_k, hard_min_experience)
    if not candidates:
        return {"results": [], "summary": empty_summary}

    by_id = {c["resume_id"]: c for c in candidates}
    resumes = {
        r.id: r
        for r in db.query(Resume).filter(Resume.id.in_(list(by_id)), Resume.user_id == user_id).all()
    }

    if must_have_skills:
        needed = set(SkillsExtractor().extract_from_list(must_have_skills))
        resumes = {
            rid: r for rid, r in resumes.items()
            if needed.issubset(set(SkillsExtractor().extract_from_list(safe_json_loads(r.skills, []))))
        }
    ids = [c["resume_id"] for c in candidates if c["resume_id"] in resumes]
    if not ids:
        return {"results": [], "summary": {**empty_summary, "total_retrieved": len(candidates)}}

    sem = semantic_scores(
        db, query, ids, query_vec=qvec,
        best_chunk_ids={rid: by_id[rid]["chunk_id"] for rid in ids},
        bi_scores={rid: by_id[rid]["similarity"] for rid in ids},
    )
    reranked = any(v["ce"] is not None for v in sem.values())
    if reranked:
        keep = min(len(ids), max(top_k * 2, RERANK_KEEP))
        ids = sorted(ids, key=lambda rid: sem[rid]["ce"] if sem[rid]["ce"] is not None else -1, reverse=True)[:keep]

    scored = []
    for rid in ids:
        resume = resumes[rid]
        skills = safe_json_loads(resume.skills, [])
        scores = ScoringService.score_candidate(
            semantic_similarity=sem[rid]["semantic"],
            candidate_skills=skills,
            required_skills=required_skills or [],
            candidate_experience=resume.experience_years,
            required_min_experience=min_experience,
            nice_to_have_skills=nice_to_have_skills,
            nice_to_have_experience=nice_to_have_experience,
        )
        scores.update({
            "resume_id": rid,
            "candidate_name": resume.candidate_name,
            "candidate_email": resume.candidate_email,
            "candidate_phone": resume.candidate_phone,
            "experience_years": resume.experience_years,
            "skills": skills,
            "recommendation": ScoringService.get_recommendation(scores["final_score"]),
            "first_stage_similarity": round(sem[rid]["bi"], 4),
            "rerank_score": round(sem[rid]["ce"], 4) if sem[rid]["ce"] is not None else None,
            "evidence_chunk_id": by_id[rid]["chunk_id"],
        })
        scored.append(scores)

    ranked = sorted(scored, key=lambda r: r["final_score"], reverse=True)
    for i, item in enumerate(ranked, 1):
        item["rank"] = i
    above = [r for r in ranked if r["final_score"] >= threshold]
    return {
        "results": above[:top_k],
        "summary": {
            "total_in_pool": pool,
            "total_retrieved": len(candidates),
            "total_scored": len(ranked),
            "total_above_threshold": len(above),
            "filtered_out": len(ranked) - len(above),
            "score_threshold": threshold,
            "reranker_used": reranked,
        },
    }
