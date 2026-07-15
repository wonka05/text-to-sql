import { BsDatabaseGear } from "react-icons/bs";

function Header() {
  return (
    <div className="text-center mb-5">

      <div
        className="d-flex justify-content-center mb-3"
      >
        <BsDatabaseGear
          size={42}
          className="text-primary"
        />
      </div>

      <h1 className="header-title">

        QueryGenie

      </h1>

      <p className="header-subtitle">

        AI-powered Natural Language to SQL Assistant

      </p>

    </div>
  );
}

export default Header;