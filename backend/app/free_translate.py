"""Ücretsiz çeviri yöntemi: API anahtarı gerektirmez.

- İlgi kontrolü: anahtar kelime eşleşmesiyle (başlıkta geçiyorsa veya metinde en az iki kez geçiyorsa ilgili)
- Kategori: çok dilli kelime kurallarıyla
- Çeviri: başlık ve haberin ilk paragrafları sırayla şu ücretsiz servislerle çevrilir:
  isteğe bağlı kendi LibreTranslate sunucunuz → Google Translate → MyMemory.
  Sınırına takılan servis o tarama boyunca atlanır; hepsi dolarsa haberler bekler.

Claude yöntemiyle aynı arayüzü (check_relevance, rewrite) sunar, bu yüzden tarama akışı değişmez.
Kalite Claude kadar iyi değildir: birebir makine çevirisidir, özet ve önemli noktalar üretilmez.
"""

import logging
import re
import time

import httpx

from . import keywords
from .ai import AIError, AIFatalError, RelevanceResult, RewriteResult
from .config import get_settings

log = logging.getLogger(__name__)

GOOGLE_URL = "https://translate.googleapis.com/translate_a/single"
MYMEMORY_URL = "https://api.mymemory.translated.net/get"
LEAD_CHARS = 1500  # telif için haberin yalnızca giriş kısmı çevrilir

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


def relevant_lead(text: str) -> str:
    """Giriş bölümü; Türkiye girişte geçmiyorsa, geçtiği ilk paragraf da eklenir ki özet konuyu içersin."""
    lead = lead_paragraphs(text)
    if keywords.is_candidate(lead):
        return lead
    for p in (x.strip() for x in text.split("\n")):
        if p and p not in lead and keywords.is_candidate(p):
            return f"{lead}\n{p[:LEAD_CHARS]}"
    return lead


def _pieces(paragraph: str, fits) -> list[str]:
    """Bir paragrafı `fits` sınırını aşmayan parçalara böler; önce cümle, sonra kelime sınırından."""
    units: list[str] = []
    for sentence in re.split(r"(?<=[.!?;·])\s+", paragraph.strip()):
        if fits(sentence):
            units.append(sentence)
            continue
        for word in sentence.split():
            while not fits(word):  # tek kelime bile sığmıyorsa zorla kes
                cut = len(word) // 2
                while cut > 1 and not fits(word[:cut]):
                    cut //= 2
                units.append(word[:cut])
                word = word[cut:]
            units.append(word)
    chunks: list[str] = []
    for unit in units:
        if chunks and fits(chunks[-1] + " " + unit):
            chunks[-1] += " " + unit
        else:
            chunks.append(unit)
    return chunks


class RateLimited(Exception):
    """Servis günlük/anlık sınırına ulaştı; bu tarama boyunca bir daha denenmez."""


class Provider:
    name = ""

    def fits(self, chunk: str) -> bool:
        raise NotImplementedError

    def translate_chunk(self, client: httpx.Client, chunk: str, source_lang: str) -> str:
        raise NotImplementedError


class GoogleProvider(Provider):
    name = "google"
    max_chars = 900  # küçük istekler Google'ın sınırına daha geç takılır

    def fits(self, chunk: str) -> bool:
        return len(chunk) <= self.max_chars

    def translate_chunk(self, client, chunk, source_lang):
        response = client.get(GOOGLE_URL, params={"client": "gtx", "sl": source_lang or "auto", "tl": "tr", "dt": "t", "q": chunk})
        if response.status_code in (429, 503):
            raise RateLimited(f"HTTP {response.status_code}")
        if response.status_code != 200:
            raise AIError(f"HTTP {response.status_code}")
        data = response.json()
        return "".join(seg[0] for seg in data[0] if seg and seg[0])


class MyMemoryProvider(Provider):
    name = "mymemory"
    max_bytes = 480  # servis istek başına 500 bayt kabul ediyor

    def __init__(self, email: str = ""):
        self.email = email

    def fits(self, chunk: str) -> bool:
        return len(chunk.encode("utf-8")) <= self.max_bytes

    def translate_chunk(self, client, chunk, source_lang):
        params = {"q": chunk, "langpair": f"{source_lang or 'en'}|tr"}
        if self.email:
            params["de"] = self.email
        response = client.get(MYMEMORY_URL, params=params)
        if response.status_code in (429, 403):
            raise RateLimited(f"HTTP {response.status_code}")
        if response.status_code != 200:
            raise AIError(f"HTTP {response.status_code}")
        data = response.json()
        text = (data.get("responseData") or {}).get("translatedText") or ""
        status = str(data.get("responseStatus", 200))
        if data.get("quotaFinished") or status in ("429", "403") or "MYMEMORY WARNING" in text.upper():
            raise RateLimited(data.get("responseDetails") or "günlük sınır doldu")
        if status != "200":
            raise AIError(data.get("responseDetails") or f"durum {status}")
        return text


