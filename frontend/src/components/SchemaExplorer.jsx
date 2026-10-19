import { useState } from "react";
import { Offcanvas } from "react-bootstrap";
import { BsArrowClockwise, BsKey, BsLink45Deg, BsLockFill } from "react-icons/bs";

function ColumnRow({ column }) {
  return (
    <li className="list-group-item px-0 py-2">
      <div className="d-flex flex-wrap align-items-center gap-2">
        <code className="text-body">{column.name}</code>
        <small className="text-body-secondary">{column.type}</small>
        {column.primary_key && (
          <span className="badge text-bg-light border" title="Primary key">
            <BsKey aria-hidden="true" /> key
          </span>
        )}
        {column.references && (
          <span className="badge text-bg-light border" title={`References ${column.references}`}>
            <BsLink45Deg aria-hidden="true" /> {column.references}
          </span>
        )}
        {column.restricted && (
          <span className="badge text-bg-warning" title="The app is not allowed to read this column">
            <BsLockFill aria-hidden="true" /> restricted
          </span>
        )}
      </div>
      {column.values && (
        <small className="d-block text-body-secondary mt-1">
          Values: {column.values.slice(0, 10).join(", ")}
          {column.values.length > 10 && ", ..."}
        </small>
      )}
      {column.value_range && (
        <small className="d-block text-body-secondary mt-1">
          Range: {column.value_range[0]} to {column.value_range[1]}
        </small>
      )}
    </li>
  );
}

// Runs directly as SQL (no AI call). Restricted columns are left out, since
// the server would reject a query that reads them.
function previewSql(table) {
  const columns = table.columns.filter((c) => !c.restricted).map((c) => `\`${c.name}\``);
  return `SELECT ${columns.join(", ")} FROM \`${table.name}\` LIMIT 10`;
}

function SchemaExplorer({ show, onHide, schema, error, loading, onReload, onRunSql, busy }) {
  const [filter, setFilter] = useState("");
  const needle = filter.trim().toLowerCase();
  const tables = (schema?.tables || []).filter(
    (t) => !needle || t.name.toLowerCase().includes(needle) || t.columns.some((c) => c.name.toLowerCase().includes(needle)),
  );

  return (
    <Offcanvas show={show} onHide={onHide} placement="end" className="schema-explorer">
      <Offcanvas.Header closeButton>
        <Offcanvas.Title>
          Schema
          {schema && <small className="d-block text-body-secondary fs-6">{schema.database}</small>}
        </Offcanvas.Title>
      </Offcanvas.Header>
      <Offcanvas.Body>
        <p className="small text-body-secondary">
          Read from the live database. These are the only tables and columns the assistant can use.
        </p>

        {loading && <p className="text-body-secondary">Loading schema...</p>}
        {error && (
          <div className="alert alert-danger small d-flex justify-content-between align-items-center gap-2">
            <span>{error}</span>
            <button type="button" className="btn btn-sm btn-outline-danger" onClick={onReload}>
              <BsArrowClockwise aria-hidden="true" /> Retry
            </button>
          </div>
        )}

        {schema && (
          <>
            <input
              type="search"
              className="form-control form-control-sm mb-3"
              placeholder="Filter tables and columns"
              aria-label="Filter tables and columns"
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
            />
            {tables.map((table) => (
              <section key={table.name} className="card mb-3">
                <div className="card-header d-flex justify-content-between align-items-center">
                  <div>
                    <strong>{table.name}</strong>
                    {table.is_view && <span className="badge text-bg-secondary ms-2">view</span>}
                    {table.row_count !== null && (
                      <small className="text-body-secondary ms-2">{table.row_count.toLocaleString()} rows</small>
                    )}
                  </div>
                  <button
                    type="button"
                    className="btn btn-sm btn-outline-primary"
                    onClick={() => onRunSql(previewSql(table))}
                    disabled={busy}
                    title="Run SELECT ... LIMIT 10 on this table (no AI call)"
                  >
                    Preview
                  </button>
                </div>
                <ul className="list-group list-group-flush px-3">
                  {table.columns.map((column) => (
                    <ColumnRow key={column.name} column={column} />
                  ))}
                </ul>
              </section>
            ))}
            {tables.length === 0 && <p className="text-body-secondary">No tables match "{filter}".</p>}
          </>
        )}
      </Offcanvas.Body>
    </Offcanvas>
  );
}

export default SchemaExplorer;
