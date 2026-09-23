from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

import core.audit as audit
from auth import (
    UserLoginRequest, UserRegisterRequest, UserResponse, create_access_token, issue_refresh_token,
    login_user, register_user, revoke_token_family, rotate_refresh_token,
)
from core.database import get_db
from auth.deps import get_current_user
from models import User
from core.rate_limit import ip_limit
from core.utils import fail, success_response

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RefreshTokenRequest(BaseModel):
    refresh_token: str


def _tokens(db: Session, user: User, request: Request) -> dict:
    refresh, _ = issue_refresh_token(db, user.id, user_agent=request.headers.get("user-agent"))
    return {"access_token": create_access_token(user.id), "refresh_token": refresh, "token_type": "bearer"}


@router.post("/register", dependencies=[Depends(ip_limit("register", 10, 3600))])
def register(payload: UserRegisterRequest, request: Request, db: Session = Depends(get_db)):
    result = register_user(db, payload)
    if result["error"]:
        return fail(400, result["error"])
    user = result["user"]
    audit.record(db, "user_registered", user_id=user.id, resource_type="user", resource_id=user.id, request=request)
    return success_response(
        data={"user": UserResponse.model_validate(user).model_dump(mode="json"), **_tokens(db, user, request)},
        message="Registration successful",
    )


@router.post("/login", dependencies=[Depends(ip_limit("login", 10, 60))])
def login(payload: UserLoginRequest, request: Request, db: Session = Depends(get_db)):
    user = login_user(db, payload)
    if not user:
        audit.record(db, "login_failed", request=request)
        return fail(401, "Invalid credentials")
    audit.record(db, "user_login", user_id=user.id, resource_type="user", resource_id=user.id, request=request)
    return success_response(
        data={**_tokens(db, user, request), "user": UserResponse.model_validate(user).model_dump(mode="json")},
        message="Login successful",
    )


@router.post("/refresh", dependencies=[Depends(ip_limit("refresh", 30, 60))])
def refresh(payload: RefreshTokenRequest, request: Request, db: Session = Depends(get_db)):
    rotated = rotate_refresh_token(db, payload.refresh_token, user_agent=request.headers.get("user-agent"))
    if not rotated:
        return fail(401, "Invalid refresh token")
    user_id, new_refresh = rotated
    return success_response(data={"access_token": create_access_token(user_id), "refresh_token": new_refresh, "token_type": "bearer"})


@router.post("/logout")
def logout(payload: RefreshTokenRequest, request: Request, db: Session = Depends(get_db)):
    revoke_token_family(db, payload.refresh_token)
    return success_response(message="Signed out")


@router.get("/me")
def me(current_user: User = Depends(get_current_user)):
    return success_response(data=UserResponse.model_validate(current_user).model_dump(mode="json"))
