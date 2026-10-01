"""Bot buyruqlari va xabar oqimi."""
import io
import logging
import os

from aiogram import F, Router
from aiogram.filters import Command, CommandObject
from aiogram.types import BufferedInputFile, CallbackQuery, FSInputFile, Message

import backup
import db
import formatter
import menus
import parsing
import poster
import pricelist
import scheduler
from config import ADMIN_IDS, DB_PATH

log = logging.getLogger("handlers")
router = Router()

HELP = """<b>🏗 dunyabunya — narxlar boti</b>

<b>Mahsulot qo'shish</b>
• 📄 Excel/CSV faylni shunchaki yuboring — barcha qatorlar navbatga tushadi
   (tagiga kategoriya nomini yozsangiz, hamma qatorga o'shani qo'yadi)
• 🖼 Rasm yuboring, tagiga yozing:
   <code>Sement M-400 — 52000 so'm/qop</code>
   (nomi Excel'da bor bo'lsa, rasm o'sha mahsulotga ulanadi)

<b>Pastdagi tugmalardan foydalaning</b> — hech narsa yozish shart emas.

<b>Buyruqlar ham bor</b>
/navbat — navbatda nechta mahsulot bor
/royxat — navbatdagi ro'yxat (ID bilan)
/korish — keyingi post qanday chiqishini ko'rish
/ochirish — mahsulot, brend yoki butun bazani o'chirish
/hozir — hoziroq keyingi postni kanalga joylash

<b>Sozlash</b>
/kanal — kanalni ulash (kanaldan post forward qiling)
/xodim 123456789 — xodimga mahsulot qo'shish ruxsatini berish\n/masul 123456789 — mas'ul xodimni belgilash
/vaqt 09:00,11:30,14:00,16:30,19:00 — post vaqtlari
/dokon dunyabunya | +998(91)785-00-90 | @kanal
/rasm — kategoriyaga rasm qo'yish · /rasmlar — holati\n/logo — logo yuklash (keyingi rasmni logo qilib oladi)
/fon — post rasmining orqa foni\n/rejim — post turi (rasm / pdf / mahsulot)\n/guruh — brend yoki kategoriya bo'yicha\n/dizayn — brend kartochkani yoqish/o'chirish
/shablon — post matni shabloni\n/filial — filiallar va raqamlari\n/buyurtma — rasmdagi buyurtma raqami\n/aloqa — raqam bog'lanadigan havola
/pauza · /davom — to'xtatish / davom ettirish\n/zaxirakanal — zaxira kanalini ulash\n/zaxira — bazani hoziroq saqlash
/statistika · /eksport · /id
"""


STAFF_HELP = """<b>🏗 dunyabunya — narxlar boti</b>

Narxlarni shu yerga yuborasiz, bot ularni kanalga o'zi joylaydi.

<b>Qanday yuboriladi</b>
• 📄 <b>Excel fayl</b> — barcha qatorlar navbatga tushadi
   (tagiga kategoriya nomini yozsangiz, hammasiga o'shani qo'yadi)
• 🖼 <b>Rasm</b> + tagiga: <code>Sement M-400 — 52000 so'm/qop</code>
• 🖼 Kategoriya rasmi: rasm + tagiga kategoriya nomi

Pastdagi tugmalardan foydalaning — hech narsa yozish shart emas.
"""


def is_admin(uid: int) -> bool:
    """Admin — Render'dagi ADMIN_IDS ro'yxatidagi odam. Hamma narsani qila oladi."""
    return not ADMIN_IDS or uid in ADMIN_IDS


async def staff_ids() -> list[int]:
    raw = await db.get("staff", "")
    return [int(x) for x in raw.replace(" ", "").split(",") if x.strip().isdigit()]


async def is_staff(uid: int) -> bool:
    """Xodim — mahsulot qo'sha oladi, sozlamalarga tegmaydi."""
    return is_admin(uid) or uid in await staff_ids()


async def deny(msg: Message) -> bool:
    """Faqat admin uchun."""
    if is_admin(msg.from_user.id):
        return False
    if await is_staff(msg.from_user.id):
        await msg.answer("🔒 Bu sozlamani faqat rahbar o'zgartira oladi.\n"
                         "Siz mahsulot qo'sha olasiz: Excel fayl yoki rasm yuboring.")
    else:
        await _ask_access(msg)
    return True


async def deny_staff(msg: Message) -> bool:
    """Admin ham, xodim ham ishlata oladi."""
    if await is_staff(msg.from_user.id):
        return False
    await _ask_access(msg)
    return True


