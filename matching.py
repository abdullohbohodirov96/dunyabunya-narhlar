"""Mahsulot nomlarini normallashtirish va taqqoslash (kirill/lotin, yozuv xatolari)."""
import re
import unicodedata

from difflib import SequenceMatcher

CYR2LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "ғ": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "j", "з": "z", "и": "i", "й": "y", "к": "k", "қ": "q", "л": "l", "м": "m",
    "н": "n", "ң": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ў": "o", "ф": "f", "х": "x", "ҳ": "h", "ц": "ts", "ч": "ch", "ш": "sh",
    "щ": "sh", "ъ": "", "ы": "i", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}

# ko'p uchraydigan yozuv variantlari -> bitta shakl
SYNONYMS = {
    "cement": "sement", "tsement": "sement", "sment": "sement", "pment": "sement",
    "kirpich": "gisht", "kirpic": "gisht",
    "pesok": "qum", "shcheben": "shagal", "sheben": "shagal", "gravий": "shagal",
    "kraska": "boyoq", "kley": "yelim",
    "profil": "profil", "profill": "profil",
    "armatur": "armatura", "armatura": "armatura",
    "gipsokarton": "gipsokarton", "gkl": "gipsokarton",
    "penoplast": "penoplast", "pena": "penoplast",
    "bazalt": "bazalt", "bazal": "bazalt",
}


def translit(text: str) -> str:
    out = []
    for ch in text:
        low = ch.lower()
        out.append(CYR2LAT.get(low, low))
    return "".join(out)


def normalize(text: str) -> str:
    """Taqqoslash uchun soddalashtirilgan shakl."""
    if not text:
        return ""
    s = unicodedata.normalize("NFKD", str(text)).lower()
    s = s.replace("ʻ", "'").replace("ʼ", "'").replace("`", "'").replace("‘", "'").replace("’", "'")
    s = translit(s)
    s = s.replace("'", "")
    s = re.sub(r"[^a-z0-9]+", " ", s)
    words = []
    for w in s.split():
        words.append(SYNONYMS.get(w, w))
    return " ".join(words).strip()


def _token_cover(q_tokens: list[str], c_tokens: list[str]) -> float:
    """So'rovdagi har bir so'z nomzodda qanchalik topilgani (0..1)."""
    if not q_tokens or not c_tokens:
        return 0.0
    total = 0.0
    for t in q_tokens:
        total += max(SequenceMatcher(None, t, c).ratio() for c in c_tokens)
    return total / len(q_tokens)


def score(query: str, candidate: str) -> float:
    """0..100. Ikki nomning o'xshashligi (so'z darajasida + butun matn)."""
    q, c = normalize(query), normalize(candidate)
    if not q or not c:
        return 0.0
    if q == c:
        return 100.0
    qt, ct = q.split(), c.split()
    cover = _token_cover(qt, ct)
    whole = SequenceMatcher(None, q, c).ratio()
    # ikki tomonlama qamrov — bittasi ikkinchisining bo'lagi bo'lsa ham ishlaydi
    back = _token_cover(ct, qt)
    return max(cover, whole, (cover + back) / 2) * 100


def best_match(query: str, choices: dict[str, object], threshold: int = 82):
    """choices: {norm_name: obyekt}. Eng mos kelganini qaytaradi yoki None."""
    q = normalize(query)
    if not q or not choices:
        return None
    if q in choices:
        return choices[q]

    best_key, best = None, 0.0
    for key in choices:
        sc = score(q, key)
        if sc > best:
            best_key, best = key, sc
    return choices[best_key] if best_key is not None and best >= threshold else None
