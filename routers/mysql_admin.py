"""MySQL mirror health + manual full sync — Ana Yönetici only."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from lib import mysql_mirror
from lib.authz import USER_MANAGE, require_perm

router = APIRouter(prefix="/mysql", tags=["mysql"])


class MysqlStatus(BaseModel):
    configured: bool
    connected: bool
    detail: str
    tables: dict[str, int] = {}
    host: str = ""
    database: str = ""


class SyncResult(BaseModel):
    ok: bool
    detail: str
    synced: dict[str, int] = {}


@router.get("/status", response_model=MysqlStatus)
async def mysql_status(user: dict = Depends(require_perm(USER_MANAGE))):
    import os

    data = await mysql_mirror.status()
    return MysqlStatus(
        **data,
        host=os.environ.get("MYSQL_HOST", ""),
        database=os.environ.get("MYSQL_DB", ""),
    )


@router.post("/sync", response_model=SyncResult)
async def mysql_sync(user: dict = Depends(require_perm(USER_MANAGE))):
    return SyncResult(**await mysql_mirror.full_sync())
