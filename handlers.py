"""Bot buyruqlari va xabar oqimi."""
import io
import logging
import os

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import (
    BufferedInputFile, FSInputFile, KeyboardButton, Message, ReplyKeyboardMarkup,
)

import backup
import cardmaker
import db
import parsing
import poster
import pricelist
import scheduler
from config import ADMIN_IDS, DB_PATH

log = logging.getLogger("handlers")
router = Router()

MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📦 Navbat"), KeyboardButton(text="📊 Statistika")],
        [KeyboardButton(text="▶️ Hozir joylash"), KeyboardButton(text="⚙️ Sozlamalar")],
    ],
    resize_keyboard=True,
)

HELP = """<b>🏗 dunyabunya — narxlar boti</b>

<b>Mahsulot qo'shish</b>
• 📄 Excel/CSV faylni shunchaki yuboring — barcha qatorlar navbatga tushadi
• 🖼 Rasm yuboring, tagiga yozing:
   <code>Sement M-400 — 52000 so'm/qop</code>
   (nomi Excel'da bor bo'lsa, rasm o'sha mahsulotga ulanadi)

<b>Asosiy buyruqlar</b>
/navbat — navbatda nechta mahsulot bor
/royxat — navbatdagi ro'yxat (ID bilan)
/korish — keyingi post qanday chiqishini ko'rish
/ochirish 12 — navbatdan o'chirish
/hozir — hoziroq keyingi postni kanalga joylash

<b>Sozlash</b>
/kanal — kanalni ulash (kanaldan post forward qiling)
/masul 123456789 — mas'ul xodimni belgilash
/vaqt 09:00,11:30,14:00,16:30,19:00 — post vaqtlari
/dokon dunyabunya | +998(91)785-00-90 | @kanal
/logo — logo yuklash (keyingi rasmni logo qilib oladi)
/rejim — post turi (pdf / rasm / mahsulot)\n/dizayn — brend kartochkani yoqish/o'chirish
/shablon — post matni shabloni\n/aloqa — raqam bog'lanadigan havola
/pauza · /davom — to'xtatish / davom ettirish\n/zaxirakanal — zaxira kanalini ulash\n/zaxira — bazani hoziroq saqlash
/statistika · /eksport · /id
"""


def is_admin(uid: int) -> bool:
    return not ADMIN_IDS or uid in ADMIN_IDS


async def deny(msg: Message) -> bool:
    if is_admin(msg.from_user.id):
        return False
    await msg.answer("⛔️ Bu bot faqat dunyabunya xodimlari uchun.")
    return True


# ---------------------------------------------------------------- start
@router.message(Command("start", "yordam", "help"))
async def cmd_start(msg: Message):
    if not ADMIN_IDS:
        await msg.answer(
            "⚠️ <b>Bot hali sozlanmagan.</b>\n\n"
            f"Sizning Telegram ID: <code>{msg.from_user.id}</code>\n"
            "Shu raqamni Render'dagi <code>ADMIN_IDS</code> o'zgaruvchisiga yozing.",
        )
        return
    if await deny(msg):
        return
    await msg.answer(HELP, reply_markup=MENU)


@router.message(Command("id"))
async def cmd_id(msg: Message):
    await msg.answer(
        f"🆔 Sizning ID: <code>{msg.from_user.id}</code>\n"
        f"Chat ID: <code>{msg.chat.id}</code>"
    )


# ---------------------------------------------------------------- kanal
@router.message(Command("kanal"))
async def cmd_channel(msg: Message, command: CommandObject):
    if await deny(msg):
        return
    target = (command.args or "").strip()
    if not target:
        cur = await db.get("channel_id")
        await msg.answer(
            f"Hozirgi kanal: <code>{cur or 'ulanmagan'}</code>\n\n"
            "Ulash uchun:\n"
            "• kanaldan istalgan postni shu yerga <b>forward</b> qiling, yoki\n"
            "• <code>/kanal @kanal_nomi</code> deb yozing\n\n"
            "⚠️ Bot kanalga <b>admin</b> qilib qo'shilgan bo'lishi shart."
        )
        return
    await _set_channel(msg, target, target if target.startswith("@") else "")


