from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status, Request
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from ..db.database import get_db
from ..models.schemas import User
from ..core.config import settings

# --- 비밀번호 처리 ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# --- JWT 처리 ---
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_token_from_cookie(request: Request) -> Optional[str]:
    token = request.cookies.get("access_token")
    if token and token.startswith("Bearer "):
        return token.split(" ")[1]
    return None

from sqlalchemy import text

from functools import lru_cache

@lru_cache(maxsize=128)
def get_user_from_db(username: str, db: Session) -> User:
    db_user = db.execute(text("SELECT role FROM employees WHERE name = :username"), {"username": username}).fetchone()
    if db_user is None:
        return None
    return User(name=username, role=db_user[0])

def get_current_user(request: Request, db: Session = Depends(get_db), use_cache: bool = True) -> User:
    token = get_token_from_cookie(request)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    if use_cache:
        user = get_user_from_db(username, db)
    else:
        user = get_user_from_db.__wrapped__(username, db)

    if user is None:
        raise credentials_exception
    
    return user

def require_role(allowed_roles: list[str], use_cache: bool = True):
    """
    현재 사용자의 역할이 허용된 역할 목록에 있는지 확인하는 의존성 함수를 생성합니다.
    """
    def dependency(request: Request, db: Session = Depends(get_db)) -> User:
        current_user = get_current_user(request, db, use_cache=use_cache)
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="이 페이지에 접근할 권한이 없습니다.",
            )
        return current_user
    return dependency
