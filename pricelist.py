"""Excel / CSV narxlar ro'yxatini o'qish.

Ustun nomlari o'zbekcha, ruscha yoki inglizcha bo'lishi mumkin — bot o'zi taniydi.
Kerakli ustun faqat bittasi: mahsulot nomi. Qolganlari ixtiyoriy.
"""
import csv
import io
import re

from openpyxl import load_workbook

COLUMN_ALIASES = {
    "name": [
        "nom", "nomi", "mahsulot", "mahsulot nomi", "tovar", "tovar nomi", "maxsulot",
        "название", "наименование", "товар", "продукт", "name", "product", "title",
        "отображаемое имя", "display name", "полное наименование",
    ],
    "price": [
        "chakana", "chakana narx", "chakana narxi", "dona narxi",
        "narx", "narxi", "narh", "yangi narx", "sotuv narxi", "summa",
        "цена", "стоимость", "розничная", "розница", "розничная цена",
        "price", "new price", "retail",
    ],
    "stock": [
        "qoldiq", "qoldig", "soni", "miqdor", "miqdori", "nalichiya", "mavjud",
        "количество в наличии", "количество", "наличие", "в наличии", "остаток",
        "stock", "qty", "quantity", "on hand", "balance",
    ],
    "wholesale": [
        "ulgurji", "ulgurji narx", "ulgurji narxi", "optom",
        "оптовая", "опт", "оптовая цена", "wholesale",
    ],
    "old_price": [
        "eski narx", "eski narxi", "avvalgi narx", "старая цена", "old price", "было",
    ],
    "unit": [
        "birlik", "birligi", "olcham", "o'lchov", "olchov", "olchov birligi",
        "ед", "ед.изм", "ед. изм.", "единица", "unit", "uom",
    ],
    "category": [
        "kategoriya", "turkum", "guruh", "bolim", "bo'lim",
        "категория", "группа", "раздел", "category", "group",
    ],
    "brand": [
        "brend", "brand", "firma", "ishlab chiqaruvchi", "zavod",
        "бренд", "производитель", "марка", "manufacturer",
    ],
    "note": [
        "izoh", "tavsif", "qoshimcha", "описание", "комментарий", "примечание",
        "note", "description", "comment",
    ],
}


def _norm_header(h) -> str:
    s = str(h or "").strip().lower()
    s = s.replace("ʻ", "'").replace("ʼ", "'").replace("`", "'").replace("’", "'")
    s = re.sub(r"[^\w\s.']+", " ", s, flags=re.UNICODE)
    return re.sub(r"\s+", " ", s).strip()


# valyutali ustunlar hech qachon narx sifatida olinmaydi
FOREIGN = re.compile(r"\b(usd|у\.?е|дол|доллар|eur|евро|rub|₽|\$)\b|\busd\b", re.IGNORECASE)


def _match_field(h: str) -> tuple[str, int] | None:
    """Ustun sarlavhasi qaysi maydonga eng mos kelishini topadi.

    Hamma maydon tekshiriladi: "Eski narx" ichida "narx" bor, lekin u
    old_price bilan to'liq mos keladi — shuning uchun eng yaxshisi olinadi.
    """
    best = None
    for field, aliases in COLUMN_ALIASES.items():
        for rank, a in enumerate(aliases):
            if h == a:
                score = 100 - rank
            elif h.startswith(a) or a in h:
                score = 60 - rank
            else:
                continue
            if best is None or score > best[1]:
                best = (field, score)
            break                      # shu maydonning eng yaxshi aliasi yetarli
    return best


def _map_columns(header_row) -> dict:
    """{maydon: ustun raqami}. Bir nechta nomzod bo'lsa — eng mosini oladi."""
    best: dict[str, tuple[int, int]] = {}      # field -> (rank, idx)
    for idx, cell in enumerate(header_row):
        h = _norm_header(cell)
        if not h:
            continue
        hit = _match_field(h)
        if hit is None:
            continue
        field, rank = hit
        # dollar/evro ustuni narx sifatida olinmaydi
        if field in ("price", "old_price", "wholesale") and FOREIGN.search(str(cell)):
            continue
        if field not in best or rank > best[field][0]:
            best[field] = (rank, idx)
    return {f: i for f, (_r, i) in best.items()}


