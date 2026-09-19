"""SQLite bazasi — mahsulotlar navbati, sozlamalar, post tarixi."""
import os
import datetime as dt
from typing import Optional

import aiosqlite

from config import DB_PATH, DEFAULTS, TZ

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);

CREATE TABLE IF NOT EXISTS products (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    name           TEXT NOT NULL,
    norm_name      TEXT NOT NULL,
    brand          TEXT DEFAULT '',
    category       TEXT DEFAULT '',
    price          TEXT DEFAULT '',
    unit           TEXT DEFAULT '',
    old_price      TEXT DEFAULT '',
    note           TEXT DEFAULT '',
    photo_file_id  TEXT DEFAULT '',
    active         INTEGER DEFAULT 1,
    created_at     TEXT,
    last_posted_at TEXT,
    post_count     INTEGER DEFAULT 0,
    source         TEXT DEFAULT 'manual'
);

CREATE TABLE IF NOT EXISTS post_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER,
    name       TEXT,
    posted_at  TEXT,
    message_id INTEGER,
    ok         INTEGER DEFAULT 1,
    error      TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS drafts (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       INTEGER,
    photo_file_id TEXT DEFAULT '',
    name          TEXT DEFAULT '',
    price         TEXT DEFAULT '',
    need          TEXT DEFAULT '',
    created_at    TEXT
);

