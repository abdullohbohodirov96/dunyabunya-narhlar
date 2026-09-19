# 🏗 dunyabunya — narxlar kanali uchun avtomatik bot

Har kuni belgilangan vaqtlarda narxlar kanaliga mahsulotlarni **o'zi** joylaydigan
Telegram bot. Mahsulotlarni Excel fayl yoki rasm orqali beresiz — qolganini bot qiladi.

---

## Nima qila oladi

| | |
|---|---|
| 📄 **Excel/CSV import** | 30–50 ta mahsulotni bir faylda yuborasiz — har biri alohida navbatga tushadi (kategoriya, brend, birlik, eski narx bilan) |
| 🖼 **Rasm biriktirish** | Rasm yuborasiz, tagiga nom yozasiz — bot Excel'dagi mos qatorga o'zi ulaydi (kirill/lotin, yozuv xatolari bilan ham topadi) |
| 📄 **Kategoriya praysi** | Har post — bitta kategoriyaning to'liq narxlari, brendlangan **PDF** fayl: `💰 dunyabunya "GIPSOKARTON" narxlari` |
| ⏰ **Avtomatik jadval** | Kuniga 5 ta post: 09:00 · 11:30 · 14:00 · 16:30 · 19:00 (Toshkent vaqti) — o'zgartirish mumkin |
| 🔄 **Aylanma navbat** | Kategoriyalar navbat bilan chiqadi, ketma-ket bir xili takrorlanmaydi |
| ✅ **Galochka** | Har postdan keyin sizga "joylandi" xabari + kun oxirida to'liq hisobot |
| 🔔 **Eslatma** | Narx tugasa yoki 7 kundan beri yangilanmasa — mas'ul xodimga **har 5 daqiqada** yozib turadi (tunda bezovta qilmaydi) |
| 📋 **To'liq prays** | Butun bazani bitta **PDF/Excel** qilib ham beradi — `/prays` |
| 🎨 **3 xil post turi** | `/rejim pdf` (asosiy) · `/rejim rasm` (narxlar rasm-jadval) · `/rejim mahsulot` (bitta mahsulot kartochkasi) |

---

## 1-qadam. Bot yaratish

