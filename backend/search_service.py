"""
Search service for semantic search using FAISS and sentence transformers.
Uses cosine similarity (IndexFlatIP) with normalised vectors for accurate matching.
Supports batch encoding for handling hundreds of resumes efficiently.
"""

import os
import numpy as np
from typing import List, Dict, Optional, Tuple
from sentence_transformers import SentenceTransformer
import faiss
from sqlalchemy.orm import Session
from models import Resume
from utils import logger, ensure_directory, save_pickle, load_pickle, SimpleCache, safe_json_loads
from scoring_service import ScoringService


class SemanticSearchService:
    """Service for semantic search using FAISS vector database."""

    # Configuration
    EMBEDDING_MODEL = "all-MiniLM-L6-v2"
    FAISS_INDEX_PATH = "data/faiss_index.bin"
    RESUME_EMBEDDINGS_PATH = "data/resume_embeddings.pkl"
    EMBEDDING_DIMENSION = 384  # Dimension of all-MiniLM-L6-v2

    # Class-level singletons
    _model = None
    _index = None
    _resume_embeddings = None

    def __init__(self):
        """Initialize search service."""
        ensure_directory("data")
        self.model = self._load_model()
        self.index, self.resume_embeddings = self._load_or_create_index()
        logger.info(f"✓ Semantic search service initialized ({self.index.ntotal} vectors)")

    @classmethod
    def _load_model(cls):
        """Load sentence transformer model (singleton)."""
        if cls._model is None:
            logger.info(f"Loading embedding model: {cls.EMBEDDING_MODEL}")
            cls._model = SentenceTransformer(cls.EMBEDDING_MODEL)
            logger.info("✓ Model loaded successfully")
        return cls._model

    @classmethod
    def _load_or_create_index(cls) -> Tuple[faiss.IndexFlatIP, Dict]:
        """Load existing FAISS index or create a new cosine-similarity index."""
        if os.path.exists(cls.FAISS_INDEX_PATH):
            try:
                cls._index = faiss.read_index(cls.FAISS_INDEX_PATH)
                cls._resume_embeddings = load_pickle(cls.RESUME_EMBEDDINGS_PATH)
                logger.info(f"✓ Loaded FAISS index with {cls._index.ntotal} vectors")
                return cls._index, cls._resume_embeddings or {}
            except Exception as e:
                logger.warning(f"Failed to load existing index: {str(e)}")

        # Create new inner-product (cosine similarity) index
        cls._index = faiss.IndexFlatIP(cls.EMBEDDING_DIMENSION)
        cls._resume_embeddings = {}
        logger.info("✓ Created new FAISS cosine-similarity index")
        return cls._index, cls._resume_embeddings

    # ── Properties ─────────────────────────────────────────────────
    @property
    def model(self):
        return self.__class__._model

    @model.setter
    def model(self, value):
        self.__class__._model = value

    @property
    def index(self):
        return self.__class__._index

    @index.setter
    def index(self, value):
        self.__class__._index = value

    @property
    def resume_embeddings(self):
        return self.__class__._resume_embeddings

    @resume_embeddings.setter
    def resume_embeddings(self, value):
        self.__class__._resume_embeddings = value

    # ── Encoding ───────────────────────────────────────────────────
    def encode_text(self, text: str) -> np.ndarray:
        """
        Encode text to normalised embedding vector for cosine similarity.
        Returns shape (1, 384).
        """
        embedding = self.model.encode(text, convert_to_numpy=True, normalize_embeddings=True)
        if embedding.ndim == 1:
            embedding = embedding.reshape(1, -1)
        return embedding.astype(np.float32)

    def encode_texts_batch(self, texts: List[str]) -> np.ndarray:
        """
        Batch encode multiple texts efficiently.
        Returns shape (N, 384) normalised.
        """
        embeddings = self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            batch_size=64,
            show_progress_bar=False,
        )
        return embeddings.astype(np.float32)

    # ── Index Operations ───────────────────────────────────────────
    def add_resume_to_index(self, resume_id: int, resume_text: str) -> bool:
        """Add a single resume to the FAISS index."""
        try:
            embedding = self.encode_text(resume_text)
            self.index.add(embedding)
            vector_id = self.index.ntotal - 1

            self.resume_embeddings[vector_id] = {
                "resume_id": resume_id,
                "embedding_index": vector_id
            }

            logger.info(f"✓ Added resume {resume_id} to index (vector_id={vector_id})")
            return True

        except Exception as e:
            logger.error(f"✗ Error adding resume to index: {str(e)}")
            return False

    def add_resumes_batch(self, resume_ids: List[int], texts: List[str]) -> bool:
        """Add multiple resumes to the index in one batch for speed."""
        try:
            if not texts:
                return True

            embeddings = self.encode_texts_batch(texts)

            start_id = self.index.ntotal
            self.index.add(embeddings)

            for i, resume_id in enumerate(resume_ids):
                vector_id = start_id + i
                self.resume_embeddings[vector_id] = {
                    "resume_id": resume_id,
                    "embedding_index": vector_id
                }

            logger.info(f"✓ Batch added {len(texts)} resumes to index")
            return True

        except Exception as e:
            logger.error(f"✗ Error batch adding resumes: {str(e)}")
            return False

    def save_index(self) -> bool:
        """Save FAISS index to disk."""
        try:
            faiss.write_index(self.index, self.FAISS_INDEX_PATH)
            save_pickle(self.resume_embeddings, self.RESUME_EMBEDDINGS_PATH)
            logger.info("✓ FAISS index saved to disk")
            return True
        except Exception as e:
            logger.error(f"✗ Error saving index: {str(e)}")
            return False

    # ── Search ─────────────────────────────────────────────────────
    def search(
        self,
        query: str,
        top_k: int = 10,
        db: Optional[Session] = None,
    ) -> List[Dict]:
        """
        Semantic search for matching resumes using cosine similarity.
        """
        if self.index.ntotal == 0:
            logger.warning("FAISS index is empty")
            return []

        try:
            query_embedding = self.encode_text(query)
            k = min(top_k, self.index.ntotal)

            # Inner product on normalised vectors = cosine similarity
            scores, indices = self.index.search(query_embedding, k)

            results = []
            for rank, (score, vector_id) in enumerate(zip(scores[0], indices[0])):
                vector_id = int(vector_id)
                if vector_id not in self.resume_embeddings:
                    continue

                resume_info = self.resume_embeddings[vector_id]
                resume_id = resume_info["resume_id"]

                resume = None
                if db:
                    resume = db.query(Resume).filter(Resume.id == resume_id).first()

                if not resume:
                    continue

                # Score is cosine similarity (0-1 for normalised vectors)
                similarity = float(max(0, min(1, score)))

                results.append({
                    "rank": rank + 1,
                    "resume_id": resume_id,
                    "candidate_name": resume.candidate_name,
                    "candidate_email": resume.candidate_email,
                    "candidate_phone": resume.candidate_phone,
                    "experience_years": resume.experience_years,
                    "skills": safe_json_loads(resume.skills, []),
                    "semantic_similarity": round(similarity, 4),
                })

            logger.info(f"✓ Search completed. Found {len(results)} results")
            return results

        except Exception as e:
            logger.error(f"✗ Error during search: {str(e)}")
            return []

    def search_with_scoring(
        self,
        query: str,
        required_skills: Optional[List[str]] = None,
        top_k: int = 10,
        db: Optional[Session] = None,
        user_id: Optional[int] = None,
        min_experience: Optional[float] = None,
        nice_to_have_skills: Optional[List[str]] = None,
        nice_to_have_experience: Optional[float] = None
    ) -> List[Dict]:
        """
        Semantic search with hybrid scoring system.
        Returns top-k candidates with full scoring breakdown including matched/missing skills.
        """
        # Ensure we search all resumes for comprehensive ranking
        if db and user_id:
            total_resumes = db.query(Resume).filter(
                Resume.user_id == user_id,
                Resume.is_processed == True
            ).count()
        else:
            total_resumes = self.index.ntotal

        if total_resumes == 0:
            logger.warning("No candidate resumes found")
            return []

        # Search all resumes for accurate ranking
        search_results = self.search(query, top_k=total_resumes, db=db)

        if not search_results:
            return []

        # Apply hybrid scoring
        scored_results = []
        for result in search_results:
            resume_dict = {
                "skills": json.dumps(result.get("skills", [])) if isinstance(result.get("skills"), list) else result.get("skills", "[]"),
                "experience_years": result.get("experience_years")
            }

            scores = ScoringService.score_candidate(
                semantic_similarity=result["semantic_similarity"],
                candidate_resume=resume_dict,
                required_skills=required_skills or [],
                required_min_experience=min_experience,
                nice_to_have_skills=nice_to_have_skills,
                nice_to_have_experience=nice_to_have_experience
            )

            # Merge result with scores
            result.update(scores)
            result["recommendation"] = ScoringService.get_recommendation(scores["final_score"])
            scored_results.append(result)

        # Rank by final score
        ranked = ScoringService.rank_candidates(scored_results)

        return ranked[:top_k]

    def rebuild_index(self, db: Session, user_id: int) -> bool:
        """
        Rebuild FAISS index for user's resumes using batch encoding.
        """
        try:
            logger.info(f"Rebuilding FAISS index for user {user_id}...")

            resumes = db.query(Resume).filter(
                Resume.user_id == user_id,
                Resume.is_processed == True
            ).all()

            # Create new cosine-similarity index
            self.__class__._index = faiss.IndexFlatIP(self.EMBEDDING_DIMENSION)
            self.__class__._resume_embeddings = {}

            if resumes:
                # Batch encode for speed
                ids = [r.id for r in resumes]
                texts = [r.extracted_text or "" for r in resumes]
                self.add_resumes_batch(ids, texts)

            self.save_index()
            logger.info(f"✓ Index rebuilt with {len(resumes)} resumes")
            return True

        except Exception as e:
            logger.error(f"✗ Error rebuilding index: {str(e)}")
            return False


# Need json import for search_with_scoring
import json

# Singleton instance
_search_service_instance = None


def get_search_service() -> SemanticSearchService:
    """Get or create search service singleton."""
    global _search_service_instance
    if _search_service_instance is None:
        _search_service_instance = SemanticSearchService()
    return _search_service_instance


if __name__ == "__main__":
    logger.info("Testing semantic search service...")
    service = get_search_service()
    print(f"✓ Search service ready. Index size: {service.index.ntotal}")
