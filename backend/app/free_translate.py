"""Ücretsiz çeviri yöntemi: API anahtarı gerektirmez.

- İlgi kontrolü: anahtar kelime eşleşmesiyle (başlıkta geçiyorsa veya metinde en az iki kez geçiyorsa ilgili)
- Kategori: çok dilli kelime kurallarıyla
- Çeviri: Google Translate'in herkese açık ücretsiz uç noktası; başlık ve haberin ilk paragrafları çevrilir

Claude yöntemiyle aynı arayüzü (check_relevance, rewrite) sunar, bu yüzden tarama akışı değişmez.
Kalite Claude kadar iyi değildir: birebir makine çevirisidir, özet ve önemli noktalar üretilmez.
"""

import httpx

from . import keywords
from .ai import AIError, AIFatalError, RelevanceResult, RewriteResult
from .config import get_settings

GOOGLE_URL = "https://translate.googleapis.com/translate_a/single"
LEAD_CHARS = 1500  # telif için haberin yalnızca giriş kısmı çevrilir
CHUNK_CHARS = 1800

# Sıra önemli: daha özel kategoriler önce denenir
CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("kibris", ["κυπρ", "cyprus", "cypriot", "קפריסין"]),
    ("ege-dogu-akdeniz", ["αιγαι", "ανατολικη μεσογει", "υφαλοκρηπιδ", "aegean", "eastern mediterranean", "continental shelf", "הים התיכון"]),
    ("savunma-guvenlik", ["στρατ", "αμυν", "πολεμικ", "εξοπλισ", "army", "military", "defence", "defense", "missile", "drone", "f-35", "f-16", "navy", "צבא", "ביטחון", "טיל", "צה\"ל", "חיל"]),
    ("goc", ["μεταναστ", "προσφυγ", "migrant", "refugee", "migration", "asylum", "מהגר", "פליט"]),
    ("ekonomi-enerji", ["οικονομ", "ενεργει", "φυσικο αεριο", "εμπορ", "economy", "economic", "trade", "energy", "pipeline", "gas", "כלכל", "אנרגי", "סחר", "גז "]),
    ("siyaset-diplomasi", ["υπουργ", "προεδρ", "κυβερνησ", "διπλωματ", "συνομιλ", "minister", "president", "government", "diplomat", "talks", "summit", "embassy", "ממשל", "נשיא", "שגריר", "דיפלומט"]),
    ("kultur-toplum", ["πολιτισ", "τουρισ", "ποδοσφ", "culture", "tourism", "football", "festival", "תרבות", "תיירות", "כדורגל"]),
]


# Eşleşen anahtar kelime kökü → Türkçe etiket
KEYWORD_TAGS = {
    "τουρκ": "Türkiye", "turkey": "Türkiye", "turkish": "Türkiye", "turkiye": "Türkiye", "טורקי": "Türkiye",
    "ερντογαν": "Erdoğan", "erdogan": "Erdoğan", "ארדואן": "Erdoğan", "ארדוגאן": "Erdoğan",
    "αγκυρα": "Ankara", "ankara": "Ankara", "אנקרה": "Ankara",
    "κωνσταντινουπολ": "İstanbul", "ισταμπουλ": "İstanbul", "istanbul": "İstanbul", "איסטנבול": "İstanbul",
    "φινταν": "Hakan Fidan", "fidan": "Hakan Fidan", "פידאן": "Hakan Fidan",
    "κατεχομεν": "Kıbrıs", "ψευδοκρατ": "Kıbrıs",
    "γαλαζια πατριδα": "Mavi Vatan", "blue homeland": "Mavi Vatan",
}


def guess_category(*texts: str | None) -> str:
    haystack = keywords.normalize(" ".join(t for t in texts if t))
    for slug, words in CATEGORY_RULES:
        if any(w in haystack for w in words):
            return slug
    return "diger"


def lead_paragraphs(text: str, limit: int = LEAD_CHARS) -> str:
    """Metnin başından, paragraf bütünlüğünü bozmadan en fazla `limit` karakter."""
    paragraphs = [p.strip() for p in (text or "").split("\n") if p.strip()]
    out: list[str] = []
    total = 0
    for p in paragraphs:
        if out and total + len(p) > limit:
            break
        out.append(p[:limit])
        total += len(p)
    return "\n".join(out)


def _chunks(text: str, size: int = CHUNK_CHARS) -> list[str]:
    chunks, current = [], ""
    for p in text.split("\n"):
        if current and len(current) + len(p) + 1 > size:
            chunks.append(current)
            current = ""
        current = f"{current}\n{p}" if current else p[:size]
    if current:
        chunks.append(current)
    return chunks


class FreeTranslator:
    name = "free"

    def __init__(self, client: httpx.Client | None = None):
        self.client = client or httpx.Client(timeout=get_settings().request_timeout_seconds)

    def ensure_ready(self) -> None:
        pass

    def translate(self, text: str) -> str:
        if not text.strip():
            return ""
        parts = []
        for chunk in _chunks(text):
            try:
                response = self.client.post(
                    GOOGLE_URL,
                    params={"client": "gtx", "sl": "auto", "tl": "tr", "dt": "t"},
                    data={"q": chunk},
                )
            except httpx.HTTPError as exc:
                raise AIError(f"Çeviri servisine ulaşılamadı: {exc}") from exc
            if response.status_code == 429:
                raise AIFatalError("Ücretsiz çeviri servisi istek sınırına ulaştı; bekleyen haberler sonraki taramada çevrilecek.")
            if response.status_code != 200:
                raise AIError(f"Çeviri servisi hata verdi: HTTP {response.status_code}")
            try:
                data = response.json()
                parts.append("".join(seg[0] for seg in data[0] if seg and seg[0]))
            except (ValueError, TypeError, IndexError) as exc:
                raise AIError("Çeviri servisinden beklenmeyen yanıt") from exc
        return "\n".join(parts)

    def check_relevance(self, title: str, text: str, language: str, categories: dict[str, str]) -> RelevanceResult:
        in_title = bool(keywords.matched_keywords(title))
        hits = keywords.count_occurrences(text)
        relevant = in_title or hits >= 2
        category = guess_category(title, text)
        if category not in categories:
            category = "diger"
        reason = "Başlıkta anahtar kelime var" if in_title else f"Metinde {hits} anahtar kelime"
        return RelevanceResult(relevant, category, reason)

    def rewrite(self, title: str, text: str, language: str, source_name: str) -> RewriteResult:
        title_tr = self.translate(title)
        summary_tr = self.translate(lead_paragraphs(text or ""))
        matched = keywords.matched_keywords(title, text)
        tags = list(dict.fromkeys(KEYWORD_TAGS[k] for k in matched if k in KEYWORD_TAGS))
        return RewriteResult(title_tr=title_tr, summary_tr=summary_tr, key_points=[], tags=tags)
