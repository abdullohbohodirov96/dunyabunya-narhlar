"""Konfiguratsiya — hammasi environment variable orqali."""
import os
from zoneinfo import ZoneInfo

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# Admin(lar) — botni boshqaradigan odamlar (Telegram raqamli ID)
ADMIN_IDS = [
    int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x.strip().lstrip("-").isdigit()
]

# Kanal: @username yoki -100... ID. Bo'sh qoldirilsa /kanal buyrug'i bilan o'rnatiladi.
CHANNEL_ID = os.getenv("CHANNEL_ID", "").strip()

# Mas'ul xodim — mahsulot tugaganda shu odamga yoziladi
MANAGER_ID = os.getenv("MANAGER_ID", "").strip()

# Ma'lumotlar bazasi fayli. Render'da Disk /data ga ulansa — /data/bot.db
DB_PATH = os.getenv("DB_PATH", "/data/bot.db")

# Zaxira kanali (yopiq kanal, bot unda admin). Diski yo'q planlarda majburiy:
# baza shu kanalga fayl qilib tashlanadi va pin qilinadi.
BACKUP_CHAT = os.getenv("BACKUP_CHAT", "").strip()

# Render web service o'z manzilini shu o'zgaruvchida beradi.
# Bepul planda servis 15 daqiqa jimlikdan keyin uxlaydi — bot o'ziga
# har 10 daqiqada so'rov yuborib, uyg'oq turadi (tashqi pinger kerak emas).
SELF_URL = (os.getenv("RENDER_EXTERNAL_URL", "") or os.getenv("SELF_URL", "")).strip().rstrip("/")

TZ_NAME = os.getenv("TZ", "Asia/Tashkent")
TZ = ZoneInfo(TZ_NAME)

# Standart sozlamalar (botning ichida /sozlama orqali o'zgaradi)
DEFAULTS = {
    "post_times": "09:00,11:30,14:00,16:30,19:00",
    "paused": "0",
    # navbatda shuncha yangi mahsulotdan kam qolsa — ogohlantirish
    "low_stock": "5",
    # bir mahsulot qayta chiqishidan oldin necha kun kutsin
    "cooldown_days": "10",
    # eslatma necha daqiqada takrorlansin
    "remind_every_min": "5",
    # eslatma faqat shu soatlar orasida yuborilsin (tunda bezovta qilmasin)
    "quiet_from": "21:30",
    "quiet_to": "08:00",
    # kunlik hisobot vaqti
    "report_at": "21:00",
    # haftalik to'liq prays-listni kanalga tashlash: "" = o'chiq, "mon 10:00" kabi
    "pricebook_at": "",
    # post turi:
    #   "rasm"     = brend narxlari rasm-jadval, PNG (asosiy)
    #   "pdf"      = o'sha jadval PDF fayl bo'lib
    #   "mahsulot" = bitta mahsulot kartochkasi
    "post_mode": "rasm",
    # post qanday guruhlansin:
    #   "brend"      = butun brend bitta post (KNAUF — ichida gipsokarton,
    #                  rotband, profil bo'limlari bilan)
    #   "kategoriya" = butun kategoriya bitta post (GIPSOKARTON)
    "group_by": "brend",
    # narxlar shuncha kundan beri yangilanmasa — mas'ulga eslatma
    "stale_days": "7",
    # rasm foni: toq (mokriy asfalt) / qora / tekis / oq
    "card_theme": "oq",
    # 1 = brend dizaynidagi kartochka yasalsin, 0 = oddiy rasm yuborilsin
    "card_design": "1",
    # mahsulot qo'sha oladigan xodimlar (Telegram ID, vergul bilan)
    "staff": "",
    "channel_id": CHANNEL_ID,
    "manager_id": MANAGER_ID,
    "shop_phone": "+998(91)785-00-90",
    # rasm ichida chiqadigan buyurtma raqami
    "order_phone": "+998 (91) 785-00-90",
    "shop_name": "dunyabunya",
    "channel_link": "@Dunyabunya_prays",
    # Filiallar: "Nomi|telefon" juftliklari, nuqtali vergul bilan ajratiladi
    "branches": (
        "Shiribom|+998(77)756-39-99;"
        "Hasanboy|+998(97)714-08-44;"
        "Qorasaroy|+998(91)785-00-90"
    ),
    # telefon raqami shu havolaga bog'lanadi (bo'sh qoldirilsa — oddiy matn)
    "contact_link": "https://t.me/db_Community_manager",
    "template": (
        "💰 {dokon} \"{nom}\" narxlari\n"
        "\n"
        "🛒 Xarid qilish uchun:\n"
        "{filiallar}"
    ),
}

# Avvalgi versiyalardagi standart shablonlar. Bazada shulardan biri
# turgan bo'lsa — foydalanuvchi o'zgartirmagan degani, migratsiya yangilaydi.
LEGACY_TEMPLATES = [
    (
        "🏗 <b>{nom}</b>\n"
        "{brend_qatori}"
        "\n"
        "💰 Narx: <b>{narx} so'm</b>{birlik}\n"
        "{eski_narx_qatori}"
        "{izoh_qatori}"
        "\n"
        "📦 {kategoriya}\n"
        "📞 Buyurtma: {telefon}\n"
        "🏬 {dokon} — {kanal}"
    ),
    (
        "💰 {dokon} \"{nom}\" narxlari\n"
        "\n"
        "📍 {dokon} barcha filiallarida\n"
        "\n"
        "{telefon_link}"
    ),
]

MAX_CAPTION = 1024
