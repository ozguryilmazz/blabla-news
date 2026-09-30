import Link from "next/link";
import { notFound } from "next/navigation";
import NewsImage from "@/components/NewsImage";
import { apiGet, ArticleDetail, COUNTRY_NAMES, formatDate, LANGUAGE_NAMES } from "@/lib/api";
import { Highlight } from "@/lib/highlight";

const API_URL = process.env.API_URL || "http://localhost:8000";

async function getArticle(id: string): Promise<ArticleDetail | null> {
  const res = await fetch(`${API_URL}/api/articles/${encodeURIComponent(id)}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export default async function ArticlePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [a, terms] = await Promise.all([getArticle(id), apiGet<string[]>("/api/highlight-terms")]);
  if (!a) notFound();

  const rtl = a.source.language === "he";

  return (
    <article>
      <p><Link href="/">← Tüm haberler</Link></p>
      <div className="meta">
        <span className={`flag flag-${a.source.country}`}>{COUNTRY_NAMES[a.source.country]}</span>
        <span>{a.source.name}</span>
        {a.category && <span className="chip">{a.category.name}</span>}
        <time>{formatDate(a.published_at)}</time>
      </div>

      <div className="side-by-side">
        <section className="pane pane-orig" dir={rtl ? "rtl" : "ltr"} lang={a.source.language}>
          <h3 className="pane-label" dir="ltr">Orijinal ({LANGUAGE_NAMES[a.source.language] ?? a.source.language})</h3>
          <NewsImage src={a.image_url} className="detail-image" />
          <h1><Highlight text={a.title_orig} terms={terms} /></h1>
          {a.excerpt_orig && <p className="excerpt"><Highlight text={a.excerpt_orig} terms={terms} /></p>}
          <p dir="ltr">
            <a href={a.url} target="_blank" rel="noopener noreferrer" className="source-link">
              Haberin tamamı: {a.source.name} ↗
            </a>
          </p>
        </section>

        <section className="pane pane-tr" lang="tr">
          <h3 className="pane-label">{a.translator === "free" ? "Türkçe çeviri (giriş bölümü)" : "Türkçe özet"}</h3>
          <h1><Highlight text={a.title_tr} terms={terms} /></h1>
          {a.summary_tr?.split("\n").filter(Boolean).map((para, i) => <p key={i}><Highlight text={para} terms={terms} /></p>)}
          {a.key_points_tr.length > 0 && (
            <>
              <h4>Öne çıkanlar</h4>
              <ul>{a.key_points_tr.map((p, i) => <li key={i}><Highlight text={p} terms={terms} /></li>)}</ul>
            </>
          )}
          {a.translator === "free" && (
            <p className="muted small">Bu metin otomatik makine çevirisidir.</p>
          )}
          {a.tags.length > 0 && (
            <div className="tags">
              {a.tags.map((t) => (
                <Link key={t} href={`/?q=${encodeURIComponent(t)}`} className="chip">{t}</Link>
              ))}
            </div>
          )}
        </section>
      </div>
    </article>
  );
}