@router.message(F.forward_origin)
async def forwarded(msg: Message):
    """Forward qilingan post — narxlar kanalini yoki zaxira kanalini ulaymiz."""
    if await deny(msg):
        return
    chat = getattr(msg.forward_origin, "chat", None)
    if chat is None:
        await msg.answer("Bu post kanaldan emas. Kanaldagi postni forward qiling.")
        return

    draft = await db.next_draft(msg.from_user.id)
    if draft and draft["need"] == "backup":
        await db.drop_draft(draft["id"])
        try:
            probe = await msg.bot.send_message(chat.id, "💾 Zaxira kanali tekshirilmoqda…")
            await msg.bot.pin_chat_message(chat.id, probe.message_id, disable_notification=True)
            await msg.bot.unpin_all_chat_messages(chat.id)
            await msg.bot.delete_message(chat.id, probe.message_id)
        except Exception as e:
            await msg.answer(
                f"❌ Bu kanalda ishlay olmadim.\n<code>{e}</code>\n\n"
                "Botni kanalga admin qiling — <b>post yuborish</b> va "
                "<b>pin qilish</b> huquqi bilan."
            )
            return
        await db.set("backup_chat", str(chat.id))
        result = await backup.save(msg.bot, "sozlash")
        await msg.answer(
            f"✅ Zaxira kanali ulandi: <code>{chat.id}</code>\n{result}\n\n"
            f"Render'ga ham yozib qo'ying: <code>BACKUP_CHAT={chat.id}</code>"
        )
        return

    await _set_channel(msg, str(chat.id), f"@{chat.username}" if chat.username else (chat.title or ""))


async def _set_channel(msg: Message, chat_id: str, link: str):
    try:
        probe = await msg.bot.send_message(chat_id, "✅ Ulanish tekshirilmoqda…")
        await msg.bot.delete_message(chat_id, probe.message_id)
    except Exception as e:
        await msg.answer(
            f"❌ Kanalga yoza olmadim.\n<code>{e}</code>\n\n"
            "Botni kanalga admin qilib qo'shing va qayta urinib ko'ring."
        )
        return
    await db.set("channel_id", chat_id)
    if link:
        await db.set("channel_link", link)
    await msg.answer(f"✅ Kanal ulandi: <code>{chat_id}</code>{(' · ' + link) if link else ''}")


# ---------------------------------------------------------------- sozlamalar
@router.message(Command("masul"))
async def cmd_manager(msg: Message, command: CommandObject):
    if await deny(msg):
        return
    arg = (command.args or "").strip()
    if not arg:
        cur = await db.get("manager_id")
        await msg.answer(
            f"Mas'ul: <code>{cur or 'belgilanmagan'}</code>\n\n"
            "Belgilash: <code>/masul 123456789</code>\n"
            "Uning ID sini bilish uchun u botga <code>/id</code> deb yozsin."
        )
        return
    await db.set("manager_id", arg.lstrip("@"))
    await msg.answer(f"✅ Mas'ul belgilandi: <code>{arg}</code>\nMahsulot tugasa unga yoziladi.")


@router.message(Command("vaqt"))
async def cmd_times(msg: Message, command: CommandObject):
    if await deny(msg):
        return
    arg = (command.args or "").strip()
    if not arg:
        cur = await db.get("post_times")
        nxt = scheduler.next_runs()
        await msg.answer(
            f"⏰ Post vaqtlari: <code>{cur}</code>\n"
            + ("Keyingilari: " + ", ".join(nxt) if nxt else "")
            + "\n\nO'zgartirish: <code>/vaqt 09:00,13:00,18:00</code>"
        )
        return
    times = scheduler.parse_times(arg)
    if not times:
        await msg.answer("❌ Format xato. Misol: <code>/vaqt 09:00,13:00,18:00</code>")
        return
    await db.set("post_times", ",".join(f"{h:02d}:{m:02d}" for h, m in times))
    await scheduler.reload_jobs()
    await msg.answer(f"✅ Yangi jadval: <code>{await db.get('post_times')}</code> (kuniga {len(times)} ta post)")


