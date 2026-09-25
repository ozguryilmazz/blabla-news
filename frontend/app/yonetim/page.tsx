"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";

type Budget = { ai_budget_eur: number; ai_spent_eur: number; monthly_budget_eur: number; server_cost_eur: number; ratio: number; warning: boolean; exhausted: boolean };
type Run = { id: number; started_at: string; finished_at: string | null; trigger: string; new_items: number; published: number; errors: number; note: string | null };
type Status = { paused: boolean; scan_running: boolean; interval_minutes: number; budget: Budget; counts: Record<string, number>; recent_runs: Run[] };
type AdminSource = { id: number; name: string; country: string; language: string; url: string; active: boolean; last_checked_at: string | null; last_error: string | null };
type Category = { id: number; slug: string; name: string; scan_enabled: boolean };

const STATUS_NAMES: Record<string, string> = {
  published: "Yayında",
  pending: "Bekliyor",
  irrelevant: "İlgisiz",
  skipped_category: "Kategori kapalı",
  failed: "Hatalı",
};

const PASSWORD_KEY = "haber-admin-password";

function readStoredPassword(): string {
  try {
    return sessionStorage.getItem(PASSWORD_KEY) ?? "";
  } catch {
    return "";
  }
}

const fmt = (v: string | null) => (v ? new Date(v).toLocaleString("tr-TR", { timeZone: "Europe/Istanbul" }) : "—");

