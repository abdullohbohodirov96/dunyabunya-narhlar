"""Excel / CSV narxlar ro'yxatini o'qish.

Ustun nomlari o'zbekcha, ruscha yoki inglizcha bo'lishi mumkin — bot o'zi taniydi.
Kerakli ustun faqat bittasi: mahsulot nomi. Qolganlari ixtiyoriy.
"""
import csv
import io
import re
from html.parser import HTMLParser

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

# foiz / kurs / ustama ustunlari ham narx emas ("Ulgurji margin" = 10, narx emas)
NOT_PRICE = re.compile(
    r"margin|ustama|foiz|%|кур[сc]|kurs|procent|процент|надбавка|наценк|скидк|discount",
    re.IGNORECASE)


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
        # dollar/evro, foiz va ustama ustunlari narx sifatida olinmaydi
        if field in ("price", "old_price", "wholesale") and (
                FOREIGN.search(str(cell)) or NOT_PRICE.search(str(cell))):
            continue
        if field not in best or rank > best[field][0]:
            best[field] = (rank, idx)
    return {f: i for f, (_r, i) in best.items()}


def _find_header(rows) -> tuple[int, dict]:
    """Sarlavha qatorini birinchi 30 qator ichidan topadi."""
    best_i, best_map = -1, {}
    for i, row in enumerate(rows[:30]):
        m = _map_columns(row)
        if "name" in m and len(m) > len(best_map):
            best_i, best_map = i, m
    return best_i, best_map


def _looks_numeric(v) -> bool:
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return True
    s = re.sub(r"[\s ]", "", str(v or ""))
    return bool(s) and bool(re.fullmatch(r"-?\d[\d.,]*", s))


