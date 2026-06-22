import os
from passlib.context import CryptContext
from jose import jwt, JWTError
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

SECRET_KEY = "railguard_hf_secret_2024"
ALGORITHM  = "HS256"
EXPIRE_MIN = 480

def is_dev_mode() -> bool:
    return os.getenv("DEV_MODE", "false").lower() == "true"

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def hash_password(pw: str) -> str:
    if is_dev_mode():
        return pw  # no hashing needed in dev
    return pwd_context.hash(pw)

def verify_password(plain: str, hashed: str) -> bool:
    if is_dev_mode():
        return True  # always true in dev
    return pwd_context.verify(plain, hashed)

def create_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=EXPIRE_MIN)
    to_encode.update({"exp": expire})
    if is_dev_mode():
        # Use a deterministic token for dev
        to_encode.update({"sub": "admin@railguard.in", "role": "admin"})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    if is_dev_mode():
        # In development mode we always return the mock admin user
        return {"user_id": "admin@railguard.in", "role": "admin"}
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        role: str = payload.get("role")
        if user_id is None:
            raise credentials_exception
        return {"user_id": user_id, "role": role}
    except JWTError:
        raise credentials_exception

async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return user

async def require_field(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "field_attendant":
        raise HTTPException(status_code=403, detail="Field attendant privileges required")
    return user