1. Telegramda [@BotFather](https://t.me/BotFather) ga kiring → `/newbot`
2. Nom va username bering → sizga **token** beradi (`1234567890:AAE...`)
3. Botni **narxlar kanalingizga admin** qilib qo'shing (posts yuborish huquqi bilan)
4. Botga `/id` deb yozing → o'z **Telegram ID** raqamingizni oling
5. Mas'ul xodim ham botga `/id` yozsin → uning raqamini oling

---

## 2-qadam. Render.com'ga joylash

1. Bu papkani GitHub'ga repo qilib yuklang
2. Render → **New +** → **Blueprint** → repo'ni tanlang (`render.yaml` o'zi o'qiladi)
3. So'ralgan o'zgaruvchilarni kiriting:

| O'zgaruvchi | Qiymat |
|---|---|
| `BOT_TOKEN` | BotFather bergan token |
| `ADMIN_IDS` | sizning ID (bir nechta bo'lsa vergul bilan: `111,222`) |
| `CHANNEL_ID` | `@kanal_nomi` (yoki keyin `/kanal` bilan ulaysiz) |
| `MANAGER_ID` | mas'ul xodim ID si |

4. **Deploy** → bot ishga tushadi va sizga "🟢 Bot ishga tushdi" deb yozadi.

### Qaysi planni tanlash

| | **Worker + disk** (`render.yaml`) | **Web service** (`render-web.yaml`) |
|---|---|---|
| Narxi | $7/oy (starter) | bepul bo'lishi mumkin |
| Uxlab qolishi | yo'q, 24/7 ishlaydi | bepulda 15 daq trafik bo'lmasa uxlaydi → **pinger kerak** |
| Baza | `/data` diskida, o'chmaydi | bepulda disk yo'q → **zaxira kanali kerak** |
| Sozlash | oson | 2 ta qo'shimcha qadam |

**Bepul web variantini ishlatmoqchi bo'lsangiz** — `render-web.yaml` ni
`render.yaml` deb nomlang va ikki narsani qiling:

1. **Uxlab qolmaslik — avtomatik.** Bot o'ziga har 10 daqiqada so'rov yuborib
   turadi (`RENDER_EXTERNAL_URL` o'zgaruvchisini Render o'zi beradi), shuning
   uchun tashqi pinger kerak emas. Log'da shunday qator ko'rinadi:
   `Uxlab qolmaslik uchun har 10 daqiqada .../health chaqiriladi`.

   > Bepul plan oyiga **750 soat** beradi. Bitta servis 24/7 ishlasa ≈730 soat —
   > sig'adi. Lekin shu hisobda boshqa bepul servisingiz bo'lsa, limit oshadi va
   > oy oxirida hammasi to'xtaydi.

2. **Zaxira kanali.** Botning "seyfi" — bazani shu yerda saqlaydi:

   - Telegramda **yopiq kanal** ochasiz (odam qo'shmaysiz, faqat siz va bot)
   - Botni unga **admin** qilasiz: *post yuborish* + *pin qilish* huquqi bilan
   - Botga `/zaxirakanal` deb yozasiz, so'ng o'sha kanaldan istalgan xabarni
     botga **forward** qilasiz — bot ID ni oladi, tekshiradi va sizga
     `BACKUP_CHAT=-100...` ni beradi. O'shani Render'ga ham yozib qo'ying
     (bot qayta ishga tushganda baza yo'q bo'lsa, faqat env orqali topa oladi).

   Bot har Excel importdan keyin va har kuni kechqurun bazani o'sha kanalga
   fayl qilib tashlaydi va **pin** qiladi; qayta ishga tushganda pin qilingan
   fayldan bazani tiklaydi. Qo'lda saqlash: `/zaxira`.

> Zaxira kanali worker + disk variantida ham foydali — disk buzilsa qutqaradi.

> **Python versiyasi.** Repo ichida `.python-version` fayli bor (`3.12`) —
> Render shuni o'qiydi. Render'ning standart versiyasi 3.14, unda Pillow/reportlab
> kabi kutubxonalar tayyor paket topa olmay qurilishga urinadi va build yiqiladi.
> Agar servisni qo'lda yaratgan bo'lsangiz va baribir xato bersa, Environment'ga
> `PYTHON_VERSION=3.12.6` deb qo'shing — u hamma narsadan ustun turadi.

Lokal kompyuterda sinash uchun: `.env.example` ni `.env` qilib to'ldiring, so'ng
`pip install -r requirements.txt && python bot.py`.

---

## 3-qadam. Sozlash (bir marta)

Botga yozing:

```
/kanal                 → kanaldan bitta postni forward qiling
/masul 987654321       → mas'ul xodimni belgilang
/dokon dunyabunya | +998(91)785-00-90 | @Dunyabunya_prays
/aloqa https://t.me/db_Community_manager
/logo                  → keyingi yuborgan rasmingiz logo bo'ladi
```

---

## Har kungi ish

### Excel bilan (asosiy usul)

Bitta faylda 30–50 ta mahsulot yuborasiz — haftaga yetadi.
Birinchi qatorda ustun nomlari bo'lsin:

| Mahsulot nomi | Kategoriya | Brend | Birlik | Narxi | Eski narx | Izoh |
|---|---|---|---|---|---|---|
| Sement M-400 50kg | Sement | Qizilqum | qop | 52000 | 58000 | |
| Profil PP 60x27 3m | Profil | Knauf | dona | 23500 | | |
| Bazalt plita 50mm | Bazalt | Izovol | m² | 41000 | | Omborda bor |

- Ustun nomlari **o'zbekcha, ruscha yoki inglizcha** bo'lsa ham bot taniydi
  (`Narxi` / `Цена` / `Price` — farqi yo'q)
- Shtrix-kod, artikul, "шт" kabi keraksiz ustunlar **e'tiborsiz qoldiriladi**
- Faylni qayta yuborsangiz — dublikat yasamaydi, narxlarni **yangilaydi**

### Post qanday chiqadi

Har postda navbatdagi kategoriya olinadi, uning hamma mahsuloti brendlangan PDF
qilib kanalga tashlanadi. Post matni:

```
💰 dunyabunya "GIPSOKARTON" narxlari

📍 dunyabunya barcha filiallarida

+998(91)785-00-90        ← havola: t.me/db_Community_manager
```

Masalan 5 ta kategoriya bo'lsa va kuniga 5 ta post bo'lsa — har kategoriya
kuniga bir martadan chiqadi. 20 ta kategoriya bo'lsa — har biri 4 kunda bir marta.

Rasm-jadval ko'rinishini afzal ko'rsangiz: `/rejim rasm`.

**Guruhlash.** Standart holatda har brend alohida post bo'ladi —
`BAZALT EVEREST` va `BAZALT PETRAWOOL` ikki xil postda chiqadi. Butun
kategoriyani bitta postga yig'ish uchun: `/guruh kategoriya`. Qaytarish:
`/guruh brend`. Hozirgi guruhlar ro'yxatini `/guruh` ko'rsatadi.

### Rasm bilan (ixtiyoriy)

Rasmni yuborib, tagiga yozing:

```
Sement M-400 — 52 000 so'm/qop
```

Bu nom Excel'da bor bo'lsa — rasm **o'sha qatorga ulanadi**. Yo'q bo'lsa — yangi
mahsulot ochiladi. Tagiga hech narsa yozmasangiz, bot o'zi nomini so'raydi.

---

## Buyruqlar

**Kundalik**
```
/navbat        navbatda nechta mahsulot bor, necha kunga yetadi
/royxat        ro'yxat (ID bilan) — 💸 narxsiz, 🖼 rasmsiz belgilari bilan
/korish        keyingi post qanday chiqishini ko'rish (kanalga chiqmaydi)
/ochirish 12   navbatdan olib tashlash
/hozir         hoziroq keyingi postni kanalga joylash
/statistika    bugungi va umumiy holat
```

**Prays-list fayl**
```
/prays                 PDF + Excel qilib sizga yuboradi
/prays pdf             faqat PDF
/prays excel           faqat Excel
/prays kanal           to'liq prays-listni kanalga joylaydi
/praysjadval dush 10:00   har dushanba 10:00 da kanalga avtomatik
/praysjadval yoq          o'chirish
```

**Sozlash**
```
/rejim pdf     post turi: pdf / rasm / mahsulot
/aloqa         raqam bog'lanadigan havola
/kanal · /masul · /dokon · /logo · /vaqt · /shablon · /dizayn
/zaxirakanal · /zaxira   zaxira kanali va qo'lda saqlash
/pauza · /davom · /eksport · /tozala · /id
```

---

## Post matni shabloni

Hozirgi shablon post ostida shunday chiqadi:

```
💰 dunyabunya "Gipsokarton KNAUF 12.5mm" narxlari

📍 dunyabunya barcha filiallarida

+998(91)785-00-90        ← havola: t.me/db_Community_manager
```

Narx matnda emas, **rasm ustida** katta qilib chiqadi — shuning uchun matn qisqa.

`/shablon` — hozirgisini ko'rsatadi. O'zgartirish uchun `/shablon` dan keyin yangi
matnni yozing. Ishlatsa bo'ladigan maydonlar:

```
{nom} {narx} {birlik} {eski_narx} {chegirma} {izoh}
{kategoriya} {brend} {telefon} {telefon_link} {dokon} {kanal}
```

`{telefon_link}` — raqam bosiladigan havola bo'lib chiqadi. Havolani `/aloqa`
bilan o'zgartirasiz, `/aloqa yoq` desangiz oddiy matn bo'ladi.

Maydoni bo'sh bo'lgan qator **avtomatik o'chib ketadi** — ya'ni eski narxi yo'q
mahsulotda "Eski narx:" qatori chiqmaydi.

---

## Dizayn

Brend ranglari kodda shu yerda turadi — `cardmaker.py` boshida:

```python
ORANGE  = (233, 118, 9)    # #e97609
ASPHALT = (46, 50, 57)     # #2e3239
BLACK   = (0, 0, 0)
WHITE   = (255, 255, 255)
```

**Shrift:** brend shrifti Montserrat. Hozircha ichida Poppins turibdi (juda yaqin
geometrik sans). Montserrat qo'yish uchun `Montserrat-Bold.ttf` va
`Montserrat-Medium.ttf` fayllarini `assets/fonts/` papkasiga tashlang — bot
o'zi ularni ustun ko'radi, kodni o'zgartirish shart emas.

**Logo:** `/logo` buyrug'i bilan yuklaysiz (shaffof fonli PNG eng yaxshisi).
Logo qo'yilmasa, bot vaqtincha "db" belgisini chizadi.

Brend kartochkani butunlay o'chirib, oddiy rasm yuborish: `/dizayn`.

---

## Texnik tuzilish

```
bot.py          ishga tushirish, polling
handlers.py     buyruqlar va xabarlar oqimi
scheduler.py    vaqt jadvali (APScheduler, Asia/Tashkent)
poster.py       kanalga joylash, eslatma, kunlik hisobot
cardmaker.py    brend kartochka (Pillow)
pricebook.py    PDF + Excel prays-list (reportlab, openpyxl)
pricelist.py    Excel/CSV o'qish
matching.py     nomlarni solishtirish (kirill↔lotin, xato yozuv)
parsing.py      rasm tagidagi matndan nom/narx ajratish
formatter.py    post matni shabloni
db.py           SQLite baza
```

**Rasmlar Telegram serverida saqlanadi** (`file_id`) — bazani shishirmaydi,
Render diskida joy yemaydi.

**Server o'chib-yonsa:** `misfire_grace_time` tufayli 30 daqiqa ichida
o'tkazib yuborilgan post baribir joylanadi. Baza `/data` diskida — o'chmaydi.
`/eksport` bilan istalgan payt zaxira nusxa olasiz.
