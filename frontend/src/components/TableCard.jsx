import { Link } from "react-router-dom";
import { formatBytes, formatEstimate, tablePath } from "../utils/format.js";

export default function TableCard({ table }) {
  const rows = formatEstimate(table.rows_estimate);
  const size = formatBytes(table.size_bytes);
  return (
    <Link to={tablePath(table.name)} className="card">
      <span className="card-icon">{table.kind === "view" ? "◇" : "▦"}</span>
      <span className="card-body">
        <span className="card-name">{table.name}</span>
        <span className="card-stats">
          {table.kind === "view" && <span className="pill">view</span>}
          {rows && <span>{rows} rows</span>}
          {size && <span>{size}</span>}
        </span>
      </span>
    </Link>
  );
}
