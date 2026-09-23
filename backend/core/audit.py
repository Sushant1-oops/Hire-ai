from typing import Optional

from fastapi import Request
from sqlalchemy.orm import Session

from models import AuditLog
from core.rate_limit import client_ip
from core.utils import logger, safe_json_dumps


def record(
    db: Session,
    action: str,
    user_id: Optional[int] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[object] = None,
    request: Optional[Request] = None,
    **meta,
) -> None:
    """Best-effort audit entry. Metadata must stay small and must never contain
    resume text or contact details: ids, counts, statuses only. A failure here is
    logged and swallowed so auditing can never break the request it describes."""
    try:
        db.add(
            AuditLog(
                user_id=user_id,
                action=action,
                resource_type=resource_type,
                resource_id=str(resource_id) if resource_id is not None else None,
                ip_address=client_ip(request) if request is not None else None,
                meta=safe_json_dumps(meta) if meta else None,
            )
        )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"audit write failed for {action}: {e}")
