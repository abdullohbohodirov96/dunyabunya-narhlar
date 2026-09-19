"""Kanalga post joylash, mas'ulga eslatma va kunlik hisobot."""
import io
import logging

from aiogram import Bot
from aiogram.types import BufferedInputFile, InputMediaPhoto

import backup
import cardmaker
import db
import formatter
import pricebook
from config import ADMIN_IDS, MAX_CAPTION

log = logging.getLogger("poster")


async def _notify(bot: Bot, chat_ids, text: str) -> None:
    for cid in chat_ids:
        if not cid:
            continue
        try:
            await bot.send_message(cid, text, parse_mode="HTML", disable_web_page_preview=True)
        except Exception as e:  # odam botni bloklagan bo'lishi mumkin
            log.warning("xabar yuborilmadi (%s): %s", cid, e)


async def _download(bot: Bot, file_id: str) -> bytes | None:
    if not file_id:
        return None
    try:
        buf = io.BytesIO()
        await bot.download(file_id, destination=buf)
        return buf.getvalue()
    except Exception as e:
        log.warning("rasm yuklanmadi: %s", e)
        return None


async def build_post(bot: Bot, product: dict, settings: dict):
    """(rasm_bayt, sarlavha_matni) qaytaradi."""
    photo = await _download(bot, product.get("photo_file_id", ""))
    caption = formatter.render_product(product, settings)
    if len(caption) > MAX_CAPTION:
        caption = caption[: MAX_CAPTION - 1].rsplit("\n", 1)[0]

    if settings.get("card_design", "1") == "1":
        try:
            image = cardmaker.make_card(product, settings, photo)
            return image, caption
        except Exception as e:
            log.exception("kartochka yasalmadi, oddiy rasm yuboriladi: %s", e)
    return photo, caption


async def post_product(bot: Bot, product: dict, settings: dict, chat_id: str):
    image, caption = await build_post(bot, product, settings)
    if image:
        file = BufferedInputFile(image, filename=f"dunyabunya_{product['id']}.jpg")
        return await bot.send_photo(chat_id, file, caption=caption, parse_mode="HTML")
    return await bot.send_message(chat_id, caption, parse_mode="HTML", disable_web_page_preview=True)


async def post_next(bot: Bot, manual_by: int | None = None) -> str:
    """Navbatdagi keyingi mahsulotni kanalga joylaydi. Natija matni qaytadi."""
    settings = await db.all_settings()

    if settings.get("paused") == "1" and manual_by is None:
        return "⏸ Bot pauzada — post qilinmadi."

    channel = (settings.get("channel_id") or "").strip()
    if not channel:
        await _notify(bot, ADMIN_IDS, "⚠️ Kanal hali ulanmagan. /kanal buyrug'i bilan ulang.")
        return "Kanal ulanmagan."

    if settings.get("post_mode", "pdf") in ("pdf", "rasm", "prays"):
        return await post_category(bot, settings, channel)

    product = await db.pick_next()
    if product is None:
        await alert_empty(bot, force=True)
        return "Navbat bo'sh."

    p = dict(product)
    try:
        msg = await post_product(bot, p, settings, channel)
    except Exception as e:
        await db.log_error(p["id"], p["name"], str(e))
        await _notify(bot, ADMIN_IDS, f"❌ Post joylanmadi: <b>{p['name']}</b>\n<code>{e}</code>")
        return f"Xato: {e}"

    await db.mark_posted(p["id"], p["name"], msg.message_id)

    done = len(await db.posts_today())
    left = await db.ready_count()
    plan = len([t for t in (settings.get("post_times") or "").split(",") if t.strip()])
    await _notify(
        bot, ADMIN_IDS,
        f"✅ <b>{p['name']}</b> kanalga joylandi\n"
        f"📊 Bugun: {done}/{plan} ta  ·  Navbatda: {left} ta mahsulot",
    )
    await alert_empty(bot)
    return f"✅ {p['name']}"


async def build_category_cards(category: str, items: list[dict], settings: dict) -> list[bytes]:
    """Kategoriya narxlarini bir nechta kartochkaga bo'lib chizadi."""
    per = cardmaker.MAX_ROWS
    chunks = [items[i:i + per] for i in range(0, len(items), per)][:10]
    total = len(chunks)
    s = dict(settings)
    s.setdefault("sana", f"{db.now():%d.%m.%Y}")
    return [cardmaker.make_list_card(category, chunk, s, i + 1, total)
            for i, chunk in enumerate(chunks)]


