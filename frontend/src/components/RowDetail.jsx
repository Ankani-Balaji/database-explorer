import { useEffect, useState } from "react";
import { fullText } from "../utils/format.js";

export default function RowDetail({ row, columns, types = {}, onClose }) {
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(row, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch { /* clipboard blocked */ }
  };

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer" role="dialog" aria-label="Row details" onClick={(e) => e.stopPropagation()}>
        <header className="drawer-head">
          <h2>Row details</h2>
          <button type="button" className="btn-small" onClick={copy}>{copied ? "Copied ✓" : "Copy as JSON"}</button>
          <button type="button" className="drawer-close" onClick={onClose} aria-label="Close">×</button>
        </header>
        <dl className="detail-list">
          {columns.map((c) => {
            const v = row[c];
            return (
              <div key={c} className="detail-item">
                <dt>{c}<small>{types[c]}</small></dt>
                <dd>
                  {v === null || v === undefined
                    ? <span className="null">NULL</span>
                    : <pre>{fullText(v, true)}</pre>}
                </dd>
              </div>
            );
          })}
        </dl>
      </aside>
    </div>
  );
}
