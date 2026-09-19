"""Rasm tagidagi matndan mahsulot nomi, narxi va birligini ajratish."""
import re

CURRENCY = r"(?:so['ʻ`’]?m|som|сум|сўм|uzs)"
UNIT_WORDS = (
    "qop", "dona", "m", "m2", "m²", "m3", "m³", "kg", "tonna", "litr", "rulon",
    "quti", "paket", "komplekt", "metr", "pog.m", "pm", "шт", "мешок", "м2", "м3", "кг",
)


def _to_number(raw: str) -> str:
    digits = re.sub(r"[^\d]", "", raw)
    return digits.lstrip("0") or digits


def parse_caption(text: str) -> dict:
    """'Sement M-400 — 52 000 so'm/qop' -> {name, price, unit, ...}"""
    text = (text or "").strip()
    if not text:
        return {}

    result = {"name": "", "price": "", "unit": "", "old_price": "", "category": "", "note": ""}

    # #teg -> kategoriya
    tags = re.findall(r"#(\w+)", text)
    if tags:
        result["category"] = tags[0].replace("_", " ").capitalize()
        text = re.sub(r"#\w+", " ", text)

    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if not lines:
        return result

    price_raw = ""
    # 1) "narx: 52000" ko'rinishi
    m = re.search(r"narx[ia]?\s*[:\-—=]?\s*([\d][\d\s.,]*)", text, re.IGNORECASE)
    # 2) "52 000 so'm"
    if not m:
        m = re.search(r"([\d][\d\s.,]*)\s*" + CURRENCY, text, re.IGNORECASE)
    # 3) "— 52000" / "- 52000" oxirida
    if not m:
        m = re.search(r"[-—–:]\s*([\d][\d\s.,]{2,})\s*$", lines[0])
    # 4) alohida qatorda faqat raqam
    if not m:
        for ln in lines[1:]:
            if re.fullmatch(r"[\d][\d\s.,]*", ln):
                m = re.match(r"([\d][\d\s.,]*)", ln)
                break
    if m:
        price_raw = m.group(0)
        result["price"] = _to_number(m.group(1))

    # birlik: "so'm/qop", "/ dona", "1 dona"
    um = re.search(r"/\s*([A-Za-zА-Яа-яЎўҚқҒғҲҳ.²³0-9]+)", text)
    if um and um.group(1).lower() in [u.lower() for u in UNIT_WORDS]:
        result["unit"] = um.group(1)
    else:
        um2 = re.search(CURRENCY + r"\s*[/\\ ]\s*([A-Za-zА-Яа-я²³0-9.]+)", text, re.IGNORECASE)
        if um2:
            result["unit"] = um2.group(1)

    # nom: birinchi qator, narx qismi olib tashlangan holda
    name = lines[0]
    if price_raw and price_raw.strip() in name:
        name = name.replace(price_raw.strip(), " ")
    name = re.sub(CURRENCY, " ", name, flags=re.IGNORECASE)
    if result["unit"]:
        name = re.sub(r"/\s*" + re.escape(result["unit"]), " ", name, flags=re.IGNORECASE)
    name = re.sub(r"[\-—–:]\s*$", "", name.strip())
    name = re.sub(r"\s{2,}", " ", name).strip(" -—–:•*")
    result["name"] = name

    # qolgan qatorlar -> izoh (narx qatori bo'lmasa)
    rest = []
    for ln in lines[1:]:
        if re.fullmatch(r"[\d][\d\s.,]*", ln):
            continue
        if re.search(r"narx", ln, re.IGNORECASE) and re.search(r"\d", ln):
            continue
        rest.append(ln)
    if rest:
        result["note"] = " · ".join(rest)[:120]

    return result
