"""dunyabunya — narxlar kanali uchun avtomatik post boti.

Ishga tushirish:  python bot.py
"""
import asyncio
import logging
import os

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

import backup
import db
import handlers
import scheduler
from config import ADMIN_IDS, BACKUP_CHAT, BOT_TOKEN, SELF_URL, TZ_NAME

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(name)s — %(message)s",
)
logging.getLogger("aiogram.event").setLevel(logging.WARNING)
log = logging.getLogger("bot")


async def health_server() -> None:
    """Render Web Service rejimida ishlatilsa — oddiy health endpoint."""
    port = os.getenv("PORT")
    if not port:
        return
    from aiohttp import web

    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text="dunyabunya bot ishlayapti ✅"))
    app.router.add_get("/health", lambda r: web.json_response({"ok": True}))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", int(port)).start()
    log.info("Health server: 0.0.0.0:%s", port)
    if SELF_URL:
        log.info("Uxlab qolmaslik uchun har 10 daqiqada %s/health chaqiriladi", SELF_URL)
    else:
        log.warning("RENDER_EXTERNAL_URL yo'q — bepul planda servis uxlab qolishi mumkin")


async def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("❌ BOT_TOKEN o'zgaruvchisi o'rnatilmagan (@BotFather dan oling).")

    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    # diski yo'q planlarda baza zaxira kanalidan qaytariladi
    restored = await backup.restore_if_needed(bot)
    log.info("Zaxira: %s", restored)

    await db.init()
    log.info("Baza tayyor. Vaqt zonasi: %s", TZ_NAME)
    dp = Dispatcher()
    dp.include_router(handlers.router)

    scheduler.start(bot)
    times = await scheduler.reload_jobs()
    log.info("Post jadvali: %s", times)

    me = await bot.get_me()
    log.info("Bot ishga tushdi: @%s", me.username)

    for admin in ADMIN_IDS:
        try:
            await bot.send_message(
                admin,
                "🟢 <b>Bot ishga tushdi</b>\n"
                f"⏰ Jadval: <code>{await db.get('post_times')}</code>\n"
                f"📦 Navbatda: {await db.queue_left()} ta"
                + (f"\n💾 {restored}" if BACKUP_CHAT else ""),
            )
        except Exception:
            pass

    await health_server()
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await db.close()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit) as e:
        log.info("To'xtatildi: %s", e)
