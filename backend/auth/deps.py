from typing import Callable

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from .auth import get_user_by_id, verify_token
from core.database import get_db
from models import User
from core.rate_limit import enforce


def get_current_user(
    request: Request,
    token: str | None = Cookie(default=None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> User:
    """The tenant is always derived from the verified token, never from anything
    the client sends in the request body or query string."""
    if not token and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    user_id = verify_token(token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    user = get_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    request.state.user_id = user.id
    return user


def user_limit(name: str, limit: int, window_seconds: int) -> Callable:
    """Per-account rate limit dependency. Returns the user so endpoints can use
    it directly in place of get_current_user."""

    def dependency(user: User = Depends(get_current_user)) -> User:
        enforce(name, user.id, limit, window_seconds)
        return user

    return dependency
