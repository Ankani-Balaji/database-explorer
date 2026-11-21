export const DB_LABEL = { postgresql: "PostgreSQL", mysql: "MySQL" };

export function formatBytes(n) {
  if (n === null || n === undefined) return null;
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  let v = Number(n);
  while (v >= 1024 && i < units.length - 1) { v /= 1024; i++; }
  return `${v >= 10 || i === 0 ? Math.round(v) : v.toFixed(1)} ${units[i]}`;
}

// Row counts from the catalog are estimates
export function formatEstimate(n) {
  if (n === null || n === undefined) return null;
  const v = Number(n);
  if (v < 1000) return `~${v}`;
  if (v < 1e6) return `~${(v / 1e3).toFixed(v < 1e4 ? 1 : 0)}k`;
  if (v < 1e9) return `~${(v / 1e6).toFixed(v < 1e7 ? 1 : 0)}M`;
  return `~${(v / 1e9).toFixed(1)}B`;
}

// Full text of a cell value (objects such as JSON columns are pretty-printed)
export function fullText(v, pretty = false) {
  if (v === null || v === undefined) return "";
  if (typeof v === "object") return JSON.stringify(v, null, pretty ? 2 : 0);
  return String(v);
}

export const tablePath = (name) => `/tables/${encodeURIComponent(name)}`;
