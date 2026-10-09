"""Admin-defined dynamic fields ('ekstra sekmeler'): label+type; products store values by key.
Ana Yönetici only — Yardımcı Yönetici cannot reshape the schema."""

import re

from fastapi import APIRouter, Depends, HTTPException

from lib import mysql_mirror
from lib.authz import FIELD_MANAGE, require_perm
from lib.db import db
from models.field import CustomField, CustomFieldCreate, CustomFieldUpdate

router = APIRouter(prefix="/fields", tags=["fields"])

TR_MAP = str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosucgiosu")


def slugify(label: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", label.strip().lower().translate(TR_MAP)).strip("_")
    return slug or "alan"


@router.get("", response_model=list[CustomField])
async def list_fields():
    docs = await db.custom_fields.find().sort("created_at", 1).to_list(1000)
    return [CustomField(**d) for d in docs]


@router.post("", response_model=CustomField, status_code=201)
async def create_field(input: CustomFieldCreate, user: dict = Depends(require_perm(FIELD_MANAGE))):
    key = slugify(input.label)
    if await db.custom_fields.find_one({"key": key}):
        raise HTTPException(status_code=409, detail=f"'{input.label}' alanı zaten tanımlı")
    field = CustomField(key=key, label=input.label.strip(), type=input.type)
    await db.custom_fields.insert_one(field.model_dump())
    await mysql_mirror.upsert("custom_fields", field.model_dump())
    return field


@router.put("/{field_id}", response_model=CustomField)
async def update_field(field_id: str, input: CustomFieldUpdate, user: dict = Depends(require_perm(FIELD_MANAGE))):
    updates = input.model_dump(exclude_unset=True, exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="Güncellenecek alan yok")
    doc = await db.custom_fields.find_one_and_update({"id": field_id}, {"$set": updates})
    if not doc:
        raise HTTPException(status_code=404, detail="Alan bulunamadı")
    doc.update(updates)
    field = CustomField(**doc)
    await mysql_mirror.upsert("custom_fields", field.model_dump())
    return field


@router.delete("/{field_id}")
async def delete_field(field_id: str, user: dict = Depends(require_perm(FIELD_MANAGE))):
    field = await db.custom_fields.find_one({"id": field_id})
    if not field:
        raise HTTPException(status_code=404, detail="Alan bulunamadı")
    await db.custom_fields.delete_one({"id": field_id})
    # Drop the column's data from every product, the field no longer exists.
    await db.products.update_many({}, {"$unset": {f"attributes.{field['key']}": ""}})
    await mysql_mirror.delete("custom_fields", field_id)
    return {"ok": True}
