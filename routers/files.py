"""Product image upload (multipart) + serving under /api/files/{name}.

Images are stored in MongoDB (collection `files`), NOT on the server disk: Render's disk is
ephemeral and is wiped on every restart/redeploy/spin-down. URLs keep the same /api/files/{name}
shape. Old files that still exist in the repo's uploads/ folder are served as a fallback.
"""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from bson import Binary
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel

from lib.authz import UPLOAD, require_perm
from lib.dates import utcnow
from lib.db import db

router = APIRouter(tags=["files"])

UPLOAD_DIR = Path(__file__).parent.parent / "uploads"
MAX_SIZE = 5 * 1024 * 1024  # 5 MB

EXT_BY_TYPE = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
    "image/heic": "heic",
    "image/svg+xml": "svg",
}
TYPE_BY_EXT = {v: k for k, v in EXT_BY_TYPE.items()}


class UploadOut(BaseModel):
    url: str


@router.post("/upload", response_model=UploadOut)
async def upload_image(file: UploadFile, user: dict = Depends(require_perm(UPLOAD))):
    ext = EXT_BY_TYPE.get(file.content_type or "")
    if not ext and file.filename and "." in file.filename:
        candidate = file.filename.rsplit(".", 1)[-1].lower()
        if candidate in TYPE_BY_EXT:
            ext = candidate
    if not ext:
        raise HTTPException(status_code=415, detail="Sadece resim dosyası yüklenebilir (jpg, png, webp, gif)")

    data = await file.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(status_code=413, detail="Dosya çok büyük (en fazla 5 MB)")
    if not data:
        raise HTTPException(status_code=400, detail="Boş dosya")

    name = f"{uuid.uuid4().hex}.{ext}"
    await db.files.insert_one(
        {
            "_id": name,
            "content_type": TYPE_BY_EXT[ext],
            "data": Binary(data),
            "size": len(data),
            "created_by": user.get("email", ""),
            "created_at": utcnow(),
        }
    )
    return UploadOut(url=f"/api/files/{name}")


@router.get("/files/{name}")
async def get_file(name: str):
    name = Path(name).name  # basename guard against path traversal
    headers = {"Cache-Control": "public, max-age=31536000, immutable"}  # names are random UUIDs
    doc = await db.files.find_one({"_id": name})
    if doc:
        return Response(content=bytes(doc["data"]), media_type=doc["content_type"], headers=headers)
    # Fallback: older images committed to the repo's uploads/ folder.
    path = UPLOAD_DIR / name
    if path.is_file():
        return FileResponse(
            path, media_type=TYPE_BY_EXT.get(path.suffix.lstrip("."), "application/octet-stream"), headers=headers
        )
    raise HTTPException(status_code=404, detail="Dosya bulunamadı")
