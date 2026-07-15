import {
  BsDatabase,
  BsMoonStars,
  BsGithub,
} from "react-icons/bs";

function Navbar() {
  return (
    <nav className="navbar navbar-expand-lg shadow-sm">

      <div className="container">

        <a
          href="/"
          className="navbar-brand d-flex align-items-center"
        >
          <BsDatabase
            className="me-2 text-primary"
            size={28}
          />

          <strong>QueryGenie</strong>

        </a>

        <div className="ms-auto">

          <button
            className="btn btn-light me-2"
            title="Dark Mode"
          >
            <BsMoonStars />
          </button>

          <a
            href="https://github.com/wonka05/text-to-sql"
            target="_blank"
            rel="noreferrer"
            className="btn btn-light"
            title="GitHub Repository"
          >
            <BsGithub />
          </a>

        </div>

      </div>

    </nav>
  );
}

export default Navbar;