import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { fullText, tablePath } from "../utils/format.js";

const cell = (v) => (v === null || v === undefined ? <span className="null">NULL</span> : fullText(v));

// Text box that reports its value after the user stops typing
function FilterInput({ value, onChange, label }) {
  const [text, setText] = useState(value);
  useEffect(() => setText(value), [value]);
  useEffect(() => {
    if (text === value) return undefined;
    const id = setTimeout(() => onChange(text), 400);
    return () => clearTimeout(id);
  }, [text]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <input className="col-filter" value={text} placeholder="filter…" aria-label={`Filter ${label}`}
      title="Contains (case-insensitive). Start with = for an exact match."
      onChange={(e) => setText(e.target.value)} />
  );
}

/**
 * columns: names; rows: objects keyed by column name.
 * Optional: types {col: type}, sort/dir/onSort, filters/onFilter, links {col: {table, column}},
 * onRowClick(row).
 */
export default function DataTable({ columns, rows, types = {}, sort, dir, onSort, filters, onFilter,
  links = {}, onRowClick, emptyText = "No records found." }) {
  const sortable = !!onSort;
  const nextSort = (c) => {
    if (sort !== c) return onSort(c, "asc");
    if (dir === "asc") return onSort(c, "desc");
    return onSort("", "asc");
  };

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c} aria-sort={sort === c ? (dir === "desc" ? "descending" : "ascending") : undefined}>
                {sortable ? (
                  <button type="button" className="th-sort" onClick={() => nextSort(c)} title="Sort">
                    {c}<span className="sort-mark">{sort === c ? (dir === "desc" ? "▼" : "▲") : "↕"}</span>
                  </button>
                ) : c}
                <small>{types[c]}{links[c] && " → " + links[c].table}</small>
              </th>
            ))}
          </tr>
          {onFilter && (
            <tr className="filter-row">
              {columns.map((c) => (
                <th key={c}>
                  <FilterInput value={filters?.[c] || ""} label={c} onChange={(v) => onFilter(c, v)} />
                </th>
              ))}
            </tr>
          )}
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className={onRowClick ? "clickable" : ""} onClick={onRowClick ? () => onRowClick(r) : undefined}>
              {columns.map((c) => {
                const v = r[c];
                const link = links[c];
                return (
                  <td key={c} title={typeof v === "object" ? "" : String(v ?? "")}>
                    {link && v !== null && v !== undefined ? (
                      <Link className="fk-link" onClick={(e) => e.stopPropagation()}
                        to={`${tablePath(link.table)}?f=${encodeURIComponent(JSON.stringify({ [link.column]: "=" + fullText(v) }))}`}>
                        {cell(v)}
                      </Link>
                    ) : cell(v)}
                  </td>
                );
              })}
            </tr>
          ))}
          {!rows.length && (
            <tr><td colSpan={columns.length || 1} className="empty-cell">{emptyText}</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
