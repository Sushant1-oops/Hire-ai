
import os
import json
import numpy as np
from typing import List, Dict, Optional, Tuple
from sqlalchemy.orm import Session
from models import Resume
from utils import logger, ensure_directory, save_pickle, load_pickle, safe_json_loads
from scoring_service import ScoringService

class SemanticSearchService:
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    FAISS_INDEX_PATH = "data/faiss_index.bin"
    RESUME_EMBEDDINGS_PATH = "data/resume_embeddings.pkl"
    EMBEDDING_DIMENSION = 384
    
    
    
    
    
    
    
    MAX_EMBEDDING_CHARS = 1800

    _model = None
    _index = None
    _resume_embeddings = None

    def __init__(self):
        ensure_directory("data")
        self.model = self._load_model()
        self.index, self.resume_embeddings = self._load_or_create_index()

    @classmethod
    def _load_model(cls):
        if cls._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                cls._model = SentenceTransformer(cls.EMBEDDING_MODEL)
            except Exception as e:
                logger.error(f"Failed to load SentenceTransformer: {str(e)}")
                cls._model = None
        return cls._model

    @classmethod
    def _load_or_create_index(cls) -> Tuple["faiss.IndexFlatIP", Dict]:
        import faiss
        if os.path.exists(cls.FAISS_INDEX_PATH):
            try:
                cls._index = faiss.read_index(cls.FAISS_INDEX_PATH)
                cls._resume_embeddings = load_pickle(cls.RESUME_EMBEDDINGS_PATH)
                return cls._index, cls._resume_embeddings or {}
            except Exception: pass
        cls._index = faiss.IndexFlatIP(cls.EMBEDDING_DIMENSION)
        cls._resume_embeddings = {}
        return cls._index, cls._resume_embeddings

    @property
    def model(self): return self.__class__._model
    @model.setter
    def model(self, value): self.__class__._model = value
    @property
    def index(self): return self.__class__._index
    @index.setter
    def index(self, value): self.__class__._index = value
    @property
    def resume_embeddings(self): return self.__class__._resume_embeddings
    @resume_embeddings.setter
    def resume_embeddings(self, value): self.__class__._resume_embeddings = value

    @classmethod
    def build_resume_embedding_text(cls, skills: Optional[List[str]], experience_years: Optional[float], extracted_text: Optional[str]) -> str:
        
        parts = []
        if skills:
            parts.append(f"Skills: {', '.join(skills)}.")
        if experience_years is not None:
            parts.append(f"{experience_years} years of experience.")
        if extracted_text:
            parts.append(extracted_text[:cls.MAX_EMBEDDING_CHARS])
        return " ".join(parts)

    @classmethod
    def build_job_embedding_text(cls, description: Optional[str], required_skills: Optional[List[str]]) -> str:
        
        parts = []
        if required_skills:
            parts.append(f"Required skills: {', '.join(required_skills)}.")
        if description:
            parts.append(description[:cls.MAX_EMBEDDING_CHARS])
        return " ".join(parts)

    def encode_text(self, text: str) -> np.ndarray:
        if not self.model: return np.zeros((1, self.EMBEDDING_DIMENSION), dtype=np.float32)
        embedding = self.model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
        return embedding.reshape(1, -1).astype(np.float32) if embedding.ndim == 1 else embedding.astype(np.float32)

    def encode_texts_batch(self, texts: List[str]) -> np.ndarray:
        if not self.model: return np.zeros((len(texts), self.EMBEDDING_DIMENSION), dtype=np.float32)
        embeddings = self.model.encode(texts, convert_to_numpy=True, normalize_embeddings=True, batch_size=64, show_progress_bar=False)
        return embeddings.astype(np.float32)

    def add_resume_to_index(self, resume_id: int, resume_text: str) -> bool:
        try:
            embedding = self.encode_text(resume_text)
            self.index.add(embedding)
            self.resume_embeddings[self.index.ntotal - 1] = {"resume_id": resume_id, "embedding_index": self.index.ntotal - 1}
            return True
        except Exception: return False

    def add_resumes_batch(self, resume_ids: List[int], texts: List[str]) -> bool:
        try:
            if not texts: return True
            embeddings = self.encode_texts_batch(texts)
            start_id = self.index.ntotal
            self.index.add(embeddings)
            for i, resume_id in enumerate(resume_ids):
                self.resume_embeddings[start_id + i] = {"resume_id": resume_id, "embedding_index": start_id + i}
            return True
        except Exception: return False

    def remove_resume(self, resume_id: int) -> bool:
        try:
            vector_ids_to_remove = [vid for vid, info in self.resume_embeddings.items() if info.get("resume_id") == resume_id]
            for vid in vector_ids_to_remove: del self.resume_embeddings[vid]
            return True
        except Exception: return False

    def save_index(self) -> bool:
        import faiss
        try:
            faiss.write_index(self.index, self.FAISS_INDEX_PATH)
            save_pickle(self.resume_embeddings, self.RESUME_EMBEDDINGS_PATH)
            return True
        except Exception: return False

    def search(self, query: str, top_k: int = 10, db: Optional[Session] = None, user_id: Optional[int] = None) -> List[Dict]:
        if self.index.ntotal == 0: return []
        try:
            query_embedding = self.encode_text(query)
            k = min(top_k, self.index.ntotal)
            scores, indices = self.index.search(query_embedding, k)
            results = []
            for rank, (score, vector_id) in enumerate(zip(scores[0], indices[0])):
                vector_id = int(vector_id)
                if vector_id not in self.resume_embeddings: continue
                resume_id = self.resume_embeddings[vector_id]["resume_id"]
                if not db: continue
                query_obj = db.query(Resume).filter(Resume.id == resume_id)
                if user_id is not None:
                    
                    
                    
                    query_obj = query_obj.filter(Resume.user_id == user_id)
                resume = query_obj.first()
                if not resume: continue
                similarity = float(max(0, min(1, score)))
                results.append({
                    "rank": rank + 1, "resume_id": resume_id, "candidate_name": resume.candidate_name,
                    "candidate_email": resume.candidate_email, "candidate_phone": resume.candidate_phone,
                    "experience_years": resume.experience_years, "skills": safe_json_loads(resume.skills, []),
                    "semantic_similarity": round(similarity, 4)
                })
            return results
        except Exception as e:
            logger.error(f"Error during search: {str(e)}")
            return []

    def search_with_scoring(self, query: str, required_skills: Optional[List[str]] = None, top_k: int = 10, db: Optional[Session] = None, user_id: Optional[int] = None, min_experience: Optional[float] = None, nice_to_have_skills: Optional[List[str]] = None, nice_to_have_experience: Optional[float] = None, min_score: Optional[float] = None) -> Dict:
        score_threshold = min_score if min_score is not None else ScoringService.MIN_SCORE_THRESHOLD

        if self.index.ntotal == 0:
            return {"results": [], "summary": {"total_in_pool": 0, "total_scored": 0, "total_above_threshold": 0, "filtered_out": 0}}

        
        
        
        
        
        if user_id is not None and self.index.ntotal <= 2000:
            k_to_search = self.index.ntotal
        else:
            k_to_search = min(self.index.ntotal, max(top_k * 5, 50))
        search_results = self.search(query, top_k=k_to_search, db=db, user_id=user_id)

        if not search_results:
            return {"results": [], "summary": {"total_in_pool": self.index.ntotal, "total_scored": 0, "total_above_threshold": 0, "filtered_out": 0}}

        scored_results = []
        for result in search_results:
            scores = ScoringService.score_candidate(
                semantic_similarity=result["semantic_similarity"],
                candidate_skills=result.get("skills", []),
                required_skills=required_skills or [],
                candidate_experience=result.get("experience_years"),
                required_min_experience=min_experience,
                nice_to_have_skills=nice_to_have_skills,
                nice_to_have_experience=nice_to_have_experience
            )
            result.update(scores)
            result["recommendation"] = ScoringService.get_recommendation(scores["final_score"])
            scored_results.append(result)

        ranked = sorted(scored_results, key=lambda x: x["final_score"], reverse=True)
        for idx, cand in enumerate(ranked, 1): cand["rank"] = idx

        filtered = [r for r in ranked if r["final_score"] >= score_threshold]
        final_results = filtered[:top_k]

        return {
            "results": final_results,
            "summary": {
                "total_in_pool": self.index.ntotal, "total_scored": len(ranked),
                "total_above_threshold": len(filtered), "filtered_out": len(ranked) - len(filtered),
                "score_threshold": score_threshold
            }
        }

    def rebuild_index(self, db: Session, user_id: int) -> bool:
        try:
            resumes = db.query(Resume).filter(Resume.user_id == user_id, Resume.is_processed == True).all()
            import faiss
            self.__class__._index = faiss.IndexFlatIP(self.EMBEDDING_DIMENSION)
            self.__class__._resume_embeddings = {}
            if resumes:
                ids = [r.id for r in resumes]
                texts = [
                    self.build_resume_embedding_text(safe_json_loads(r.skills, []), r.experience_years, r.extracted_text)
                    for r in resumes
                ]
                self.add_resumes_batch(ids, texts)
            self.save_index()
            return True
        except Exception as e:
            logger.error(f"Error rebuilding index: {str(e)}")
            return False

_search_service_instance = None
def get_search_service() -> SemanticSearchService:
    global _search_service_instance
    if _search_service_instance is None:
        _search_service_instance = SemanticSearchService()
    return _search_service_instance