async def _ask_access(msg: Message) -> None:
    """Notanish odam — o'ziga ID, adminlarga so'rov."""
    u = msg.from_user
    await msg.answer(
        "🔒 Sizda hali ruxsat yo'q.\n\n"
        f"Sizning ID: <code>{u.id}</code>\n"
        "Shu raqamni rahbarga yuboring — u sizga ruxsat beradi."
    )
    tag = f"@{u.username}" if u.username else (u.full_name or "—")
    for admin in ADMIN_IDS:
        try:
            await msg.bot.send_message(
                admin,
                f"👤 <b>{tag}</b> botdan foydalanmoqchi.\n"
                f"ID: <code>{u.id}</code>\n\n"
                f"Ruxsat berish: <code>/xodim {u.id}</code>",
            )
        except Exception:
            pass

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
    if await deny_staff(msg):
        return
    if not is_admin(msg.from_user.id):
        await msg.answer(STAFF_HELP, reply_markup=menus.STAFF)
        return
    await msg.answer(HELP, reply_markup=menus.MAIN)


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
@router.message(Command("xodim"))
async def cmd_staff(msg: Message, command: CommandObject):
    """Mahsulot qo'sha oladigan xodimlar ro'yxati."""
    if await deny(msg):
        return
    arg = (command.args or "").strip()
    ids = await staff_ids()

    if not arg:
        lst = "\n".join(f"• <code>{i}</code>" for i in ids) or "— hali yo'q —"
        await msg.answer(
            f"👥 <b>Xodimlar</b> (mahsulot qo'sha oladi):\n{lst}\n\n"
            "Qo'shish: <code>/xodim 123456789</code>\n"
            "O'chirish: <code>/xodim ochir 123456789</code>\n\n"
            "Xodim botga <code>/id</code> deb yozsa, o'z raqamini ko'radi.\n"
            "<i>Xodim faqat mahsulot qo'shadi — kanal, vaqt, dizayn "
            "sozlamalariga tegmaydi.</i>"
        )
        return

    parts = arg.split()
    if parts[0].lower() in ("ochir", "o'chir", "olib", "del"):
        target = next((p for p in parts[1:] if p.isdigit()), "")
        if not target:
            await msg.answer("Format: <code>/xodim ochir 123456789</code>")
            return
        ids = [i for i in ids if i != int(target)]
        await db.set("staff", ",".join(str(i) for i in ids))
        await msg.answer(f"🗑 <code>{target}</code> ro'yxatdan chiqarildi.")
        return

    if not parts[0].isdigit():
        await msg.answer("Format: <code>/xodim 123456789</code>\n"
                         "Raqamni xodim <code>/id</code> yozib oladi.")
        return

    uid = int(parts[0])
    if uid not in ids:
        ids.append(uid)
        await db.set("staff", ",".join(str(i) for i in ids))
    await msg.answer(f"✅ <code>{uid}</code> endi mahsulot qo'sha oladi.")
    try:
        await msg.bot.send_message(
            uid,
            "✅ <b>Sizga ruxsat berildi!</b>\n\n"
            "Endi narxlarni yuborishingiz mumkin:\n"
            "📄 Excel fayl — barcha qatorlar navbatga tushadi\n"
            "🖼 Rasm + tagiga mahsulot nomi va narxi\n\n"
            "Navbatni ko'rish: /navbat",
        )
    except Exception:
        await msg.answer("⚠️ Unga xabar yubora olmadim — avval u botga "
                         "<code>/start</code> yozsin.")


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


@router.message(Command("buyurtma"))
async def cmd_order_phone(msg: Message, command: CommandObject):
    """Rasm ichida chiqadigan buyurtma raqami."""
    if await deny(msg):
        return
    arg = (command.args or "").strip()
    if not arg:
        cur = await db.get("order_phone")
        await msg.answer(
            f"📞 Rasmdagi buyurtma raqami: <b>{cur}</b>\n\n"
            "O'zgartirish: <code>/buyurtma +998 (91) 785-00-90</code>"
        )
        return
    await db.set("order_phone", arg)
    await msg.answer(f"✅ Rasmda shu raqam chiqadi: <b>{arg}</b>\n\n"
                     "Ko'rish: <code>/korish</code>")


@router.message(Command("filial"))
async def cmd_branches(msg: Message, command: CommandObject):
    """Post ostida chiqadigan filiallar va ularning raqamlari."""
    if await deny(msg):
        return
    import formatter as _f

    arg = (command.args or "").strip()
    if not arg:
        rows = _f.parse_branches(await db.get("branches"))
        cur = "\n".join(f"• {n} — {ph or '—'}" for n, ph in rows) or "— yo'q —"
        await msg.answer(
            f"🏬 <b>Filiallar</b>\n{cur}\n\n"
            "O'zgartirish (nuqtali vergul bilan ajrating):\n"
            "<code>/filial Shirinobod|+998901112233; Hasanboy|+998901112234; "
            "Qorasaroy|+998901112235</code>\n\n"
            "Har filialga o'z raqami bo'lmasa, bitta raqamni uchalasiga yozing."
        )
        return
    rows = _f.parse_branches(arg)
    if not rows:
        await msg.answer("❌ Format: <code>/filial Nomi|+998901112233; Nomi2|+998...</code>")
        return
    await db.set("branches", arg)
    await msg.answer(
        "✅ Saqlandi. Post ostida shunday chiqadi:\n\n"
        "🛒 Xarid qilish uchun:\n" + _f.branches_block({"branches": arg})
    )


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
        "rasm": "🖼 Brend narxlari — rasm-jadval (PNG)",
        "pdf": "📄 O'sha jadval PDF fayl bo'lib",
        "mahsulot": "📦 Bitta mahsulot kartochkasi",
    }
    if arg not in names:
        cur = await db.get("post_mode", "rasm")
        cur = "pdf" if cur == "prays" else cur
        await msg.answer(
            f"Hozirgi rejim: <b>{names.get(cur, cur)}</b>\n\n"
            "O'zgartirish:\n"
            "<code>/rejim rasm</code> — narxlar jadvali rasm (PNG) bo'lib chiqadi\n"
            "<code>/rejim pdf</code> — o'sha jadval PDF fayl bo'lib\n"
            "<code>/rejim mahsulot</code> — har post bitta mahsulot kartochkasi"
        )
        return
    await db.set("post_mode", arg)
    await msg.answer(f"✅ Rejim: <b>{names[arg]}</b>\n\nKo'rish: <code>/korish</code>")