@router.message(Command("dokon"))
async def cmd_shop(msg: Message, command: CommandObject):
    if await deny(msg):
        return
    arg = (command.args or "").strip()
    if not arg:
        s = await db.all_settings()
        await msg.answer(
            f"🏬 Do'kon: <b>{s['shop_name']}</b>\n📞 {s['shop_phone']}\n"
            f"🔗 {s['channel_link']}\n💬 Aloqa havolasi: {s['contact_link'] or '—'}\n\n"
            "O'zgartirish:\n<code>/dokon dunyabunya | +998(91)785-00-90 | @Dunyabunya_prays</code>"
        )
        return
    parts = [p.strip() for p in arg.split("|")]
    if parts and parts[0]:
        await db.set("shop_name", parts[0])
    if len(parts) > 1 and parts[1]:
        await db.set("shop_phone", parts[1])
    if len(parts) > 2 and parts[2]:
        await db.set("channel_link", parts[2])
    s = await db.all_settings()
    await msg.answer(f"✅ Saqlandi:\n🏬 {s['shop_name']}\n📞 {s['shop_phone']}\n🔗 {s['channel_link']}")


@router.message(Command("aloqa"))
async def cmd_contact(msg: Message, command: CommandObject):
    """Postdagi telefon raqami qaysi havolaga bog'lanishi."""
    if await deny(msg):
        return
    arg = (command.args or "").strip()
    if not arg:
        cur = await db.get("contact_link")
        await msg.answer(
            f"💬 Raqam bog'langan havola: <code>{cur or 'yo‘q (oddiy matn)'}</code>\n\n"
            "O'zgartirish: <code>/aloqa https://t.me/db_Community_manager</code>\n"
            "O'chirish: <code>/aloqa yoq</code>"
        )
        return
    if arg.lower() in ("yoq", "off", "o'chir", "ochir"):
        await db.set("contact_link", "")
        await msg.answer("✅ Raqam endi oddiy matn bo'lib chiqadi.")
        return
    await db.set("contact_link", arg)
    await msg.answer(f"✅ Raqam shu havolaga bog'landi:\n{arg}")


@router.message(Command("rejim"))
async def cmd_mode(msg: Message, command: CommandObject):
    """Post turi: pdf / rasm / mahsulot."""
    if await deny(msg):
        return
    arg = (command.args or "").strip().lower()
    names = {
        "pdf": "📄 Kategoriya narxlari — PDF fayl",
        "rasm": "🖼 Kategoriya narxlari — rasm-jadval",
        "mahsulot": "📦 Bitta mahsulot kartochkasi",
    }
    if arg not in names:
        cur = await db.get("post_mode", "pdf")
        cur = "pdf" if cur == "prays" else cur
        await msg.answer(
            f"Hozirgi rejim: <b>{names.get(cur, cur)}</b>\n\n"
            "O'zgartirish:\n"
            "<code>/rejim pdf</code> — har post bitta kategoriya narxlari, PDF fayl\n"
            "<code>/rejim rasm</code> — o'sha narxlar rasm-jadval ko'rinishida\n"
            "<code>/rejim mahsulot</code> — har post bitta mahsulot kartochkasi"
        )
        return
    await db.set("post_mode", arg)
    await msg.answer(f"✅ Rejim: <b>{names[arg]}</b>\n\nKo'rish: <code>/korish</code>")


@router.message(Command("dizayn"))
async def cmd_design(msg: Message):
    if await deny(msg):
        return
    cur = await db.get("card_design", "1")
    new = "0" if cur == "1" else "1"
    await db.set("card_design", new)
    await msg.answer(
        "🎨 Brend kartochka <b>yoqildi</b> — postlar dunyabunya dizaynida chiqadi."
        if new == "1" else
        "🖼 Brend kartochka <b>o'chirildi</b> — rasm o'z holicha yuboriladi."
    )


