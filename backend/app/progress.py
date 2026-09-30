"""Süren taramanın canlı durumu: aşama, ilerleme, olay akışı ve iptal isteği.

Tek süreçte tek tarama çalıştığı için bellek içi tek bir nesne yeterlidir; yönetim paneli
/api/admin/progress ile bunu okur.
"""

import threading
from collections import deque
from datetime import datetime, timezone


class ScanCancelled(Exception):
    """Yeni bir tarama başlatıldığı için süren tarama durduruldu."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ScanProgress:
    PHASES = ["Kaynaklar okunuyor", "Haberler çevriliyor"]

    def __init__(self):
        self._lock = threading.Lock()
        self.cancel = threading.Event()
        self._state: dict = {"running": False, "events": []}
        self._events: deque = deque(maxlen=300)

    def start(self, run_id: int, trigger: str) -> None:
        with self._lock:
            self._events.clear()
            self._state = {
                "running": True,
                "run_id": run_id,
                "trigger": trigger,
                "started_at": _now(),
                "finished_at": None,
                "phase": None,
                "phase_index": 0,
                "phase_count": len(self.PHASES),
                "total": 0,
                "done": 0,
                "current": None,
                "note": None,
            }
        self.event("Tarama başladı")

    def phase(self, index: int, total: int) -> None:
        with self._lock:
            self._state.update(phase=self.PHASES[index], phase_index=index + 1, total=total, done=0, current=None)
        self.event(f"{self.PHASES[index]} ({total})")

    def step(self, current: str) -> None:
        with self._lock:
            self._state["current"] = current

    def advance(self) -> None:
        with self._lock:
            self._state["done"] = min(self._state.get("done", 0) + 1, self._state.get("total", 0))

    def event(self, text: str, level: str = "info") -> None:
        with self._lock:
            self._events.append({"at": _now(), "text": text[:300], "level": level})

    def finish(self, note: str | None) -> None:
        self.event(note or "Tarama bitti", "error" if note else "ok")
        with self._lock:
            self._state.update(running=False, finished_at=_now(), current=None, note=note)

    def check_cancel(self) -> None:
        if self.cancel.is_set():
            raise ScanCancelled()

    def snapshot(self) -> dict:
        with self._lock:
            return {**self._state, "events": list(reversed(self._events))}


progress = ScanProgress()
