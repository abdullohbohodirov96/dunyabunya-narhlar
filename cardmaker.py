"""dunyabunya brend dizaynidagi narx-kartochkasini yasaydi (Pillow).

Ranglar: to'q ko'k (dark navy) + "mokriy asfalt" (to'q kulrang) fon, to'q sariq aksent.
Chiqish: 1080x1350 PNG (Telegram kanal + Instagram uchun mos).
"""
import io
import os
import re
import textwrap

from PIL import Image, ImageDraw, ImageFilter, ImageFont

BASE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = os.path.join(BASE, "assets", "fonts")
def logo_path() -> str:
    """Logo fayli: LOGO_PATH env -> baza papkasi -> repo assets."""
    env = os.getenv("LOGO_PATH", "").strip()
    if env:
        return env
    data_dir = os.path.dirname(os.getenv("DB_PATH", "/data/bot.db")) or "."
    candidate = os.path.join(data_dir, "logo.png")
    if os.path.exists(candidate):
        return candidate
    return os.path.join(BASE, "assets", "logo.png")

W, H = 1080, 1350
PAD = 64

# ---- dunyabunya BREND RANGLARI -----------------------------------------
# #e97609 (to'q sariq) · #2e3239 (mokriy asfalt) · #000000 · #ffffff
ORANGE = (233, 118, 9)
ORANGE_DARK = (196, 96, 5)
ASPHALT = (46, 50, 57)
ASPHALT_LIGHT = (62, 68, 77)
BLACK = (0, 0, 0)
NAVY = (26, 29, 34)          # qora bilan asfalt orasidagi oraliq
NAVY_DEEP = (10, 11, 13)
WHITE = (255, 255, 255)
MUTED = (163, 170, 180)

CYRILLIC = re.compile(r"[Ѐ-ӿ]")
_font_cache: dict = {}


# Brend shrifti — Montserrat. assets/fonts ichiga Montserrat-Bold.ttf va
# Montserrat-Medium.ttf tashlansa, bot avtomatik o'shani ishlatadi.
# Bo'lmasa — Poppins (juda yaqin geometrik sans), kirill uchun DejaVu.
FONT_STACK = {
    (True, False): ["Montserrat-Bold.ttf", "Poppins-Bold.ttf", "DejaVuSans-Bold.ttf"],
    (False, False): ["Montserrat-Medium.ttf", "Montserrat-Regular.ttf",
                     "Poppins-Medium.ttf", "DejaVuSans.ttf"],
    (True, True): ["Montserrat-Bold.ttf", "DejaVuSans-Bold.ttf"],
    (False, True): ["Montserrat-Medium.ttf", "DejaVuSans.ttf"],
}


def _font_file(bold: bool, cyr: bool) -> str:
    for name in FONT_STACK[(bold, cyr)]:
        path = os.path.join(FONT_DIR, name)
        if os.path.exists(path):
            return path
    return os.path.join(FONT_DIR, "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")


def font(size: int, bold: bool = False, text: str = "") -> ImageFont.FreeTypeFont:
    key = (size, bold, bool(CYRILLIC.search(text or "")))
    if key not in _font_cache:
        try:
            _font_cache[key] = ImageFont.truetype(_font_file(bold, key[2]), size)
        except OSError:
            _font_cache[key] = ImageFont.load_default()
    return _font_cache[key]


def _w(draw, text, f) -> int:
    return draw.textbbox((0, 0), text, font=f)[2]


def _h(draw, text, f) -> int:
    b = draw.textbbox((0, 0), text or "Ag", font=f)
    return b[3] - b[1]