@router.message(Command("logo"))
async def cmd_logo(msg: Message):
    if await deny(msg):
        return
    await db.add_draft(msg.from_user.id, need="logo")
    await msg.answer(
        "🖼 Logoni <b>rasm</b> qilib yuboring (fon shaffof PNG bo'lsa eng yaxshisi).\n"
        "Bekor qilish: /tozala"
    )


@router.message(Command("shablon"))
async def cmd_template(msg: Message, command: CommandObject):
    if await deny(msg):
        return
    arg = (command.args or "").strip()
    if not arg:
        cur = await db.get("template")
        await msg.answer(
            "📝 <b>Hozirgi shablon:</b>\n<pre>" + cur.replace("<", "&lt;") + "</pre>\n"
            "Maydonlar: <code>{nom} {narx} {birlik} {eski_narx} {izoh} {kategoriya} "
            "{brend} {chegirma} {telefon} {telefon_link} {dokon} {kanal}</code>\n\n"
            "<i>{telefon_link} — raqam havola bo'lib chiqadi (/aloqa).</i>\n"
            "O'zgartirish: <code>/shablon</code> dan keyin yangi matnni yozing.\n"
            "Maydoni bo'sh bo'lgan qator avtomatik o'chiriladi."
        )
        return
    await db.set("template", arg)
    await msg.answer("✅ Shablon yangilandi. Ko'rish uchun: <code>/korish &lt;ID&gt;</code>")


# ---------------------------------------------------------------- navbat
@router.message(Command("navbat"))
@router.message(F.text == "📦 Navbat")
async def cmd_queue(msg: Message):
    if await deny(msg):
        return
    settings = await db.all_settings()
    times = scheduler.parse_times(settings["post_times"])
    per_day = max(1, len(times))
    nxt = scheduler.next_runs(3)
    age = await db.price_age_days()

    if settings.get("post_mode", "pdf") != "mahsulot":
        cats = await db.categories()
        picked = await db.pick_next_category()
        body = (
            f"📂 Kategoriyalar: <b>{len(cats)}</b> ta\n"
            f"🔄 Har kategoriya ~{max(1, len(cats) // per_day)} kunda bir marta "
            f"(kuniga {per_day} ta post)\n"
            + (f"➡️ Keyingisi: <b>{picked[0]}</b> ({len(picked[1])} ta mahsulot)\n" if picked else "")
        )
    else:
        ready = await db.ready_count()
        body = (f"✅ Postga tayyor: <b>{ready}</b> ta mahsulot\n"
                f"📅 Yetadi: ~{ready // per_day} kunga\n")

    await msg.answer(
        f"📦 <b>Navbat</b>\n\n" + body
        + f"⚠️ Narxsiz: {await db.no_price_count()} ta\n"
        + (f"🕓 Narxlar {age} kun oldin yangilangan\n" if age is not None else "")
        + (f"\n⏰ Keyingi postlar: {', '.join(nxt)}" if nxt else "")
        + ("\n\n⏸ <b>Bot pauzada</b>" if settings.get("paused") == "1" else "")
    )


@router.message(Command("royxat"))
async def cmd_list(msg: Message):
    if await deny(msg):
        return
    rows = await db.all_products(limit=30)
    if not rows:
        await msg.answer("Navbat bo'sh. Excel fayl yoki rasm yuboring.")
        return
    lines = ["📋 <b>Navbatdagi mahsulotlar</b>\n"]
    for r in rows[:30]:
        flags = ""
        if not r["price"]:
            flags += " 💸"
        if not r["photo_file_id"]:
            flags += " 🖼"
        if r["post_count"]:
            flags += f" ✅×{r['post_count']}"
        lines.append(f"<code>{r['id']:>3}</code> · {r['name'][:46]}{flags}")
    lines.append("\n💸 narxi yo'q · 🖼 rasmi yo'q · ✅ chiqqan")
    await msg.answer("\n".join(lines))