def _find_header(rows) -> tuple[int, dict]:
    """Sarlavha qatorini birinchi 10 qator ichidan topadi."""
    best_i, best_map = -1, {}
    for i, row in enumerate(rows[:10]):
        m = _map_columns(row)
        if "name" in m and len(m) > len(best_map):
            best_i, best_map = i, m
    return best_i, best_map


CODE_PREFIX = re.compile(r"^\s*[\[\(]\s*[A-Za-z0-9][A-Za-z0-9._/-]*\s*[\]\)]\s*")
UPPER_BRAND = re.compile(r"\b([A-ZА-ЯЎҚҒҲ]{3,}(?:[- ][A-ZА-ЯЎҚҒҲ]{2,})?)\b")
UNIT_LIKE = {"MM", "SM", "KG", "GR", "ML", "LED", "PVC", "UV", "GKL", "GKLV", "OSB", "MDF"}


def clean_name(raw: str) -> str:
    """'[0066-01890] Bazalt PETRAWOOL (100mm)' -> 'Bazalt PETRAWOOL (100mm)'"""
    s = str(raw or "").strip()
    prev = None
    while s != prev:                 # bir nechta kod ketma-ket bo'lishi mumkin
        prev = s
        s = CODE_PREFIX.sub("", s)
    return re.sub(r"\s{2,}", " ", s).strip(" -–—|")


def category_from_filename(filename: str) -> str:
    """'unitaz.xlsx' -> 'Unitaz'. Kategoriya ustuni bo'lmaganda ishlatiladi."""
    stem = re.sub(r"\.[A-Za-z]+$", "", str(filename or "")).strip()
    stem = re.sub(r"[_\-]+", " ", stem)
    stem = re.sub(r"\(\s*\d+\s*\)", " ", stem)          # "narxlar (2)" -> "narxlar"
    stem = re.sub(r"\b(prays|price|narx|narxlar|list|spisok|export|eksport)\b",
                  " ", stem, flags=re.IGNORECASE)
    stem = re.sub(r"[^\w\s'ʻ-]+", " ", stem, flags=re.UNICODE)
    stem = re.sub(r"\s{2,}", " ", stem).strip()
    if not stem or len(stem) < 3 or stem.isdigit():
        return ""
    return stem[:1].upper() + stem[1:]


def _stock_value(v) -> float | None:
    """Qoldiq ustunidagi qiymat. Aniqlab bo'lmasa None."""
    if v in (None, ""):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", ".")
    s = re.sub(r"[^\d.\-]", "", s)
    try:
        return float(s) if s not in ("", "-", ".") else None
    except ValueError:
        return None


def guess_category(name: str) -> str:
    """Kategoriya ustuni bo'lmasa — nomning birinchi so'zidan."""
    first = clean_name(name).split()
    if not first:
        return ""
    w = first[0].strip(".,;:")
    return w.capitalize() if len(w) > 2 else ""


def guess_brand(name: str, category: str = "") -> str:
    """Brend ustuni bo'lmasa — nomdagi BOSH HARFLI so'z (PETRAWOOL, EVEREST)."""
    body = clean_name(name)
    if category:
        body = re.sub(r"^" + re.escape(category), "", body, flags=re.IGNORECASE).strip()
    for m in UPPER_BRAND.finditer(body):
        cand = m.group(1).strip()
        if cand.upper() in UNIT_LIKE or cand.isdigit():
            continue
        return cand.title() if len(cand) > 3 else cand
    return ""


def _clean_price(v) -> str:
    if v in (None, ""):
        return ""
    if isinstance(v, (int, float)):
        return str(int(round(float(v))))
    s = str(v).strip()
    s = re.sub(r"(so'm|som|сум|sum|uzs|руб)\.?", "", s, flags=re.IGNORECASE).strip()
    digits = re.sub(r"[^\d]", "", s.replace(".", "").replace(",", ""))
    return digits or s


