// Sunucu tarafı bileşenler arka uca doğrudan bağlanır
const API_URL = process.env.API_URL || "http://localhost:8000";

export type Source = { id: number; name: string; country: "GR" | "IL"; language: string };
export type Category = { id: number; slug: string; name: string; scan_enabled: boolean };

export type ArticleSummary = {
  id: number;
  url: string;
  published_at: string | null;
  title_orig: string;
  title_tr: string | null;
  excerpt_tr: string;
  source: Source;
  category: Category | null;
};

export type ArticlePage = { items: ArticleSummary[]; total: number; page: number; page_size: number };

export type ArticleDetail = {
  id: number;
  url: string;
  published_at: string | null;
  title_orig: string;
  excerpt_orig: string | null;
  title_tr: string | null;
  summary_tr: string | null;
  key_points_tr: string[];
  tags: string[];
  translator: "claude" | "free" | null;
  source: Source;
  category: Category | null;
};

export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
  return res.json() as Promise<T>;
}

export const COUNTRY_NAMES: Record<string, string> = { GR: "Yunanistan", IL: "İsrail" };
export const LANGUAGE_NAMES: Record<string, string> = { el: "Yunanca", he: "İbranice", en: "İngilizce" };

export function formatDate(value: string | null): string {
  if (!value) return "";
  return new Date(value).toLocaleString("tr-TR", { dateStyle: "medium", timeStyle: "short", timeZone: "Europe/Istanbul" });
}
