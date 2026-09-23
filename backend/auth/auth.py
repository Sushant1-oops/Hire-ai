import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional, Tuple

import bcrypt
from jose import JWTError, jwt
from pydantic import BaseModel, ConfigDict, EmailStr, field_validator
from sqlalchemy.orm import Session

from core.config import ACCESS_TOKEN_MINUTES, MIN_PASSWORD_LENGTH, REFRESH_REUSE_GRACE_SECONDS, REFRESH_TOKEN_DAYS, SECRET_KEY
from models import RefreshToken, User
from core.utils import logger

ALGORITHM = "HS256"


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str
    username: Optional[str] = None
    full_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None

    @field_validator("password")
    @classmethod
    def password_min_length(cls, v: str) -> str:
        if len(v) < MIN_PASSWORD_LENGTH:
            raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters")
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 bytes")  # bcrypt ignores everything past 72
        return v


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    username: str
    first_name: str
    last_name: str
    company: Optional[str]
    is_active: bool
    created_at: datetime


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: int) -> str:
    now = datetime.utcnow()
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _decode(token: str, expected_type: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
    if payload.get("type") != expected_type or payload.get("sub") is None:
        return None
    return payload


def verify_token(token: str) -> Optional[int]:
    """Access tokens only. A refresh token presented as a bearer token is rejected."""
    payload = _decode(token, "access")
    if not payload:
        return None
    try:
        return int(payload["sub"])
    except (TypeError, ValueError):
        return None


def issue_refresh_token(db: Session, user_id: int, family_id: Optional[str] = None, user_agent: Optional[str] = None) -> Tuple[str, str]:
    """Creates a refresh token and its server-side record. Returns (token, jti)."""
    now = datetime.utcnow()
    jti = uuid.uuid4().hex
    family_id = family_id or uuid.uuid4().hex
    expires = now + timedelta(days=REFRESH_TOKEN_DAYS)
    payload = {"sub": str(user_id), "type": "refresh", "jti": jti, "fid": family_id, "iat": now, "exp": expires}
    db.add(RefreshToken(user_id=user_id, jti=jti, family_id=family_id, expires_at=expires, user_agent=(user_agent or "")[:255]))
    db.commit()
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM), jti


def rotate_refresh_token(db: Session, token: str, user_agent: Optional[str] = None) -> Optional[Tuple[int, str]]:
    """Single-use refresh. The presented token is revoked and a new one issued in
    the same family. If a token that was already used shows up again, someone is
    replaying it, so every token in that family is revoked."""
    payload = _decode(token, "refresh")
    if not payload or not payload.get("jti"):
        return None
    record = db.query(RefreshToken).filter(RefreshToken.jti == payload["jti"]).first()
    if not record:
        return None
    if record.revoked_at is not None:
        just_rotated = (
            record.replaced_by is not None
            and (datetime.utcnow() - record.revoked_at).total_seconds() < REFRESH_REUSE_GRACE_SECONDS
        )
        if just_rotated:
            return None  # two tabs refreshing at once; reject this one but keep the session alive
        logger.warning(f"refresh token reuse detected for user {record.user_id}; revoking family")
        revoke_family(db, record.family_id)
        return None
    if record.expires_at < datetime.utcnow():
        return None
    user = db.query(User).filter(User.id == record.user_id, User.is_active.is_(True)).first()
    if not user:
        return None

    record.revoked_at = datetime.utcnow()  # committed together with the new token's row below
    new_token, new_jti = issue_refresh_token(db, user.id, family_id=record.family_id, user_agent=user_agent)
    record.replaced_by = new_jti
    db.commit()
    return user.id, new_token


def revoke_family(db: Session, family_id: str) -> None:
    now = datetime.utcnow()
    db.query(RefreshToken).filter(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None)).update(
        {"revoked_at": now}, synchronize_session=False
    )
    db.commit()


def revoke_token_family(db: Session, token: str) -> bool:
    payload = _decode(token, "refresh")
    if not payload or not payload.get("fid"):
        return False
    revoke_family(db, payload["fid"])
    return True


def revoke_all_for_user(db: Session, user_id: int) -> None:
    db.query(RefreshToken).filter(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None)).update(
        {"revoked_at": datetime.utcnow()}, synchronize_session=False
    )
    db.commit()


def register_user(db: Session, user_data: UserRegisterRequest) -> dict:
    username = (user_data.username or user_data.email.split("@")[0]).lower()

    first_name, last_name = user_data.first_name, user_data.last_name
    if user_data.full_name and not first_name:
        parts = user_data.full_name.split(" ", 1)
        first_name = parts[0]
        last_name = parts[1] if len(parts) > 1 else ""
    first_name = first_name or ""
    last_name = last_name or ""

    email = user_data.email.lower()
    if db.query(User).filter(User.email == email).first():
        return {"user": None, "error": "Email already registered"}

    candidate = username
    for _ in range(6):
        if not db.query(User).filter(User.username == candidate).first():
            break
        candidate = f"{username}{secrets.randbelow(9000) + 1000}"
    else:
        return {"user": None, "error": "Could not allocate a username, please try again"}

    try:
        new_user = User(
            email=email,
            username=candidate,
            hashed_password=hash_password(user_data.password),
            first_name=first_name,
            last_name=last_name,
            company=user_data.company,
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return {"user": new_user, "error": None}
    except Exception as e:
        db.rollback()
        logger.error(f"registration failed: {e}")
        return {"user": None, "error": "Registration failed"}


_dummy_hash: Optional[str] = None


def login_user(db: Session, login_data: UserLoginRequest) -> Optional[User]:
    global _dummy_hash
    user = db.query(User).filter(User.email == login_data.email.lower()).first()
    if not user:
        # Spend the same bcrypt time as a real check so response timing doesn't reveal which emails exist.
        _dummy_hash = _dummy_hash or hash_password("not-a-real-password")
        verify_password(login_data.password, _dummy_hash)
        return None
    if not verify_password(login_data.password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email.lower()).first()
