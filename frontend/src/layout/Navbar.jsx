import {
  BsDatabase,
  BsMoonStars,
  BsSun,
  BsGithub,
} from "react-icons/bs";

function Navbar({ darkMode, setDarkMode }) {
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

        

      </div>

    </nav>
  );
}

export default Navbar;