# ---------------------------------------------------------------- fon
def _background() -> Image.Image:
    small = Image.new("RGB", (2, 2))
    small.putpixel((0, 0), ASPHALT_LIGHT)
    small.putpixel((1, 0), ASPHALT)
    small.putpixel((0, 1), NAVY)
    small.putpixel((1, 1), NAVY_DEEP)
    bg = small.resize((W, H), Image.Resampling.BICUBIC)

    # yengil diagonal chiziqlar (qurilish teksturasi)
    stripes = Image.new("L", (W, H), 0)
    sd = ImageDraw.Draw(stripes)
    for x in range(-H, W, 46):
        sd.line([(x, H), (x + H, 0)], fill=16, width=12)
    bg = Image.composite(Image.new("RGB", (W, H), WHITE), bg, stripes.filter(ImageFilter.GaussianBlur(1)))

    # pastki chap burchakda yengil to'q sariq nur
    glow = Image.new("RGB", (W, H), ORANGE)
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).ellipse([-460, H - 380, 420, H + 380], fill=46)
    bg = Image.composite(glow, bg, mask.filter(ImageFilter.GaussianBlur(140)))
    return bg


def _cover(img: Image.Image, box_w: int, box_h: int) -> Image.Image:
    img = img.convert("RGB")
    ratio = max(box_w / img.width, box_h / img.height)
    img = img.resize((max(1, int(img.width * ratio)), max(1, int(img.height * ratio))), Image.Resampling.LANCZOS)
    left = (img.width - box_w) // 2
    top = (img.height - box_h) // 2
    return img.crop((left, top, left + box_w, top + box_h))


def _round_mask(size, radius: int) -> Image.Image:
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, size[0] - 1, size[1] - 1], radius=radius, fill=255)
    return m


