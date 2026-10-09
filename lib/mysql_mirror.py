"""Best-effort MySQL mirror — every write also lands in MySQL for external reporting/backup.

Design rules:
- NEVER blocks or breaks an API call. MySQL unreachable (wrong host, server down, no creds) =>
  the warning is logged once and the request succeeds on MongoDB alone. MongoDB stays the
  source of truth; MySQL is a live copy you can connect to from outside.
- pymysql is synchronous, so every call runs in a worker thread via asyncio.to_thread.
- Tables are created on demand; rows are REPLACEd by primary key (id), so re-mirroring is idempotent.
"""

import asyncio
import logging
import os
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

_warned = False

DDL = {
    "users": """
        CREATE TABLE IF NOT EXISTS users (
            id VARCHAR(64) PRIMARY KEY,
            email VARCHAR(255),
            name VARCHAR(255),
            role VARCHAR(32),
            created_at DATETIME NULL
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
    """,
    "products": """
        CREATE TABLE IF NOT EXISTS products (
            id VARCHAR(64) PRIMARY KEY,
            name VARCHAR(255),
            brand VARCHAR(255),
            model VARCHAR(255),
            lot_number VARCHAR(255),
            unit VARCHAR(16),
            purchase_price DECIMAL(14,2),
            sale_price DECIMAL(14,2),
            quantity DECIMAL(16,3),
            min_stock DECIMAL(16,3),
            image TEXT,
            images TEXT,
            notes TEXT,
            attributes TEXT,
            created_at DATETIME NULL,
            updated_at DATETIME NULL
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
    """,
    "movements": """
        CREATE TABLE IF NOT EXISTS movements (
            id VARCHAR(64) PRIMARY KEY,
            product_id VARCHAR(64),
            product_name VARCHAR(255),
            type VARCHAR(32),
            quantity DECIMAL(16,3),
            unit VARCHAR(16),
            date VARCHAR(16),
            destination TEXT,
            note TEXT,
            unit_price DECIMAL(14,2) NULL,
            created_by VARCHAR(255),
            created_at DATETIME NULL,
            INDEX idx_product (product_id),
            INDEX idx_type (type)
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
    """,
    "custom_fields": """
        CREATE TABLE IF NOT EXISTS custom_fields (
            id VARCHAR(64) PRIMARY KEY,
            `key` VARCHAR(128),
            label VARCHAR(255),
            type VARCHAR(32),
            created_at DATETIME NULL
        ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
    """,
}

# Columns mirrored per table, in DDL order.
COLUMNS = {
    "users": ["id", "email", "name", "role", "created_at"],
    "products": [
        "id", "name", "brand", "model", "lot_number", "unit", "purchase_price", "sale_price",
        "quantity", "min_stock", "image", "images", "notes", "attributes", "created_at", "updated_at",
    ],
    "movements": [
        "id", "product_id", "product_name", "type", "quantity", "unit", "date", "destination",
        "note", "unit_price", "created_by", "created_at",
    ],
    "custom_fields": ["id", "key", "label", "type", "created_at"],
}


def is_configured() -> bool:
    return bool(os.environ.get("MYSQL_HOST") and os.environ.get("MYSQL_DB"))


def _connect():
    import pymysql

    return pymysql.connect(
        host=os.environ["MYSQL_HOST"],
        port=int(os.environ.get("MYSQL_PORT", "3306")),
        user=os.environ.get("MYSQL_USER", ""),
        password=os.environ.get("MYSQL_PASSWORD", ""),
        database=os.environ["MYSQL_DB"],
        charset="utf8mb4",
        connect_timeout=5,
        read_timeout=10,
        write_timeout=10,
        autocommit=True,
    )


def _coerce(value: Any) -> Any:
    import json

    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _sync_upsert(table: str, rows: list[dict]) -> None:
    cols = COLUMNS[table]
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(DDL[table])
            placeholders = ", ".join(["%s"] * len(cols))
            collist = ", ".join(f"`{c}`" for c in cols)
            sql = f"REPLACE INTO `{table}` ({collist}) VALUES ({placeholders})"
            cur.executemany(sql, [tuple(_coerce(r.get(c)) for c in cols) for r in rows])
    finally:
        conn.close()


def _sync_delete(table: str, row_id: str) -> None:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(DDL[table])
            cur.execute(f"DELETE FROM `{table}` WHERE id = %s", (row_id,))
    finally:
        conn.close()


def _sync_delete_by(table: str, column: str, value: str) -> None:
    conn = _connect()
    try:
        with conn.cursor() as cur:
            cur.execute(DDL[table])
            cur.execute(f"DELETE FROM `{table}` WHERE `{column}` = %s", (value,))
    finally:
        conn.close()


async def _run(fn, *args) -> None:
    """Fire a mirror operation; swallow every failure so the API never fails because of MySQL."""
    global _warned
    if not is_configured():
        return
    try:
        await asyncio.to_thread(fn, *args)
    except Exception as exc:
        if not _warned:
            logger.warning(
                "MySQL aynası devre dışı (%s). Uygulama MongoDB ile çalışmaya devam ediyor; "
                "MYSQL_HOST/MYSQL_USER/MYSQL_PASSWORD/MYSQL_DB değerlerini kontrol edin.",
                exc,
            )
            _warned = True
        else:
            logger.debug("MySQL mirror skipped: %s", exc)


async def upsert(table: str, doc: dict) -> None:
    await _run(_sync_upsert, table, [doc])


async def upsert_many(table: str, docs: list[dict]) -> None:
    if docs:
        await _run(_sync_upsert, table, docs)


async def delete(table: str, row_id: str) -> None:
    await _run(_sync_delete, table, row_id)


async def delete_by(table: str, column: str, value: str) -> None:
    await _run(_sync_delete_by, table, column, value)


async def status() -> dict:
    """Admin panel health read — reports whether the mirror is reachable and row counts."""
    if not is_configured():
        return {"configured": False, "connected": False, "detail": "MySQL bilgileri tanımlı değil", "tables": {}}

    def _check() -> dict:
        conn = _connect()
        try:
            counts = {}
            with conn.cursor() as cur:
                for table in DDL:
                    cur.execute(DDL[table])
                    cur.execute(f"SELECT COUNT(*) FROM `{table}`")
                    row = cur.fetchone()
                    counts[table] = int(row[0]) if row else 0
            return {"configured": True, "connected": True, "detail": "Bağlantı başarılı", "tables": counts}
        finally:
            conn.close()

    try:
        return await asyncio.to_thread(_check)
    except Exception as exc:
        return {"configured": True, "connected": False, "detail": f"Bağlanılamadı: {exc}", "tables": {}}


async def full_sync() -> dict:
    """Push every Mongo document to MySQL (manual 'Tümünü Eşitle' button)."""
    from lib.db import db

    if not is_configured():
        return {"ok": False, "detail": "MySQL bilgileri tanımlı değil", "synced": {}}

    synced: dict[str, int] = {}
    try:
        for table, collection in (
            ("users", db.users),
            ("products", db.products),
            ("movements", db.movements),
            ("custom_fields", db.custom_fields),
        ):
            docs = await collection.find().to_list(5000)
            clean = [{k: v for k, v in d.items() if not k.startswith("_")} for d in docs]
            if clean:
                await asyncio.to_thread(_sync_upsert, table, clean)
            synced[table] = len(clean)
        return {"ok": True, "detail": "Tüm veriler MySQL'e eşitlendi", "synced": synced}
    except Exception as exc:
        return {"ok": False, "detail": f"Eşitleme başarısız: {exc}", "synced": synced}
