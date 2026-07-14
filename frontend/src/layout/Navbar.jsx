import { BsDatabase, BsMoonStars, BsInfoCircle } from "react-icons/bs";

function Navbar() {
  return (
    <nav
      className="navbar navbar-expand-lg bg-white border-bottom shadow-sm sticky-top"
      style={{ height: "70px" }}
    >
      <div className="container">

        <a
          className="navbar-brand fw-bold fs-4 d-flex align-items-center"
          href="#"
          style={{ color: "#2563EB" }}
        >
          <BsDatabase className="me-2" size={26} />
          QueryGenie
        </a>

        <div className="ms-auto d-flex gap-3">

          <button
            className="btn btn-light border"
            title="Dark Mode"
          >
            <BsMoonStars />
          </button>

          <button
            className="btn btn-light border"
            title="About"
          >
            <BsInfoCircle />
          </button>

        </div>

      </div>
    </nav>
  );
}

export default Navbar;