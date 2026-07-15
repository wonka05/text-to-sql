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
  const cards = [
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
    <div className="card shadow-sm mb-4">

      <div className="card-header">

        <strong>Execution Details</strong>

      </div>

      <div className="card-body">

        <div className="row">

          {cards.map((card, index) => (

            <div
              className="col-md-3 mb-3"
              key={index}
            >

              <div className="stats-card border rounded p-3 h-100">

                <div
                  className="text-primary mb-2"
                  style={{ fontSize: "22px" }}
                >
                  {card.icon}
                </div>

                <small className="text-muted">
                  {card.title}
                </small>

                <h6 className="mt-2 fw-bold">
                  {card.value}
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