def _guess_columns(rows) -> tuple[dict, int]:
    """Sarlavhasi yo'q fayl: nomni va narxni ustunlar ko'rinishidan topamiz.

    Nom — eng ko'p matnli va eng uzun ustun. Narx — eng ko'p son bo'lgan,
    qiymatlari 100 dan katta ustun.
    """
    body = rows[:400]
    if len(body) < 2:
        return {}, 0
    width = max(len(r) for r in body)
    text_score = [0.0] * width
    num_score = [0] * width
    big_num = [0] * width
    for r in body:
        for i in range(width):
            v = r[i] if i < len(r) else ""
            s = str(v or "").strip()
            if not s:
                continue
            if _looks_numeric(v):
                num_score[i] += 1
                try:
                    if float(re.sub(r"[^\d.]", "", s) or 0) >= 100:
                        big_num[i] += 1
                except ValueError:
                    pass
            elif len(s) >= 3 and re.search(r"[A-Za-zА-Яа-яЎўҚқҒғҲҳ]", s):
                text_score[i] += len(s)

    name_i = max(range(width), key=lambda i: text_score[i])
    if text_score[name_i] <= 0:
        return {}, 0
    price_i = max((i for i in range(width) if i != name_i),
                  key=lambda i: (big_num[i], num_score[i]), default=None)
    mapping = {"name": name_i}
    if price_i is not None and big_num[price_i] >= max(2, len(body) // 10):
        mapping["price"] = price_i
    return mapping, 0          # sarlavha yo'q — birinchi qatordan o'qiymiz


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


def _rows_from_xls(data: bytes) -> list[list]:
    """Eski Excel (97-2003, .xls). xlrd bo'lmasa — bo'sh."""
    import xlrd                                   # faqat kerak bo'lganda
    book = xlrd.open_workbook(file_contents=data)
    rows = []
    for sh in book.sheets():
        sheet_rows = [[sh.cell_value(r, c) for c in range(sh.ncols)]
                      for r in range(sh.nrows)]
        if len(sheet_rows) > len(rows):
            rows = sheet_rows
    return rows


class _TableGrab(HTMLParser):
    """1C va boshqa programmalar 'Excel' deb HTML jadval beradi — shuni o'qiydi."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        self._rows: list[list[str]] | None = None
        self._cells: list[str] | None = None
        self._buf: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self._rows = []
        elif tag == "tr" and self._rows is not None:
            self._cells = []
        elif tag in ("td", "th") and self._cells is not None:
            self._buf = []
        elif tag == "br" and self._buf is not None:
            self._buf.append(" ")

    def handle_data(self, data):
        if self._buf is not None:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._buf is not None:
            text = re.sub(r"\s+", " ", "".join(self._buf)).strip()
            if self._cells is not None:
                self._cells.append(text)
            self._buf = None
        elif tag == "tr" and self._cells is not None:
            if self._rows is not None:
                self._rows.append(self._cells)
            self._cells = None
        elif tag == "table" and self._rows is not None:
            if self._rows:
                self.tables.append(self._rows)
            self._rows = None


def _rows_from_html(data: bytes) -> list[list]:
    for enc in ("utf-8-sig", "utf-8", "cp1251", "windows-1252"):
        try:
            text = data.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = data.decode("utf-8", errors="replace")
    m = re.search(r'charset=["\']?([\w-]+)', text[:2000], re.IGNORECASE)
    if m and m.group(1).lower() not in ("utf-8", "utf8"):
        try:
            text = data.decode(m.group(1))
        except (UnicodeDecodeError, LookupError):
            pass
    p = _TableGrab()
    p.feed(text)
    return max(p.tables, key=len) if p.tables else []


def _rows_from_xml(data: bytes) -> list[list]:
    """Excel 2003 XML (SpreadsheetML)."""
    import xml.etree.ElementTree as ET
    root = ET.fromstring(data)
    ns = "{urn:schemas-microsoft-com:office:spreadsheet}"
    best: list[list] = []
    for table in root.iter(f"{ns}Table"):
        rows = []
        for tr in table.iter(f"{ns}Row"):
            cells, col = [], 0
            for td in tr.iter(f"{ns}Cell"):
                idx = td.get(f"{ns}Index")
                if idx:
                    col = int(idx) - 1
                while len(cells) < col:
                    cells.append("")
                d = td.find(f"{ns}Data")
                cells.append("" if d is None else (d.text or ""))
                col += 1
            rows.append(cells)
        if len(rows) > len(best):
            best = rows
    return best


def _sniff(data: bytes, filename: str) -> str:
    """Faylning haqiqiy turi — kengaytmaga emas, ichidagi baytlarga qarab."""
    head = data[:2048]
    if head[:4] == b"PK\x03\x04":
        return "xlsx"
    if head[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "xls"
    stripped = head.lstrip(b"\xef\xbb\xbf \t\r\n")
    low = stripped[:1024].lower()
    if low.startswith(b"<?xml"):
        return "xml" if b"urn:schemas-microsoft-com:office:spreadsheet" in head.lower() \
            else ("html" if b"<table" in data[:200000].lower() else "xml")
    if low.startswith((b"<!doctype", b"<html", b"<meta", b"<table", b"<body")) \
            or b"<table" in low:
        return "html"
    lower = filename.lower()
    if lower.endswith((".csv", ".tsv", ".txt")):
        return "csv"
    if lower.endswith((".xlsx", ".xlsm", ".xltx")):
        return "xlsx"
    if lower.endswith(".xls"):
        return "xls"
    return "csv"              # oxirgi imkoniyat — matn deb ko'ramiz


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
    if not data:
        return [], "❌ Fayl bo'sh keldi — qaytadan yuborib ko'ring."

    kind = _sniff(data, filename)
    readers = {"xlsx": _rows_from_xlsx, "xls": _rows_from_xls,
               "html": _rows_from_html, "xml": _rows_from_xml, "csv": _rows_from_csv}
    order = [kind] + [k for k in ("xlsx", "xls", "html", "xml", "csv") if k != kind]

    rows, errors = [], []
    for k in order:                      # biri bo'lmasa — boshqasini sinab ko'ramiz
        try:
            got = readers[k](data)
        except Exception as e:            # noqa: BLE001 — har qanday format xatosi
            errors.append(f"{k}: {type(e).__name__}")
            continue
        got = [r for r in got if any(str(c or "").strip() for c in r)]
        if len(got) >= 2:
            rows = got
            break
        if got and not rows:
            rows = got
    if not rows:
        return [], (
            "❌ Faylni o'qiy olmadim — ichida jadval topilmadi.\n\n"
            "Excel'da faylni ochib <b>«Сохранить как» → .xlsx</b> qilib "
            "qayta yuboring.\n"
            f"<i>Fayl: {filename} · {len(data) // 1024} KB</i>"
            + (f"\n<i>({'; '.join(errors[:3])})</i>" if errors else "")
        )

    h_idx, mapping = _find_header(rows)
    start = h_idx + 1
    if h_idx < 0:                       # sarlavha yo'q — ustunlarni o'zimiz topamiz
        mapping, start = _guess_columns(rows)
    if "name" not in mapping:
        preview = " | ".join(str(c or "")[:18] for c in rows[0][:6])
        return [], (
            "❌ Mahsulot nomi ustunini topa olmadim.\n\n"
            "Birinchi qatorda ustun nomlari bo'lsin, masalan:\n"
            "<code>Nomi | Kategoriya | Brend | Narx | Birlik</code>\n\n"
            f"<i>Birinchi qator shunday ko'rindi:</i>\n<code>{preview}</code>"
        )

    items, skipped, out_of_stock = [], 0, 0
    file_category = category_from_filename(filename)
    for row in rows[start:]:
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