@router.message(Command("ochirish"))
async def cmd_delete(msg: Message, command: CommandObject):
    if await deny(msg):
        return
    arg = (command.args or "").strip()
    if not arg.isdigit():
        await msg.answer("Format: <code>/ochirish 12</code> (ID ni /royxat dan oling)")
        return
    ok = await db.delete_product(int(arg))
    await msg.answer("🗑 O'chirildi." if ok else "❌ Bunday ID topilmadi.")


@router.message(Command("korish", "preview"))
async def cmd_preview(msg: Message, command: CommandObject):
    if await deny(msg):
        return
    arg = (command.args or "").strip()
    settings = await db.all_settings()

    # prays rejimi: keyingi kategoriya qanday chiqishini ko'rsatamiz
    if not arg.isdigit() and settings.get("post_mode", "pdf") != "mahsulot":
        picked = await db.pick_next_category()
        if picked is None:
            await msg.answer("❌ Bazada narxli mahsulot yo'q. Excel fayl yuboring.")
            return
        category, items = picked
        caption = __import__("formatter").render_product(
            {"name": category.upper(), "category": category}, settings)
        note = f"\n\n<i>👁 Ko'rish rejimi — kanalga joylanmadi</i>"
        s2 = dict(settings); s2["sana"] = f"{db.now():%d.%m.%Y}"
        if settings.get("post_mode", "pdf") in ("pdf", "prays"):
            import pricebook
            data = pricebook.make_pdf(items, s2)
            await msg.answer_document(
                BufferedInputFile(data, filename=f"{category}.pdf"),
                caption=caption + note)
        else:
            cards = await poster.build_category_cards(category, items, settings)
            await msg.answer_photo(
                BufferedInputFile(cards[0], filename="preview.jpg"),
                caption=caption + note)
        return

    row = await db.get_product(int(arg)) if arg.isdigit() else await db.pick_next()
    if row is None:
        await msg.answer("❌ Mahsulot topilmadi.")
        return
    image, caption = await poster.build_post(msg.bot, dict(row), settings)
    note = f"\n\n<i>👁 Ko'rish rejimi — kanalga joylanmadi (ID {row['id']})</i>"
    if image:
        await msg.answer_photo(
            BufferedInputFile(image, filename="preview.jpg"), caption=caption + note
        )
    else:
        await msg.answer(caption + note)


@router.message(Command("hozir", "test"))
@router.message(F.text == "▶️ Hozir joylash")
async def cmd_now(msg: Message):
    if await deny(msg):
        return
    await msg.answer("⏳ Joylanmoqda…")
    result = await poster.post_next(msg.bot, manual_by=msg.from_user.id)
    await msg.answer(result)


@router.message(Command("pauza"))
async def cmd_pause(msg: Message):
    if await deny(msg):
        return
    await db.set("paused", "1")
    await msg.answer("⏸ To'xtatildi. Davom ettirish: /davom")


@router.message(Command("davom"))
async def cmd_resume(msg: Message):
    if await deny(msg):
        return
    await db.set("paused", "0")
    await msg.answer("▶️ Davom etamiz. Jadval: <code>" + await db.get("post_times") + "</code>")


@router.message(Command("statistika"))
@router.message(F.text == "📊 Statistika")
async def cmd_stats(msg: Message):
    if await deny(msg):
        return
    posts = await db.posts_today()
    times = scheduler.parse_times(await db.get("post_times"))
    async with db.conn().execute("SELECT COUNT(*) c FROM post_log WHERE ok = 1") as cur:
        total = (await cur.fetchone())["c"]
    async with db.conn().execute("SELECT COUNT(*) c FROM products WHERE active = 1") as cur:
        prods = (await cur.fetchone())["c"]

    lines = [f"📊 <b>Statistika</b>\n",
             f"Bugun: <b>{len(posts)}/{max(1, len(times))}</b> ta post",
             f"Jami postlar: {total} ta",
             f"Bazadagi mahsulot: {prods} ta",
             f"Postga tayyor: {await db.ready_count()} ta"]
    if posts:
        lines.append("\n<b>Bugun chiqqanlar:</b>")
        for r in posts:
            t = db.parse_iso(r["posted_at"])
            lines.append(f"✅ {t:%H:%M} — {r['name'][:40]}" if t else f"✅ {r['name'][:40]}")
    await msg.answer("\n".join(lines))