async def post_category(bot: Bot, settings: dict, channel: str) -> str:
    """Navbatdagi kategoriya narxlarini kanalga joylaydi."""
    picked = await db.pick_next_category()
    if picked is None:
        await alert_empty(bot, force=True)
        return "Bazada narxli mahsulot yo'q."

    category, items = picked
    caption = formatter.render_product(
        {"name": category.upper(), "category": category}, settings
    )
    if len(caption) > MAX_CAPTION:
        caption = caption[: MAX_CAPTION - 1]

    mode = settings.get("post_mode", "pdf")
    try:
        if mode in ("pdf", "prays"):
            s2 = dict(settings)
            s2["sana"] = f"{db.now():%d.%m.%Y}"
            data = pricebook.make_pdf(items, s2)
            safe = "".join(ch if ch.isalnum() else "_" for ch in category).strip("_")
            fname = f"dunyabunya_{safe}_{db.now():%Y-%m-%d}.pdf"
            msg = await bot.send_document(
                channel, BufferedInputFile(data, filename=fname),
                caption=caption, parse_mode="HTML",
            )
            await _after_category(bot, settings, category, items, msg)
            return f"✅ {category} — {len(items)} ta mahsulot (PDF)"

        cards = await build_category_cards(category, items, settings)
        files = [BufferedInputFile(c, filename=f"{category}_{i + 1}.jpg")
                 for i, c in enumerate(cards)]
        if len(files) == 1:
            msg = await bot.send_photo(channel, files[0], caption=caption, parse_mode="HTML")
        else:
            media = [InputMediaPhoto(media=f) for f in files]
            media[0].caption = caption
            media[0].parse_mode = "HTML"
            sent = await bot.send_media_group(channel, media)
            msg = sent[0]
    except Exception as e:
        await db.log_error(0, category, str(e))
        await _notify(bot, ADMIN_IDS,
                      f"❌ Prays joylanmadi: <b>{category}</b>\n<code>{e}</code>")
        return f"Xato: {e}"

    await _after_category(bot, settings, category, items, msg)
    return f"✅ {category} — {len(items)} ta mahsulot"


async def _after_category(bot: Bot, settings: dict, category: str, items: list, msg) -> None:
    await db.mark_category_posted(category)
    await db.conn().execute(
        "INSERT INTO post_log (product_id, name, posted_at, message_id, ok) VALUES (0, ?, ?, ?, 1)",
        (f"{category} ({len(items)} ta)", db.iso(), msg.message_id),
    )
    await db.conn().commit()

    done = len(await db.posts_today())
    plan = len([t for t in (settings.get("post_times") or "").split(",") if t.strip()])
    await _notify(
        bot, ADMIN_IDS,
        f"✅ <b>{category}</b> narxlari kanalga joylandi ({len(items)} ta mahsulot)\n"
        f"📊 Bugun: {done}/{plan} ta  ·  Kategoriyalar: {len(await db.categories())} ta",
    )
    await alert_empty(bot)


async def build_pricebook(fmt: str = "pdf") -> tuple[bytes, str, int]:
    """To'liq narxlar ro'yxati fayli. (bayt, fayl_nomi, mahsulot_soni)"""
    settings = await db.all_settings()
    async with db.conn().execute(
        "SELECT * FROM products WHERE active = 1 AND price <> '' "
        "ORDER BY category, brand, name"
    ) as cur:
        rows = [dict(r) for r in await cur.fetchall()]

    stamp = f"{db.now():%Y-%m-%d}"
    if fmt == "xlsx":
        return pricebook.make_xlsx(rows, settings), f"dunyabunya_narxlar_{stamp}.xlsx", len(rows)
    return pricebook.make_pdf(rows, settings), f"dunyabunya_narxlar_{stamp}.pdf", len(rows)


async def post_pricebook(bot: Bot, chat_id: str | None = None) -> str:
    """Brendlangan prays-listni kanalga (yoki berilgan chatga) joylaydi."""
    settings = await db.all_settings()
    target = chat_id or (settings.get("channel_id") or "").strip()
    if not target:
        return "Kanal ulanmagan."

    data, filename, count = await build_pricebook("pdf")
    if not count:
        return "Bazada narxli mahsulot yo'q."

    caption = (
        f"📋 <b>{settings.get('shop_name', 'dunyabunya')} — to'liq narxlar ro'yxati</b>\n"
        f"🗓 {db.now():%d.%m.%Y}  ·  {count} ta mahsulot\n\n"
        f"📞 {settings.get('shop_phone', '')}"
    )
    await bot.send_document(
        target, BufferedInputFile(data, filename=filename), caption=caption, parse_mode="HTML"
    )
    return f"✅ Prays-list joylandi ({count} ta mahsulot)."


# ---------------------------------------------------------------- eslatma
def _hm(s: str, default):
    try:
        h, m = s.strip().split(":")
        return int(h), int(m)
    except Exception:
        return default


