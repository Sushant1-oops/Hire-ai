import os
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from starlette.exceptions import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

import core.config as config
from services import embedding_service
from ai import reranker
from core.database import init_db
from core.observability import LangSmithTracingMiddleware
from routers import ai_routes, auth_routes, job_routes, resume_routes, search_routes, system_routes
from core.utils import fail, logger, request_id_var, safe_json_dumps


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.validate_for_startup(logger, os.getenv("ALLOWED_ORIGINS", "*"))
    init_db()
    # Load models at startup so the first user request isn't the one that pays for it.
    if not embedding_service.warmup():
        logger.warning("Embedding model failed to load: search and resume processing will return errors until it does")
    reranker.is_available()
    yield


app = FastAPI(title="HireAI", version="2.0.0", lifespan=lifespan)

_allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "*")
ALLOWED_ORIGINS = ["*"] if _allowed_origins_env.strip() == "*" else [o.strip() for o in _allowed_origins_env.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=ALLOWED_ORIGINS != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "Retry-After"],
)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Request id on every log line and response, plus one access-log line per
    request. Also sets the baseline security headers."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        try:
            # Public endpoints take uploads from strangers: refuse oversized bodies before parsing them.
            declared = request.headers.get("content-length")
            if request.url.path.startswith("/api/public/") and declared and declared.isdigit() \
                    and int(declared) > (config.MAX_UPLOAD_MB + 1) * 1024 * 1024:
                response = fail(413, f"Upload is larger than {config.MAX_UPLOAD_MB} MB")
            else:
                response = await call_next(request)
            duration_ms = round((time.perf_counter() - started) * 1000)
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "no-referrer"
            if request.url.path not in ("/health/live", "/health/ready"):
                logger.info(
                    f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms} ms)",
                    extra={"event": "http_request", "path": request.url.path, "status_code": response.status_code, "duration_ms": duration_ms},
                )
            return response
        finally:
            request_id_var.reset(token)


app.add_middleware(RequestContextMiddleware)
app.add_middleware(LangSmithTracingMiddleware)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    first = exc.errors()[0] if exc.errors() else None
    field = ".".join(str(p) for p in first["loc"] if p != "body") if first else None
    message = f"{field}: {first['msg']}" if first and field else (first["msg"] if first else "Invalid request")
    return fail(422, message, safe_json_dumps([{"loc": e.get("loc"), "msg": e.get("msg")} for e in exc.errors()]))


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return fail(exc.status_code, str(exc.detail), headers=dict(exc.headers) if exc.headers else None)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.method} {request.url.path}: {exc}", exc_info=True)
    return fail(500, "Something went wrong on our side")


for module in (system_routes, auth_routes, resume_routes, job_routes, search_routes, ai_routes):
    app.include_router(module.router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=os.getenv("APP_ENV", "development") != "production")
