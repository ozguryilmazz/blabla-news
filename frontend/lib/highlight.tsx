import { Fragment, ReactNode } from "react";

// Arka uçtaki keywords.normalize ile aynı: küçük harf, aksansız. Her karakter ayrı normalize edilir
// ki normalize metindeki konum orijinal metne geri eşlenebilsin.
function normalizeWithMap(text: string): { norm: string; map: number[] } {
  let norm = "";
  const map: number[] = [];
  for (let i = 0; i < text.length; i++) {
    const n = text[i].normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();
    for (const ch of n) {
      norm += ch;
      map.push(i);
    }
  }
  return { norm, map };
}

const LETTER = /[\p{L}\p{N}'’]/u;

/** Türkiye ile ilgili kelimeleri (kök eşleşmesi, kelimenin tamamı) kırmızı kalın gösterir. */
export function Highlight({ text, terms }: { text: string | null | undefined; terms: string[] }): ReactNode {
  if (!text) return null;
  if (terms.length === 0) return text;
  const { norm, map } = normalizeWithMap(text);
  const ranges: [number, number][] = [];
  for (const term of terms) {
    let from = 0;
    for (let at = norm.indexOf(term, from); at !== -1; at = norm.indexOf(term, from)) {
      let start = map[at];
      let end = map[at + term.length - 1] + 1;
      while (start > 0 && LETTER.test(text[start - 1])) start--;
      while (end < text.length && LETTER.test(text[end]) && !"'’".includes(text[end])) end++;
      ranges.push([start, end]);
      from = at + term.length;
    }
  }
  if (ranges.length === 0) return text;
  ranges.sort((a, b) => a[0] - b[0]);
  const merged: [number, number][] = [];
  for (const r of ranges) {
    const last = merged[merged.length - 1];
    if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]);
    else merged.push([...r]);
  }
  const out: ReactNode[] = [];
  let pos = 0;
  merged.forEach(([s, e], i) => {
    if (s > pos) out.push(text.slice(pos, s));
    out.push(<strong key={i} className="kw">{text.slice(s, e)}</strong>);
    pos = e;
  });
  if (pos < text.length) out.push(text.slice(pos));
  return <Fragment>{out}</Fragment>;
}
