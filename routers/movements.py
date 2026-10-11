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


def weighted_avg_price(old_qty: float, old_price: float, in_qty: float, in_price: float) -> float:
    """Ağırlıklı ortalama alış fiyatı: (eski stok x eski fiyat + giren x giriş fiyatı) / toplam stok."""
    old_qty = max(float(old_qty or 0), 0.0)  # eksi/boş stok maliyeti bozmasın
    old_price = float(old_price or 0)
    total_qty = old_qty + float(in_qty)
    if total_qty <= 0:
        return float(in_price)
    return round((old_qty * old_price + float(in_qty) * float(in_price)) / total_qty, 4)


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
    updates: dict = {}
    price_before = price_after = None
    if delta:
        updates["quantity"] = normalize_qty(current + delta, unit)
    if input.type == "giris" and input.unit_price is not None:
        # Ortalamayı stok artırılmadan ÖNCEKİ miktarla hesapla (current = giriş öncesi stok).
        price_before = float(product.get("purchase_price", 0) or 0)
        price_after = weighted_avg_price(current, price_before, qty, input.unit_price)
        updates["purchase_price"] = price_after
    if updates:
        await db.products.update_one({"id": input.product_id}, {"$set": updates})

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
        price_before=price_before,
        price_after=price_after,
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
        updates: dict = {}
        if reverse:
            updates["quantity"] = normalize_qty(max(0.0, float(product.get("quantity", 0)) + reverse), unit)
        # Giriş silinirse, alış fiyatı o girişten beri değişmediyse eski fiyata geri dön.
        if (
            doc["type"] == "giris"
            and doc.get("price_before") is not None
            and doc.get("price_after") is not None
            and abs(float(product.get("purchase_price", 0) or 0) - float(doc["price_after"])) < 1e-6
        ):
            updates["purchase_price"] = float(doc["price_before"])
        if updates:
            await db.products.update_one({"id": product["id"]}, {"$set": updates})

    await db.movements.delete_one({"id": movement_id})
    fresh = await _touch_product(doc["product_id"]) if product else None
    await mysql_mirror.delete("movements", movement_id)
    if fresh:
        await mysql_mirror.upsert("products", {k: v for k, v in fresh.items() if not k.startswith("_")})
    return {"ok": True}
