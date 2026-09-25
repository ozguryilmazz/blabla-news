"""Türkiye ile ilgili haberler için çok dilli anahtar kelime ön elemesi.

Metin küçük harfe çevrilip aksanlardan arındırılır, ardından kök eşleşmesi yapılır.
Alt dize eşleşmesi İbranicedeki bitişik ön ekleri (ב, ל, ה, מ, ו) ve
Yunancadaki çekim eklerini kendiliğinden kapsar. Kesin karar yapay zekâ adımındadır.
"""

import unicodedata

KEYWORDS: dict[str, list[str]] = {
    "el": [
        "τουρκ",  # Τουρκία, τουρκικός, Τούρκος
        "ερντογαν",
        "αγκυρα",
        "κωνσταντινουπολ",
        "ισταμπουλ",
        "φινταν",
        "κατεχομεν",  # κατεχόμενα (işgal altındaki bölgeler)
        "ψευδοκρατ",
        "γαλαζια πατριδα",  # Mavi Vatan
    ],
    "he": [
        "טורקי",  # טורקיה, טורקים, טורקית
        "ארדואן",
        "ארדוגאן",
        "אנקרה",
        "איסטנבול",
        "פידאן",
    ],
    "en": [
        "turkey",
        "turkish",
        "turkiye",
        "erdogan",
        "ankara",
        "istanbul",
        "fidan",
        "blue homeland",
    ],
}

ALL_KEYWORDS = sorted({k for words in KEYWORDS.values() for k in words})


def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


def matched_keywords(*texts: str | None) -> list[str]:
    haystack = normalize(" ".join(t for t in texts if t))
    return [k for k in ALL_KEYWORDS if k in haystack]


def is_candidate(*texts: str | None) -> bool:
    return bool(matched_keywords(*texts))
