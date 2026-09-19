"""Mahsulot nomlarini normallashtirish va taqqoslash (kirill/lotin, yozuv xatolari)."""
import re
import unicodedata

try:
    from rapidfuzz import fuzz, process as rf_process

    HAVE_RF = True
except ImportError:  # zaxira variant
    import difflib

    HAVE_RF = False

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


def best_match(query: str, choices: dict[str, object], threshold: int = 82):
    """choices: {norm_name: obyekt}. Eng mos kelganini qaytaradi yoki None."""
    q = normalize(query)
    if not q or not choices:
        return None
    if q in choices:
        return choices[q]

    keys = list(choices)
    if HAVE_RF:
        hit = rf_process.extractOne(q, keys, scorer=fuzz.token_set_ratio, score_cutoff=threshold)
        if hit:
            return choices[hit[0]]
        # qisman: so'rov nomning bir qismi bo'lsa
        hit = rf_process.extractOne(q, keys, scorer=fuzz.partial_ratio, score_cutoff=92)
        return choices[hit[0]] if hit else None

    close = difflib.get_close_matches(q, keys, n=1, cutoff=threshold / 100)
    return choices[close[0]] if close else None
