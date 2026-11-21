import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import ThemeToggle from "./ThemeToggle.jsx";
import { listSchemas } from "../services/api.js";
import { DB_LABEL, tablePath } from "../utils/format.js";

export default function Sidebar({ collapsed, onToggle, conn, objects, onDisconnect, onSchema }) {
  const [q, setQ] = useState("");
  const [schemas, setSchemas] = useState([]);
  const pg = conn.db_type === "postgresql";

  useEffect(() => {
    if (pg) listSchemas().then((d) => setSchemas(d.schemas)).catch(() => setSchemas([]));
  }, [pg, conn.database]);

  const shown = objects.filter((o) => o.name.toLowerCase().includes(q.toLowerCase()));

  return (
    <>
      <button
        className={`toggle-btn ${collapsed ? "closed" : "open"}`}
        onClick={onToggle}
        title={collapsed ? "Open sidebar" : "Close sidebar"}
        aria-label={collapsed ? "Open sidebar" : "Close sidebar"}
      >
        {collapsed ? "›" : "‹"}
      </button>

      <aside className={`sidebar ${collapsed ? "collapsed" : ""}`}>
        <div className="sidebar-inner">
          <div className="brand">
            <img src="/logo-192.png" alt="" className="brand-logo" />
            DB Explorer
            <ThemeToggle className="on-dark" />
          </div>
          <NavLink to="/" end className="nav">Dashboard</NavLink>
          <NavLink to="/query" className="nav">SQL Console</NavLink>

          {pg && schemas.length > 1 && (
            <label className="side-schema">
              Schema
              <select value={conn.schema} onChange={(e) => onSchema(e.target.value)}>
                {!schemas.includes(conn.schema) && <option value={conn.schema}>{conn.schema}</option>}
                {schemas.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </label>
          )}

          <div className="side-tables">
            <input className="side-filter" type="search" placeholder={`Filter ${objects.length} tables…`}
              value={q} onChange={(e) => setQ(e.target.value)} />
            <nav className="side-list">
              {shown.map((o) => (
                <NavLink key={o.name} to={tablePath(o.name)} className="side-item" title={o.name}>
                  <span className="side-icon">{o.kind === "view" ? "◇" : "▦"}</span>
                  <span className="side-name">{o.name}</span>
                </NavLink>
              ))}
              {!shown.length && <div className="side-empty">{objects.length ? "No match" : "No tables"}</div>}
            </nav>
          </div>

          <div className="conn-box">
            <span className="badge">{DB_LABEL[conn.db_type] || conn.db_type}</span>
            <div className="conn-db">{conn.database}{pg && <span className="conn-schema"> · {conn.schema}</span>}</div>
            <div className="conn-host">{conn.user}@{conn.host}:{conn.port}</div>
            <button className="btn-disconnect" onClick={onDisconnect}>Disconnect</button>
          </div>
        </div>
      </aside>
    </>
  );
}
