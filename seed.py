"""Idempotent demo seed — run once: `cd /app/backend && python seed.py`."""

import asyncio
from datetime import timedelta

from lib.authz import ANA, UYE, YARDIMCI
from lib.db import db, ensure_indexes
from lib.dates import utcnow
from lib.security import hash_password
from routers.fields import slugify

DEMO_PASSWORD = "demo123"
USERS = [
    ("demo@stoktakip.com", "Demo Yönetici", ANA),
    ("yardimci@stoktakip.com", "Yardımcı Yönetici", YARDIMCI),
    ("uye@stoktakip.com", "Sıradan Üye", UYE),
]

FIELDS = [("Bulunduğu Yer", "text"), ("Raf No", "text"), ("Tedarikçi", "text")]

IMG_PEN_BLUE = "https://images.unsplash.com/photo-1585336261022-680e295ce3fe?crop=entropy&cs=srgb&fm=jpg&q=80&w=900&h=900&fit=crop"
IMG_PASTEL = "https://images.unsplash.com/photo-1601311911926-dbdae16e54c9?crop=entropy&cs=srgb&fm=jpg&q=80&w=900&h=900&fit=crop"
IMG_FOUNTAIN = "https://images.unsplash.com/photo-1546493918-8bcb44f37c8e?crop=entropy&cs=srgb&fm=jpg&q=80&w=900&h=900&fit=crop"
IMG_WAREHOUSE = "https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?crop=entropy&cs=srgb&fm=jpg&q=80&w=900&h=900&fit=crop"
IMG_HONEY = "https://images.unsplash.com/photo-1587049352846-4a222e784d38?crop=entropy&cs=srgb&fm=jpg&q=80&w=900&h=900&fit=crop"

PRODUCTS = [
    {
        "name": "Faber-Castell Dolma Kalem",
        "brand": "Faber-Castell",
        "model": "Ambition",
        "lot_number": "FC-AMB-118",
        "unit": "adet",
        "purchase_price": 180,
        "sale_price": 275,
        "min_stock": 5,
        "images": [IMG_FOUNTAIN, IMG_PEN_BLUE, IMG_WAREHOUSE],
        "notes": "Hediye kutusunda, siyah mürekkep",
        "attributes": {"bulundugu_yer": "Merkez Depo", "raf_no": "A-12", "tedarikci": "Kırtasiye A.Ş."},
    },
    {
        "name": "Rotring Tikky 0.7mm Versatil",
        "brand": "Rotring",
        "model": "Tikky 0.7",
        "lot_number": "RT-TKY-554",
        "unit": "adet",
        "purchase_price": 62,
        "sale_price": 95,
        "min_stock": 5,
        "images": [IMG_PEN_BLUE, IMG_FOUNTAIN],
        "notes": "",
        "attributes": {"bulundugu_yer": "Merkez Depo", "raf_no": "A-14", "tedarikci": "Ofis Deposu Ltd."},
    },
    {
        "name": "Pastel Fosforlu Kalem Seti (24'lü)",
        "brand": "Faber-Castell",
        "model": "Pastel 24",
        "lot_number": "PC-24-077",
        "unit": "adet",
        "purchase_price": 95,
        "sale_price": 149,
        "min_stock": 5,
        "images": [IMG_PASTEL, IMG_PEN_BLUE],
        "notes": "",
        "attributes": {"bulundugu_yer": "Kadıköy Mağaza", "raf_no": "B-03"},
    },
    {
        "name": "A4 Fotokopi Kağıdı (500 Yaprak)",
        "brand": "Kağıt Market",
        "model": "A4 80gr",
        "lot_number": "A4-80-1002",
        "unit": "adet",
        "purchase_price": 55,
        "sale_price": 79,
        "min_stock": 5,
        "images": [IMG_WAREHOUSE],
        "notes": "Paket başı 500 yaprak",
        "attributes": {"bulundugu_yer": "Merkez Depo", "raf_no": "C-01", "tedarikci": "Kağıtçılık A.Ş."},
    },
    {
        "name": "Post-it Not Kağıdı 76x76",
        "brand": "3M",
        "model": "Post-it 76x76",
        "lot_number": "P3M-76-330",
        "unit": "adet",
        "purchase_price": 38,
        "sale_price": 59,
        "min_stock": 5,
        "images": [IMG_WAREHOUSE, IMG_PASTEL],
        "notes": "",
        "attributes": {"bulundugu_yer": "Kadıköy Mağaza", "raf_no": "B-07"},
    },
    {
        # Kilogramla satılan örnek: fiyatlar kg başınadır, stok gram hassasiyetinde tutulur.
        "name": "Çiçek Balı (Dökme)",
        "brand": "Akkaya Arıcılık",
        "model": "Çiçek Balı",
        "lot_number": "BAL-2026-07",
        "unit": "kg",
        "purchase_price": 150,
        "sale_price": 200,
        "min_stock": 5,
        "images": [IMG_HONEY],
        "notes": "Kg başına fiyatlandırılır; 500 gram satış 100₺ olarak hesaplanır.",
        "attributes": {"bulundugu_yer": "Merkez Depo", "raf_no": "D-02", "tedarikci": "Akkaya Arıcılık"},
    },
]

