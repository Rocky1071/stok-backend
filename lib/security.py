"""Password hashing + JWT session-cookie helpers (email+password auth)."""

import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, Request
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

SESSION_COOKIE = "stoktakip_session"
ALGORITHM = "HS256"
SESSION_DAYS = 30


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(password, hashed)
    except Exception:
        return False


def create_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(days=SESSION_DAYS)}
    return jwt.encode(payload, os.environ["SECRET_KEY"], algorithm=ALGORITHM)


def decode_token(token: str) -> str | None:
    try:
        payload = jwt.decode(token, os.environ["SECRET_KEY"], algorithms=[ALGORITHM])
        return payload.get("sub")
    except jwt.PyJWTError:
        return None


def set_session_cookie(response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_DAYS * 24 * 3600,
        httponly=True,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


async def require_user(request: Request) -> dict:
    """Dependency for write endpoints: raises 401 unless a valid session cookie is present."""
    from lib.db import db

    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Bu işlem için giriş yapmalısınız")
    user_id = decode_token(token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Oturum süresi doldu, lütfen tekrar giriş yapın")
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=401, detail="Kullanıcı bulunamadı, lütfen tekrar giriş yapın")
    return user
