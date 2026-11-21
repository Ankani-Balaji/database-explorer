import { useSearchParams } from "react-router-dom";
import TableCard from "../components/TableCard.jsx";
import SearchBar from "../components/SearchBar.jsx";
import { DB_LABEL, formatBytes } from "../utils/format.js";

const SORTS = {
  name: (a, b) => a.name.localeCompare(b.name),
  rows: (a, b) => (b.rows_estimate ?? -1) - (a.rows_estimate ?? -1),
  size: (a, b) => (b.size_bytes ?? -1) - (a.size_bytes ?? -1),
};

export default function Dashboard({ objects, onRefresh }) {
  const [params, setParams] = useSearchParams();
  const q = params.get("q") || "";
  const sort = SORTS[params.get("sort")] ? params.get("sort") : "name";
  const setParam = (k, v, dflt = "") =>
    setParams((p) => { const n = new URLSearchParams(p); v && v !== dflt ? n.set(k, v) : n.delete(k); return n; }, { replace: true });

  const info = objects.data;
  const all = info?.tables || [];
  const shown = all.filter((t) => t.name.toLowerCase().includes(q.toLowerCase())).sort(SORTS[sort]);
  const views = all.filter((t) => t.kind === "view").length;
  const totalSize = all.reduce((s, t) => s + (t.size_bytes || 0), 0);

  return (
    <>
      <h1>Database Explorer</h1>
      {objects.loading && !info && <div className="state"><div className="spinner" />Loading tables…</div>}
      {objects.error && <div className="state error">⚠ {objects.error}</div>}
      {info && (
        <>
          <div className="meta">
            <span>Type: <b>{DB_LABEL[info.db_type] || info.db_type}</b></span>
            <span>Database: <b>{info.database}</b></span>
            {info.db_type === "postgresql" && <span>Schema: <b>{info.schema}</b></span>}
            <span>Tables: <b>{all.length - views}</b></span>
            {views > 0 && <span>Views: <b>{views}</b></span>}
            {totalSize > 0 && <span>Size: <b>{formatBytes(totalSize)}</b></span>}
          </div>
          <div className="toolbar">
            <SearchBar value={q} onChange={(v) => setParam("q", v)} placeholder="Filter tables…" />
            <label className="inline-select">
              Sort by
              <select value={sort} onChange={(e) => setParam("sort", e.target.value, "name")}>
                <option value="name">Name</option>
                <option value="rows">Rows</option>
                <option value="size">Size</option>
              </select>
            </label>
            <button className="btn-small" onClick={onRefresh} disabled={objects.loading}>
              {objects.loading ? "Refreshing…" : "↻ Refresh"}
            </button>
          </div>
          {shown.length ? (
            <div className="grid">{shown.map((t) => <TableCard key={t.name} table={t} />)}</div>
          ) : <div className="state">{all.length ? `No tables match “${q}”.` : "This schema has no tables."}</div>}
          <p className="muted small">Row counts are estimates from the database's statistics.</p>
        </>
      )}
    </>
  );
}
