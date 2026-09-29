"""Tugmalar — botni yozmasdan, bosib boshqarish uchun."""
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup,
)

# ---------------------------------------------------------------- pastki menyu
MAIN = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📦 Navbat"), KeyboardButton(text="👁 Ko'rish")],
        [KeyboardButton(text="▶️ Hozir joylash"), KeyboardButton(text="📋 Prays")],
        [KeyboardButton(text="🗑 Tozalash"), KeyboardButton(text="⚙️ Sozlamalar")],
    ],
    resize_keyboard=True,
)

STAFF = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📦 Navbat"), KeyboardButton(text="👁 Ko'rish")],
        [KeyboardButton(text="📊 Statistika")],
    ],
    resize_keyboard=True,
)


# Barcha pastki tugmalar matni — "Tushunmadim" filtri shularni o'tkazib yuboradi.
LABELS = frozenset(
    b.text for kb in (MAIN, STAFF) for row in kb.keyboard for b in row
)


def _b(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def _mark(active: bool) -> str:
    return "✅ " if active else "▫️ "


# ---------------------------------------------------------------- sozlamalar
def settings_menu(s: dict) -> InlineKeyboardMarkup:
    paused = s.get("paused") == "1"
    return InlineKeyboardMarkup(inline_keyboard=[
        [_b("🖼 Post turi", "m:rejim"), _b("🏷 Guruhlash", "m:guruh")],
        [_b("🎨 Fon rangi", "m:fon"), _b("⏰ Post vaqtlari", "m:vaqt")],
        [_b("🏬 Filiallar", "m:filial"), _b("📞 Buyurtma raqami", "m:buyurtma")],
        [_b("🖼 Kategoriya rasmlari", "m:rasmlar"), _b("👥 Xodimlar", "m:xodim")],
        [_b("▶️ Davom ettirish" if paused else "⏸ To'xtatish",
            "act:davom" if paused else "act:pauza")],
        [_b("💾 Zaxira saqlash", "act:zaxira"), _b("📊 Statistika", "act:stat")],
    ])


def mode_menu(cur: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_b(_mark(cur == "rasm") + "Rasm (PNG jadval)", "set:rejim:rasm")],
        [_b(_mark(cur == "pdf") + "PDF fayl", "set:rejim:pdf")],
        [_b(_mark(cur == "mahsulot") + "Bitta mahsulot kartochkasi", "set:rejim:mahsulot")],
        [_b("⬅️ Orqaga", "m:asosiy")],
    ])


def group_menu(cur: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_b(_mark(cur == "brend") + "Brend bo'yicha (KNAUF)", "set:guruh:brend")],
        [_b(_mark(cur == "kategoriya") + "Kategoriya bo'yicha (GIPSOKARTON)",
            "set:guruh:kategoriya")],
        [_b("⬅️ Orqaga", "m:asosiy")],
    ])


def theme_menu(cur: str) -> InlineKeyboardMarkup:
    names = [("oq", "⬜️ Oq"), ("toq", "🌑 To'q"), ("qora", "⚫️ Qora"), ("tekis", "▪️ Tekis")]
    rows = [[_b(_mark(cur == k) + n, f"set:fon:{k}")] for k, n in names]
    rows.append([_b("⬅️ Orqaga", "m:asosiy")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def times_menu(cur: str) -> InlineKeyboardMarkup:
    presets = [
        ("09:00,11:30,14:00,16:30,19:00", "Kuniga 5 ta"),
        ("09:00,14:00,18:00", "Kuniga 3 ta"),
        ("10:00,16:00", "Kuniga 2 ta"),
        ("11:00", "Kuniga 1 ta"),
    ]
    rows = [[_b(_mark(cur == v) + f"{n}  ({v})", f"set:vaqt:{v}")] for v, n in presets]
    rows.append([_b("⬅️ Orqaga", "m:asosiy")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ---------------------------------------------------------------- tozalash
def wipe_menu(total: int, groups: list[str]) -> InlineKeyboardMarkup:
    rows = [[_b(f"🗑 Hammasini o'chirish ({total} ta)", "del:all")]]
    for g in groups[:8]:
        rows.append([_b(f"🗑 {g}", f"del:g:{g}")])
    rows.append([_b("❌ Yopish", "act:yop")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm(yes_data: str, text: str = "Ha, o'chirilsin") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_b(f"✅ {text}", yes_data), _b("❌ Bekor", "act:yop")],
    ])


# ---------------------------------------------------------------- prays
def pricebook_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_b("📄 PDF", "prays:pdf"), _b("📊 Excel", "prays:excel")],
        [_b("📢 Kanalga joylash", "prays:kanal")],
        [_b("❌ Yopish", "act:yop")],
    ])


def after_preview() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [_b("📢 Shuni hoziroq joylash", "act:hozir")],
        [_b("🎨 Fonni o'zgartirish", "m:fon"), _b("🏷 Guruhlash", "m:guruh")],
    ])
