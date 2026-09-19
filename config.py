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
    #   "pdf"      = kategoriya narxlari PDF fayl (asosiy)
    #   "rasm"     = kategoriya narxlari rasm-jadval
    #   "mahsulot" = bitta mahsulot kartochkasi
    "post_mode": "pdf",
    # narxlar shuncha kundan beri yangilanmasa — mas'ulga eslatma
    "stale_days": "7",
    # 1 = brend dizaynidagi kartochka yasalsin, 0 = oddiy rasm yuborilsin
    "card_design": "1",
    "channel_id": CHANNEL_ID,
    "manager_id": MANAGER_ID,
    "shop_phone": "+998(91)785-00-90",
    "shop_name": "dunyabunya",
    "channel_link": "@Dunyabunya_prays",
    # telefon raqami shu havolaga bog'lanadi (bo'sh qoldirilsa — oddiy matn)
    "contact_link": "https://t.me/db_Community_manager",
    "template": (
        "💰 {dokon} \"{nom}\" narxlari\n"
        "\n"
        "📍 {dokon} barcha filiallarida\n"
        "\n"
        "{telefon_link}"
    ),
}

MAX_CAPTION = 1024
