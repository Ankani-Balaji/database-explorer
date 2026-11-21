import { useCallback, useEffect, useState } from "react";
import { Routes, Route, Navigate, useNavigate } from "react-router-dom";
import Sidebar from "./components/Sidebar.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import TableViewer from "./pages/TableViewer.jsx";
import ConnectPage from "./pages/ConnectPage.jsx";
import QueryConsole from "./pages/QueryConsole.jsx";
import { getConnId, setConnId, getConnection, disconnect, getTables, switchSchema, errMsg } from "./services/api.js";

export default function App() {
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);
  const [conn, setConn] = useState(null);
  const [checking, setChecking] = useState(!!getConnId());
  // Tables and views of the current schema, shared by the sidebar and the dashboard
  const [objects, setObjects] = useState({ data: null, loading: false, error: "" });

  useEffect(() => {
    if (getConnId()) {
      getConnection()
        .then((d) => setConn(d.info))
        .catch(() => setConn(null))
        .finally(() => setChecking(false));
    }
    const onUnauth = () => setConn(null);
    window.addEventListener("ifm-unauth", onUnauth);
    return () => window.removeEventListener("ifm-unauth", onUnauth);
  }, []);

  const loadObjects = useCallback(() => {
    setObjects((o) => ({ ...o, loading: true, error: "" }));
    getTables()
      .then((d) => setObjects({ data: d, loading: false, error: "" }))
      .catch((e) => setObjects({ data: null, loading: false, error: errMsg(e) }));
  }, []);

  const connKey = conn ? `${conn.database}/${conn.schema}` : "";
  useEffect(() => {
    if (connKey) loadObjects();
    else setObjects({ data: null, loading: false, error: "" });
  }, [connKey, loadObjects]);

  const handleDisconnect = async () => {
    try { await disconnect(); } catch { /* ignore */ }
    setConnId(null);
    setConn(null);
  };

  const handleSchema = async (schema) => {
    try {
      const d = await switchSchema(schema);
      setConn(d.info);
      navigate("/");
    } catch (e) {
      setObjects((o) => ({ ...o, error: errMsg(e) }));
    }
  };

  if (checking) return <div className="state"><div className="spinner" />Checking connection…</div>;

  if (!conn) {
    return (
      <Routes>
        <Route path="/connect" element={<ConnectPage onConnected={setConn} />} />
        <Route path="*" element={<Navigate to="/connect" replace />} />
      </Routes>
    );
  }

  return (
    <div className="layout">
      <Sidebar collapsed={collapsed} onToggle={() => setCollapsed((c) => !c)}
        conn={conn} objects={objects.data?.tables || []} onDisconnect={handleDisconnect}
        onSchema={handleSchema} />
      <main className="main">
        <Routes>
          <Route path="/" element={<Dashboard objects={objects} onRefresh={loadObjects} />} />
          <Route path="/tables/:tableName" element={<TableViewer />} />
          <Route path="/query" element={<QueryConsole conn={conn} />} />
          <Route path="/connect" element={<Navigate to="/" replace />} />
          <Route path="*" element={<div className="state error">Page not found</div>} />
        </Routes>
      </main>
    </div>
  );
}
