import { Spinner } from "react-bootstrap";

function LoadingSpinner() {
  return (
    <div className="text-center py-5">

      <Spinner
        animation="border"
        variant="primary"
      />

      <p
        className="mt-3 text-muted"
        style={{
          fontSize: "15px",
        }}
      >
        QueryGenie is generating SQL...
      </p>

    </div>
  );
}

export default LoadingSpinner;