@router.message(F.text == "⚙️ Sozlamalar")
async def cmd_settings(msg: Message):
    if await deny(msg):
        return
    s = await db.all_settings()
    await msg.answer(
        "⚙️ <b>Sozlamalar</b>\n\n"
        f"📢 Kanal: <code>{s['channel_id'] or '—'}</code>\n"
        f"⏰ Vaqtlar: <code>{s['post_times']}</code>\n"
        f"👤 Mas'ul: <code>{s['manager_id'] or '—'}</code>\n"
        f"🎨 Brend kartochka: {'yoqilgan' if s['card_design'] == '1' else 'o‘chirilgan'}\n"
        f"🔔 Eslatma: har {s['remind_every_min']} daq "
        f"(tinch soat {s['quiet_from']}–{s['quiet_to']})\n"
        f"📉 Ogohlantirish chegarasi: {s['low_stock']} ta\n"
        f"🗓 Kunlik hisobot: {s['report_at']}\n\n"
        "O'zgartirish: /vaqt · /kanal · /masul · /dokon · /dizayn · /shablon"
    )


@router.message(Command("prays", "prays"))
async def cmd_pricebook(msg: Message, command: CommandObject):
    """Brendlangan to'liq narxlar ro'yxati — PDF va Excel."""
    if await deny(msg):
        return
    arg = (command.args or "").strip().lower()

    if arg.startswith("kanal"):
        await msg.answer("⏳ Prays-list tayyorlanmoqda…")
        await msg.answer(await poster.post_pricebook(msg.bot))
        return

    status = await msg.answer("⏳ Prays-list tayyorlanmoqda…")
    want = ["xlsx"] if arg.startswith(("excel", "xls")) else (
        ["pdf"] if arg.startswith("pdf") else ["pdf", "xlsx"])

    count = 0
    for fmt in want:
        data, filename, count = await poster.build_pricebook(fmt)
        if not count:
            await status.edit_text("Bazada narxli mahsulot yo'q. Avval Excel fayl yuboring.")
            return
        await msg.answer_document(BufferedInputFile(data, filename=filename))

    await status.edit_text(
        f"📋 Tayyor — {count} ta mahsulot, kategoriyalar bo'yicha guruhlangan.\n\n"
        "Kanalga joylash: <code>/prays kanal</code>\n"
        "Haftalik avtomatik: <code>/praysjadval dush 10:00</code>"
    )


@router.message(Command("praysjadval"))
async def cmd_pricebook_schedule(msg: Message, command: CommandObject):
    if await deny(msg):
        return
    arg = (command.args or "").strip().lower()
    if not arg:
        cur = await db.get("pricebook_at")
        await msg.answer(
            f"📋 Haftalik prays-list: <b>{cur or 'o‘chirilgan'}</b>\n\n"
            "Yoqish: <code>/praysjadval dush 10:00</code>\n"
            "Kunlar: dush, sesh, chor, pay, jum, shan, yak\n"
            "O'chirish: <code>/praysjadval yoq</code>"
        )
        return
    if arg in ("yoq", "off", "o'chir", "ochir"):
        await db.set("pricebook_at", "")
        await scheduler.reload_jobs()
        await msg.answer("📋 Haftalik prays-list o'chirildi.")
        return
    if not scheduler.parse_weekly(arg):
        await msg.answer("❌ Format: <code>/praysjadval dush 10:00</code>")
        return
    await db.set("pricebook_at", arg)
    await scheduler.reload_jobs()
    await msg.answer(f"✅ Har hafta <b>{arg}</b> da to'liq prays-list kanalga joylanadi.")


@router.message(Command("zaxira"))
async def cmd_backup(msg: Message):
    """Bazani zaxira kanaliga saqlash."""
    if await deny(msg):
        return
    await msg.answer(await backup.save(msg.bot, "qo'lda"))