@router.message(Command("guruh"))
async def cmd_group(msg: Message, command: CommandObject):
    """Post qanday guruhlansin: brend bo'yicha yoki butun kategoriya."""
    if await deny(msg):
        return
    arg = (command.args or "").strip().lower()
    names = {
        "brend": "🏷 Butun brend bitta post (ichida kategoriyalarga bo'linadi)",
        "kategoriya": "📂 Butun kategoriya bitta post",
    }
    if arg not in names:
        cur = await db.get("group_by", "brend")
        groups = await db.categories()
        await msg.answer(
            f"Hozirgi guruhlash: <b>{names.get(cur, cur)}</b>\n"
            f"Hozir {len(groups)} ta post guruhi bor:\n"
            + "\n".join(f"• {g}" for g in groups[:12])
            + ("\n…" if len(groups) > 12 else "")
            + "\n\n<code>/guruh brend</code> — butun KNAUF bitta postda, ichida "
              "gipsokarton / rotband / profil bo'limlari bilan\n"
              "<code>/guruh kategoriya</code> — GIPSOKARTON bitta post, ichida brendlar"
        )
        return
    await db.set("group_by", arg)
    groups = await db.categories()
    await msg.answer(
        f"✅ {names[arg]}\n\nEndi {len(groups)} ta post guruhi:\n"
        + "\n".join(f"• {g}" for g in groups[:12])
        + ("\n…" if len(groups) > 12 else "")
        + "\n\nKo'rish: <code>/korish</code>"
    )


@router.message(Command("fon"))
async def cmd_theme(msg: Message, command: CommandObject):
    """Post rasmining orqa foni."""
    if await deny(msg):
        return
    names = {
        "toq": "🌑 To'q — mokriy asfalt, diagonal chiziqlar bilan",
        "qora": "⚫️ Qora — sof qora, minimal",
        "tekis": "▪️ Tekis — bitta rang, teksturasiz (eng toza)",
        "oq": "⬜️ Oq — yorug' fon, tepasida to'q chiziq",
    }
    arg = (command.args or "").strip().lower()
    if arg not in names:
        cur = await db.get("card_theme", "toq")
        await msg.answer(
            f"🎨 Hozirgi fon: <b>{names.get(cur, cur)}</b>\n\n"
            + "\n".join(f"<code>/fon {k}</code> — {v}" for k, v in names.items())
            + "\n\nTanlagandan keyin <code>/korish</code> bilan ko'ring."
        )
        return
    await db.set("card_theme", arg)

    # tanlangan fonni darrov ko'rsatamiz
    picked = await db.pick_next_category()
    if picked is None:
        await msg.answer(f"✅ Fon: <b>{names[arg]}</b>")
        return
    category, items = picked
    settings = await db.all_settings()
    cards = await poster.build_category_cards(category, items, settings, msg.bot)
    await msg.answer_photo(
        BufferedInputFile(cards[0], filename="fon.png"),
        caption=f"✅ Fon: <b>{names[arg]}</b>\n<i>Namuna — kanalga joylanmadi</i>",
    )


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


@router.message(Command("rasm"))
async def cmd_cat_photo(msg: Message, command: CommandObject):
    """Kategoriyaga rasm biriktirish."""
    if await deny_staff(msg):
        return
    arg = (command.args or "").strip()
    if not arg:
        await msg.answer(
            "🖼 <b>Kategoriyaga rasm qo'yish</b>\n\n"
            "Eng oson yo'l: <b>rasmni tashlang, tagiga kategoriya nomini yozing</b>.\n"
            "Masalan rasm + <code>Bazalt</code>\n\n"
            "Yoki: <code>/rasm Bazalt</code> deb yozib, keyin rasmni tashlang.\n\n"
            "Holatni ko'rish: /rasmlar"
        )
        return
    if arg.lower().startswith(("ochir", "o'chir")):
        name = arg.split(maxsplit=1)[1] if len(arg.split()) > 1 else ""
        cat = await _match_category(name) or name
        ok = await db.drop_cat_photo(cat)
        await msg.answer(f"🗑 <b>{cat}</b> rasmi o'chirildi." if ok
                         else f"❌ <b>{cat}</b> uchun rasm topilmadi.")
        return

    cat = await _match_category(arg)
    if not cat:
        cats = await db.product_categories()
        await msg.answer(
            f"❌ <b>{arg}</b> degan kategoriya topilmadi.\n\n"
            + ("Mavjudlari: " + ", ".join(cats[:12]) if cats else
               "Avval Excel fayl yuboring.")
        )
        return
    await db.add_draft(msg.from_user.id, name=cat, need="catphoto")
    await msg.answer(f"🖼 Endi <b>{cat}</b> uchun rasmni yuboring.\nBekor qilish: /tozala")