def _fit_lines(draw, text: str, max_w: int, size: int, bold: bool, max_lines: int):
    """Matnni qatorlarga bo'ladi, sig'masa shriftni kichraytiradi."""
    while size > 28:
        f = font(size, bold, text)
        avg = max(1, _w(draw, "ABCDEFGHIJ", f) // 10)
        lines = textwrap.wrap(text, width=max(6, int(max_w / avg * 1.05))) or [text]
        if len(lines) <= max_lines and all(_w(draw, ln, f) <= max_w for ln in lines):
            return lines, f
        size -= 4
    f = font(size, bold, text)
    lines = textwrap.wrap(text, width=24)[:max_lines] or [text]
    return lines, f


def _money(v) -> str:
    s = str(v or "").strip().replace(" ", "").replace(",", "")
    if re.fullmatch(r"\d+(\.\d+)?", s):
        return f"{int(float(s)):,}".replace(",", " ")
    return str(v or "").strip()


# ---------------------------------------------------------------- logo
def _draw_logo(img: Image.Image, draw: ImageDraw.ImageDraw, shop_name: str) -> int:
    """Yuqori chap burchakka logo yoki wordmark. Pastki y ni qaytaradi."""
    y = PAD
    lp = logo_path()
    if os.path.exists(lp):
        try:
            logo = Image.open(lp).convert("RGBA")
            target_h = 96
            ratio = target_h / logo.height
            logo = logo.resize((int(logo.width * ratio), target_h), Image.Resampling.LANCZOS)
            img.paste(logo, (PAD, y), logo)
            return y + target_h
        except Exception:
            pass

    draw.rounded_rectangle([PAD, y, PAD + 84, y + 84], radius=20, fill=ORANGE)
    f_mark = font(44, True, "db")
    draw.text((PAD + 42, y + 44), "db", font=f_mark, fill=WHITE, anchor="mm")

    f_name = font(38, True, shop_name)
    draw.text((PAD + 106, y + 16), shop_name, font=f_name, fill=WHITE)
    f_sub = font(21, False, "QURILISH MOLLARI")
    draw.text((PAD + 108, y + 56), "QURILISH MOLLARI", font=f_sub, fill=MUTED)
    return y + 84


# ---------------------------------------------------------------- asosiy
def make_card(product: dict, settings: dict, photo_bytes: bytes | None = None) -> bytes:
    name = (product.get("name") or "").strip()
    price = _money(product.get("price"))
    old_price = _money(product.get("old_price"))
    unit = (product.get("unit") or "").strip()
    brand = (product.get("brand") or "").strip()
    category = (product.get("category") or "").strip()
    note = (product.get("note") or "").strip()
    shop = (settings.get("shop_name") or "dunyabunya").strip()
    phone = (settings.get("shop_phone") or "").strip()
    channel = (settings.get("channel_link") or "").strip()

    img = _background()
    draw = ImageDraw.Draw(img)

    # --- sarlavha qatori
    logo_bottom = _draw_logo(img, draw, shop)
    badge = "NARXLAR"
    f_badge = font(24, True, badge)
    bw = _w(draw, badge, f_badge) + 44
    draw.rounded_rectangle([W - PAD - bw, PAD + 18, W - PAD, PAD + 18 + 54], radius=27,
                           outline=ORANGE, width=3)
    draw.text((W - PAD - bw / 2, PAD + 18 + 27), badge, font=f_badge, fill=ORANGE, anchor="mm")

    # --- mahsulot rasmi
    top = logo_bottom + 48
    ph_h = 540
    if photo_bytes:
        try:
            src = Image.open(io.BytesIO(photo_bytes))
            photo = _cover(src, W - 2 * PAD, ph_h)
            mask = _round_mask(photo.size, 36)
            shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
            ImageDraw.Draw(shadow).rounded_rectangle(
                [PAD + 8, top + 16, W - PAD + 8, top + ph_h + 22], radius=36, fill=(0, 0, 0, 150)
            )
            img.paste(Image.alpha_composite(img.convert("RGBA"), shadow.filter(
                ImageFilter.GaussianBlur(18))).convert("RGB"), (0, 0))
            draw = ImageDraw.Draw(img)
            img.paste(photo, (PAD, top), mask)
            draw.rounded_rectangle([PAD, top, W - PAD - 1, top + ph_h - 1], radius=36,
                                   outline=(255, 255, 255, 40), width=2)
        except Exception:
            photo_bytes = None

    if not photo_bytes:
        ph_h = 430
        draw.rounded_rectangle([PAD, top, W - PAD, top + ph_h], radius=36, fill=ASPHALT_LIGHT)
        f_ph = font(30, True, shop)
        draw.text((W / 2, top + ph_h / 2), shop, font=f_ph, fill=MUTED, anchor="mm")

    y = top + ph_h + 46

    # --- kategoriya / brend chiplari
    chips = [c for c in (category, brand) if c]
    if chips:
        x = PAD
        for i, chip in enumerate(chips[:2]):
            f_c = font(24, True, chip)
            cw = _w(draw, chip.upper(), f_c) + 40
            if x + cw > W - PAD:
                break
            fill = ORANGE if i == 0 else None
            draw.rounded_rectangle([x, y, x + cw, y + 50], radius=25,
                                   fill=fill, outline=None if fill else MUTED, width=2)
            draw.text((x + cw / 2, y + 25), chip.upper(), font=f_c,
                      fill=WHITE if fill else MUTED, anchor="mm")
            x += cw + 14
        y += 74

    # --- mahsulot nomi
    lines, f_name = _fit_lines(draw, name, W - 2 * PAD, 62, True, 3)
    for ln in lines:
        draw.text((PAD, y), ln, font=f_name, fill=WHITE)
        y += int(f_name.size * 1.22)
    y += 16

    # --- narx paneli
    panel_h = 172
    panel_y = H - PAD - 96 - panel_h - 24
    panel_y = max(y + 10, panel_y)
    draw.rounded_rectangle([PAD, panel_y, W - PAD, panel_y + panel_h], radius=32, fill=ORANGE)
    draw.rounded_rectangle([PAD, panel_y, PAD + 10, panel_y + panel_h], radius=6, fill=ORANGE_DARK)

    f_lbl = font(24, False, "NARXI")
    draw.text((PAD + 40, panel_y + 26), "NARXI", font=f_lbl, fill=(255, 235, 215))

    price_txt = price or "—"
    size = 84
    while size > 44 and _w(draw, price_txt, font(size, True, price_txt)) > W - 2 * PAD - 300:
        size -= 4
    f_price = font(size, True, price_txt)
    px, py = PAD + 40, panel_y + 62
    draw.text((px, py), price_txt, font=f_price, fill=WHITE)
    px += _w(draw, price_txt, f_price) + 12

    f_cur = font(34, True, "so'm")
    draw.text((px, py + size - 44), "so'm", font=f_cur, fill=(255, 240, 225))
    px += _w(draw, "so'm", f_cur) + 8
    if unit:
        f_u = font(28, False, unit)
        draw.text((px, py + size - 40), f"/ {unit}", font=f_u, fill=(255, 228, 205))

    if old_price:
        old_txt = f"{old_price} so'm"
        f_old = font(30, False, old_txt)
        ow = _w(draw, old_txt, f_old)
        ox = W - PAD - 40 - ow
        oy = panel_y + 38
        draw.text((ox, oy), old_txt, font=f_old, fill=(255, 226, 202))
        mid = oy + f_old.size * 0.72
        draw.line([(ox - 6, mid), (ox + ow + 6, mid)], fill=(255, 226, 202), width=3)

    if note:
        f_n = font(26, False, note)
        nt = note if _w(draw, note, f_n) <= W - 2 * PAD else note[:60] + "…"
        draw.text((PAD + 4, panel_y - 44), nt, font=f_n, fill=MUTED)

    # --- pastki qator
    fy = H - PAD - 62
    draw.line([(PAD, fy - 26), (W - PAD, fy - 26)], fill=(90, 100, 112), width=2)
    if phone:
        # kichik telefon belgisi (emoji o'rniga — har qanday tizimda chiziladi)
        draw.rounded_rectangle([PAD, fy + 2, PAD + 28, fy + 40], radius=8, fill=ORANGE)
        draw.rounded_rectangle([PAD + 8, fy + 10, PAD + 20, fy + 30], radius=4, fill=NAVY_DEEP)
        f_f = font(28, True, phone)
        draw.text((PAD + 44, fy + 4), phone, font=f_f, fill=WHITE)
    if channel:
        f_ch = font(26, False, channel)
        draw.text((W - PAD, fy + 8), channel, font=f_ch, fill=ORANGE, anchor="ra")

    out = io.BytesIO()
    img.save(out, format="JPEG", quality=92, optimize=True)
    return out.getvalue()


# ================================================================
#  BREND PRAYS KARTOCHKASI  (asosiy post turi)
#  Bitta rasmda bitta brendning hamma mahsuloti, kategoriyalarga bo'lingan.
#  Fon mavzusi /fon buyrug'i bilan tanlanadi.
# ================================================================
MAX_ROWS = 18
ROW_H = 76
SECTION_H = 62
BAND_H = 236          # yuqoridagi to'q chiziq (logo oq bo'lgani uchun kerak)

THEMES = {
    # to'q: mokriy asfalt + qora, diagonal chiziqlar bilan
    "toq": {
        "bg": ASPHALT_LIGHT, "bg2": ASPHALT, "bg3": NAVY, "bg4": NAVY_DEEP,
        "stripe": (255, 255, 255), "stripe_a": 16, "glow": 46,
        "text": WHITE, "muted": MUTED, "row": ASPHALT_LIGHT,
        "line": (78, 86, 97), "band": None, "foot_line": (90, 100, 112),
    },
    # qora: sof qora, minimal
    "qora": {
        "bg": (24, 24, 26), "bg2": (12, 12, 14), "bg3": (8, 8, 9), "bg4": BLACK,
        "stripe": (255, 255, 255), "stripe_a": 10, "glow": 34,
        "text": WHITE, "muted": (150, 152, 158), "row": (38, 38, 42),
        "line": (62, 62, 68), "band": None, "foot_line": (70, 70, 76),
    },
    # tekis: bitta rang, hech qanday tekstura yo'q — eng toza
    "tekis": {
        "bg": ASPHALT, "bg2": ASPHALT, "bg3": ASPHALT, "bg4": ASPHALT,
        "stripe": None, "stripe_a": 0, "glow": 0,
        "text": WHITE, "muted": (160, 168, 178), "row": (58, 63, 71),
        "line": (74, 80, 89), "band": None, "foot_line": (88, 95, 104),
    },
    # oq: yorug' fon, tepasida to'q chiziq (logo oq bo'lgani uchun)
    "oq": {
        "bg": (248, 249, 250), "bg2": (241, 243, 245), "bg3": (238, 240, 242),
        "bg4": (232, 235, 238),
        "stripe": (255, 255, 255), "stripe_a": 80, "glow": 0,
        "text": (17, 19, 22), "muted": (112, 120, 130), "row": (255, 255, 255),
        "line": (223, 226, 230), "band": ASPHALT, "foot_line": (214, 218, 223),
    },
}


def theme_of(settings: dict) -> dict:
    return THEMES.get((settings.get("card_theme") or "toq").strip().lower(), THEMES["toq"])


def _background_theme(height: int, t: dict) -> Image.Image:
    small = Image.new("RGB", (2, 2))
    small.putpixel((0, 0), t["bg"])
    small.putpixel((1, 0), t["bg2"])
    small.putpixel((0, 1), t["bg3"])
    small.putpixel((1, 1), t["bg4"])
    bg = small.resize((W, height), Image.Resampling.BICUBIC)

    if t["stripe"] and t["stripe_a"]:
        stripes = Image.new("L", (W, height), 0)
        sd = ImageDraw.Draw(stripes)
        for x in range(-height, W, 46):
            sd.line([(x, height), (x + height, 0)], fill=t["stripe_a"], width=12)
        bg = Image.composite(Image.new("RGB", (W, height), t["stripe"]),
                             bg, stripes.filter(ImageFilter.GaussianBlur(1)))

    if t["glow"]:
        glow = Image.new("RGB", (W, height), ORANGE)
        mask = Image.new("L", (W, height), 0)
        ImageDraw.Draw(mask).ellipse([-460, height - 380, 420, height + 380], fill=t["glow"])
        bg = Image.composite(glow, bg, mask.filter(ImageFilter.GaussianBlur(140)))

    if t["band"]:
        d = ImageDraw.Draw(bg)
        d.rectangle([0, 0, W, BAND_H], fill=t["band"])
        d.rectangle([0, BAND_H - 8, W, BAND_H], fill=ORANGE)
    return bg


def group_sections(items: list[dict]) -> list[tuple[str, list[dict]]]:
    """Kategoriya bo'yicha bo'limlar: bo'limlar alifbo, ichi tabiiy tartibda."""
    from pricebook import natural_key

    groups: dict[str, list] = {}
    for it in items:
        cat = (it.get("category") or "").strip() or "Boshqa"
        groups.setdefault(cat, []).append(it)
    for rows in groups.values():
        rows.sort(key=lambda r: natural_key(r.get("name") or ""))
    return sorted(groups.items(), key=lambda kv: kv[0].lower())


def split_pages(items: list[dict], per_page: int = MAX_ROWS) -> list[list[dict]]:
    pages, cur = [], []
    for _cat, rows in group_sections(items):
        for r in rows:
            if len(cur) >= per_page:
                pages.append(cur)
                cur = []
            cur.append(r)
    if cur:
        pages.append(cur)
    return pages or [[]]


def _draw_row(draw, item: dict, top: int, zebra: bool, t: dict) -> None:
    if zebra:
        draw.rounded_rectangle([PAD - 14, top, W - PAD + 14, top + ROW_H - 8],
                               radius=16, fill=t["row"])

    price = _money(item.get("price")) or "—"
    unit = (item.get("unit") or "").strip()
    f_price = font(35, True, price)
    f_cur = font(23, True, "so'm")
    f_unit = font(22, False, unit)

    price_w = _w(draw, price, f_price)
    cur_w = _w(draw, "so'm", f_cur) + 8
    unit_txt = f" / {unit}" if unit else ""
    unit_w = _w(draw, unit_txt, f_unit) if unit_txt else 0

    px = W - PAD - price_w - cur_w - unit_w - 10
    base = top + (ROW_H - 8) / 2

    name = (item.get("name") or "").strip()
    f_n = font(30, True, name)
    max_w = px - PAD - 40
    if _w(draw, name, f_n) > max_w:
        while name and _w(draw, name.rstrip() + "…", f_n) > max_w:
            name = name[:-1]
        name = name.rstrip() + "…"
    draw.text((PAD + 4, base), name, font=f_n, fill=t["text"], anchor="lm")

    draw.text((px, base), price, font=f_price, fill=ORANGE, anchor="lm")
    draw.text((px + price_w + 8, base + 5), "so'm", font=f_cur, fill=ORANGE, anchor="lm")
    if unit_txt:
        draw.text((px + price_w + cur_w + 6, base + 6), unit_txt, font=f_unit,
                  fill=t["muted"], anchor="lm")

    if not zebra:
        draw.line([(PAD - 14, top + ROW_H - 8), (W - PAD + 14, top + ROW_H - 8)],
                  fill=t["line"], width=1)


def make_list_card(title: str, items: list[dict], settings: dict,
                   page: int = 1, pages: int = 1) -> bytes:
    """Bitta brend narxlari — jadval ko'rinishidagi PNG."""
    t = theme_of(settings)
    shop = (settings.get("shop_name") or "dunyabunya").strip()
    phone = (settings.get("shop_phone") or "").strip()
    channel = (settings.get("channel_link") or "").strip()
    branches = settings.get("branch_names", "")
    sana = settings.get("sana", "")

    sections = group_sections(items)
    many = len(sections) > 1
    light = t["band"] is not None

    head_h = BAND_H + 14 if light else 250
    title_h = 150
    foot_h = 150
    body_h = len(items) * ROW_H + (len(sections) * SECTION_H if many else 0)
    height = max(940, head_h + title_h + body_h + foot_h)

    img = _background_theme(height, t)
    draw = ImageDraw.Draw(img)

    # --- logo + belgi (doim to'q fon ustida)
    logo_bottom = _draw_logo(img, draw, shop)
    badge = "NARXLAR" if pages == 1 else f"{page}/{pages}"
    f_badge = font(24, True, badge)
    bw = _w(draw, badge, f_badge) + 44
    draw.rounded_rectangle([W - PAD - bw, PAD + 18, W - PAD, PAD + 18 + 54],
                           radius=27, outline=ORANGE, width=3)
    draw.text((W - PAD - bw / 2, PAD + 18 + 27), badge, font=f_badge, fill=ORANGE, anchor="mm")

    # --- brend sarlavhasi
    y = (BAND_H + 40) if light else (logo_bottom + 52)
    lines, f_cat = _fit_lines(draw, title.upper(), W - 2 * PAD, 72, True, 2)
    for ln in lines:
        draw.text((PAD, y), ln, font=f_cat, fill=t["text"])
        y += int(f_cat.size * 1.18)
    draw.rounded_rectangle([PAD, y + 10, PAD + 120, y + 18], radius=4, fill=ORANGE)
    if sana:
        f_d = font(24, False, sana)
        draw.text((W - PAD, y - 34), f"{sana} holatiga", font=f_d, fill=t["muted"], anchor="ra")
    y += 56

    # --- bo'limlar va qatorlar
    row_i = 0
    for cat, rows in sections:
        if many:
            f_s = font(27, True, cat)
            draw.rounded_rectangle([PAD - 14, y + 6, PAD + _w(draw, cat.upper(), f_s) + 30,
                                    y + SECTION_H - 12], radius=10, fill=ORANGE)
            draw.text((PAD + 4, y + (SECTION_H - 6) / 2 - 3), cat.upper(),
                      font=f_s, fill=WHITE, anchor="lm")
            y += SECTION_H
            row_i = 0
        for it in rows:
            _draw_row(draw, it, y, row_i % 2 == 0, t)
            y += ROW_H
            row_i += 1

    # --- pastki qator
    fy = height - PAD - 62
    draw.line([(PAD, fy - 26), (W - PAD, fy - 26)], fill=t["foot_line"], width=2)
    left_text = branches or phone
    if left_text:
        draw.rounded_rectangle([PAD, fy + 2, PAD + 28, fy + 40], radius=8, fill=ORANGE)
        draw.rounded_rectangle([PAD + 8, fy + 10, PAD + 20, fy + 30], radius=4,
                               fill=t["bg4"] if not light else WHITE)
        f_f = font(26 if branches else 28, True, left_text)
        draw.text((PAD + 44, fy + 6), left_text, font=f_f, fill=t["text"])
    if channel:
        f_ch = font(26, False, channel)
        draw.text((W - PAD, fy + 8), channel, font=f_ch, fill=ORANGE, anchor="ra")

    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()