class LibreTranslateProvider(Provider):
    name = "libretranslate"
    max_chars = 2000

    def __init__(self, url: str, api_key: str = ""):
        self.url = url.rstrip("/")
        self.api_key = api_key

    def fits(self, chunk: str) -> bool:
        return len(chunk) <= self.max_chars

    def translate_chunk(self, client, chunk, source_lang):
        body = {"q": chunk, "source": source_lang or "auto", "target": "tr", "format": "text"}
        if self.api_key:
            body["api_key"] = self.api_key
        response = client.post(f"{self.url}/translate", json=body)
        if response.status_code == 429:
            raise RateLimited("HTTP 429")
        if response.status_code != 200:
            raise AIError(f"HTTP {response.status_code}")
        return response.json()["translatedText"]


def default_providers() -> list[Provider]:
    s = get_settings()
    providers: list[Provider] = []
    if s.libretranslate_url:  # kendi sunucunuz: sınırsız, bu yüzden ilk sırada
        providers.append(LibreTranslateProvider(s.libretranslate_url, s.libretranslate_api_key))
    providers += [GoogleProvider(), MyMemoryProvider(s.mymemory_email)]
    return providers


class FreeTranslator:
    name = "free"

    def __init__(self, client: httpx.Client | None = None, providers: list[Provider] | None = None, delay: float | None = None):
        s = get_settings()
        self.client = client or httpx.Client(timeout=s.request_timeout_seconds, follow_redirects=True)
        self.providers = providers if providers is not None else default_providers()
        self.delay = s.free_translate_delay_seconds if delay is None else delay
        self.exhausted: set[str] = set()  # sınıra takılan servisler bu taramada atlanır
        self._last_call = 0.0

    def ensure_ready(self) -> None:
        pass

    def _wait(self) -> None:
        pause = self.delay - (time.monotonic() - self._last_call)
        if pause > 0:
            time.sleep(pause)
        self._last_call = time.monotonic()

    def _translate_with(self, provider: Provider, text: str, source_lang: str) -> str:
        paragraphs = []
        for paragraph in text.split("\n"):
            if not paragraph.strip():
                continue
            parts = []
            for chunk in _pieces(paragraph, provider.fits):
                self._wait()
                try:
                    parts.append(provider.translate_chunk(self.client, chunk, source_lang))
                except httpx.HTTPError as exc:
                    raise AIError(f"ulaşılamadı: {exc}") from exc
                except (ValueError, TypeError, IndexError, KeyError) as exc:
                    raise AIError("beklenmeyen yanıt") from exc
            paragraphs.append(" ".join(parts))
        return "\n".join(paragraphs)

    def translate(self, text: str, source_lang: str = "auto") -> str:
        if not text.strip():
            return ""
        errors = []
        for provider in self.providers:
            if provider.name in self.exhausted:
                continue
            try:
                return self._translate_with(provider, text, source_lang)
            except RateLimited as exc:
                log.warning("%s çeviri sınırına ulaştı: %s", provider.name, exc)
                self.exhausted.add(provider.name)
                errors.append(f"{provider.name}: sınır doldu")
            except AIError as exc:
                log.warning("%s çeviri hatası: %s", provider.name, exc)
                errors.append(f"{provider.name}: {exc}")
        if all(p.name in self.exhausted for p in self.providers):
            raise AIFatalError(
                "Ücretsiz çeviri servislerinin hepsi istek sınırına ulaştı; bekleyen haberler sonraki taramada çevrilecek."
            )
        raise AIError("Çeviri yapılamadı (" + "; ".join(errors) + ")")

    def check_relevance(self, title: str, text: str, language: str, categories: dict[str, str]) -> RelevanceResult:
        """Haberin konusu Türkiye mi? Sayfa metninin sonundaki "ilgili haberler" bağlantıları
        yanıltmasın diye asıl ağırlık başlığa ve okurun gördüğü giriş bölümüne verilir."""
        in_title = bool(keywords.matched_keywords(title))
        lead_hits = keywords.count_occurrences(lead_paragraphs(text or ""))
        total_hits = keywords.count_occurrences(text)
        relevant = in_title or lead_hits >= 2 or (lead_hits >= 1 and total_hits >= 3)
        category = guess_category(title, text)
        if category not in categories:
            category = "diger"
        if in_title:
            reason = "Başlıkta anahtar kelime var"
        else:
            reason = f"Girişte {lead_hits}, metnin tamamında {total_hits} anahtar kelime"
        return RelevanceResult(relevant, category, reason)

    def rewrite(self, title: str, text: str, language: str, source_name: str) -> RewriteResult:
        title_tr = self.translate(title, language)
        summary_tr = self.translate(relevant_lead(text or ""), language)
        matched = keywords.matched_keywords(title, text)
        tags = list(dict.fromkeys(KEYWORD_TAGS[k] for k in matched if k in KEYWORD_TAGS))
        return RewriteResult(title_tr=title_tr, summary_tr=summary_tr, key_points=[], tags=tags)