@router.message(Command("zaxirakanal"))
async def cmd_backup_channel(msg: Message):
    """Zaxira kanalini ulash (keyingi forward qilingan post bo'yicha)."""
    if await deny(msg):
        return
    cur = await backup.chat_id()
    await db.add_draft(msg.from_user.id, need="backup")
    await msg.answer(
        f"💾 Hozirgi zaxira kanali: <code>{cur or 'yo‘q'}</code>\n\n"
        "<b>Yangisini ulash:</b>\n"
        "1️⃣ Telegramda <b>yopiq kanal</b> oching (odam qo'shmaysiz)\n"
        "2️⃣ Botni unga <b>admin</b> qiling — post yuborish va pin qilish huquqi bilan\n"
        "3️⃣ O'sha kanaldan istalgan xabarni shu yerga <b>forward</b> qiling\n\n"
        "Bekor qilish: /tozala"
    )


@router.message(Command("eksport"))
async def cmd_export(msg: Message):
    if await deny(msg):
        return
    if os.path.exists(DB_PATH):
        await msg.answer_document(FSInputFile(DB_PATH, filename="dunyabunya_backup.db"),
                                  caption="💾 Baza zaxira nusxasi")
    else:
        await msg.answer("Baza fayli topilmadi.")


@router.message(Command("tozala"))
async def cmd_clear(msg: Message):
    if await deny(msg):
        return
    n = await db.clear_drafts(msg.from_user.id)
    await msg.answer(f"🧹 {n} ta tugallanmagan yozuv tozalandi.")


# ---------------------------------------------------------------- Excel
@router.message(F.document)
async def got_document(msg: Message):
    if await deny(msg):
        return
    doc = msg.document
    name = (doc.file_name or "").lower()
    if not name.endswith((".xlsx", ".xlsm", ".xltx", ".csv", ".tsv", ".txt")):
        await msg.answer("📄 Faqat <b>.xlsx</b> yoki <b>.csv</b> fayl qabul qilaman.\n"
                         "PDF bo'lsa — Excel'ga o'girib yuboring.")
        return

    status = await msg.answer("⏳ Fayl o'qilmoqda…")
    buf = io.BytesIO()
    await msg.bot.download(doc, destination=buf)
    items, info = pricelist.parse(buf.getvalue(), name)
    if not items:
        await status.edit_text(info)
        return

    added = updated = 0
    for it in items:
        _, is_new = await db.upsert_product(source="excel", **it)
        added += is_new
        updated += not is_new

    await db.set("last_import_at", db.iso())
    cats = await db.categories()
    per_day = max(1, len(scheduler.parse_times(await db.get("post_times"))))
    await status.edit_text(
        f"✅ <b>{len(items)}</b> ta qator o'qildi\n"
        f"➕ Yangi: {added} ta · 🔄 Yangilandi: {updated} ta\n"
        f"{info}\n\n"
        f"📂 Kategoriyalar: <b>{len(cats)}</b> ta "
        f"({', '.join(cats[:6])}{'…' if len(cats) > 6 else ''})\n"
        f"📅 Kuniga {per_day} ta post — har kategoriya ~{max(1, len(cats) // per_day)} kunda bir marta\n\n"
        "Ko'rish: <code>/korish</code>  ·  Hoziroq joylash: <code>/hozir</code>"
    )
    await backup.save(msg.bot, "excel import")
    await poster.alert_empty(msg.bot)


# ---------------------------------------------------------------- rasm
@router.message(F.photo)
async def got_photo(msg: Message):
    if await deny(msg):
        return
    file_id = msg.photo[-1].file_id

    # logo kutilyaptimi?
    draft = await db.next_draft(msg.from_user.id)
    if draft and draft["need"] == "logo":
        buf = io.BytesIO()
        await msg.bot.download(file_id, destination=buf)
        path = os.path.join(os.path.dirname(DB_PATH) or ".", "logo.png")
        try:
            from PIL import Image
            Image.open(io.BytesIO(buf.getvalue())).convert("RGBA").save(path, "PNG")
            await db.drop_draft(draft["id"])
            await msg.answer("✅ Logo saqlandi. Tekshirish: <code>/korish</code>")
        except Exception as e:
            await msg.answer(f"❌ Logo saqlanmadi: <code>{e}</code>")
        return

    caption = msg.caption or ""
    data = parsing.parse_caption(caption)

    if not data.get("name"):
        await db.add_draft(msg.from_user.id, photo_file_id=file_id, need="name")
        await msg.answer("🖼 Rasm qabul qilindi.\nEndi <b>mahsulot nomini</b> yozing "
                         "(narxi bilan birga bo'lsa ham bo'ladi).")
        return

    await _save_product(msg, data, file_id)


