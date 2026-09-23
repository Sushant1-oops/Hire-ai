from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import get_db
from auth.deps import user_limit
from services.embedding_service import EmbeddingUnavailable
from models import SearchHistory, User
from services.search_service import search_with_scoring
from ai.skills_extractor import SkillsExtractor
from core.utils import fail, logger, safe_json_dumps, success_response

router = APIRouter(prefix="/api", tags=["search"])


class SearchRequest(BaseModel):
    query: str = Field(min_length=2, max_length=6000)
    job_description: Optional[str] = Field(default=None, max_length=20000)
    required_skills: Optional[List[str]] = None
    min_experience: Optional[float] = Field(default=None, ge=0, le=50)
    nice_to_have_skills: Optional[List[str]] = None
    nice_to_have_experience: Optional[float] = Field(default=None, ge=0, le=50)
    top_k: int = Field(default=10, ge=1, le=50)
    min_score: Optional[float] = Field(default=None, ge=0, le=1)
    hard_min_experience: Optional[float] = Field(default=None, ge=0, le=50)
    must_have_skills: Optional[List[str]] = None


@router.post("/search")
def semantic_search(request: SearchRequest, current_user: User = Depends(user_limit("search", 120, 60)), db: Session = Depends(get_db)):
    required_skills = request.required_skills or []
    if not required_skills and request.job_description:
        required_skills = SkillsExtractor().extract(request.job_description)
    try:
        result = search_with_scoring(
            db, current_user.id, request.query, required_skills=required_skills, top_k=request.top_k,
            min_experience=request.min_experience, nice_to_have_skills=request.nice_to_have_skills,
            nice_to_have_experience=request.nice_to_have_experience, min_score=request.min_score,
            hard_min_experience=request.hard_min_experience, must_have_skills=request.must_have_skills,
        )
    except EmbeddingUnavailable:
        return fail(503, "Search is temporarily unavailable (embedding model not loaded)")
    except Exception as e:
        logger.error(f"search failed: {e}", exc_info=True)
        return fail(500, "Search failed")

    summary = result["summary"]
    db.add(SearchHistory(
        user_id=current_user.id, query=request.query[:2000], required_skills=safe_json_dumps(required_skills),
        min_experience=request.min_experience, results_count=len(result["results"]),
    ))
    db.commit()
    return success_response(data=result, message=f"Found {summary.get('total_above_threshold', len(result['results']))} matching candidates")
