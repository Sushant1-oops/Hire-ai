

import os
import time
from typing import Optional

from utils import logger

LANGSMITH_ENABLED = bool(os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY"))
_traceable_impl = None
_trace_impl = None

if LANGSMITH_ENABLED:
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    if os.getenv("LANGSMITH_API_KEY") and not os.getenv("LANGCHAIN_API_KEY"):
        os.environ["LANGCHAIN_API_KEY"] = os.getenv("LANGSMITH_API_KEY")
    os.environ.setdefault("LANGCHAIN_PROJECT", os.getenv("LANGSMITH_PROJECT", "hireai"))
    try:
        from langsmith import traceable as _traceable_impl  
        from langsmith.run_helpers import trace as _trace_impl
        logger.info(f"LangSmith tracing enabled (project: {os.environ['LANGCHAIN_PROJECT']})")
    except Exception as e:
        logger.warning(f"LANGSMITH_API_KEY is set but the langsmith package failed to import ({e}); "
                        f"tracing disabled. Run: pip install langsmith")
        LANGSMITH_ENABLED = False


def traceable(*t_args, **t_kwargs):
    
    if LANGSMITH_ENABLED and _traceable_impl:
        return _traceable_impl(*t_args, **t_kwargs)

    def _decorator(fn):
        return fn
    return _decorator


def langsmith_status() -> dict:
    return {
        "enabled": LANGSMITH_ENABLED,
        "project": os.environ.get("LANGCHAIN_PROJECT") if LANGSMITH_ENABLED else None,
    }


class LangSmithTracingMiddleware:
    

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not LANGSMITH_ENABLED or not _trace_impl:
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "")
        path = scope.get("path", "")
        status_holder = {"code": None}

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                status_holder["code"] = message["status"]
            await send(message)

        
        
        
        
        run_cm, run = None, None
        try:
            run_cm = _trace_impl(name=f"{method} {path}", run_type="chain", inputs={"method": method, "path": path})
            run = run_cm.__enter__()
        except Exception:
            logger.warning("LangSmith request trace failed to start; continuing without it", exc_info=True)
            run_cm = None

        start = time.perf_counter()
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            if run_cm is not None:
                try:
                    duration_ms = round((time.perf_counter() - start) * 1000, 1)
                    if run is not None:
                        run.end(outputs={"status_code": status_holder["code"], "duration_ms": duration_ms})
                    run_cm.__exit__(None, None, None)
                except Exception:
                    logger.warning("LangSmith request trace failed to finish", exc_info=True)
