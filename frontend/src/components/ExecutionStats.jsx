import {
  BsCpu,
  BsClock,
  BsTable,
  BsCheckCircle,
} from "react-icons/bs";

function ExecutionStats({
  model,
  executionTime,
  rowsReturned,
  status,
}) {
  const stats = [
    {
      icon: <BsCpu />,
      title: "AI Model",
      value: model,
    },
    {
      icon: <BsClock />,
      title: "Execution Time",
      value: `${executionTime} ms`,
    },
    {
      icon: <BsTable />,
      title: "Rows Returned",
      value: rowsReturned,
    },
    {
      icon: <BsCheckCircle />,
      title: "Status",
      value: status,
    },
  ];

  return (
    <div className="card shadow-sm border-0 mb-4">

      <div className="card-header bg-white">
        <strong>Execution Details</strong>
      </div>

      <div className="card-body">

        <div className="row">

          {stats.map((item, index) => (

            <div
              key={index}
              className="col-md-3 mb-3"
            >

              <div
                className="border rounded p-3 h-100"
              >

                <div
                  className="text-primary mb-2"
                  style={{ fontSize: "22px" }}
                >
                  {item.icon}
                </div>

                <small className="text-muted">
                  {item.title}
                </small>

                <h6 className="mt-2 mb-0 fw-bold">
                  {item.value}
                </h6>

              </div>

            </div>

          ))}

        </div>

      </div>

    </div>
  );
}

export default ExecutionStats;