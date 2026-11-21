import { useEffect, useState } from "react";
import { API_BASE } from "../services/api.js";

const newId = () =>
  window.crypto?.randomUUID?.() || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;

/**
 * Tells the desktop app this window is still open, so it can shut itself down once every
 * window is closed (see backend/lifecycle.py). Shows a notice if the app has stopped.
 */
export default function SessionKeeper() {
  const [stopped, setStopped] = useState(false);

  useEffect(() => {
    if (import.meta.env.DEV) return undefined; // the dev server never shuts down
    const page = newId();
    const body = JSON.stringify({ page });
    let autoClose = false;

    const beat = () =>
      fetch(`${API_BASE}/session/heartbeat`, {
        method: "POST", headers: { "Content-Type": "application/json" }, body,
      })
        .then((r) => r.json())
        .then((d) => { autoClose = !!d.auto_close; setStopped(false); })
        .catch(() => { if (autoClose) setStopped(true); });
    const bye = () => navigator.sendBeacon?.(`${API_BASE}/session/bye`, new Blob([body], { type: "application/json" }));
    const onVisible = () => document.visibilityState === "visible" && beat();

    beat();
    const timer = setInterval(beat, 5000);
    document.addEventListener("visibilitychange", onVisible);
    window.addEventListener("pagehide", bye);
    window.addEventListener("pageshow", beat); // coming back from the back/forward cache
    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
      window.removeEventListener("pagehide", bye);
      window.removeEventListener("pageshow", beat);
    };
  }, []);

  if (!stopped) return null;
  return (
    <div className="stopped-overlay" role="alertdialog" aria-labelledby="stopped-title">
      <div className="stopped-card">
        <img src="/logo-192.png" alt="" width="56" height="56" />
        <h2 id="stopped-title">Database Explorer has closed</h2>
        <p className="muted">Open it again from the Database Explorer icon on your desktop or in the Start menu.</p>
        <button className="btn-secondary" onClick={() => window.location.reload()}>Try again</button>
      </div>
    </div>
  );
}
