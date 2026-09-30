import Link from "next/link";
import CountryFlag from "@/components/CountryFlag";
import NewsImage from "@/components/NewsImage";
import { Highlight } from "@/lib/highlight";
import { apiGet, ArticlePage, Category, COUNTRY_NAMES, formatDate, Source } from "@/lib/api";

type Search = { [key: string]: string | string[] | undefined };

// Satırda 3 kutu olduğu için sayfa boyu 3'ün katı
const PAGE_SIZE = 18;

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
  params.set("page_size", String(PAGE_SIZE));

  const [data, categories, sources, terms] = await Promise.all([
    apiGet<ArticlePage>(`/api/articles?${params}`),
    apiGet<Category[]>("/api/categories"),
    apiGet<Source[]>("/api/sources"),
    apiGet<string[]>("/api/highlight-terms"),
  ]);
  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));

  const pageLink = (p: number) => {
    const next = new URLSearchParams(params);
    next.delete("page_size");
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
        <ul className="article-grid">
          {data.items.map((a) => (
            <li key={a.id} className="article-box">
              <div className={`box-head box-head-${a.source.country}`}>
                <CountryFlag country={a.source.country} />
                <span className="box-country">{COUNTRY_NAMES[a.source.country]}</span>
              </div>
              <div className="box-meta">
                {a.category && <span className="chip">{a.category.name}</span>}
                <time>{formatDate(a.published_at)}</time>
                <a className="box-source" href={a.url} target="_blank" rel="noopener noreferrer">
                  Kaynağa git: {a.source.name} ↗
                </a>
              </div>
              <Link href={`/haber/${a.id}`} className="box-image-link" tabIndex={-1}>
                <NewsImage src={a.image_url} className="box-image" />
              </Link>
              <div className="box-body">
                <h2><Link href={`/haber/${a.id}`}><Highlight text={a.title_tr ?? a.title_orig} terms={terms} /></Link></h2>
                <p className="orig-title" dir="auto"><Highlight text={a.title_orig} terms={terms} /></p>
                <p className="box-excerpt"><Highlight text={a.excerpt_tr} terms={terms} /></p>
              </div>
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
