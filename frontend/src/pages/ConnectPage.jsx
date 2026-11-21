import { useEffect, useState } from "react";
import { connect, listDatabases, listSchemasFor, setConnId, errMsg } from "../services/api.js";
import ThemeToggle from "../components/ThemeToggle.jsx";

const PORTS = { postgresql: "5432", mysql: "3306" };
const RECENT_KEY = "ifm_recent";

const loadRecent = () => {
  try {
    return JSON.parse(localStorage.getItem(RECENT_KEY)) || [];
  } catch {
    return [];
  }
};
const saveRecent = (f) => {
  const { password, ...r } = f; // never store the password
  const same = (x) =>
    x.db_type === r.db_type &&
    x.host === r.host &&
    String(x.port) === String(r.port) &&
    x.database === r.database &&
    x.user === r.user;
  localStorage.setItem(
    RECENT_KEY,
    JSON.stringify([r, ...loadRecent().filter((x) => !same(x))].slice(0, 5)),
  );
};

const EMPTY = {
  db_type: "postgresql",
  host: "localhost",
  port: "5432",
  database: "",
  user: "",
  password: "",
  schema: "public",
};

export default function ConnectPage({ onConnected }) {
  const [step, setStep] = useState(1); // 1 = server login, 2 = choose database
  const [form, setForm] = useState(EMPTY);
  const [dbs, setDbs] = useState([]);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [recent] = useState(loadRecent);
  // PostgreSQL schemas of the selected database (null = not loaded / couldn't load: type it instead)
  const [schemas, setSchemas] = useState(null);

  const pickedDb = step === 2 && form.db_type === "postgresql" ? form.database : "";
  useEffect(() => {
    setSchemas(null);
    if (!pickedDb) return undefined;
    let live = true;
    listSchemasFor({ ...form, database: pickedDb })
      .then((d) => {
        if (!live) return;
        setSchemas(d.schemas);
        setForm((f) => ({
          ...f,
          schema: d.schemas.includes(f.schema) ? f.schema : d.schemas.includes("public") ? "public" : d.schemas[0] || f.schema,
        }));
      })
      .catch(() => live && setSchemas(null));
    return () => { live = false; };
  }, [pickedDb]); // eslint-disable-line react-hooks/exhaustive-deps

  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const changeType = (t) =>
    setForm((f) => ({
      ...f,
      db_type: t,
      port: Object.values(PORTS).includes(String(f.port)) ? PORTS[t] : f.port,
    }));

  // Step 1: log in to the server and fetch its databases
  const loginServer = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const d = await listDatabases({ ...form, database: "" });
      setDbs(d.databases);
      setFilter("");
      setForm((f) => ({
        ...f,
        database: d.databases.includes(f.database) ? f.database : "",
      }));
      setStep(2);
    } catch (err) {
      setError(errMsg(err));
    }
    setLoading(false);
  };

  // Step 2: open the chosen database (submit button, or double-click on a name)
  const openDatabase = async (database) => {
    if (loading || !database) return;
    const chosen = { ...form, database };
    setLoading(true);
    setError("");
    try {
      const d = await connect(chosen);
      setConnId(d.connection_id);
      saveRecent(chosen);
      onConnected(d.info);
    } catch (err) {
      setError(errMsg(err));
      setLoading(false);
    }
  };

  const shown = dbs.filter((n) =>
    n.toLowerCase().includes(filter.toLowerCase()),
  );

  return (
    <div className="connect-wrap">
      <ThemeToggle className="corner" />
      {step === 1 ? (
        <form className="connect-card" onSubmit={loginServer}>
          <h1>
            <img src="/logo-192.png" alt="" className="connect-logo" />
            Database Explorer
          </h1>
          <p className="muted">
            Step 1 of 2 — connect to your database server (read-only).
          </p>

          {recent.length > 0 && (
            <div className="recent">
              <span className="muted">Recent:</span>
              {recent.map((r, i) => (
                <button
                  type="button"
                  key={i}
                  className="chip"
                  onClick={() =>
                    setForm({
                      ...EMPTY,
                      ...r,
                      port: String(r.port),
                      password: "",
                    })
                  }
                >
                  {r.user}@{r.host} · {r.db_type === "mysql" ? "MySQL" : "PG"}
                </button>
              ))}
            </div>
          )}

          <label>
            Database type
            <select
              value={form.db_type}
              onChange={(e) => changeType(e.target.value)}
            >
              <option value="postgresql">PostgreSQL</option>
              <option value="mysql">MySQL</option>
            </select>
          </label>

          <div className="row">
            <label className="grow">
              Host
              <input
                value={form.host}
                onChange={(e) => set("host", e.target.value)}
                required
              />
            </label>
            <label className="port">
              Port
              <input
                type="number"
                value={form.port}
                onChange={(e) => set("port", e.target.value)}
                required
              />
            </label>
          </div>

          <div className="row">
            <label className="grow">
              Username
              <input
                value={form.user}
                onChange={(e) => set("user", e.target.value)}
                required
                autoFocus
              />
            </label>
            <label className="grow">
              Password
              <input
                type="password"
                value={form.password}
                onChange={(e) => set("password", e.target.value)}
              />
            </label>
          </div>

          {error && <div className="state error">⚠ {error}</div>}

          <button className="btn-primary" disabled={loading}>
            {loading ? "Connecting…" : "Connect to Server"}
          </button>
        </form>
      ) : (
        <form
          className="connect-card"
          onSubmit={(e) => {
            e.preventDefault();
            openDatabase(form.database);
          }}
        >
          <h1>Choose a database</h1>
          <p className="muted">
            Step 2 of 2 — {form.user}@{form.host}:{form.port} (
            {form.db_type === "mysql" ? "MySQL" : "PostgreSQL"}) · {dbs.length}{" "}
            database{dbs.length === 1 ? "" : "s"} found
          </p>

          {dbs.length > 6 && (
            <input
              className="filter"
              placeholder="Filter databases…"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
          )}

          <div className="db-list">
            {shown.map((n) => (
              <button
                type="button"
                key={n}
                className={`db-item ${form.database === n ? "active" : ""}`}
                onClick={() => set("database", n)}
                onDoubleClick={() => {
                  set("database", n);
                  openDatabase(n);
                }}
              >
                <span>🛢️</span> {n}
              </button>
            ))}
            {!shown.length && (
              <div className="state">
                {dbs.length
                  ? "No databases match."
                  : "No databases found on this server."}
              </div>
            )}
          </div>

          {form.db_type === "postgresql" && form.database && (
            <label>
              Schema
              {schemas && schemas.length ? (
                <select
                  value={form.schema}
                  onChange={(e) => set("schema", e.target.value)}
                >
                  {schemas.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              ) : (
                <input
                  value={form.schema}
                  onChange={(e) => set("schema", e.target.value)}
                  placeholder="public"
                />
              )}
            </label>
          )}

          {error && <div className="state error">⚠ {error}</div>}

          <div className="row">
            <button
              type="button"
              className="btn-secondary"
              onClick={() => {
                setStep(1);
                setError("");
              }}
            >
              ← Change server
            </button>
            <button
              className="btn-primary grow"
              disabled={loading || !form.database}
            >
              {loading
                ? "Opening…"
                : form.database
                  ? `Open ${form.database}`
                  : "Select a database"}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
