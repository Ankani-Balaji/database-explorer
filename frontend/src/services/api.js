import axios from "axios";

// Dev server (npm run dev) talks to Flask on port 5000; the built app is served by the backend
// itself, so it uses the same address it was loaded from.
export const API_BASE =
  import.meta.env.VITE_API_URL || (import.meta.env.DEV ? "http://localhost:5000/api" : "/api");
const http = axios.create({ baseURL: API_BASE });

const KEY = "ifm_conn_id";
export const getConnId = () => localStorage.getItem(KEY);
export const setConnId = (id) => (id ? localStorage.setItem(KEY, id) : localStorage.removeItem(KEY));

http.interceptors.request.use((cfg) => {
  const id = getConnId();
  if (id) cfg.headers["X-Connection-Id"] = id;
  return cfg;
});

// Lost/expired connection (e.g. Flask restarted) -> tell the app to go back to the form
http.interceptors.response.use(
  (r) => r,
  (e) => {
    if (e.response?.status === 401) {
      setConnId(null);
      window.dispatchEvent(new Event("ifm-unauth"));
    }
    return Promise.reject(e);
  }
);

export const errMsg = (e) =>
  e.response?.data?.error ||
  (e.request
    ? import.meta.env.DEV
      ? "Cannot reach the Flask backend (is it running on port 5000?)"
      : "Cannot reach Database Explorer. Is the app still running? Start it again and reload this page."
    : e.message);

// Search / filter / sort parameters shared by data, count and export
const tableParams = ({ search = "", filters = {}, sort = "", dir = "asc" } = {}) => ({
  search: search || undefined,
  filters: Object.keys(filters).length ? JSON.stringify(filters) : undefined,
  sort: sort || undefined,
  dir: sort ? dir : undefined,
});

const enc = encodeURIComponent;
export const connect = (payload) => http.post("/connect", payload).then((r) => r.data);
export const getConnection = () => http.get("/connection").then((r) => r.data);
export const disconnect = () => http.post("/disconnect").then((r) => r.data);
export const listDatabases = (payload) => http.post("/databases", payload).then((r) => r.data);
export const listSchemasFor = (payload) => http.post("/schemas", payload).then((r) => r.data);
export const listSchemas = () => http.get("/schemas").then((r) => r.data);
export const switchSchema = (schema) => http.post("/connection/schema", { schema }).then((r) => r.data);
export const getTables = () => http.get("/tables").then((r) => r.data);
export const getSchema = (t) => http.get(`/tables/${enc(t)}/schema`).then((r) => r.data);
export const getData = (t, page, limit, opts) =>
  http.get(`/tables/${enc(t)}/data`, { params: { page, limit, ...tableParams(opts) } }).then((r) => r.data);
export const getCount = (t, opts) =>
  http.get(`/tables/${enc(t)}/count`, { params: tableParams(opts) }).then((r) => r.data);
export const runQuery =(sql) => http.post("/query", { sql }).then((r) => r.data);

// Download a CSV of the current view. Returns { rows, truncated }.
export async function exportCsv(t, opts) {
  let r;
  try {
    r = await http.get(`/tables/${enc(t)}/export`, { params: tableParams(opts), responseType: "blob" });
  } catch (e) {
    // Errors come back as a JSON blob: read it so errMsg() can show the message
    if (e.response?.data instanceof Blob) {
      try { e.response.data = JSON.parse(await e.response.data.text()); } catch { /* keep as is */ }
    }
    throw e;
  }
  const url = URL.createObjectURL(r.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${t}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return { rows: Number(r.headers["x-export-rows"] || 0), truncated: r.headers["x-export-truncated"] === "1" };
}
