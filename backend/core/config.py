import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# backend/ — this file is backend/core/config.py, so two levels up.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(_BACKEND_DIR, ".env"))


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


INSECURE_DEFAULT_KEY = "your-secret-key-change-in-production"

APP_ENV = os.getenv("APP_ENV", "development").lower()
IS_PRODUCTION = APP_ENV == "production"
SECRET_KEY = os.getenv("SECRET_KEY", INSECURE_DEFAULT_KEY)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/ai_hr_saas")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = "postgresql+psycopg2://" + DATABASE_URL[len("postgres://"):]
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = "postgresql+psycopg2://" + DATABASE_URL[len("postgresql://"):]

REDIS_URL = os.getenv("REDIS_URL", "").strip()

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_DIM = 384

RERANKER_ENABLED = _bool("RERANKER_ENABLED", True)
RERANKER_MODEL = os.getenv("RERANKER_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
RERANK_BLEND = _float("RERANK_BLEND", 0.3)
RETRIEVE_K = _int("RETRIEVE_K", 50)
RERANK_KEEP = _int("RERANK_KEEP", 20)

# MiniLM cosine similarity between a job and a genuinely relevant resume
# typically lands around 0.4-0.6, and an unrelated one around 0.1-0.2, so the
# raw number never spans 0-1. The semantic score is stretched from this window
# onto 0-1 before it is blended into the final score; otherwise the 40% weight
# it carries can never be fully earned and every score is quietly compressed.
# These are starting values: tune them with `python -m evaluation.run_retrieval`
# on labelled resumes from your own domain.
SEMANTIC_FLOOR = _float("SEMANTIC_FLOOR", 0.15)
SEMANTIC_CEIL = _float("SEMANTIC_CEIL", 0.65)

MAX_UPLOAD_MB = _int("MAX_UPLOAD_MB", 10)
MAX_BATCH_FILES = _int("MAX_BATCH_FILES", 25)

STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "auto").lower()
CLOUDINARY_URL = os.getenv("CLOUDINARY_URL", "").strip()
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip()
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "").strip()
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "").strip()
CLOUDINARY_FOLDER = os.getenv("CLOUDINARY_FOLDER", "hireai/resumes")
# Anchored to the backend/ directory rather than left as a bare relative path:
# a relative path is resolved against the process's current working directory,
# which differs between "uvicorn main:app" run from backend/, a --reload
# restart, and a container's WORKDIR — any mismatch make previously-uploaded
# files "disappear" (they are still on disk, just under a different absolute
# path than the one being read from). An absolute LOCAL_STORAGE_DIR in the
# environment is still honoured as-is.
_default_storage_dir = os.path.join(_BACKEND_DIR, "data", "resumes")
LOCAL_STORAGE_DIR = os.getenv("LOCAL_STORAGE_DIR", _default_storage_dir)
if not os.path.isabs(LOCAL_STORAGE_DIR):
    LOCAL_STORAGE_DIR = os.path.join(_BACKEND_DIR, LOCAL_STORAGE_DIR)

ACCESS_TOKEN_MINUTES = _int("ACCESS_TOKEN_MINUTES", 30)
REFRESH_TOKEN_DAYS = _int("REFRESH_TOKEN_DAYS", 7)
REFRESH_REUSE_GRACE_SECONDS = _int("REFRESH_REUSE_GRACE_SECONDS", 10)
MIN_PASSWORD_LENGTH = _int("MIN_PASSWORD_LENGTH", 8)

TRUST_PROXY = _bool("TRUST_PROXY", False)
RATE_LIMIT_ENABLED = _bool("RATE_LIMIT_ENABLED", True)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("LLM_MODEL", "llama3.2:3b")

SMTP_SERVER = os.getenv("SMTP_SERVER", "").strip()
SMTP_PORT = _int("SMTP_PORT", 587)
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "").strip() or SMTP_USERNAME

LLM_REDACT_PII = _bool("LLM_REDACT_PII", True)
LLM_MAX_INPUT_CHARS = _int("LLM_MAX_INPUT_CHARS", 12000)
LLM_MAX_RETRIES = _int("LLM_MAX_RETRIES", 3)
GROQ_TIMEOUT = _int("GROQ_TIMEOUT", 30)
OLLAMA_TIMEOUT = _int("OLLAMA_TIMEOUT", 180)

EVIDENCE_MIN_SIMILARITY = _float("EVIDENCE_MIN_SIMILARITY", 0.30)
OCR_ENABLED = _bool("OCR_ENABLED", True)
# Pages read from a PDF. Real resumes are 1-3 pages; a 400-page upload should
# not be able to hold a worker for minutes.
MAX_PDF_PAGES = _int("MAX_PDF_PAGES", 12)
NER_ENABLED = _bool("NER_ENABLED", True)
NAME_CONFIDENCE_THRESHOLD = _float("NAME_CONFIDENCE_THRESHOLD", 0.6)


def validate_for_startup(logger, allowed_origins: str = "*") -> None:
    weak = SECRET_KEY == INSECURE_DEFAULT_KEY or len(SECRET_KEY) < 32
    if weak and IS_PRODUCTION:
        raise RuntimeError("SECRET_KEY must be set to a random value of 32+ characters when APP_ENV=production")
    if weak:
        logger.warning("SECRET_KEY is weak or default. Fine for local dev, not for a deployment.")
    if IS_PRODUCTION and allowed_origins.strip() == "*":
        raise RuntimeError("ALLOWED_ORIGINS must list your frontend origin(s) when APP_ENV=production")
    if not DATABASE_URL.startswith("postgresql"):
        raise RuntimeError("DATABASE_URL must be a PostgreSQL connection string. SQLite is not supported.")
