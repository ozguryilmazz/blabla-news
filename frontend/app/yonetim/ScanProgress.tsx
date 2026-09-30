"use client";

import { useEffect, useState } from "react";

export type Progress = {
  running: boolean;
  run_id?: number;
  started_at?: string;
  finished_at?: string | null;
  phase?: string | null;
  phase_index?: number;
  phase_count?: number;
  total?: number;
  done?: number;
  current?: string | null;
  note?: string | null;
  events: { at: string; text: string; level: "info" | "ok" | "error" }[];
};

const time = (v: string) => new Date(v).toLocaleTimeString("tr-TR", { timeZone: "Europe/Istanbul" });

function elapsed(from?: string, to?: string | null): string {
  if (!from) return "";
  const s = Math.max(0, Math.round(((to ? new Date(to) : new Date()).getTime() - new Date(from).getTime()) / 1000));
  return s < 60 ? `${s} sn` : `${Math.floor(s / 60)} dk ${s % 60} sn`;
}

/** Süren taramanın aşaması, ilerleme çubuğu ve canlı olay akışı. Tarama sürerken sık yenilenir. */
export default function ScanProgress({ fetchProgress, onFinished }: { fetchProgress: () => Promise<Progress>; onFinished: () => void }) {
  const [p, setP] = useState<Progress | null>(null);

  useEffect(() => {
    let stop = false;
    let wasRunning = false;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      try {
        const next = await fetchProgress();
        if (stop) return;
        setP(next);
        if (wasRunning && !next.running) onFinished();
        wasRunning = next.running;
      } catch {}
      if (!stop) timer = setTimeout(tick, wasRunning ? 1500 : 5000);
    };
    tick();
    return () => {
      stop = true;
      clearTimeout(timer);
    };
  }, [fetchProgress, onFinished]);

  if (!p || !p.started_at) return <p className="muted small">Henüz tarama yapılmadı.</p>;

  const total = p.total ?? 0;
  const done = p.done ?? 0;
  // İki aşama tek çubukta: okuma ilk yarı, çeviri ikinci yarı
  const phaseShare = 100 / (p.phase_count || 2);
  const within = total ? (done / total) * phaseShare : 0;
  const percent = p.running ? Math.min(99, ((p.phase_index || 1) - 1) * phaseShare + within) : 100;

  return (
    <div className="scan-progress">
      <div className="scan-progress-head">
        <strong>{p.running ? `${p.phase_index}/${p.phase_count}: ${p.phase ?? "Başlıyor"}` : p.note ? "Tarama bitti (not var)" : "Tarama bitti"}</strong>
        <span className="muted small">
          {p.running && total > 0 && `${done}/${total} · `}
          {elapsed(p.started_at, p.finished_at)}
        </span>
      </div>
      <div className="bar" role="progressbar" aria-valuenow={Math.round(percent)} aria-valuemin={0} aria-valuemax={100}>
        <div className={`bar-fill${p.running ? " live" : p.note ? " warn" : ""}`} style={{ width: `${percent}%` }} />
      </div>
      {p.running && p.current && <p className="scan-current small" dir="auto">Şu an: {p.current}</p>}
      <ol className="scan-events">
        {p.events.map((e, i) => (
          <li key={`${e.at}-${i}`} className={`ev-${e.level}`}>
            <time>{time(e.at)}</time> <span dir="auto">{e.text}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}