@router.message(Command("rasmlar"))
async def cmd_cat_photos(msg: Message):
    """Qaysi kategoriyada rasm bor, qaysisida yo'q."""
    if await deny_staff(msg):
        return
    cats = await db.product_categories()
    if not cats:
        await msg.answer("Bazada mahsulot yo'q. Avval Excel fayl yuboring.")
        return
    have = {k.strip().lower() for k in (await db.all_cat_photos())}
    lines = [("🖼 " if c.strip().lower() in have else "⬜️ ") + c for c in cats]
    missing = [c for c in cats if c.strip().lower() not in have]
    await msg.answer(
        "<b>Kategoriya rasmlari</b>\n" + "\n".join(lines[:30])
        + ("\n…" if len(lines) > 30 else "")
        + (f"\n\n{len(missing)} tasida rasm yo'q. Rasmni tashlab, tagiga "
           "kategoriya nomini yozing." if missing else "\n\nHammasida rasm bor ✅")
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
    if arg.lower() in ("tiklash", "standart", "reset"):
        from config import DEFAULTS as _D

        await db.set("template", _D["template"])
        settings = await db.all_settings()
        await msg.answer(
            "✅ Shablon standart holatga qaytarildi. Post ostida shunday chiqadi:\n\n"
            + formatter.render_product({"name": "KNAUF", "category": "Knauf"}, settings)
        )
        return

    if not arg:
        cur = await db.get("template")
        await msg.answer(
            "📝 <b>Hozirgi shablon:</b>\n<pre>" + cur.replace("<", "&lt;") + "</pre>\n"
            "Maydonlar: <code>{nom} {narx} {birlik} {eski_narx} {izoh} {kategoriya} "
            "{brend} {chegirma} {telefon} {telefon_link} {dokon} {kanal}</code>\n\n"
            "<i>{telefon_link} — raqam havola bo'lib chiqadi (/aloqa).</i>\n"
            "O'zgartirish: <code>/shablon</code> dan keyin yangi matnni yozing.\n"
            "Standartga qaytarish: <code>/shablon tiklash</code>\n"
            "Maydoni bo'sh bo'lgan qator avtomatik o'chiriladi."
        )
        return
    await db.set("template", arg)
    await msg.answer("✅ Shablon yangilandi. Ko'rish uchun: <code>/korish &lt;ID&gt;</code>")


# ---------------------------------------------------------------- navbat
@router.message(Command("navbat"))
@router.message(F.text == "📦 Navbat")
async def cmd_queue(msg: Message):
    if await deny_staff(msg):
        return
    settings = await db.all_settings()
    times = scheduler.parse_times(settings["post_times"])
    per_day = max(1, len(times))
    nxt = scheduler.next_runs(3)
    age = await db.price_age_days()

    body = await poster.queue_summary(settings) + "\n"
    body += f"📅 Kuniga {per_day} ta post\n"

    await msg.answer(
        "📦 <b>Navbat</b>\n\n" + body
        + f"⚠️ Narxsiz: {await db.no_price_count()} ta\n"
        + (f"🕓 Narxlar {age} kun oldin yangilangan\n" if age is not None else "")
        + (f"\n⏰ Keyingi postlar: {', '.join(nxt)}" if nxt else "")
        + ("\n\n⏸ <b>Bot pauzada</b>" if settings.get("paused") == "1" else "")
    )


@router.message(Command("royxat"))
async def cmd_list(msg: Message):
    if await deny_staff(msg):
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
    """Bitta mahsulot, bitta brend yoki butun bazani o'chirish."""
    if await deny(msg):
        return
    arg = (command.args or "").strip()
    low = arg.lower()

    if not arg:
        total = await db.total_products()
        await msg.answer(
            f"🗑 <b>O'chirish</b>  (bazada {total} ta mahsulot)\n\n"
            "<code>/ochirish 12</code> — bitta mahsulot (ID ni /royxat dan oling)\n"
            "<code>/ochirish Nova</code> — shu brend/kategoriyaning hammasi\n"
            "<code>/ochirish hammasi</code> — butun bazani tozalash\n\n"
            "<i>Yangi narxlar ro'yxatini yuborishdan oldin eskisini tozalasangiz, "
            "kanalga eski mahsulot chiqib qolmaydi.</i>"
        )
        return

    if arg.isdigit():
        ok = await db.delete_product(int(arg))
        await msg.answer("🗑 O'chirildi." if ok else "❌ Bunday ID topilmadi.")
        return

    # --- butun baza
    if low.startswith("hammasi"):
        total = await db.total_products()
        if not low.endswith(("ha", "tasdiq")):
            await msg.answer(
                f"⚠️ <b>Bazadagi {total} ta mahsulot o'chiriladi.</b>\n"
                "Kategoriya rasmlari va post tarixi saqlanib qoladi.\n\n"
                "Tasdiqlash: <code>/ochirish hammasi ha</code>"
            )
            return
        await backup.save(msg.bot, "tozalashdan oldin")
        n = await db.wipe_products()
        await msg.answer(
            f"🗑 <b>{n} ta mahsulot o'chirildi.</b> Baza toza.\n\n"
            "Endi yangi Excel faylni yuboring."
        )
        return

    # --- bitta brend / kategoriya
    parts = arg.split()
    confirm = parts[-1].lower() in ("ha", "tasdiq")
    name = " ".join(parts[:-1]) if confirm else arg

    groups = await db.categories()
    from matching import best_match, normalize
    hit = best_match(name, {normalize(g): g for g in groups}, threshold=85)
    if not hit:
        await msg.answer(
            f"❌ <b>{name}</b> topilmadi.\n\n"
            + ("Navbatdagilar: " + ", ".join(groups[:12]) if groups else "Navbat bo'sh.")
        )
        return

    count = len(await db.category_items(hit))
    if not confirm:
        await msg.answer(
            f"⚠️ <b>{hit}</b> — {count} ta mahsulot o'chiriladi.\n\n"
            f"Tasdiqlash: <code>/ochirish {hit} ha</code>"
        )
        return
    n = await db.wipe_products(hit)
    await msg.answer(f"🗑 <b>{hit}</b> o'chirildi ({n} ta mahsulot).")


@router.message(Command("korish", "preview"))
async def cmd_preview(msg: Message, command: CommandObject):
    if await deny_staff(msg):
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
        note = "\n\n<i>👁 Ko'rish rejimi — kanalga joylanmadi</i>"
        s2 = dict(settings); s2["sana"] = f"{db.now():%d.%m.%Y}"
        if settings.get("post_mode", "pdf") in ("pdf", "prays"):
            import pricebook
            data = pricebook.make_pdf(items, s2)
            await msg.answer_document(
                BufferedInputFile(data, filename=f"{category}.pdf"),
                caption=caption + note)
        else:
            cards = await poster.build_category_cards(category, items, settings, msg.bot)
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
    if await deny_staff(msg):
        return
    posts = await db.posts_today()
    times = scheduler.parse_times(await db.get("post_times"))
    async with db.conn().execute("SELECT COUNT(*) c FROM post_log WHERE ok = 1") as cur:
        total = (await cur.fetchone())["c"]
    async with db.conn().execute("SELECT COUNT(*) c FROM products WHERE active = 1") as cur:
        prods = (await cur.fetchone())["c"]

    lines = ["📊 <b>Statistika</b>\n",
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
    if await deny_staff(msg):
        return
    doc = msg.document
    name = (doc.file_name or "fayl.xlsx").lower()
    # o'qib bo'lmaydigani aniq bo'lgan formatlar
    if name.endswith((".pdf", ".doc", ".docx", ".jpg", ".jpeg", ".png", ".zip",
                      ".rar", ".7z", ".mp4", ".heic", ".webp", ".pptx")):
        await msg.answer(
            f"📄 <b>{doc.file_name}</b> qabul qilindi, lekin bu formatni o'qiy olmayman.\n\n"
            "Excel (<b>.xlsx</b>) yoki <b>.csv</b> qilib yuboring — "
            "PDF bo'lsa Excel'ga o'girib bering.")
        return

    status = await msg.answer("✅ <b>Fayl qabul qilindi</b> — o'qiyapman…")
    buf = io.BytesIO()
    try:
        await msg.bot.download(doc, destination=buf)
    except Exception as e:                      # noqa: BLE001
        log.exception("fayl yuklab olinmadi")
        await status.edit_text(
            "❌ Faylni Telegram'dan yuklab ola olmadim.\n"
            "Qaytadan yuborib ko'ring — fayl 20 MB dan kichik bo'lsin.\n"
            f"<i>({type(e).__name__})</i>")
        return

    # fayl tagiga kategoriya yozilgan bo'lsa — hamma qatorga o'sha qo'llanadi
    caption = (msg.caption or "").strip()
    try:
        items, info = pricelist.parse(buf.getvalue(), name, default_category=caption)
    except Exception as e:                      # noqa: BLE001
        log.exception("faylni o'qishda xato")
        await status.edit_text(
            f"❌ Faylni o'qishda xato: <i>{type(e).__name__}</i>\n\n"
            "Excel'da ochib <b>«Сохранить как» → .xlsx</b> qilib qayta yuboring.")
        return
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

    # birinchi uchta qator — tekshirib ko'rish uchun
    sample = []
    for it in items[:3]:
        bits = [b for b in (it["category"], it["brand"]) if b]
        sample.append(
            f"• {it['name'][:44]}\n   {formatter.money(it['price'])} so'm"
            + (f" / {it['unit']}" if it["unit"] else "")
            + (f"  ·  {' · '.join(bits)}" if bits else "")
        )

    await status.edit_text(
        f"✅ <b>{len(items)}</b> ta qator o'qildi\n"
        f"➕ Yangi: {added} ta · 🔄 Yangilandi: {updated} ta\n"
        f"{info}\n\n"
        + ("<b>Shunday tushundim:</b>\n" + "\n".join(sample) + "\n\n" if sample else "")
        + f"📂 Kategoriyalar ({len(cats)} ta): "
        f"{', '.join(cats[:8])}{'…' if len(cats) > 8 else ''}\n"
        f"📅 Kuniga {per_day} ta post — har kategoriya ~{max(1, len(cats) // per_day)} kunda bir marta\n\n"
        "Kategoriya noto'g'ri bo'lsa: faylni qayta yuboring va "
        "<b>tagiga kategoriya nomini yozing</b>.\n\n"
        "Ko'rish: <code>/korish</code>  ·  Hoziroq joylash: <code>/hozir</code>"
    )

    # rasmi yo'q kategoriyalar bo'lsa — so'raymiz
    missing = await db.categories_without_photo()
    if missing:
        await msg.answer(
            "🖼 <b>Bu kategoriyalarga rasm yo'q:</b>\n"
            + "\n".join(f"• {c}" for c in missing[:10])
            + ("\n…" if len(missing) > 10 else "")
            + "\n\nRasm yubormoqchi bo'lsangiz — <b>rasmni tashlang va tagiga "
              "kategoriya nomini yozing</b> (masalan: <code>Bazalt</code>).\n"
              "Bitta rasm butun kategoriyaga ishlaydi, har brendga alohida shart emas.\n\n"
              "Rasmsiz ham bo'laveradi — postlar baribir chiqadi."
        )
    await backup.save(msg.bot, "excel import")
    await poster.alert_empty(msg.bot)


# ---------------------------------------------------------------- rasm
@router.message(F.photo)
async def got_photo(msg: Message):
    if await deny_staff(msg):
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

    caption = (msg.caption or "").strip()

    # /rasm buyrug'idan keyin kutilayotgan kategoriya rasmi
    if draft and draft["need"] == "catphoto":
        await db.drop_cat_photo(draft["name"])
        await db.set_cat_photo(draft["name"], file_id)
        await db.drop_draft(draft["id"])
        await msg.answer(f"✅ <b>{draft['name']}</b> kategoriyasiga rasm qo'yildi.\n"
                         f"Ko'rish: <code>/korish</code>")
        return

    # tagiga kategoriya nomi yozilgan bo'lsa — o'sha kategoriyaning rasmi
    if caption:
        cat = await _match_category(caption)
        if cat:
            await db.set_cat_photo(cat, file_id)
            await msg.answer(
                f"🖼 Rasm <b>{cat}</b> kategoriyasiga qo'yildi.\n"
                "Shu kategoriyadagi hamma post shu rasm bilan chiqadi.\n\n"
                "Ko'rish: <code>/korish</code>"
            )
            return

    data = parsing.parse_caption(caption)

    if not data.get("name"):
        await db.add_draft(msg.from_user.id, photo_file_id=file_id, need="name")
        await msg.answer("🖼 Rasm qabul qilindi.\nEndi <b>mahsulot nomini</b> yozing "
                         "(narxi bilan birga bo'lsa ham bo'ladi).")
        return

    await _save_product(msg, data, file_id)


async def _match_category(text: str) -> str:
    """Matn mavjud kategoriya nomiga to'g'ri kelsa — o'sha nomni qaytaradi."""
    from matching import best_match, normalize

    text = text.strip()
    if not text or len(text.split()) > 4:
        return ""
    cats = await db.product_categories()
    if not cats:
        return ""
    exact = {normalize(c): c for c in cats}
    hit = best_match(text, exact, threshold=88)
    return hit or ""


async def _save_product(msg: Message, data: dict, file_id: str = ""):
    """Nomi bo'yicha bazadan topadi (rasmni ulaydi) yoki yangi mahsulot ochadi."""
    from matching import best_match

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
        await db.add_draft(msg.from_user.id, photo_file_id=file_id,
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
@router.message(F.text & ~F.text.startswith("/") & ~F.text.in_(menus.LABELS))
async def got_text(msg: Message):
    if await deny_staff(msg):
        return
    draft = await db.next_draft(msg.from_user.id)
    if draft is None:
        await msg.answer("Tushunmadim 🤔\nExcel fayl yoki rasm yuboring, "
                         "yoki /yordam ni bosing.", reply_markup=menus.MAIN)
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


# ================================================================
#  TUGMALAR — hamma narsani yozmasdan, bosib qilish uchun
# ================================================================
async def _edit(cb: CallbackQuery, text: str, markup=None) -> None:
    try:
        await cb.message.edit_text(text, reply_markup=markup)
    except Exception:
        await cb.message.answer(text, reply_markup=markup)


async def _settings_text() -> str:
    s = await db.all_settings()
    modes = {"rasm": "Rasm (PNG)", "pdf": "PDF fayl", "mahsulot": "Bitta mahsulot"}
    themes = {"oq": "Oq", "toq": "To'q", "qora": "Qora", "tekis": "Tekis"}
    return (
        "⚙️ <b>Sozlamalar</b>\n\n"
        f"🖼 Post turi: <b>{modes.get(s.get('post_mode'), s.get('post_mode'))}</b>\n"
        f"🏷 Guruhlash: <b>{s.get('group_by')}</b>\n"
        f"🎨 Fon: <b>{themes.get(s.get('card_theme'), s.get('card_theme'))}</b>\n"
        f"⏰ Vaqtlar: <code>{s.get('post_times')}</code>\n"
        f"📢 Kanal: <code>{s.get('channel_id') or '—'}</code>\n"
        + ("\n⏸ <b>Bot pauzada</b>" if s.get("paused") == "1" else "")
    )


@router.callback_query(F.data.startswith("m:"))
async def cb_menu(cb: CallbackQuery):
    """Menyular orasida yurish."""
    if not is_admin(cb.from_user.id):
        await cb.answer("Faqat rahbar uchun", show_alert=True)
        return
    what = cb.data.split(":", 1)[1]
    s = await db.all_settings()

    if what == "asosiy":
        await _edit(cb, await _settings_text(), menus.settings_menu(s))
    elif what == "rejim":
        await _edit(cb, "🖼 <b>Post turi</b>\n\nKanalga nima chiqsin?",
                    menus.mode_menu(s.get("post_mode", "rasm")))
    elif what == "guruh":
        await _edit(cb, "🏷 <b>Guruhlash</b>\n\nBitta postga nima yig'ilsin?",
                    menus.group_menu(s.get("group_by", "brend")))
    elif what == "fon":
        await _edit(cb, "🎨 <b>Fon rangi</b>\n\nTanlangandan keyin namuna ko'rsataman.",
                    menus.theme_menu(s.get("card_theme", "oq")))
    elif what == "vaqt":
        await _edit(cb, "⏰ <b>Post vaqtlari</b>\n\nO'zingiz yozmoqchi bo'lsangiz:\n"
                        "<code>/vaqt 09:00,13:00,18:00</code>",
                    menus.times_menu(s.get("post_times", "")))
    elif what == "filial":
        import formatter as _f
        rows = _f.parse_branches(s.get("branches", ""))
        cur = "\n".join(f"• {n} — {ph or '—'}" for n, ph in rows) or "— yo'q —"
        await _edit(cb, f"🏬 <b>Filiallar</b>\n{cur}\n\nO'zgartirish:\n"
                        "<code>/filial Shiribom|+998901112233; Hasanboy|+998901112234</code>",
                    menus.settings_menu(s))
    elif what == "buyurtma":
        await _edit(cb, f"📞 <b>Rasmdagi buyurtma raqami</b>\n<b>{s.get('order_phone')}</b>\n\n"
                        "O'zgartirish: <code>/buyurtma +998 90 123 45 67</code>",
                    menus.settings_menu(s))
    elif what == "rasmlar":
        await cb.message.answer("⏳")
        await cmd_cat_photos(cb.message)
    elif what == "xodim":
        ids = await staff_ids()
        lst = "\n".join(f"• <code>{i}</code>" for i in ids) or "— hali yo'q —"
        await _edit(cb, f"👥 <b>Xodimlar</b>\n{lst}\n\n"
                        "Qo'shish: <code>/xodim 123456789</code>\n"
                        "Xodim botga <code>/id</code> yozsa, raqamini ko'radi.",
                    menus.settings_menu(s))
    await cb.answer()


@router.callback_query(F.data.startswith("set:"))
async def cb_set(cb: CallbackQuery):
    """Sozlamani o'zgartirish."""
    if not is_admin(cb.from_user.id):
        await cb.answer("Faqat rahbar uchun", show_alert=True)
        return
    _, key, value = cb.data.split(":", 2)

    if key == "rejim":
        await db.set("post_mode", value)
        await cb.answer("✅ Saqlandi")
        await _edit(cb, "🖼 <b>Post turi</b>", menus.mode_menu(value))
    elif key == "guruh":
        await db.set("group_by", value)
        await cb.answer("✅ Saqlandi")
        await _edit(cb, "🏷 <b>Guruhlash</b>", menus.group_menu(value))
    elif key == "vaqt":
        await db.set("post_times", value)
        await scheduler.reload_jobs()
        await cb.answer("✅ Saqlandi")
        await _edit(cb, "⏰ <b>Post vaqtlari</b>", menus.times_menu(value))
    elif key == "fon":
        await db.set("card_theme", value)
        await cb.answer("✅ Saqlandi, namuna tayyorlanmoqda…")
        await _edit(cb, "🎨 <b>Fon rangi</b>", menus.theme_menu(value))
        await _send_preview(cb.message, cb.bot)


@router.callback_query(F.data.startswith("act:"))
async def cb_action(cb: CallbackQuery):
    """Tugma bilan bajariladigan ishlar."""
    what = cb.data.split(":", 1)[1]
    if what == "yop":
        try:
            await cb.message.delete()
        except Exception:
            pass
        await cb.answer()
        return

    if not is_admin(cb.from_user.id):
        await cb.answer("Faqat rahbar uchun", show_alert=True)
        return

    if what == "hozir":
        await cb.answer("⏳ Joylanmoqda…")
        await cb.message.answer(await poster.post_next(cb.bot, manual_by=cb.from_user.id))
    elif what in ("pauza", "davom"):
        await db.set("paused", "1" if what == "pauza" else "0")
        await cb.answer("⏸ To'xtatildi" if what == "pauza" else "▶️ Davom etamiz")
        await _edit(cb, await _settings_text(), menus.settings_menu(await db.all_settings()))
    elif what == "zaxira":
        await cb.answer("⏳")
        await cb.message.answer(await backup.save(cb.bot, "qo'lda"))
    elif what == "stat":
        await cb.answer()
        await cmd_stats(cb.message)


@router.callback_query(F.data.startswith("prays:"))
async def cb_pricebook(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        await cb.answer("Faqat rahbar uchun", show_alert=True)
        return
    what = cb.data.split(":", 1)[1]
    await cb.answer("⏳ Tayyorlanmoqda…")
    if what == "kanal":
        await cb.message.answer(await poster.post_pricebook(cb.bot))
        return
    data, name, count = await poster.build_pricebook("xlsx" if what == "excel" else "pdf")
    if not count:
        await cb.message.answer("Bazada narxli mahsulot yo'q.")
        return
    await cb.message.answer_document(BufferedInputFile(data, filename=name),
                                     caption=f"📋 {count} ta mahsulot")


@router.callback_query(F.data.startswith("del:"))
async def cb_delete(cb: CallbackQuery):
    """O'chirish — tasdiq tugmasi bilan."""
    if not is_admin(cb.from_user.id):
        await cb.answer("Faqat rahbar uchun", show_alert=True)
        return
    parts = cb.data.split(":", 2)
    kind = parts[1]

    if kind == "all":
        total = await db.total_products()
        await _edit(cb, f"⚠️ <b>Bazadagi {total} ta mahsulot o'chiriladi.</b>\n"
                        "Kategoriya rasmlari va tarix saqlanadi.\n\nRostdan o'chiramizmi?",
                    menus.confirm("del:allyes"))
    elif kind == "allyes":
        await backup.save(cb.bot, "tozalashdan oldin")
        n = await db.wipe_products()
        await _edit(cb, f"🗑 <b>{n} ta mahsulot o'chirildi.</b> Baza toza.\n\n"
                        "Endi yangi Excel faylni yuboring.")
    elif kind == "g":
        group = parts[2]
        count = len(await db.category_items(group))
        await _edit(cb, f"⚠️ <b>{group}</b> — {count} ta mahsulot o'chiriladi.\n\nRostdanmi?",
                    menus.confirm(f"del:gyes:{group}"))
    elif kind == "gyes":
        group = parts[2]
        n = await db.wipe_products(group)
        await _edit(cb, f"🗑 <b>{group}</b> o'chirildi ({n} ta mahsulot).")
    await cb.answer()


async def _send_preview(msg: Message, bot) -> None:
    """Keyingi post qanday chiqishini ko'rsatadi."""
    settings = await db.all_settings()
    if settings.get("post_mode", "rasm") == "mahsulot":
        row = await db.pick_next()
        if row is None:
            await msg.answer("Navbat bo'sh. Excel fayl yuboring.")
            return
        image, caption = await poster.build_post(bot, dict(row), settings)
        await msg.answer_photo(BufferedInputFile(image, filename="p.png"),
                               caption=caption + "\n\n<i>👁 Namuna</i>")
        return

    picked = await db.pick_next_category()
    if picked is None:
        await msg.answer("📦 Navbat bo'sh. Yangi Excel faylni yuboring.")
        return
    category, items = picked
    caption = formatter.render_product({"name": category.upper(), "category": category}, settings)
    note = "\n\n<i>👁 Namuna — kanalga joylanmadi</i>"
    if settings.get("post_mode", "rasm") in ("pdf", "prays"):
        import pricebook
        s2 = poster._card_settings(settings)
        data = pricebook.make_pdf(items, s2)
        await msg.answer_document(BufferedInputFile(data, filename=f"{category}.pdf"),
                                  caption=caption + note, reply_markup=menus.after_preview())
    else:
        cards = await poster.build_category_cards(category, items, settings, bot)
        await msg.answer_photo(BufferedInputFile(cards[0], filename="preview.png"),
                               caption=caption + note, reply_markup=menus.after_preview())


# ---------------------------------------------------------------- pastki tugmalar
@router.message(F.text == "⚙️ Sozlamalar")
async def btn_settings(msg: Message):
    if await deny(msg):
        return
    await msg.answer(await _settings_text(), reply_markup=menus.settings_menu(await db.all_settings()))


@router.message(F.text == "👁 Ko'rish")
async def btn_preview(msg: Message):
    if await deny_staff(msg):
        return
    await _send_preview(msg, msg.bot)


@router.message(F.text == "📋 Prays")
async def btn_pricebook(msg: Message):
    if await deny(msg):
        return
    await msg.answer("📋 <b>To'liq prays-list</b>\nQaysi ko'rinishda kerak?",
                     reply_markup=menus.pricebook_menu())


@router.message(F.text == "🗑 Tozalash")
async def btn_wipe(msg: Message):
    if await deny(msg):
        return
    total = await db.total_products()
    if not total:
        await msg.answer("Baza allaqachon bo'sh.")
        return
    groups = await db.categories()
    await msg.answer(
        f"🗑 <b>Tozalash</b> — bazada {total} ta mahsulot\n\n"
        "Nimani o'chiramiz?",
        reply_markup=menus.wipe_menu(total, groups),
    )
