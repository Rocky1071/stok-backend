"""Product image upload (multipart) + static serving under /api/files/{name}."""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from lib.authz import UPLOAD, require_perm

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

    UPLOAD_DIR.mkdir(exist_ok=True)
    name = f"{uuid.uuid4().hex}.{ext}"
    (UPLOAD_DIR / name).write_bytes(data)
    return UploadOut(url=f"/api/files/{name}")


@router.get("/files/{name}")
async def get_file(name: str):
    path = UPLOAD_DIR / Path(name).name  # basename guard against path traversal
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Dosya bulunamadı")
    return FileResponse(path, media_type=TYPE_BY_EXT.get(path.suffix.lstrip("."), "application/octet-stream"))
