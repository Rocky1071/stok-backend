"""Aggregate stats.

- Yapılan Satış Toplamı: realized revenue from 'satış' movements. A sale without a recorded
  unit_price is valued at the product's current sale price.
- Stok Maliyeti (Alış): total money spent on purchases = sum of quantity x unit_price over all
  'giriş' movements. It does NOT drop when stock is sold. A giriş without a unit_price is valued
  at the product's current purchase price."""

from fastapi import APIRouter

from lib.db import db
from models.stats import Stats

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("", response_model=Stats)
async def get_stats():
    products = await db.products.find({}, {"id": 1, "sale_price": 1, "purchase_price": 1}).to_list(2000)
    price_by_product = {p["id"]: p.get("sale_price") or 0 for p in products}
    purchase_by_product = {p["id"]: p.get("purchase_price") or 0 for p in products}

    sales = await db.movements.find({"type": "satis"}, {"quantity": 1, "unit_price": 1, "product_id": 1}).to_list(5000)
    total = 0.0
    for m in sales:
        unit = m.get("unit_price")
        if unit is None:
            unit = price_by_product.get(m.get("product_id"), 0) or 0
        total += unit * m.get("quantity", 0)

    entries = await db.movements.find({"type": "giris"}, {"quantity": 1, "unit_price": 1, "product_id": 1}).to_list(20000)
    purchase_total = 0.0
    for m in entries:
        price = m.get("unit_price")
        if price is None:
            price = purchase_by_product.get(m.get("product_id"), 0) or 0
        purchase_total += price * m.get("quantity", 0)

    return Stats(sale_total=round(total, 2), sale_count=len(sales), purchase_total=round(purchase_total, 2))
