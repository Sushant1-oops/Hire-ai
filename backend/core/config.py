import os
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))


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

MAX_UPLOAD_MB = _int("MAX_UPLOAD_MB", 10)
MAX_BATCH_FILES = _int("MAX_BATCH_FILES", 25)

STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "auto").lower()
CLOUDINARY_URL = os.getenv("CLOUDINARY_URL", "").strip()
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME", "").strip()
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY", "").strip()
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET", "").strip()
CLOUDINARY_FOLDER = os.getenv("CLOUDINARY_FOLDER", "hireai/resumes")
LOCAL_STORAGE_DIR = os.getenv("LOCAL_STORAGE_DIR", "data/resumes")

ACCESS_TOKEN_MINUTES = _int("ACCESS_TOKEN_MINUTES", 30)
REFRESH_TOKEN_DAYS = _int("REFRESH_TOKEN_DAYS", 7)
REFRESH_REUSE_GRACE_SECONDS = _int("REFRESH_REUSE_GRACE_SECONDS", 10)
MIN_PASSWORD_LENGTH = _int("MIN_PASSWORD_LENGTH", 8)

TRUST_PROXY = _bool("TRUST_PROXY", False)
RATE_LIMIT_ENABLED = _bool("RATE_LIMIT_ENABLED", True)

LLM_REDACT_PII = _bool("LLM_REDACT_PII", True)
LLM_MAX_INPUT_CHARS = _int("LLM_MAX_INPUT_CHARS", 12000)
LLM_MAX_RETRIES = _int("LLM_MAX_RETRIES", 3)
GROQ_TIMEOUT = _int("GROQ_TIMEOUT", 30)
OLLAMA_TIMEOUT = _int("OLLAMA_TIMEOUT", 180)

EVIDENCE_MIN_SIMILARITY = _float("EVIDENCE_MIN_SIMILARITY", 0.30)
OCR_ENABLED = _bool("OCR_ENABLED", True)
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