export default function AdminPage() {
  const [password, setPassword] = useState("");
  const [authed, setAuthed] = useState(false);
  const [status, setStatus] = useState<Status | null>(null);
  const [sources, setSources] = useState<AdminSource[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [message, setMessage] = useState("");

  const call = useCallback(
    async (path: string, init: RequestInit = {}, pw = password) => {
      const res = await fetch(path, {
        ...init,
        headers: { "Content-Type": "application/json", "X-Admin-Password": pw, ...(init.headers ?? {}) },
      });
      if (res.status === 401) {
        setAuthed(false);
        throw new Error("Şifre hatalı");
      }
      if (!res.ok) throw new Error((await res.json().catch(() => ({}))).detail ?? `Hata ${res.status}`);
      return res.json();
    },
    [password],
  );

  const load = useCallback(
    async (pw = password) => {
      const [s, src, cats] = await Promise.all([
        call("/api/admin/status", {}, pw),
        call("/api/admin/sources", {}, pw),
        fetch("/api/categories").then((r) => r.json()),
      ]);
      setStatus(s);
      setSources(src);
      setCategories(cats);
      setAuthed(true);
    },
    [call, password],
  );

  useEffect(() => {
    const stored = readStoredPassword();
    if (stored) {
      setPassword(stored);
      load(stored).catch(() => {});
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (!authed) return;
    const t = setInterval(() => load().catch(() => {}), 10000);
    return () => clearInterval(t);
  }, [authed, load]);

  const run = async (fn: () => Promise<unknown>, ok: string) => {
    try {
      await fn();
      setMessage(ok);
      await load();
    } catch (e) {
      setMessage((e as Error).message);
    }
  };

  const login = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await load(password);
      try {
        sessionStorage.setItem(PASSWORD_KEY, password);
      } catch {}
      setMessage("");
    } catch (err) {
      setMessage((err as Error).message);
    }
  };

  const addSource = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = e.currentTarget;
    const data = Object.fromEntries(new FormData(form));
    await run(() => call("/api/admin/sources", { method: "POST", body: JSON.stringify(data) }), "Kaynak eklendi");
    form.reset();
  };

  if (!authed) {
    return (
      <form className="login" onSubmit={login}>
        <h1>Yönetim paneli</h1>
        <input type="password" placeholder="Yönetici şifresi" value={password} onChange={(e) => setPassword(e.target.value)} />
        <button type="submit">Giriş</button>
        {message && <p className="error">{message}</p>}
      </form>
    );
  }

  const b = status?.budget;

  return (
    <div className="admin">
      <h1>Yönetim paneli</h1>
      {message && <p className="notice">{message}</p>}

      <section className="panel">
        <h2>Tarama</h2>
        <p>
          Otomatik tarama: <strong>{status?.paused ? "Durduruldu" : `Açık (${status?.interval_minutes} dakikada bir)`}</strong>
          {status?.scan_running && <span className="chip">Tarama sürüyor…</span>}
        </p>
        <div className="actions">
          <button disabled={status?.scan_running} onClick={() => run(() => call("/api/admin/scan", { method: "POST" }), "Tarama başlatıldı")}>Şimdi tara</button>
          {status?.paused ? (
            <button onClick={() => run(() => call("/api/admin/resume", { method: "POST" }), "Otomatik tarama açıldı")}>Devam ettir</button>
          ) : (
            <button onClick={() => run(() => call("/api/admin/pause", { method: "POST" }), "Otomatik tarama durduruldu")}>Durdur</button>
          )}
        </div>
        <p className="counts">
          {Object.entries(status?.counts ?? {}).map(([k, v]) => (
            <span key={k} className="chip">{STATUS_NAMES[k] ?? k}: {v}</span>
          ))}
        </p>
      </section>

      {b && (
        <section className="panel">
          <h2>Bütçe (bu ay)</h2>
          <p>
            Yapay zekâ: <strong>{b.ai_spent_eur.toFixed(2)} €</strong> / {b.ai_budget_eur.toFixed(2)} €
            <span className="muted"> (toplam sınır {b.monthly_budget_eur} €, sunucu için {b.server_cost_eur} € ayrıldı)</span>
          </p>
          <div className="bar"><div className={`bar-fill ${b.exhausted ? "bad" : b.warning ? "warn" : ""}`} style={{ width: `${Math.min(100, b.ratio * 100)}%` }} /></div>
          {b.exhausted && <p className="error">Bütçe doldu: haberler toplanıyor, Türkçeleştirme gelecek ay devam edecek.</p>}
          {!b.exhausted && b.warning && <p className="warn-text">Bütçe sınırına yaklaşıldı.</p>}
        </section>
      )}

      <section className="panel">
        <h2>Taranacak kategoriler</h2>
        <p className="muted">İşaretli olmayan kategorilerdeki haberler Türkçeleştirilmez ve yayınlanmaz.</p>
        <div className="checks">
          {categories.map((c) => (
            <label key={c.id}>
              <input
                type="checkbox"
                checked={c.scan_enabled}
                onChange={(e) => run(() => call(`/api/admin/categories/${c.id}`, { method: "PATCH", body: JSON.stringify({ scan_enabled: e.target.checked }) }), "Kategori güncellendi")}
              />
              {c.name}
            </label>
          ))}
        </div>
      </section>

      <section className="panel">
        <h2>Kaynaklar</h2>
        <div className="table-wrap">
          <table>
            <thead>
              <tr><th>Ad</th><th>Ülke</th><th>Dil</th><th>Son kontrol</th><th>Son hata</th><th>Durum</th></tr>
            </thead>
            <tbody>
              {sources.map((s) => (
                <tr key={s.id} className={s.active ? "" : "inactive"}>
                  <td><a href={s.url} target="_blank" rel="noopener noreferrer">{s.name}</a></td>
                  <td>{s.country}</td>
                  <td>{s.language}</td>
                  <td>{fmt(s.last_checked_at)}</td>
                  <td className="error-cell">{s.last_error ?? ""}</td>
                  <td>
                    <button onClick={() => run(() => call(`/api/admin/sources/${s.id}`, { method: "PATCH", body: JSON.stringify({ active: !s.active }) }), "Kaynak güncellendi")}>
                      {s.active ? "Kapat" : "Aç"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <form className="add-source" onSubmit={addSource}>
          <input name="name" placeholder="Kaynak adı" required />
          <select name="country" required defaultValue="GR"><option value="GR">Yunanistan</option><option value="IL">İsrail</option></select>
          <select name="language" required defaultValue="el"><option value="el">Yunanca</option><option value="he">İbranice</option><option value="en">İngilizce</option></select>
          <input name="url" type="url" placeholder="RSS adresi" required />
          <button type="submit">Kaynak ekle</button>
        </form>
      </section>

      <section className="panel">
        <h2>Son taramalar</h2>
        <div className="table-wrap">
          <table>
            <thead><tr><th>Başlangıç</th><th>Tür</th><th>Yeni aday</th><th>Yayınlanan</th><th>Hata</th><th>Not</th></tr></thead>
            <tbody>
              {status?.recent_runs.map((r) => (
                <tr key={r.id}>
                  <td>{fmt(r.started_at)}</td>
                  <td>{r.trigger === "manual" ? "Manuel" : "Otomatik"}</td>
                  <td>{r.new_items}</td>
                  <td>{r.published}</td>
                  <td>{r.errors}</td>
                  <td>{r.finished_at ? r.note ?? "" : "Sürüyor…"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
