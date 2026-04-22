"""
Authentication module with JWT and bcrypt password hashing.
Provides user registration, login, and token management.
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Tuple
from jose import JWTError, jwt
import bcrypt
# from passlib.context import CryptContext  # replaced by direct bcrypt use
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session
from models import User

# Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
REFRESH_TOKEN_EXPIRE_DAYS = 7

# Password hashing
# using direct bcrypt calls instead of passlib context due to compatibility issues
# pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ==================== SCHEMAS ====================
class TokenResponse(BaseModel):
    """Response model for authentication tokens."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserRegisterRequest(BaseModel):
    """User registration request."""
    email: EmailStr
    username: str
    password: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    company: Optional[str] = None


class UserLoginRequest(BaseModel):
    """User login request."""
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """User response model."""
    id: int
    email: str
    username: str
    first_name: str
    last_name: str
    company: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenPayload(BaseModel):
    """JWT token payload."""
    sub: str  # user_id
    exp: datetime


# ==================== PASSWORD HASHING ====================
def hash_password(password: str) -> str:
    """Hash a password using bcrypt directly, returning the encoded string."""
    # bcrypt has a 72-byte limit; we ensure password is encoded to utf-8
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    # store as utf-8 string for database
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its bcrypt hash using bcrypt.checkpw."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        # if the hash is somehow malformed, deny access
        return False


# ==================== JWT TOKENS ====================
def create_access_token(user_id: int) -> str:
    """Create a JWT access token."""
    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": datetime.utcnow(),
        "type": "access",
    }
    encoded_jwt = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(user_id: int) -> str:
    """Create a JWT refresh token."""
    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "iat": datetime.utcnow(),
        "type": "refresh",
    }
    encoded_jwt = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[int]:
    """
    Verify a JWT token and return user_id.
    Returns None if token is invalid or expired.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        return int(user_id)
    except JWTError:
        return None


# ==================== USER OPERATIONS ====================
def register_user(db: Session, user_data: UserRegisterRequest) -> dict:
    """
    Register a new user.
    Returns dict with keys: user (UserResponse or None), error (str or None)
    """
    # Check if email already exists
    existing_email = db.query(User).filter(User.email == user_data.email.lower()).first()
    if existing_email:
        return {"user": None, "error": "Email already registered"}

    # Check if username already exists
    existing_username = db.query(User).filter(User.username == user_data.username.lower()).first()
    if existing_username:
        return {"user": None, "error": "Username already taken"}

    try:
        # Create new user
        new_user = User(
            email=user_data.email.lower(),
            username=user_data.username.lower(),
            hashed_password=hash_password(user_data.password),
            first_name=user_data.first_name or "",
            last_name=user_data.last_name or "",
            company=user_data.company,
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)
        return {"user": UserResponse.from_orm(new_user), "error": None}
    except Exception as e:
        db.rollback()
        return {"user": None, "error": f"Registration failed: {str(e)}"}


def login_user(db: Session, login_data: UserLoginRequest) -> Optional[User]:
    """
    Authenticate user with email and password.
    Returns User object if credentials are valid, None otherwise.
    """
    # Case-insensitive email lookup
    user = db.query(User).filter(User.email == login_data.email.lower()).first()

    if not user or not verify_password(login_data.password, user.hashed_password):
        return None

    if not user.is_active:
        return None

    return user


def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """Get user by ID."""
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """Get user by email (case-insensitive)."""
    return db.query(User).filter(User.email == email.lower()).first()


def update_user(db: Session, user_id: int, **kwargs) -> Optional[User]:
    """Update user information."""
    user = get_user_by_id(db, user_id)
    if not user:
        return None

    for key, value in kwargs.items():
        if hasattr(user, key) and key not in ["id", "hashed_password"]:
            setattr(user, key, value)

    user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return user


def deactivate_user(db: Session, user_id: int) -> bool:
    """Deactivate a user account."""
    user = get_user_by_id(db, user_id)
    if not user:
        return False

    user.is_active = False
    user.updated_at = datetime.utcnow()
    db.commit()
    return True
