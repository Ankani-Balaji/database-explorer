export default function Pagination({ page, totalPages, limit, onPage, onLimit }) {
  return (
    <div className="pagination">
      <button onClick={() => onPage(1)} disabled={page <= 1}>«</button>
      <button onClick={() => onPage(page - 1)} disabled={page <= 1}>‹ Prev</button>
      <span>Page {page} of {totalPages}</span>
      <button onClick={() => onPage(page + 1)} disabled={page >= totalPages}>Next ›</button>
      <button onClick={() => onPage(totalPages)} disabled={page >= totalPages}>»</button>
      <select value={limit} onChange={(e) => onLimit(Number(e.target.value))}>
        {[10, 25, 50, 100, 200].map((n) => <option key={n} value={n}>{n} / page</option>)}
      </select>
    </div>
  );
}
