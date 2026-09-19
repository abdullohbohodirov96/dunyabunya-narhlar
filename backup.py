"""Bazani Telegram kanaliga zaxiralash va qaytarish.

Nega kerak: Render'ning bepul planida doimiy disk yo'q — har qayta ishga
tushganda fayllar o'chadi. Shuning uchun baza yopiq kanalga fayl qilib
tashlanadi va o'sha xabar <b>pin</b> qilinadi. Bot qayta ishga tushganda
kanalning pin qilingan xabaridan bazani qaytarib oladi.

BACKUP_CHAT o'rnatilmagan bo'lsa — bu modul umuman ishlamaydi (zarari yo'q).
"""
import logging
import os

from aiogram import Bot
from aiogram.types import FSInputFile

from config import BACKUP_CHAT, DB_PATH

log = logging.getLogger("backup")


async def chat_id() -> str:
    """Zaxira kanali: /zaxirakanal bilan qo'yilgani, bo'lmasa BACKUP_CHAT env."""
    try:
        import db
        return (await db.get("backup_chat", "")).strip() or BACKUP_CHAT
    except Exception:
        return BACKUP_CHAT


def _size(path: str) -> int:
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


async def restore_if_needed(bot: Bot) -> str:
    """Baza fayli yo'q bo'lsa — kanaldan oxirgi zaxirani tortib oladi."""
    chat_to = BACKUP_CHAT          # start paytida baza hali ochilmagan
    if not chat_to:
        return "zaxira sozlanmagan"
    if _size(DB_PATH) > 0:
        return "mavjud baza ishlatiladi"

    try:
        chat = await bot.get_chat(chat_to)
        pinned = getattr(chat, "pinned_message", None)
        doc = getattr(pinned, "document", None) if pinned else None
        if doc is None:
            return "kanalda zaxira topilmadi"

        folder = os.path.dirname(DB_PATH)
        if folder:
            os.makedirs(folder, exist_ok=True)
        await bot.download(doc.file_id, destination=DB_PATH)
        log.info("Zaxira qaytarildi: %s (%s bayt)", doc.file_name, _size(DB_PATH))
        return f"zaxira qaytarildi ({_size(DB_PATH) // 1024} KB)"
    except Exception as e:
        log.warning("Zaxira qaytarilmadi: %s", e)
        return f"zaxira qaytarilmadi: {e}"


async def save(bot: Bot, reason: str = "") -> str:
    """Bazani kanalga yuboradi va pin qiladi (eskisini pin'dan chiqaradi)."""
    chat_to = await chat_id()
    if not chat_to:
        return "zaxira kanali sozlanmagan (/zaxirakanal)"
    if _size(DB_PATH) == 0:
        return "baza bo'sh"

    import db

    try:
        await db.conn().execute("PRAGMA wal_checkpoint(TRUNCATE)")
        await db.conn().commit()
    except Exception:
        pass

    try:
        caption = f"💾 {db.now():%d.%m.%Y %H:%M}" + (f" · {reason}" if reason else "")
        msg = await bot.send_document(
            chat_to,
            FSInputFile(DB_PATH, filename=f"bot_{db.now():%Y%m%d_%H%M}.db"),
            caption=caption,
            disable_notification=True,
        )
        await bot.unpin_all_chat_messages(chat_to)
        await bot.pin_chat_message(chat_to, msg.message_id, disable_notification=True)
        log.info("Zaxira saqlandi (%s KB)", _size(DB_PATH) // 1024)
        return f"✅ zaxira saqlandi ({_size(DB_PATH) // 1024} KB)"
    except Exception as e:
        log.warning("Zaxira saqlanmadi: %s", e)
        return f"❌ zaxira saqlanmadi: {e}"
