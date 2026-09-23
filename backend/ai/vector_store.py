from typing import Dict, List, Optional

import numpy as np
from sqlalchemy import Float, or_
from sqlalchemy.orm import Session

from models import Resume, ResumeChunk
from core.utils import logger




def replace_resume_chunks(db: Session, resume: Resume, chunks: List[str], embeddings: np.ndarray) -> None:
    """Swap in a resume's chunks. Caller commits, so the resume flags and its
    vectors land in the same transaction."""
    if len(chunks) != len(embeddings):
        raise ValueError("chunks and embeddings must be the same length")
    db.query(ResumeChunk).filter(ResumeChunk.resume_id == resume.id).delete(synchronize_session=False)
    for i, (text, vector) in enumerate(zip(chunks, embeddings)):
        db.add(ResumeChunk(resume_id=resume.id, user_id=resume.user_id, chunk_index=i, chunk_text=text, embedding=vector))
    db.flush()


def delete_resume_chunks(db: Session, resume_id: int) -> None:
    db.query(ResumeChunk).filter(ResumeChunk.resume_id == resume_id).delete(synchronize_session=False)


def count_indexed_resumes(db: Session, user_id: int) -> int:
    return (
        db.query(ResumeChunk.resume_id)
        .filter(ResumeChunk.user_id == user_id)
        .distinct()
        .count()
    )


def search(db: Session, user_id: int, query_vec: np.ndarray, limit: int, min_experience: Optional[float] = None) -> List[Dict]:
    """First-stage retrieval using pgvector HNSW cosine distance. The tenant filter
    (and optional hard experience filter) are part of the query itself, so another
    tenant's vectors are never candidates. A resume's similarity is its best chunk's
    cosine similarity.
    Returns [{resume_id, similarity, chunk_id}] best first."""
    query_vec = np.asarray(query_vec, dtype=np.float32).reshape(-1)
    try:
        with db.begin_nested():
            db.execute(_sql("SET LOCAL hnsw.ef_search = 200"))
            db.execute(_sql("SET LOCAL hnsw.iterative_scan = relaxed_order"))
    except Exception:
        pass  # older pgvector: filtered HNSW queries are still correct, just less complete on huge tenants

    distance = ResumeChunk.embedding.op("<=>", return_type=Float)(query_vec).label("dist")
    query = (
        db.query(ResumeChunk.resume_id.label("resume_id"), ResumeChunk.id.label("chunk_id"), distance)
        .join(Resume, Resume.id == ResumeChunk.resume_id)
        .filter(ResumeChunk.user_id == user_id, Resume.is_processed.is_(True))
    )
    if min_experience is not None:
        query = query.filter(Resume.experience_years >= min_experience)
    rows = query.order_by(distance).limit(max(limit * 4, 50)).all()

    best: Dict[int, Dict] = {}
    for row in rows:
        if row.resume_id not in best:
            best[row.resume_id] = {
                "resume_id": row.resume_id,
                "chunk_id": row.chunk_id,
                "similarity": float(max(0.0, min(1.0, 1.0 - row.dist))),
            }
        if len(best) >= limit:
            break
    return list(best.values())


def similarities(db: Session, resume_ids: List[int], query_vec: np.ndarray) -> Dict[int, float]:
    """Best-chunk cosine similarity for specific resumes (job applicants, one
    candidate being analysed). No re-embedding of resume text: vectors were
    computed once when the resume was processed."""
    if not resume_ids:
        return {}
    query_vec = np.asarray(query_vec, dtype=np.float32).reshape(-1)
    rows = db.query(ResumeChunk.resume_id, ResumeChunk.embedding).filter(ResumeChunk.resume_id.in_(resume_ids)).all()
    out: Dict[int, float] = {}
    for row in rows:
        sim = float(max(0.0, min(1.0, float(row.embedding @ query_vec))))
        if sim > out.get(row.resume_id, -1.0):
            out[row.resume_id] = sim
    return out


def best_chunk(db: Session, resume_id: int, vec: np.ndarray) -> Optional[Dict]:
    vec = np.asarray(vec, dtype=np.float32).reshape(-1)
    chunks = db.query(ResumeChunk).filter(ResumeChunk.resume_id == resume_id).all()
    best = None
    for chunk in chunks:
        sim = float(chunk.embedding @ vec)
        if best is None or sim > best["similarity"]:
            best = {"chunk_id": chunk.id, "chunk_index": chunk.chunk_index, "text": chunk.chunk_text, "similarity": sim}
    return best


def rerank_documents(db: Session, resume_ids: List[int], best_chunk_ids: Optional[Dict[int, int]] = None) -> Dict[int, str]:
    """Text handed to the cross-encoder for each resume: the profile chunk
    (skills, experience, top of the resume) plus the chunk that matched the
    query best, when we know which one that was."""
    if not resume_ids:
        return {}
    wanted = list((best_chunk_ids or {}).values())
    condition = ResumeChunk.chunk_index == 0
    if wanted:
        condition = or_(condition, ResumeChunk.id.in_(wanted))
    rows = (
        db.query(ResumeChunk.id, ResumeChunk.resume_id, ResumeChunk.chunk_index, ResumeChunk.chunk_text)
        .filter(ResumeChunk.resume_id.in_(resume_ids), condition)
        .order_by(ResumeChunk.resume_id, ResumeChunk.chunk_index)
        .all()
    )
    docs: Dict[int, List[str]] = {}
    for row in rows:
        docs.setdefault(row.resume_id, []).append(row.chunk_text)
    return {rid: " ".join(parts)[:1800] for rid, parts in docs.items()}


def _sql(statement: str):
    from sqlalchemy import text
    return text(statement)
