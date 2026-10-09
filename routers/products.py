"""Product CRUD. Creating a product with stock auto-records an opening 'giriş' movement."""

from fastapi import APIRouter, Depends, HTTPException
from pymongo import ReturnDocument

from lib import mysql_mirror
from lib.authz import PRODUCT_CREATE, PRODUCT_DELETE, PRODUCT_UPDATE, require_perm
from lib.db import aware_doc, db
from lib.dates import today_iso, utcnow
from lib.units import normalize_qty
from models.movement import Movement
from models.product import Product, ProductCreate, ProductUpdate

router = APIRouter(prefix="/products", tags=["products"])


def sync_images(data: dict) -> None:
    """`images` list is the source of truth; `image` mirrors the cover (first) image.
    Legacy docs/forms that only set `image` get backfilled into `images`."""
    images = [u for u in (data.get("images") or []) if isinstance(u, str) and u.strip()]
    if not images and data.get("image"):
        images = [data["image"]]
    data["images"] = images
    data["image"] = images[0] if images else None


@router.get("", response_model=list[Product])
async def list_products():
    docs = await db.products.find().sort("created_at", -1).to_list(1000)
    return [Product(**aware_doc(d)) for d in docs]


@router.get("/{product_id}", response_model=Product)
async def get_product(product_id: str):
    doc = await db.products.find_one({"id": product_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")
    return Product(**aware_doc(doc))


@router.post("", response_model=Product, status_code=201)
async def create_product(input: ProductCreate, user: dict = Depends(require_perm(PRODUCT_CREATE))):
    data = input.model_dump()
    sync_images(data)
    data["quantity"] = normalize_qty(data.get("quantity", 0), data.get("unit", "adet"))
    data["min_stock"] = normalize_qty(data.get("min_stock", 0), data.get("unit", "adet"))
    product = Product(**data)
    await db.products.insert_one(product.model_dump())
    await mysql_mirror.upsert("products", product.model_dump())

    if product.quantity > 0:
        opening = Movement(
            product_id=product.id,
            product_name=product.name,
            type="giris",
            quantity=product.quantity,
            unit=product.unit,
            date=today_iso(),
            note="Açılış stoğu",
            created_by=user.get("email", ""),
        )
        await db.movements.insert_one(opening.model_dump())
        await mysql_mirror.upsert("movements", opening.model_dump())
    return product


@router.put("/{product_id}", response_model=Product)
async def update_product(
    product_id: str, input: ProductUpdate, user: dict = Depends(require_perm(PRODUCT_UPDATE))
):
    doc = await db.products.find_one({"id": product_id})
    if not doc:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")

    updates = input.model_dump(exclude_unset=True, exclude_none=True)
    if input.attributes is not None:
        updates["attributes"] = input.attributes  # explicit replace ({} clears custom values)

    merged = {k: v for k, v in doc.items() if not k.startswith("_")} | updates
    sync_images(merged)
    unit = merged.get("unit", "adet")
    updates["images"] = merged["images"]
    updates["image"] = merged["image"]
    if "quantity" in updates:
        updates["quantity"] = normalize_qty(updates["quantity"], unit)
    if "min_stock" in updates:
        updates["min_stock"] = normalize_qty(updates["min_stock"], unit)
    updates["updated_at"] = utcnow()

    updated = await db.products.find_one_and_update(
        {"id": product_id},
        {"$set": updates},
        return_document=ReturnDocument.AFTER,
    )
    product = Product(**aware_doc(updated))
    await mysql_mirror.upsert("products", product.model_dump())
    return product


@router.delete("/{product_id}")
async def delete_product(product_id: str, user: dict = Depends(require_perm(PRODUCT_DELETE))):
    result = await db.products.delete_one({"id": product_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Ürün bulunamadı")
    await db.movements.delete_many({"product_id": product_id})
    await mysql_mirror.delete("products", product_id)
    await mysql_mirror.delete_by("movements", "product_id", product_id)
    return {"ok": True}
