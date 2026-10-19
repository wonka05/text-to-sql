import { BsDatabase, BsDiagram3, BsMoonStars, BsSun } from "react-icons/bs";

function StatusBadge({ health }) {
  const states = {
    checking: { dot: "bg-secondary", text: "Checking connection..." },
    ok: { dot: "bg-success", text: "Database connected" },
    degraded: { dot: "bg-danger", text: "Database unavailable" },
    offline: { dot: "bg-danger", text: "API unreachable" },
  };
  const { dot, text } = states[health.state] || states.checking;
  const title = health.error || (health.model ? `Model: ${health.model}` : undefined);

  return (
    <span className="status-badge" title={title} role="status" aria-live="polite">
      <span className={`status-dot ${dot}`} aria-hidden="true" />
      <span className="d-none d-sm-inline">{text}</span>
      {health.model && <span className="text-body-secondary d-none d-md-inline"> · {health.model}</span>}
    </span>
  );
}

function Navbar({ theme, onToggleTheme, health, onOpenSchema }) {
  const dark = theme === "dark";
  return (
    <nav className="navbar border-bottom bg-body sticky-top">
      <div className="container-fluid px-3 px-lg-4 gap-2">
        <span className="navbar-brand d-flex align-items-center gap-2 me-auto">
          <BsDatabase className="text-primary" size={24} aria-hidden="true" />
          <strong>Querent</strong>
          <small className="text-body-secondary fw-normal fs-6 d-none d-md-inline">
            ask your database in plain English
          </small>
        </span>

        <StatusBadge health={health} />

        <button type="button" className="btn btn-sm btn-outline-secondary" onClick={onOpenSchema}>
          <BsDiagram3 className="me-1" aria-hidden="true" />
          Schema
        </button>

        <button
          type="button"
          className="btn btn-sm btn-outline-secondary"
          onClick={onToggleTheme}
          aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
          title={dark ? "Light theme" : "Dark theme"}
        >
          {dark ? <BsSun aria-hidden="true" /> : <BsMoonStars aria-hidden="true" />}
        </button>
      </div>
    </nav>
  );
}

export default Navbar;
