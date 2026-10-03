from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from services.cache_service import get_redis
from core.config import REDIS_URL
from core.database import db_ready, get_db
from auth.deps import get_current_user
from services.llm_service import get_llm_status
from models import User
from services.queue_service import redis_mode
from services.dashboard_service import get_dashboard
from services.storage_service import default_backend_name
from core.utils import success_response

router = APIRouter(tags=["system"])


@router.get("/health/live")
def live():
    """Liveness: the process is up. No dependencies on purpose."""
    return {"status": "alive"}


@router.get("/health/ready")
def ready():
    """Readiness: can this replica serve traffic? Needs the database. Redis is
    required only when REDIS_URL is configured."""
    checks = {"database": db_ready()}
    if REDIS_URL:
        checks["redis"] = get_redis() is not None
    ok = all(checks.values())
    return JSONResponse(status_code=200 if ok else 503, content={"status": "ready" if ok else "not_ready", "checks": checks})


@router.get("/health")
def health():
    return {
        "status": "healthy",
        "llm": get_llm_status(),
        "queue": "redis" if redis_mode() else "inline",
        "storage": default_backend_name(),
    }


@router.get("/api/dashboard/stats")
def get_dashboard_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return success_response(data=get_dashboard(db, current_user.id))
