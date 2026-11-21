import { Link } from "react-router-dom";
import { tablePath } from "../utils/format.js";

export default function Structure({ schema }) {
  if (!schema) return <div className="state"><div className="spinner" />Loading structure…</div>;
  const { columns, foreign_keys: fks, indexes } = schema;

  return (
    <div className="structure">
      <section>
        <h2>Columns <span className="muted">({columns.length})</span></h2>
        <div className="table-wrap">
          <table>
            <thead><tr><th>#</th><th>Name</th><th>Type</th><th>Nullable</th><th>Default</th><th>Keys</th></tr></thead>
            <tbody>
              {columns.map((c, i) => (
                <tr key={c.name}>
                  <td className="muted">{i + 1}</td>
                  <td><b>{c.name}</b></td>
                  <td><code>{c.type}</code></td>
                  <td>{c.nullable ? "yes" : <span className="pill">NOT NULL</span>}</td>
                  <td>{c.default === null || c.default === undefined ? <span className="null">—</span> : <code>{c.default}</code>}</td>
                  <td>
                    {c.primary_key && <span className="pill pk">PK</span>}
                    {c.foreign_key && <span className="pill fk">FK</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2>Foreign keys <span className="muted">({fks.length})</span></h2>
        {fks.length ? (
          <ul className="plain-list">
            {fks.map((fk) => (
              <li key={fk.name}>
                <code>({fk.columns.join(", ")})</code> →{" "}
                {fk.same_schema
                  ? <Link to={tablePath(fk.ref_table)}>{fk.ref_table}</Link>
                  : <span>{fk.ref_schema}.{fk.ref_table}</span>}
                <code>({fk.ref_columns.join(", ")})</code>
                <span className="muted small"> {fk.name}</span>
              </li>
            ))}
          </ul>
        ) : <p className="muted">None.</p>}
      </section>

      <section>
        <h2>Indexes <span className="muted">({indexes.length})</span></h2>
        {indexes.length ? (
          <ul className="plain-list">
            {indexes.map((ix) => (
              <li key={ix.name}>
                <b>{ix.name}</b> <code>({ix.columns.join(", ")})</code>
                {ix.primary && <span className="pill pk">primary</span>}
                {ix.unique && !ix.primary && <span className="pill">unique</span>}
              </li>
            ))}
          </ul>
        ) : <p className="muted">None{schema.kind === "view" ? " (views have no indexes)" : ""}.</p>}
      </section>
    </div>
  );
}