async def _is_quiet(settings: dict) -> bool:
    now = db.now()
    fh, fm = _hm(settings.get("quiet_from", "21:30"), (21, 30))
    th, tm = _hm(settings.get("quiet_to", "08:00"), (8, 0))
    cur = now.hour * 60 + now.minute
    start, end = fh * 60 + fm, th * 60 + tm
    return cur >= start or cur < end if start > end else start <= cur < end


async def alert_empty(bot: Bot, force: bool = False) -> None:
    """Narx tugasa yoki eskirsa — mas'ulga va adminlarga eslatma."""
    settings = await db.all_settings()
    prays = settings.get("post_mode", "pdf") != "mahsulot"
    left = await db.queue_left()
    # prays rejimida kategoriyalar aylanadi — faqat umuman narx qolmasa muammo.
    # mahsulot rejimida esa har mahsulot bir marta chiqadi, shuning uchun zaxira kerak.
    threshold = 0 if prays else int(settings.get("low_stock", "5") or 5)
    stale_days = int(settings.get("stale_days", "7") or 7)
    age = await db.price_age_days()
    stale = age is not None and age >= stale_days

    if left > threshold and not stale and not force:
        await db.set("alert_active", "0")
        return
    if await _is_quiet(settings) and not force:
        return

    manager = (settings.get("manager_id") or "").strip()
    no_photo = await db.no_photo_count()
    no_price = await db.no_price_count()

    unit_word = "kategoriya" if prays else "mahsulot"
    if left == 0:
        head = "🔴 <b>NAVBAT BO'SH!</b> Kanalga joylash uchun narx qolmadi."
    elif stale:
        head = (f"🟠 <b>Narxlar {age} kundan beri yangilanmadi.</b> "
                "Kanalga eski narx chiqib ketmasin.")
    else:
        head = f"🟠 <b>Diqqat:</b> navbatda atigi <b>{left}</b> ta {unit_word} qoldi."

    extra = []
    if no_price:
        extra.append(f"• {no_price} ta mahsulotda narx yo'q")
    if no_photo:
        extra.append(f"• {no_photo} ta mahsulotda rasm yo'q")

    text = (
        f"{head}\n\n"
        "Iltimos yangi narxlarni yuboring:\n"
        "1️⃣ Excel fayl (nomi + narxi + kategoriya + brend)\n"
        "2️⃣ yoki rasm + tagiga mahsulot nomi va narxi\n"
        + ("\n" + "\n".join(extra) if extra else "")
        + f"\n\n⏰ Har {settings.get('remind_every_min', '5')} daqiqada eslatib turaman."
    )

    targets = list(ADMIN_IDS)
    if manager and manager not in [str(a) for a in ADMIN_IDS]:
        targets.append(manager)
    await _notify(bot, targets, text)
    await db.set("alert_active", "1")


# ---------------------------------------------------------------- hisobot
async def daily_report(bot: Bot) -> None:
    settings = await db.all_settings()
    posts = await db.posts_today()
    plan = len([t for t in (settings.get("post_times") or "").split(",") if t.strip()])
    left = await db.queue_left()

    lines = [f"🗓 <b>Kunlik hisobot — {db.now():%d.%m.%Y}</b>", ""]
    if posts:
        for i, r in enumerate(posts, 1):
            t = db.parse_iso(r["posted_at"])
            lines.append(f"✅ {i}. {r['name']} — {t:%H:%M}" if t else f"✅ {i}. {r['name']}")
    else:
        lines.append("❌ Bugun hech narsa joylanmadi.")

    lines += ["", f"📊 Reja: {plan} ta · Bajarildi: {len(posts)} ta"]
    if len(posts) < plan:
        lines.append(f"⚠️ {plan - len(posts)} ta post qolib ketdi.")
    prays = settings.get("post_mode", "pdf") != "mahsulot"
    lines.append(f"📦 Navbatda: {left} ta " + ("kategoriya" if prays else "mahsulot"))
    if left == 0:
        lines.append("\n🔴 Narx qolmadi — yangi ro'yxat yuboring!")
    elif not prays and left < plan:
        lines.append("\n🔴 Ertaga uchun yetmaydi — yangi mahsulotlar yuboring!")
    age = await db.price_age_days()
    if age is not None and age >= int(settings.get("stale_days", "7") or 7):
        lines.append(f"⚠️ Narxlar {age} kundan beri yangilanmadi.")

    targets = list(ADMIN_IDS)
    manager = (settings.get("manager_id") or "").strip()
    if manager and manager not in [str(a) for a in ADMIN_IDS]:
        targets.append(manager)
    await _notify(bot, targets, "\n".join(lines))
    await backup.save(bot, "kunlik")
