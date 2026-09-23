from concurrent.futures import ThreadPoolExecutor

from core.config import REDIS_URL
from .cache_service import get_redis
from core.utils import logger

QUEUE_NAME = "resumes"
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="resume-inline")


def _rq_connection():
    import redis
    # RQ pickles job data, so it needs a connection without decode_responses.
    return redis.Redis.from_url(REDIS_URL)


def redis_mode() -> bool:
    return get_redis() is not None


def enqueue_resume_processing(resume_id: int) -> str:
    """Durable path: a job on the Redis queue, picked up by `python worker.py`.
    Without REDIS_URL (local dev) the job runs on a thread inside the API
    process. That fallback is convenient but loses in-flight jobs if the process
    dies, which is exactly why production runs Redis plus a worker."""
    if redis_mode():
        from rq import Queue, Retry
        queue = Queue(QUEUE_NAME, connection=_rq_connection())
        queue.enqueue(
            "tasks.process_resume_job",
            resume_id,
            job_timeout=900,
            retry=Retry(max=2, interval=[15, 60]),
            result_ttl=0,
            failure_ttl=86400,
        )
        return "redis"
    from tasks import process_resume_job
    _executor.submit(process_resume_job, resume_id)
    logger.info("Redis not configured: processing resume inline", extra={"resume_id": resume_id})
    return "inline"