# (product index, type, quantity, days_ago, destination, note) — kg ürünlerde miktar kilogramdır
MOVEMENTS = [
    (0, "giris", 40, 30, "Kırtasiye A.Ş.", "İlk alım"),
    (0, "satis", 8, 12, "Müşteri Siparişi #1042", ""),
    (0, "satis", 6, 5, "Perakende satış", ""),
    (0, "kullanim", 2, 2, "Ofis içi kullanım", ""),
    (1, "giris", 60, 25, "Ofis Deposu Ltd.", ""),
    (1, "satis", 15, 10, "Müşteri Siparişi #1051", ""),
    (1, "transfer", 5, 3, "Kadıköy Mağaza", "Mağaza stoğu için aktarıldı"),
    (2, "giris", 30, 20, "", ""),
    (2, "satis", 10, 7, "Müşteri Siparişi #1058", ""),
    (2, "satis", 2, 1, "Perakende satış", ""),
    (3, "giris", 150, 18, "Kağıtçılık A.Ş.", "10 koli"),
    (3, "satis", 25, 9, "Müşteri Siparişi #1063", ""),
    (3, "kullanim", 10, 4, "Büro sarfı", ""),
    (4, "giris", 20, 15, "", ""),
    (4, "satis", 12, 6, "Perakende satış", ""),
    (4, "kullanim", 5, 3, "Ekip toplantısı", ""),
    (5, "giris", 20, 14, "Akkaya Arıcılık", "20 kg dökme bal"),
    (5, "satis", 10.5, 4, "Perakende satış", "10 kg 500 g satıldı"),
    (5, "kullanim", 0.25, 2, "Tadım standı", "250 g tadım için kullanıldı"),
]


async def main() -> None:
    await ensure_indexes()
    if await db.products.find_one({"id": "seed-product-0"}):
        print("Seed verisi zaten mevcut — atlanıyor.")
        return

    now = utcnow()
    for email, name, role in USERS:
        if not await db.users.find_one({"email": email}):
            await db.users.insert_one(
                {
                    "id": f"seed-user-{email}",
                    "name": name,
                    "email": email,
                    "role": role,
                    "hashed_password": hash_password(DEMO_PASSWORD),
                    "created_at": now,
                }
            )

    for i, (label, ftype) in enumerate(FIELDS):
        await db.custom_fields.insert_one(
            {"id": f"seed-field-{i}", "key": slugify(label), "label": label, "type": ftype, "created_at": now}
        )

    product_ids = []
    for i, p in enumerate(PRODUCTS):
        pid = f"seed-product-{i}"
        product_ids.append(pid)
        quantity = round(
            sum(q if t == "giris" else -q for (idx, t, q, *_r) in MOVEMENTS if idx == i and t != "transfer"), 3
        )
        await db.products.insert_one(
            {
                "id": pid,
                "name": p["name"],
                "brand": p["brand"],
                "model": p["model"],
                "lot_number": p["lot_number"],
                "unit": p["unit"],
                "purchase_price": p["purchase_price"],
                "sale_price": p["sale_price"],
                "quantity": quantity,
                "min_stock": p["min_stock"],
                "image": p["images"][0],
                "images": p["images"],
                "notes": p["notes"],
                "attributes": p["attributes"],
                "created_at": now - timedelta(days=30 - i),
                "updated_at": now - timedelta(days=1),
            }
        )

    for j, (idx, mtype, qty, days_ago, destination, note) in enumerate(MOVEMENTS):
        await db.movements.insert_one(
            {
                "id": f"seed-movement-{j}",
                "product_id": product_ids[idx],
                "product_name": PRODUCTS[idx]["name"],
                "type": mtype,
                "quantity": float(qty),
                "unit": PRODUCTS[idx]["unit"],
                "date": (now - timedelta(days=days_ago)).strftime("%Y-%m-%d"),
                "destination": destination,
                "note": note,
                "unit_price": None,
                "created_by": USERS[0][0],
                "created_at": now - timedelta(days=days_ago),
            }
        )

    print(
        f"Seed tamam: {len(PRODUCTS)} ürün, {len(MOVEMENTS)} hareket, {len(FIELDS)} özel alan, "
        f"{len(USERS)} kullanıcı ({', '.join(u[0] for u in USERS)})"
    )


if __name__ == "__main__":
    asyncio.run(main())
