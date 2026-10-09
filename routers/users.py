"""Admin panel: member list, role grants, membership deletion — Ana Yönetici only.

Guard rails: an admin cannot demote or delete themselves, and the last Ana Yönetici can
never be removed, so the system can't be locked out of its own admin panel.
"""

from fastapi import APIRouter, Depends, HTTPException

from lib import mysql_mirror
from lib.authz import ANA, USER_MANAGE, require_perm
from lib.db import aware_doc, db
from models.auth import RoleUpdate, UserOut

router = APIRouter(prefix="/users", tags=["users"])


async def _count_admins(exclude_id: str | None = None) -> int:
    query: dict = {"role": ANA}
    if exclude_id:
        query["id"] = {"$ne": exclude_id}
    return await db.users.count_documents(query)


@router.get("", response_model=list[UserOut])
async def list_users(user: dict = Depends(require_perm(USER_MANAGE))):
    docs = await db.users.find().sort("created_at", 1).to_list(1000)
    return [UserOut(**aware_doc(d, ("created_at",))) for d in docs]


@router.patch("/{user_id}/role", response_model=UserOut)
async def set_role(user_id: str, input: RoleUpdate, user: dict = Depends(require_perm(USER_MANAGE))):
    target = await db.users.find_one({"id": user_id})
    if not target:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")

    if target["id"] == user["id"] and input.role != ANA:
        raise HTTPException(status_code=400, detail="Kendi yöneticiliğinizi kaldıramazsınız")
    if target.get("role") == ANA and input.role != ANA and await _count_admins(exclude_id=target["id"]) == 0:
        raise HTTPException(status_code=400, detail="Son Ana Yönetici'nin yetkisi kaldırılamaz")

    await db.users.update_one({"id": user_id}, {"$set": {"role": input.role}})
    target["role"] = input.role
    out = UserOut(**aware_doc(target, ("created_at",)))
    await mysql_mirror.upsert("users", out.model_dump())
    return out


@router.delete("/{user_id}")
async def delete_user(user_id: str, user: dict = Depends(require_perm(USER_MANAGE))):
    target = await db.users.find_one({"id": user_id})
    if not target:
        raise HTTPException(status_code=404, detail="Kullanıcı bulunamadı")
    if target["id"] == user["id"]:
        raise HTTPException(status_code=400, detail="Kendi hesabınızı silemezsiniz")
    if target.get("role") == ANA and await _count_admins(exclude_id=target["id"]) == 0:
        raise HTTPException(status_code=400, detail="Son Ana Yönetici silinemez")

    await db.users.delete_one({"id": user_id})
    await mysql_mirror.delete("users", user_id)
    return {"ok": True}