async def _save_product(msg: Message, data: dict, file_id: str = ""):
    """Nomi bo'yicha bazadan topadi (rasmni ulaydi) yoki yangi mahsulot ochadi."""
    from matching import best_match, normalize

    existing = await db.find_by_name(data["name"])
    if existing is None:
        rows = await db.all_products(limit=800)
        choices = {r["norm_name"]: r for r in rows}
        existing = best_match(data["name"], choices)

    if existing is not None:
        payload = {k: v for k, v in data.items() if v}
        payload["name"] = existing["name"]
        if file_id:
            payload["photo_file_id"] = file_id
        await db.upsert_product(**payload)
        price = payload.get("price") or existing["price"]
        await msg.answer(
            f"🔗 <b>{existing['name']}</b> bilan bog'landi\n"
            f"💰 Narx: {price or '—'}\n"
            f"🖼 Rasm: {'ulandi' if file_id else 'oldingi'}\n\n"
            f"Kartochkani ko'rish: <code>/korish {existing['id']}</code>"
        )
        await poster.alert_empty(msg.bot)
        return

    if not data.get("price"):
        did = await db.add_draft(msg.from_user.id, photo_file_id=file_id,
                                 name=data["name"], need="price")
        await msg.answer(f"📝 <b>{data['name']}</b>\n\nEndi <b>narxini</b> yozing "
                         f"(faqat raqam, masalan <code>52000</code>).")
        return

    pid = await db.add_product(photo_file_id=file_id, source="photo", **data)
    await msg.answer(
        f"✅ Navbatga qo'shildi (ID {pid})\n"
        f"📦 {data['name']}\n💰 {data['price']} so'm"
        + (f" / {data['unit']}" if data.get("unit") else "")
        + f"\n\nKo'rish: <code>/korish {pid}</code>"
    )
    await poster.alert_empty(msg.bot)


# ---------------------------------------------------------------- matn
@router.message(F.text & ~F.text.startswith("/"))
async def got_text(msg: Message):
    if await deny(msg):
        return
    draft = await db.next_draft(msg.from_user.id)
    if draft is None:
        await msg.answer("Tushunmadim 🤔\nExcel fayl yoki rasm yuboring, "
                         "yoki /yordam ni bosing.", reply_markup=MENU)
        return

    text = msg.text.strip()

    if draft["need"] == "name":
        data = parsing.parse_caption(text)
        if not data.get("name"):
            await msg.answer("Mahsulot nomini yozing, masalan: <code>Sement M-400</code>")
            return
        await db.drop_draft(draft["id"])
        await _save_product(msg, data, draft["photo_file_id"])
        return

    if draft["need"] == "price":
        digits = "".join(ch for ch in text if ch.isdigit())
        if not digits:
            await msg.answer("Narxni raqam bilan yozing, masalan: <code>52000</code>")
            return
        extra = parsing.parse_caption(text)
        await db.drop_draft(draft["id"])
        pid = await db.add_product(
            name=draft["name"], price=digits, unit=extra.get("unit", ""),
            photo_file_id=draft["photo_file_id"], source="photo",
        )
        await msg.answer(
            f"✅ Navbatga qo'shildi (ID {pid})\n📦 {draft['name']}\n💰 {digits} so'm\n\n"
            f"Ko'rish: <code>/korish {pid}</code>"
        )
        await poster.alert_empty(msg.bot)
        return

    await db.drop_draft(draft["id"])
    await msg.answer("Bekor qilindi.")
