"""Yapay zekâ adımları: ucuz modelle ilgi kontrolü, güçlü modelle Türkçe yeniden yazım."""

from dataclasses import dataclass, field

import anthropic
from pydantic import BaseModel, Field

from .budget import cost_usd
from .config import get_settings

RELEVANCE_CHARS = 2000
REWRITE_CHARS = 15000


class AIError(Exception):
    def __init__(self, message: str, usage: "Usage | None" = None):
        super().__init__(message)
        self.usage = usage  # başarısız ama ücretlendirilmiş çağrılar da bütçeye yazılır


@dataclass
class Usage:
    model: str
    purpose: str
    input_tokens: int
    output_tokens: int

    @property
    def cost_usd(self) -> float:
        return cost_usd(self.model, self.input_tokens, self.output_tokens)


@dataclass
class RelevanceResult:
    relevant: bool
    category: str
    reason: str
    usage: Usage | None = None


@dataclass
class RewriteResult:
    title_tr: str
    summary_tr: str
    key_points: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    usage: Usage | None = None


class _RelevanceOut(BaseModel):
    relevant: bool = Field(description="Haber gerçekten Türkiye ile ilgili mi")
    category: str = Field(description="Verilen listeden tek bir kategori kısa adı")
    reason: str = Field(description="Tek cümlelik Türkçe gerekçe")


class _RewriteOut(BaseModel):
    title_tr: str
    summary_tr: str
    key_points: list[str]
    tags: list[str]


RELEVANCE_SYSTEM = """Sen Yunan ve İsrail basınını izleyen bir haber analistisin.
Sana bir haberin başlığı ve metninin başı verilecek. Haberin Türkiye ile doğrudan ilgili olup olmadığına karar ver:
Türkiye devleti, hükümeti, ordusu, ekonomisi, vatandaşları, Türkiye'nin taraf olduğu anlaşmazlıklar (Ege, Kıbrıs, Doğu Akdeniz vb.) veya Türkiye'nin belirgin bir rol oynadığı bölgesel gelişmeler ilgili sayılır.
Türkiye'nin yalnızca geçerken anıldığı, hindi (turkey) gibi eş sesli kelimeler veya Türk menşeli olup haberle ilgisiz ayrıntılar ilgili sayılmaz.
İlgiliyse, haberi verilen kategorilerden en uygun olanına ata."""

REWRITE_SYSTEM = """Sen Yunan ve İsrail basınındaki Türkiye haberlerini Türk okuyuculara aktaran bir editörsün.
Haberi birebir çevirme. Kendi cümlelerinle, Türkçe olarak yeniden yaz:
- title_tr: Haberin özünü veren, kaynağın başlığını kelimesi kelimesine çevirmeyen, tarafsız bir Türkçe başlık.
- summary_tr: 150-300 kelimelik geniş bir özet. Kim, ne, nerede, ne zaman, neden sorularını yanıtla. Kaynağın iddialarını ve görüşlerini "habere göre", "gazeteye göre" gibi ifadelerle kaynağa atfet; kendi yorumunu ekleme. Uzun doğrudan alıntı yapma.
- key_points: 3-5 maddelik önemli noktalar.
- tags: 3-6 kısa Türkçe etiket (kişi, kurum, yer, konu).
Özel isimleri Türkçede yerleşik yazımlarıyla kullan (ör. Miçotakis, Netanyahu, Atina, Kudüs)."""


class ClaudeAI:
    def __init__(self, client: anthropic.Anthropic | None = None):
        s = get_settings()
        self.client = client or anthropic.Anthropic(
            api_key=s.anthropic_api_key or None, timeout=120.0, max_retries=2
        )
        self.relevance_model = s.relevance_model
        self.rewrite_model = s.rewrite_model

    def _parse(self, *, model: str, purpose: str, system: str, content: str, schema, max_tokens: int, **extra):
        try:
            response = self.client.messages.parse(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": content}],
                output_format=schema,
                **extra,
            )
        except anthropic.APIError as exc:
            raise AIError(f"{purpose}: {exc}") from exc

        usage = Usage(model, purpose, response.usage.input_tokens, response.usage.output_tokens)
        if response.stop_reason != "end_turn" or response.parsed_output is None:
            raise AIError(f"{purpose}: beklenmeyen yanıt ({response.stop_reason})", usage)
        return response.parsed_output, usage

    def check_relevance(self, title: str, text: str, language: str, categories: dict[str, str]) -> RelevanceResult:
        category_list = "\n".join(f"- {slug}: {name}" for slug, name in categories.items())
        content = (
            f"Kategoriler:\n{category_list}\n\n"
            f"Haberin dili: {language}\nBaşlık: {title}\n\nMetnin başı:\n{(text or '')[:RELEVANCE_CHARS]}"
        )
        out, usage = self._parse(
            model=self.relevance_model,
            purpose="relevance",
            system=RELEVANCE_SYSTEM,
            content=content,
            schema=_RelevanceOut,
            max_tokens=512,
        )
        category = out.category if out.category in categories else "diger"
        return RelevanceResult(out.relevant, category, out.reason, usage)

    def rewrite(self, title: str, text: str, language: str, source_name: str) -> RewriteResult:
        content = (
            f"Kaynak: {source_name}\nDil: {language}\nOrijinal başlık: {title}\n\n"
            f"Haber metni:\n{(text or title)[:REWRITE_CHARS]}"
        )
        out, usage = self._parse(
            model=self.rewrite_model,
            purpose="rewrite",
            system=REWRITE_SYSTEM,
            content=content,
            schema=_RewriteOut,
            max_tokens=4000,
            # Düz yeniden yazım görevi: düşünme kapalı, maliyet öngörülebilir kalır
            thinking={"type": "disabled"},
        )
        return RewriteResult(out.title_tr, out.summary_tr, out.key_points, out.tags, usage)
