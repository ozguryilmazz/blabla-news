import json

import anthropic
import httpx2 as httpx

from app.ai import ClaudeAI
from app.collector import make_excerpt, parse_feed

RSS = """<?xml version="1.0"?><rss version="2.0"><channel><title>T</title>
<item><title>Ερντογάν: νέες δηλώσεις</title><link>https://ex.gr/a</link>
<description>&lt;p&gt;Ο Τούρκος πρόεδρος &lt;b&gt;είπε&lt;/b&gt;&lt;/p&gt;</description>
<pubDate>Sun, 20 Sep 2026 10:00:00 GMT</pubDate></item>
<item><title></title><link>https://ex.gr/empty</link></item>
</channel></rss>"""


def test_parse_feed_cleans_html_and_skips_empty():
    entries = parse_feed(RSS)
    assert len(entries) == 1
    assert entries[0].summary == "Ο Τούρκος πρόεδρος είπε"
    assert entries[0].published_at.day == 20


def test_make_excerpt_cuts_on_word():
    assert make_excerpt("kelime " * 100, 20).endswith("…")


def _fake_client(payloads, seen):
    def handler(request: httpx.Request):
        body = json.loads(request.content)
        seen.append(body)
        text = json.dumps(payloads.pop(0))
        return httpx.Response(200, json={
            "id": "msg_1", "type": "message", "role": "assistant", "model": body["model"],
            "content": [{"type": "text", "text": text}],
            "stop_reason": "end_turn", "stop_sequence": None,
            "usage": {"input_tokens": 1200, "output_tokens": 300},
        })

    return anthropic.Anthropic(api_key="test", http_client=httpx.Client(transport=httpx.MockTransport(handler)))


def test_claude_ai_requests_and_parsing():
    seen = []
    client = _fake_client([
        {"relevant": True, "category": "bilinmeyen", "reason": "Türkiye cumhurbaşkanı"},
        {"title_tr": "Başlık", "summary_tr": "Özet", "key_points": ["a"], "tags": ["b"]},
    ], seen)
    ai = ClaudeAI(client=client)

    rel = ai.check_relevance("Erdogan", "metin", "en", {"diger": "Diğer", "kibris": "Kıbrıs"})
    assert rel.relevant and rel.category == "diger"  # listede olmayan kategori "diğer"e düşer
    assert rel.usage.model == "claude-haiku-4-5"

    rw = ai.rewrite("Erdogan", "metin", "en", "Times of Israel")
    assert rw.title_tr == "Başlık" and rw.usage.cost_usd > 0

    assert seen[0]["model"] == "claude-haiku-4-5"
    assert seen[1]["model"] == "claude-sonnet-5"
    assert seen[1]["thinking"] == {"type": "disabled"}
    assert seen[0]["output_config"]["format"]["type"] == "json_schema"
