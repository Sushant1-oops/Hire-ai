# utils.py
import os
import json
import logging
import re
from datetime import datetime
from contextvars import ContextVar
from typing import Any, Dict, List, Optional
from pathlib import Path
from ai.skills_extractor import SkillsExtractor

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_var.get(),
        }
        for key in ("event", "user_id", "resume_id", "job_id", "duration_ms", "status_code", "path"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class _TextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        record.request_id = request_id_var.get()
        return super().format(record)


def setup_logging(name: str = "ai_hr_saas") -> logging.Logger:
    import sys
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    if logger.handlers:
        return logger
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    if os.getenv("LOG_FORMAT", "text").lower() == "json":
        ch.setFormatter(JsonFormatter())
    else:
        ch.setFormatter(_TextFormatter("%(asctime)s - %(levelname)s - [%(request_id)s] - %(message)s"))
    logger.addHandler(ch)
    # A file handler only makes sense on a machine with a persistent disk. In
    # containers the platform collects stdout, so it is opt-in.
    if os.getenv("LOG_TO_FILE", "false").lower() in {"1", "true", "yes"}:
        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)
        fh = logging.FileHandler(log_dir / f"{name}_{datetime.now().strftime('%Y%m%d')}.log", encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(JsonFormatter() if os.getenv("LOG_FORMAT", "text").lower() == "json" else _TextFormatter("%(asctime)s - %(levelname)s - [%(request_id)s] - %(message)s"))
        logger.addHandler(fh)
    return logger

logger = setup_logging()

def ensure_directory(directory: str) -> Path:
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=True)
    return path

def extract_skills_from_text(text: str) -> List[str]:
    return SkillsExtractor().extract(text)

def extract_experience_years(text: str) -> Optional[float]:
    from ai.extraction import extract_experience
    return extract_experience(text)[0]

def extract_education(text: str) -> List[Dict]:
    from ai.extraction import extract_education as _extract_education
    return _extract_education(text)

def clean_text(text: str) -> str:
    text = ' '.join(text.split())
    text = re.sub(r'[^\w\s\-.,@+()/:;]', '', text)
    return text.strip()

def validate_email(email: str) -> bool:
    return re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email) is not None

def safe_json_loads(json_str: str, default=None) -> Any:
    try: return json.loads(json_str) if json_str else default
    except: return default

def safe_json_dumps(obj: Any, default=None) -> str:
    try: return json.dumps(obj, default=str)
    except: return default or "[]"

def error_response(code: int, message: str, details: Optional[str] = None) -> Dict:
    return {"error": True, "code": code, "message": message, "details": details, "timestamp": datetime.utcnow().isoformat()}

def success_response(data: Any = None, message: str = "Success") -> Dict:
    return {"error": False, "message": message, "data": data, "timestamp": datetime.utcnow().isoformat()}

def fail(code: int, message: str, details: Optional[str] = None, headers: Optional[Dict[str, str]] = None):
    """Error response with a real HTTP status. (The old handlers returned the error
    envelope with HTTP 200, so the frontend saw a 'successful' request with null data.)"""
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=code, content=error_response(code, message, details), headers=headers)
