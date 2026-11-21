import { useEffect, useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { getData, getSchema, getCount, exportCsv, errMsg } from "../services/api.js";
import DataTable from "../components/DataTable.jsx";
import Pagination from "../components/Pagination.jsx";
import SearchBar from "../components/SearchBar.jsx";
import RowDetail from "../components/RowDetail.jsx";
import Structure from "../components/Structure.jsx";

// Keyed by table name: switching tables mounts a fresh view instead of reusing the old state.
export default function TableViewer() {
  const { tableName } = useParams();
  return <TableView key={tableName} tableName={tableName} />;
}

const parseFilters = (raw) => {
  try {
    const f = JSON.parse(raw || "{}");
    return f && typeof f === "object" && !Array.isArray(f) ? f : {};
  } catch {
    return {};
  }
};

function TableView({ tableName }) {
  // Page, search, sort, filters and tab live in the URL, so a view can be bookmarked or shared
  const [params, setParams] = useSearchParams();
  const page = Math.max(Number(params.get("page")) || 1, 1);
  const limit = Number(params.get("limit")) || 25;
  const search = params.get("q") || "";
  const sort = params.get("sort") || "";
  const dir = params.get("dir") === "desc" ? "desc" : "asc";
  const rawFilters = params.get("f") || "";
  const filters = useMemo(() => parseFilters(rawFilters), [rawFilters]);
  const tab = params.get("tab") === "structure" ? "structure" : "data";

  const update = (changes) =>
    setParams((prev) => {
      const p = new URLSearchParams(prev);
      if (!("page" in changes)) p.delete("page"); // any other change goes back to page 1
      for (const [k, v] of Object.entries(changes)) {
        if (v === "" || v === null || v === undefined || (k === "page" && v === 1)) p.delete(k);
        else p.set(k, String(v));
      }
      return p;
    }, { replace: true });

  const [schema, setSchema] = useState(null);
  const [schemaError, setSchemaError] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [input, setInput] = useState(search);
  const [detail, setDetail] = useState(null);
  const [exporting, setExporting] = useState(false);
  const [notice, setNotice] = useState("");
  // Exact row count, fetched on request when the backend sent an estimate
  const [exact, setExact] = useState({ value: null, loading: false });

  useEffect(() => {
    getSchema(tableName).then(setSchema).catch((e) => setSchemaError(errMsg(e)));
  }, [tableName]);

  // Search box: write to the URL after typing stops; follow the URL on back/forward
  useEffect(() => setInput(search), [search]);
  useEffect(() => {
    if (input === search) return undefined;
    const id = setTimeout(() => update({ q: input }), 400);
    return () => clearTimeout(id);
  }, [input]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    let live = true;
    setLoading(true); setError("");
    getData(tableName, page, limit, { search, filters, sort, dir })
      .then((d) => live && setResult(d))
      .catch((e) => live && setError(errMsg(e)))
      .finally(() => live && setLoading(false));
    return () => { live = false; };
  }, [tableName, page, limit, search, rawFilters, sort, dir]); // eslint-disable-line react-hooks/exhaustive-deps

  const types = useMemo(
    () => Object.fromEntries((schema?.columns || []).map((c) => [c.name, c.type])), [schema]);
  // Single-column foreign keys into this schema become links to the referenced row
  const links = useMemo(() => Object.fromEntries((schema?.foreign_keys || [])
    .filter((fk) => fk.columns.length === 1 && fk.same_schema)
    .map((fk) => [fk.columns[0], { table: fk.ref_table, column: fk.ref_columns[0] }])), [schema]);

  const setFilter = (col, value) => {
    const next = { ...filters };
    if (value) next[col] = value; else delete next[col];
    update({ f: Object.keys(next).length ? JSON.stringify(next) : "" });
  };
  const filterCount = Object.keys(filters).length;

  const countExactly = async () => {
    setExact({ value: null, loading: true });
    try {
      const d = await getCount(tableName, { search, filters });
      setExact({ value: d.count, loading: false });
    } catch (e) {
      setExact({ value: null, loading: false });
      setNotice("⚠ Counting failed: " + errMsg(e));
    }
  };
  const estimated = result?.total_estimated && exact.value === null;
  const total = result?.total_estimated && exact.value !== null ? exact.value : result?.total;

  const doExport = async () => {
    setExporting(true); setNotice("");
    try {
      const r = await exportCsv(tableName, { search, filters, sort, dir });
      setNotice(r.truncated
        ? `Exported the first ${r.rows.toLocaleString()} rows (export limit). Narrow the search to get the rest.`
        : `Exported ${r.rows.toLocaleString()} rows.`);
    } catch (e) {
      setNotice("⚠ Export failed: " + errMsg(e));
    }
    setExporting(false);
  };

  return (
    <>
      <Link to="/" className="back">← Back to Dashboard</Link>
      <h1>{tableName} {schema?.kind === "view" && <span className="pill">view</span>}</h1>
      <div className="meta">
        <span>Total records: <b>{result ? (estimated ? "≈ " : "") + total.toLocaleString() : "…"}</b>
          {(search || filterCount > 0) && " (filtered)"}
          {estimated && (
            <button type="button" className="link-btn" onClick={countExactly} disabled={exact.loading}
              title="Large table: the total is an estimate. Counting exactly reads the whole table.">
              {exact.loading ? "counting…" : "count exactly"}
            </button>
          )}</span>
        <span>Columns: <b>{result ? result.columns.length : "…"}</b></span>
        {schema?.primary_key?.length > 0 && <span>Primary key: <b>{schema.primary_key.join(", ")}</b></span>}
      </div>

      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "data"} className={tab === "data" ? "active" : ""}
          onClick={() => update({ tab: "", page })}>Data</button>
        <button role="tab" aria-selected={tab === "structure"} className={tab === "structure" ? "active" : ""}
          onClick={() => update({ tab: "structure", page })}>Structure</button>
      </div>

      {tab === "structure" ? (
        schemaError ? <div className="state error">⚠ {schemaError}</div> : <Structure schema={schema} />
      ) : (
        <>
          <div className="toolbar">
            <SearchBar value={input} onChange={setInput} placeholder="Search all columns…" />
            {(filterCount > 0 || sort) && (
              <button className="btn-small" onClick={() => update({ f: "", sort: "", dir: "" })}>
                Clear {filterCount > 0 ? `${filterCount} filter${filterCount > 1 ? "s" : ""}` : ""}{filterCount > 0 && sort ? " & " : ""}{sort ? "sort" : ""}
              </button>
            )}
            <button className="btn-small" onClick={doExport} disabled={exporting || !result?.total}>
              {exporting ? "Exporting…" : "⤓ Export CSV"}
            </button>
          </div>
          {notice && <div className={`notice ${notice.startsWith("⚠") ? "error" : ""}`}>{notice}</div>}
          {loading && <div className="state"><div className="spinner" />Loading data…</div>}
          {error && <div className="state error">⚠ {error}</div>}
          {result && !error && (
            <>
              <DataTable columns={result.columns} rows={result.rows} types={types}
                sort={sort} dir={dir} onSort={(s, d) => update({ sort: s, dir: s && d === "desc" ? "desc" : "" })}
                filters={filters} onFilter={setFilter} links={links} onRowClick={setDetail} />
              <Pagination page={result.page} totalPages={result.total_pages} limit={limit}
                onPage={(p) => update({ page: p })} onLimit={(n) => update({ limit: n === 25 ? "" : n })} />
              <p className="muted small">Click a row to see every field. Click a column name to sort.</p>
            </>
          )}
        </>
      )}

      {detail && result && (
        <RowDetail row={detail} columns={result.columns} types={types} onClose={() => setDetail(null)} />
      )}
    </>
  );
}