CREATE TABLE IF NOT EXISTS cat_log (
    category       TEXT PRIMARY KEY,
    last_posted_at TEXT,
    post_count     INTEGER DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_products_norm ON products(norm_name);
CREATE INDEX IF NOT EXISTS idx_products_queue ON products(active, post_count, last_posted_at);
"""

_db: Optional[aiosqlite.Connection] = None


def now() -> dt.datetime:
    return dt.datetime.now(TZ)


def iso(d: Optional[dt.datetime] = None) -> str:
    return (d or now()).isoformat(timespec="seconds")


def parse_iso(s: Optional[str]) -> Optional[dt.datetime]:
    if not s:
        return None
    try:
        d = dt.datetime.fromisoformat(s)
        return d if d.tzinfo else d.replace(tzinfo=TZ)
    except ValueError:
        return None


async def init() -> None:
    global _db
    folder = os.path.dirname(DB_PATH)
    if folder:
        os.makedirs(folder, exist_ok=True)
    _db = await aiosqlite.connect(DB_PATH)
    _db.row_factory = aiosqlite.Row
    await _db.executescript(SCHEMA)
    await _db.commit()
    for k, v in DEFAULTS.items():
        await _db.execute("INSERT OR IGNORE INTO settings(key, value) VALUES(?, ?)", (k, v))
    await _db.commit()


def conn() -> aiosqlite.Connection:
    assert _db is not None, "db.init() chaqirilmagan"
    return _db


async def close() -> None:
    if _db:
        await _db.close()


# ---------------------------------------------------------------- sozlamalar
async def get(key: str, default: str = "") -> str:
    async with conn().execute("SELECT value FROM settings WHERE key = ?", (key,)) as cur:
        row = await cur.fetchone()
    if row is None:
        return DEFAULTS.get(key, default)
    return row["value"] if row["value"] is not None else default


async def get_int(key: str, default: int = 0) -> int:
    try:
        return int((await get(key)).strip())
    except (TypeError, ValueError):
        return default


async def all_settings() -> dict:
    async with conn().execute("SELECT key, value FROM settings") as cur:
        rows = await cur.fetchall()
    out = dict(DEFAULTS)
    out.update({r["key"]: r["value"] for r in rows})
    return out


async def set(key: str, value: str) -> None:
    await conn().execute(
        "INSERT INTO settings(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )
    await conn().commit()


# ---------------------------------------------------------------- mahsulotlar
async def add_product(**kw) -> int:
    from matching import normalize

    fields = {
        "name": kw.get("name", "").strip(),
        "norm_name": normalize(kw.get("name", "")),
        "brand": (kw.get("brand") or "").strip(),
        "category": (kw.get("category") or "").strip(),
        "price": str(kw.get("price") or "").strip(),
        "unit": (kw.get("unit") or "").strip(),
        "old_price": str(kw.get("old_price") or "").strip(),
        "note": (kw.get("note") or "").strip(),
        "photo_file_id": (kw.get("photo_file_id") or "").strip(),
        "created_at": iso(),
        "source": kw.get("source", "manual"),
    }
    cur = await conn().execute(
        "INSERT INTO products (name, norm_name, brand, category, price, unit, old_price, "
        "note, photo_file_id, created_at, source) VALUES "
        "(:name, :norm_name, :brand, :category, :price, :unit, :old_price, :note, "
        ":photo_file_id, :created_at, :source)",
        fields,
    )
    await conn().commit()
    return cur.lastrowid


async def upsert_product(**kw) -> tuple[int, bool]:
    """Nomi bo'yicha bor bo'lsa yangilaydi, yo'q bo'lsa qo'shadi. (id, yangi_mi)"""
    from matching import normalize

    norm = normalize(kw.get("name", ""))
    async with conn().execute(
        "SELECT id, photo_file_id FROM products WHERE norm_name = ? ORDER BY id DESC LIMIT 1", (norm,)
    ) as cur:
        row = await cur.fetchone()
    if row is None:
        return await add_product(**kw), True

    pid = row["id"]
    sets, vals = [], []
    for col in ("brand", "category", "price", "unit", "old_price", "note"):
        if kw.get(col) not in (None, ""):
            sets.append(f"{col} = ?")
            vals.append(str(kw[col]).strip())
    if kw.get("photo_file_id"):
        sets.append("photo_file_id = ?")
        vals.append(kw["photo_file_id"])
    sets.append("active = 1")
    if sets:
        vals.append(pid)
        await conn().execute(f"UPDATE products SET {', '.join(sets)} WHERE id = ?", vals)
        await conn().commit()
    return pid, False


async def set_photo(product_id: int, file_id: str) -> None:
    await conn().execute("UPDATE products SET photo_file_id = ? WHERE id = ?", (file_id, product_id))
    await conn().commit()


async def get_product(pid: int):
    async with conn().execute("SELECT * FROM products WHERE id = ?", (pid,)) as cur:
        return await cur.fetchone()


async def delete_product(pid: int) -> bool:
    cur = await conn().execute("UPDATE products SET active = 0 WHERE id = ?", (pid,))
    await conn().commit()
    return cur.rowcount > 0


async def all_products(limit: int = 500):
    async with conn().execute(
        "SELECT * FROM products WHERE active = 1 ORDER BY post_count ASC, id ASC LIMIT ?", (limit,)
    ) as cur:
        return await cur.fetchall()


async def find_by_name(name: str):
    """Aniq (normallashtirilgan) nom bo'yicha qidirish."""
    from matching import normalize

    async with conn().execute(
        "SELECT * FROM products WHERE norm_name = ? AND active = 1 ORDER BY id DESC LIMIT 1",
        (normalize(name),),
    ) as cur:
        return await cur.fetchone()


async def ready_count() -> int:
    """Postga to'liq tayyor (narxi bor) va hali chiqmagan mahsulotlar soni."""
    async with conn().execute(
        "SELECT COUNT(*) c FROM products WHERE active = 1 AND post_count = 0 AND price <> ''"
    ) as cur:
        return (await cur.fetchone())["c"]


async def no_photo_count() -> int:
    async with conn().execute(
        "SELECT COUNT(*) c FROM products WHERE active = 1 AND photo_file_id = '' AND price <> ''"
    ) as cur:
        return (await cur.fetchone())["c"]


async def no_price_count() -> int:
    async with conn().execute(
        "SELECT COUNT(*) c FROM products WHERE active = 1 AND price = ''"
    ) as cur:
        return (await cur.fetchone())["c"]


async def pick_next():
    """Navbatdagi keyingi mahsulot.

    1) Hali hech chiqmaganlaridan eng eskisi (kategoriya aylanishi bilan).
    2) Bo'lmasa — cooldown kunidan oshib ketgan, eng uzoq vaqt chiqmagani.
    """
    async with conn().execute(
        "SELECT * FROM products WHERE active = 1 AND post_count = 0 AND price <> '' "
        "ORDER BY id ASC LIMIT 40"
    ) as cur:
        fresh = await cur.fetchall()

    if fresh:
        return _rotate_category(fresh, await last_categories(3))

    days = await get_int("cooldown_days", 10)
    limit_dt = iso(now() - dt.timedelta(days=days))
    async with conn().execute(
        "SELECT * FROM products WHERE active = 1 AND price <> '' "
        "AND (last_posted_at IS NULL OR last_posted_at < ?) "
        "ORDER BY last_posted_at ASC, post_count ASC LIMIT 40",
        (limit_dt,),
    ) as cur:
        old = await cur.fetchall()
    if old:
        return _rotate_category(old, await last_categories(3))
    return None


def _rotate_category(rows, recent_cats):
    """Ketma-ket bir xil kategoriya chiqmasligi uchun almashtirib tanlaydi."""
    recent = {c for c in recent_cats if c}
    for r in rows:
        if (r["category"] or "").strip().lower() not in recent:
            return r
    return rows[0]


async def last_categories(n: int = 3):
    async with conn().execute(
        "SELECT p.category FROM post_log l JOIN products p ON p.id = l.product_id "
        "WHERE l.ok = 1 ORDER BY l.id DESC LIMIT ?",
        (n,),
    ) as cur:
        return [(r["category"] or "").strip().lower() for r in await cur.fetchall()]


async def mark_posted(product_id: int, name: str, message_id: int) -> None:
    await conn().execute(
        "UPDATE products SET post_count = post_count + 1, last_posted_at = ? WHERE id = ?",
        (iso(), product_id),
    )
    await conn().execute(
        "INSERT INTO post_log (product_id, name, posted_at, message_id, ok) VALUES (?, ?, ?, ?, 1)",
        (product_id, name, iso(), message_id),
    )
    await conn().commit()


async def log_error(product_id: int, name: str, error: str) -> None:
    await conn().execute(
        "INSERT INTO post_log (product_id, name, posted_at, message_id, ok, error) "
        "VALUES (?, ?, ?, 0, 0, ?)",
        (product_id, name, iso(), error[:400]),
    )
    await conn().commit()


async def posts_today():
    start = now().replace(hour=0, minute=0, second=0, microsecond=0)
    async with conn().execute(
        "SELECT * FROM post_log WHERE ok = 1 AND posted_at >= ? ORDER BY id ASC", (iso(start),)
    ) as cur:
        return await cur.fetchall()


# ------------------------------------------------- kategoriya navbati (prays)
async def categories() -> list[str]:
    """Narxi bor faol mahsulotlar kategoriyalari."""
    async with conn().execute(
        "SELECT DISTINCT COALESCE(NULLIF(TRIM(category), ''), 'Boshqa mahsulotlar') c "
        "FROM products WHERE active = 1 AND price <> '' ORDER BY c"
    ) as cur:
        return [r["c"] for r in await cur.fetchall()]


async def category_items(name: str):
    async with conn().execute(
        "SELECT * FROM products WHERE active = 1 AND price <> '' "
        "AND COALESCE(NULLIF(TRIM(category), ''), 'Boshqa mahsulotlar') = ?",
        (name,),
    ) as cur:
        rows = [dict(r) for r in await cur.fetchall()]
    from pricebook import natural_key
    rows.sort(key=lambda r: (natural_key(r.get("brand") or ""), natural_key(r.get("name") or "")))
    return rows


async def pick_next_category():
    """Eng uzoq vaqt chiqmagan kategoriya. (nomi, mahsulotlar) yoki None."""
    cats = await categories()
    if not cats:
        return None
    async with conn().execute(
        "SELECT category, last_posted_at, post_count FROM cat_log"
    ) as cur:
        seen = {r["category"]: (r["last_posted_at"] or "", r["post_count"] or 0)
                for r in await cur.fetchall()}

    fresh = [c for c in cats if c not in seen]
    if fresh:
        pick = fresh[0]
    else:
        # eng uzoq vaqt chiqmagani; vaqt teng bo'lsa — kamroq chiqqani
        pick = min(cats, key=lambda c: (seen[c][0], seen[c][1], c))
    return pick, await category_items(pick)


async def mark_category_posted(name: str) -> None:
    await conn().execute(
        "INSERT INTO cat_log (category, last_posted_at, post_count) VALUES (?, ?, 1) "
        "ON CONFLICT(category) DO UPDATE SET last_posted_at = excluded.last_posted_at, "
        "post_count = cat_log.post_count + 1",
        (name, iso()),
    )
    await conn().commit()


async def price_age_days() -> int | None:
    """Narxlar oxirgi marta necha kun oldin yangilangan."""
    last = await get("last_import_at", "")
    d = parse_iso(last)
    if d is None:
        async with conn().execute("SELECT MAX(created_at) m FROM products WHERE active = 1") as cur:
            d = parse_iso((await cur.fetchone())["m"])
    return None if d is None else (now() - d).days


async def queue_left() -> int:
    """Rejimga qarab: navbatdagi kategoriya yoki mahsulot soni."""
    if (await get("post_mode", "pdf")) in ("pdf", "rasm", "prays"):
        return len(await categories())
    return await ready_count()


# ---------------------------------------------------------------- draftlar
async def add_draft(user_id: int, photo_file_id: str = "", name: str = "", need: str = "name") -> int:
    cur = await conn().execute(
        "INSERT INTO drafts (user_id, photo_file_id, name, need, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, photo_file_id, name, need, iso()),
    )
    await conn().commit()
    return cur.lastrowid


async def next_draft(user_id: int):
    async with conn().execute(
        "SELECT * FROM drafts WHERE user_id = ? AND need <> '' ORDER BY id ASC LIMIT 1", (user_id,)
    ) as cur:
        return await cur.fetchone()


async def update_draft(draft_id: int, **kw) -> None:
    if not kw:
        return
    sets = ", ".join(f"{k} = ?" for k in kw)
    await conn().execute(f"UPDATE drafts SET {sets} WHERE id = ?", [*kw.values(), draft_id])
    await conn().commit()


async def drop_draft(draft_id: int) -> None:
    await conn().execute("DELETE FROM drafts WHERE id = ?", (draft_id,))
    await conn().commit()


async def clear_drafts(user_id: int) -> int:
    cur = await conn().execute("DELETE FROM drafts WHERE user_id = ?", (user_id,))
    await conn().commit()
    return cur.rowcount
