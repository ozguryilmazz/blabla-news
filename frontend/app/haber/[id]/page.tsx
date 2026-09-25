import Link from "next/link";
import { notFound } from "next/navigation";
import { ArticleDetail, COUNTRY_NAMES, formatDate, LANGUAGE_NAMES } from "@/lib/api";

const API_URL = process.env.API_URL || "http://localhost:8000";

async function getArticle(id: string): Promise<ArticleDetail | null> {
  const res = await fetch(`${API_URL}/api/articles/${encodeURIComponent(id)}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export default async function ArticlePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const a = await getArticle(id);
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
          <h1>{a.title_orig}</h1>
          {a.excerpt_orig && <p className="excerpt">{a.excerpt_orig}</p>}
          <p dir="ltr">
            <a href={a.url} target="_blank" rel="noopener noreferrer" className="source-link">
              Haberin tamamı: {a.source.name} ↗
            </a>
          </p>
        </section>

        <section className="pane pane-tr" lang="tr">
          <h3 className="pane-label">Türkçe özet</h3>
          <h1>{a.title_tr}</h1>
          {a.summary_tr?.split("\n").filter(Boolean).map((para, i) => <p key={i}>{para}</p>)}
          {a.key_points_tr.length > 0 && (
            <>
              <h4>Öne çıkanlar</h4>
              <ul>{a.key_points_tr.map((p, i) => <li key={i}>{p}</li>)}</ul>
            </>
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
