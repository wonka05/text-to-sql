import { BsSearch } from "react-icons/bs";

function Header() {
  return (
    <div className="text-center py-5">

      <h1
        className="fw-bold"
        style={{
          fontSize: "3rem",
          color: "#111827",
        }}
      >
        Natural Language SQL Assistant
      </h1>

      <p
        className="text-muted mt-3"
        style={{
          fontSize: "1.15rem",
        }}
      >
        Convert plain English into SQL, execute queries,
        visualize results and export analytics.
      </p>

      <div className="mt-4">

        <span
          className="badge bg-primary fs-6 px-3 py-2"
        >
          <BsSearch className="me-2" />
          Powered by Gemini AI
        </span>

      </div>

    </div>
  );
}

export default Header;