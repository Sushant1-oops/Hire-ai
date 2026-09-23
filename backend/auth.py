
import os
import random
from datetime import datetime, timedelta
from typing import Optional, Tuple
from dotenv import load_dotenv, find_dotenv
from jose import JWTError, jwt
import bcrypt

load_dotenv(find_dotenv())
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))

from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session
from models import User

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24
REFRESH_TOKEN_EXPIRE_DAYS = 7

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

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
        
        
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v

class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
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
    sub: str
    exp: datetime

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except Exception:
        return False

def create_access_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "iat": datetime.utcnow(),
        "type": "access",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(user_id: int) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "iat": datetime.utcnow(),
        "type": "refresh",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def verify_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        return int(user_id)
    except JWTError:
        return None

def register_user(db: Session, user_data: UserRegisterRequest) -> dict:
    if not user_data.username:
        user_data.username = user_data.email.split('@')[0]

    if user_data.full_name and not user_data.first_name:
        parts = user_data.full_name.split(' ', 1)
        user_data.first_name = parts[0]
        user_data.last_name = parts[1] if len(parts) > 1 else ""
    elif not user_data.first_name:
        user_data.first_name = ""
        user_data.last_name = user_data.last_name or ""

    existing_email = db.query(User).filter(User.email == user_data.email.lower()).first()
    if existing_email:
        return {"user": None, "error": "Email already registered"}

    existing_username = db.query(User).filter(User.username == user_data.username.lower()).first()
    if existing_username:
        user_data.username = f"{user_data.username}{random.randint(10, 99)}"

    try:
        new_user = User(
            email=user_data.email.lower(),
            username=user_data.username.lower(),
            hashed_password=hash_password(user_data.password),
            first_name=user_data.first_name,
            last_name=user_data.last_name,
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
    user = db.query(User).filter(User.email == login_data.email.lower()).first()
    if not user or not verify_password(login_data.password, user.hashed_password):
        return None
    if not user.is_active:
        return None
    return user

def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    return db.query(User).filter(User.id == user_id).first()

def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.query(User).filter(User.email == email.lower()).first()