def _rows_from_xlsx(data: bytes) -> list[list]:
    wb = load_workbook(io.BytesIO(data), data_only=True, read_only=True)
    rows = []
    for ws in wb.worksheets:
        sheet_rows = [list(r) for r in ws.iter_rows(values_only=True)]
        if len(sheet_rows) > len(rows):
            rows = sheet_rows
    wb.close()
    return rows


def _rows_from_csv(data: bytes) -> list[list]:
    for enc in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = data.decode("utf-8", errors="replace")
    sample = text[:4000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        delim = dialect.delimiter
    except csv.Error:
        delim = ";" if sample.count(";") > sample.count(",") else ","
    return [row for row in csv.reader(io.StringIO(text), delimiter=delim)]


def parse(data: bytes, filename: str, default_category: str = "") -> tuple[list[dict], str]:
    """Faylni o'qib, mahsulotlar ro'yxatini qaytaradi. (mahsulotlar, xabar)

    default_category — fayl bilan birga yozilgan kategoriya nomi (caption).
    Bo'sh bo'lsa, kategoriya mahsulot nomining birinchi so'zidan olinadi.
    """
    lower = filename.lower()
    if lower.endswith((".xlsx", ".xlsm", ".xltx")):
        rows = _rows_from_xlsx(data)
    elif lower.endswith((".csv", ".txt", ".tsv")):
        rows = _rows_from_csv(data)
    else:
        return [], (
            "❌ Bu format qo'llab-quvvatlanmaydi.\n"
            "Iltimos <b>.xlsx</b> yoki <b>.csv</b> fayl yuboring.\n"
            "(PDF bo'lsa — Excel'ga o'girib yuboring.)"
        )

    rows = [r for r in rows if any(str(c or "").strip() for c in r)]
    if not rows:
        return [], "❌ Fayl bo'sh ko'rinadi."

    h_idx, mapping = _find_header(rows)
    if h_idx < 0:
        return [], (
            "❌ Mahsulot nomi ustunini topa olmadim.\n\n"
            "Birinchi qatorda ustun nomlari bo'lsin, masalan:\n"
            "<code>Nomi | Kategoriya | Brend | Narx | Birlik | Eski narx | Izoh</code>"
        )

    items, skipped, out_of_stock = [], 0, 0
    file_category = category_from_filename(filename)
    for row in rows[h_idx + 1:]:
        def cell(field):
            i = mapping.get(field)
            if i is None or i >= len(row):
                return ""
            v = row[i]
            return "" if v is None else str(v).strip()

        name = clean_name(cell("name"))
        if not name or _norm_header(name) in COLUMN_ALIASES["name"]:
            continue

        # qoldig'i yo'q mahsulot kanalga chiqmaydi
        if "stock" in mapping:
            qty = _stock_value(row[mapping["stock"]] if mapping["stock"] < len(row) else None)
            if qty is not None and qty <= 0:
                out_of_stock += 1
                continue
        price = _clean_price(row[mapping["price"]]) if "price" in mapping and mapping["price"] < len(row) else ""
        if not price and "wholesale" in mapping and mapping["wholesale"] < len(row):
            price = _clean_price(row[mapping["wholesale"]])
        old = _clean_price(row[mapping["old_price"]]) if "old_price" in mapping and mapping["old_price"] < len(row) else ""
        if not price:
            skipped += 1
        category = (cell("category") or default_category
                    or file_category or guess_category(name))
        brand = cell("brand") or guess_brand(name, category)
        items.append({
            "name": name,
            "price": price,
            "old_price": old,
            "unit": cell("unit"),
            "category": category,
            "brand": brand,
            "note": cell("note"),
        })

    found = ", ".join(sorted(mapping)) or "—"
    msg = f"Topilgan ustunlar: <code>{found}</code>"
    if "stock" in mapping:
        msg += "\n📦 Qoldiq ustuni topildi — omborda yo'q mahsulotlar olinmadi"
        if out_of_stock:
            msg += f" ({out_of_stock} ta)"
    if skipped:
        msg += f"\n⚠️ {skipped} ta qatorda narx yo'q — ular navbatga chiqmaydi."
    if not mapping.get("category") and file_category:
        msg += f"\n📂 Kategoriya fayl nomidan olindi: <b>{file_category}</b>"
    return items, msg
