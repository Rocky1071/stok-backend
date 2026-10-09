"""Stock movements: giriş (+stok), satış / kullanım (-stok), transfer (kayıt).

Every movement also stamps the product's `updated_at`, so "Son Güncelleme" on the product
reflects the last stock operation — not just the last time the form was edited.
"""

from fastapi import APIRouter, Depends, HTTPException

from lib import mysql_mirror
from lib.authz import MOVEMENT_CREATE, MOVEMENT_DELETE, require_perm
from lib.db import aware_doc, db
from lib.dates import today_iso, utcnow
from lib.units import format_qty, normalize_qty
from models.movement import Movement, MovementCreate

router = APIRouter(prefix="/movements", tags=["movements"])


async def _touch_product(product_id: str) -> dict | None:
    """Bump updated_at and return the fresh product doc (for the MySQL mirror)."""
    from pymongo import ReturnDocument

    return await db.products.find_one_and_update(
        {"id": product_id},
        {"$set": {"updated_at": utcnow()}},
        return_document=ReturnDocument.AFTER,
    )


@router.get("", response_model=list[Movement])
async def list_movements(type: str | None = None, product_id: str | None = None, q: str | None = None):
    query: dict = {}
    if type:
        query["type"] = type
    if product_id:
        query["product_id"] = product_id
    if q and q.strip():
        # Product-name search for the movements page search box.
        import re

        query["product_name"] = {"$regex": re.escape(q.strip()), "$options": "i"}
    docs = await db.movements.find(query).sort([("date", -1), ("created_at", -1)]).to_list(1000)
    return [Movement(**aware_doc(d, ("created_at",))) for d in docs]


@router.post("", response_model=Movement, status_code=201)
async def create_movement(input: MovementCreate, user: dict = Depends(require_perm(MOVEMENT_CREATE))):
    product = await db.products.find_one({"id": input.product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")

    unit = product.get("unit", "adet")
    qty = normalize_qty(input.quantity, unit)
    if qty <= 0:
        raise HTTPException(status_code=400, detail="Miktar 0'dan büyük olmalıdır")

    current = float(product.get("quantity", 0))
    if input.type in ("satis", "kullanim") and qty > current + 1e-9:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Yetersiz stok: '{product['name']}' ürününde {format_qty(current, unit)} var, "
                f"{format_qty(qty, unit)} düşülemez"
            ),
        )

    delta = {"giris": qty, "satis": -qty, "kullanim": -qty, "transfer": 0}[input.type]
    if delta:
        new_qty = normalize_qty(current + delta, unit)
        await db.products.update_one({"id": input.product_id}, {"$set": {"quantity": new_qty}})

    movement = Movement(
        product_id=input.product_id,
        product_name=product["name"],
        type=input.type,
        quantity=qty,
        unit=unit,
        date=input.date or today_iso(),
        destination=input.destination,
        note=input.note,
        unit_price=input.unit_price,
        created_by=user.get("email", ""),
    )
    await db.movements.insert_one(movement.model_dump())

    fresh = await _touch_product(input.product_id)
    await mysql_mirror.upsert("movements", movement.model_dump())
    if fresh:
        await mysql_mirror.upsert("products", {k: v for k, v in fresh.items() if not k.startswith("_")})
    return movement


@router.delete("/{movement_id}")
async def delete_movement(movement_id: str, user: dict = Depends(require_perm(MOVEMENT_DELETE))):
    doc = await db.movements.find_one({"id": movement_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Hareket kaydı bulunamadı")

    product = await db.products.find_one({"id": doc["product_id"]})
    if product:
        unit = product.get("unit", "adet")
        qty = float(doc["quantity"])
        reverse = {"giris": -qty, "satis": qty, "kullanim": qty, "transfer": 0}[doc["type"]]
        if reverse:
            new_qty = normalize_qty(max(0.0, float(product.get("quantity", 0)) + reverse), unit)
            await db.products.update_one({"id": product["id"]}, {"$set": {"quantity": new_qty}})

    await db.movements.delete_one({"id": movement_id})
    fresh = await _touch_product(doc["product_id"]) if product else None
    await mysql_mirror.delete("movements", movement_id)
    if fresh:
        await mysql_mirror.upsert("products", {k: v for k, v in fresh.items() if not k.startswith("_")})
    return {"ok": True}
