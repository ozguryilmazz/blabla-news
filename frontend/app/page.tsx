import Link from "next/link";
import { apiGet, ArticlePage, Category, COUNTRY_NAMES, formatDate, Source } from "@/lib/api";

type Search = { [key: string]: string | string[] | undefined };

const FILTER_KEYS = ["q", "country", "category", "source_id", "date_from", "date_to"] as const;

function one(value: string | string[] | undefined): string {
  return Array.isArray(value) ? value[0] ?? "" : value ?? "";
}

export default async function HomePage({ searchParams }: { searchParams: Promise<Search> }) {
  const sp = await searchParams;
  const params = new URLSearchParams();
  for (const key of FILTER_KEYS) {
    const v = one(sp[key]);
    if (v) params.set(key, v);
  }
  const page = Math.max(1, Number(one(sp.page)) || 1);
  params.set("page", String(page));

  const [data, categories, sources] = await Promise.all([
    apiGet<ArticlePage>(`/api/articles?${params}`),
    apiGet<Category[]>("/api/categories"),
    apiGet<Source[]>("/api/sources"),
  ]);
  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));

  const pageLink = (p: number) => {
    const next = new URLSearchParams(params);
    next.set("page", String(p));
    return `/?${next}`;
  };

  return (
    <>
      <form className="filters" method="get">
        <input name="q" placeholder="Ara (Türkçe veya orijinal başlık)" defaultValue={one(sp.q)} />
        <select name="country" defaultValue={one(sp.country)}>
          <option value="">Tüm ülkeler</option>
          <option value="GR">Yunanistan</option>
          <option value="IL">İsrail</option>
        </select>
        <select name="category" defaultValue={one(sp.category)}>
          <option value="">Tüm kategoriler</option>
          {categories.map((c) => (
            <option key={c.slug} value={c.slug}>{c.name}</option>
          ))}
        </select>
        <select name="source_id" defaultValue={one(sp.source_id)}>
          <option value="">Tüm kaynaklar</option>
          {sources.map((s) => (
            <option key={s.id} value={s.id}>{s.name}</option>
          ))}
        </select>
        <label>Başlangıç <input type="date" name="date_from" defaultValue={one(sp.date_from)} /></label>
        <label>Bitiş <input type="date" name="date_to" defaultValue={one(sp.date_to)} /></label>
        <button type="submit">Filtrele</button>
        <Link href="/" className="reset">Temizle</Link>
      </form>

      <p className="result-count">{data.total} haber</p>

      {data.items.length === 0 ? (
        <p className="empty">Bu filtrelerle eşleşen haber yok.</p>
      ) : (
        <ul className="article-list">
          {data.items.map((a) => (
            <li key={a.id} className="article-card">
              <div className="meta">
                <span className={`flag flag-${a.source.country}`}>{COUNTRY_NAMES[a.source.country]}</span>
                <span>{a.source.name}</span>
                {a.category && <span className="chip">{a.category.name}</span>}
                <time>{formatDate(a.published_at)}</time>
              </div>
              <h2><Link href={`/haber/${a.id}`}>{a.title_tr ?? a.title_orig}</Link></h2>
              <p className="orig-title" dir="auto">{a.title_orig}</p>
              <p>{a.excerpt_tr}</p>
            </li>
          ))}
        </ul>
      )}

      {totalPages > 1 && (
        <nav className="pager">
          {page > 1 && <Link href={pageLink(page - 1)}>← Önceki</Link>}
          <span>Sayfa {page} / {totalPages}</span>
          {page < totalPages && <Link href={pageLink(page + 1)}>Sonraki →</Link>}
        </nav>
      )}
    </>
  );
}
