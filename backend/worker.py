"""Run with:  python worker.py   (needs REDIS_URL)"""
import sys

from services import embedding_service
from ai import reranker
from core.config import REDIS_URL
from services.queue_service import QUEUE_NAME, _rq_connection
from core.utils import logger


def main() -> int:
    if not REDIS_URL:
        logger.error("REDIS_URL is not set; there is no queue to work on.")
        return 1
    from rq import Worker

    embedding_service.warmup()
    reranker.is_available()
    worker = Worker([QUEUE_NAME], connection=_rq_connection())
    logger.info(f"Worker listening on queue '{QUEUE_NAME}'")
    worker.work(with_scheduler=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
