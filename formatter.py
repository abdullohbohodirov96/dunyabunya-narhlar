"""Shablonni to'ldirish — bo'sh maydonli qatorlar o'zi olib tashlanadi."""
import html
import re

PLACEHOLDER = re.compile(r"\{(\w+)\}")

# Shablonda ishlatish mumkin bo'lgan barcha kalitlar (yordam matni uchun)
KEYS = [
    "nom", "brend", "brend_qatori", "narx", "birlik", "eski_narx", "eski_narx_qatori",
    "chegirma", "izoh", "izoh_qatori", "kategoriya", "telefon", "telefon_link",
    "filiallar", "dokon", "kanal", "sana",
]


def money(value) -> str:
    """'52000' -> '52 000'. Matnli qiymat bo'lsa o'zgartirmaydi."""
    if value in (None, ""):
        return ""
    s = str(value).strip().replace(" ", " ")
    cleaned = s.replace(" ", "").replace(",", "").replace("'", "")
    if re.fullmatch(r"\d+(\.\d+)?", cleaned):
        num = int(float(cleaned))
        return f"{num:,}".replace(",", " ")
    return s


def _digits(value) -> float | None:
    s = re.sub(r"[^\d.]", "", str(value or "").replace(",", ""))
    try:
        return float(s) if s else None
    except ValueError:
        return None


def _phone_link(settings: dict) -> str:
    """Telefon raqamini havolaga o'raydi (Telegram HTML)."""
    phone = html.escape(str(settings.get("shop_phone") or "").strip())
    link = str(settings.get("contact_link") or "").strip()
    if not phone:
        return ""
    if not link:
        return phone
    return f'<a href="{html.escape(link, quote=True)}">{phone}</a>'


def parse_branches(raw: str) -> list[tuple[str, str]]:
    """'Shirinobod|+998...;Hasanboy|+998...' -> [(nom, telefon), ...]"""
    out = []
    for chunk in str(raw or "").split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        name, _, phone = chunk.partition("|")
        name, phone = name.strip(), phone.strip()
        if name:
            out.append((name, phone))
    return out


def branches_block(settings: dict) -> str:
    """Filiallar ro'yxati — har biri alohida qatorda, raqami bosiladigan."""
    rows = parse_branches(settings.get("branches", ""))
    if not rows:
        return _phone_link(settings)
    lines = []
    for name, phone in rows:
        line = f"📍 {html.escape(name)}"
        if phone:
            digits = re.sub(r"[^\d+]", "", phone)
            line += f" — <a href=\"tel:{digits}\">{html.escape(phone)}</a>"
        lines.append(line)
    return "\n".join(lines)


def build_values(product: dict, settings: dict) -> dict:
    esc = lambda v: html.escape(str(v or "").strip())

    name = esc(product.get("name"))
    brand = esc(product.get("brand"))
    category = esc(product.get("category"))
    unit = esc(product.get("unit"))
    note = esc(product.get("note"))
    price = money(product.get("price"))
    old = money(product.get("old_price"))

    discount = ""
    p, o = _digits(product.get("price")), _digits(product.get("old_price"))
    if p and o and o > p:
        discount = f"-{round((o - p) / o * 100)}%"

    values = {
        "nom": name,
        "brend": brand,
        "brend_qatori": f"🏷 {brand}\n" if brand else "",
        "narx": price,
        "birlik": f" / {unit}" if unit else "",
        "eski_narx": old,
        "eski_narx_qatori": (
            f"🔻 Eski narx: <s>{old} so'm</s>" + (f"  ({discount})" if discount else "") + "\n"
        ) if old else "",
        "chegirma": discount,
        "izoh": note,
        "izoh_qatori": f"ℹ️ {note}\n" if note else "",
        "kategoriya": category,
        "telefon": esc(settings.get("shop_phone")),
        "telefon_link": _phone_link(settings),
        "filiallar": branches_block(settings),
        "dokon": esc(settings.get("shop_name")),
        "kanal": esc(settings.get("channel_link")),
        "sana": settings.get("sana", ""),
    }
    return values


def render(template: str, values: dict) -> str:
    """Shablonni to'ldiradi; ichidagi hamma maydoni bo'sh bo'lgan qatorni o'chiradi."""
    lines_out = []
    for line in template.split("\n"):
        keys = PLACEHOLDER.findall(line)
        if keys:
            filled = [str(values.get(k, "") or "").strip() for k in keys]
            if all(v == "" for v in filled):
                continue
        lines_out.append(PLACEHOLDER.sub(lambda m: str(values.get(m.group(1), "") or ""), line))

    text = "\n".join(lines_out)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def render_product(product: dict, settings: dict) -> str:
    return render(settings.get("template", ""), build_values(product, settings))
