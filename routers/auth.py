"""Auth routes — sessions are httpOnly cookies; passwords hashed, ids are uuid4 strings.

Role assignment on signup is server-side only (never read from the request body): the very
first account becomes Ana Yönetici so the system has an admin, everyone after that is a
view-only Üye until an Ana Yönetici promotes them from the admin panel.
"""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response

from lib import mysql_mirror
from lib.authz import ANA, UYE
from lib.db import aware_doc, db
from lib.dates import utcnow
from lib.security import (
    clear_session_cookie,
    create_token,
    hash_password,
    require_user,
    set_session_cookie,
    verify_password,
)
from models.auth import LoginInput, RegisterInput, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=UserOut, status_code=201)
async def register(input: RegisterInput, response: Response):
    email = input.email.lower()
    if await db.users.find_one({"email": email}):
        raise HTTPException(status_code=409, detail="Bu e-posta ile kayıtlı bir hesap zaten var")

    bootstrap = await db.users.count_documents({}) == 0
    doc = {
        "id": str(uuid4()),
        "name": input.name.strip(),
        "email": email,
        "role": ANA if bootstrap else UYE,  # server-decided; body cannot set a role
        "hashed_password": hash_password(input.password),
        "created_at": utcnow(),
    }
    await db.users.insert_one(doc)
    set_session_cookie(response, create_token(doc["id"]))
    out = UserOut(**doc)
    await mysql_mirror.upsert("users", out.model_dump())
    return out


@router.post("/login", response_model=UserOut)
async def login(input: LoginInput, response: Response):
    email = input.email.lower()
    user = await db.users.find_one({"email": email})
    if not user or not verify_password(input.password, user.get("hashed_password", "")):
        raise HTTPException(status_code=401, detail="E-posta veya şifre hatalı")
    set_session_cookie(response, create_token(user["id"]))
    return UserOut(**aware_doc(user, ("created_at",)))


@router.post("/logout")
async def logout(response: Response):
    clear_session_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
async def me(user: dict = Depends(require_user)):
    return UserOut(**aware_doc(user, ("created_at",)))
