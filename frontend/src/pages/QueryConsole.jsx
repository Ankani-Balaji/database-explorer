import { useState } from "react";
import { runQuery, errMsg } from "../services/api.js";
import DataTable from "../components/DataTable.jsx";
import RowDetail from "../components/RowDetail.jsx";

const KEY = "ifm_console_sql";
const load = () => { try { return localStorage.getItem(KEY) || ""; } catch { return ""; } };
const save = (v) => { try { localStorage.setItem(KEY, v); } catch { /* ignore */ } };

export default function QueryConsole({ conn }) {
  const pg = conn.db_type === "postgresql";
  const [sql, setSql] = useState(() => load() ||
    (pg ? `SELECT * FROM "${conn.schema}".` : "SELECT * FROM ") + "your_table LIMIT 50");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");
  const [running, setRunning] = useState(false);
  const [detail, setDetail] = useState(null);

  const run = async () => {
    if (running || !sql.trim()) return;
    save(sql);
    setRunning(true); setError("");
    try {
      setResult(await runQuery(sql));
    } catch (e) {
      setError(errMsg(e));
      setResult(null);
    }
    setRunning(false);
  };

  return (
    <>
      <h1>SQL Console</h1>
      <p className="muted">
        Read-only: one statement at a time (SELECT, WITH, SHOW, EXPLAIN…), run inside a read-only
        transaction that is always rolled back. Up to 1,000 rows are shown.
      </p>
      <textarea className="sql-editor" value={sql} spellCheck={false} rows={8}
        aria-label="SQL query"
        onChange={(e) => setSql(e.target.value)}
        onKeyDown={(e) => {
          if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); run(); }
        }} />
      <div className="toolbar">
        <button className="btn-primary btn-run" onClick={run} disabled={running || !sql.trim()}>
          {running ? "Running…" : "▶ Run"}
        </button>
        <span className="muted small">Ctrl + Enter to run</span>
        {result && (
          <span className="muted small">
            {result.row_count.toLocaleString()} row{result.row_count === 1 ? "" : "s"}
            {result.truncated && " (first 1,000 shown)"} · {result.elapsed_ms} ms
          </span>
        )}
      </div>
      {error && <div className="state error">⚠ {error}</div>}
      {result && !error && (
        result.columns.length
          ? <DataTable columns={result.columns} rows={result.rows} onRowClick={setDetail}
              emptyText="The query returned no rows." />
          : <div className="state">The statement ran and returned no result set.</div>
      )}
      {detail && result && <RowDetail row={detail} columns={result.columns} onClose={() => setDetail(null)} />}
    </>
  );
}
