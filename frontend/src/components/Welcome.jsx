import { BsDatabaseGear } from "react-icons/bs";

// Examples for the bundled sample database (scripts/setup_db.py)
const SAMPLE_EXAMPLES = [
  {
    title: "Look things up",
    questions: ["Which products have fewer than 10 units in stock?", "Who is the highest paid employee?"],
  },
  {
    title: "Summarise",
    questions: ["What is the average salary in each department?", "How many orders were placed each year?"],
  },
  {
    title: "Combine tables",
    questions: ["Who are the top 5 customers by total amount spent?", "What is the total revenue for each product category?"],
  },
  {
    title: "Dig deeper",
    questions: [
      "Which employees earn more than the average salary of their own department?",
      "Which customers have never placed an order?",
    ],
  },
];
const SAMPLE_TABLES = ["customers", "employees", "orders", "products"];

function examplesFor(schema) {
  const names = schema?.tables.map((t) => t.name) || [];
  if (!schema || SAMPLE_TABLES.every((name) => names.includes(name))) return SAMPLE_EXAMPLES;
  // Some other database: offer generic starting points for its own tables
  return [
    {
      title: "Explore",
      questions: names.slice(0, 4).map((name) => `Show a sample of the ${name} table`),
    },
    {
      title: "Count",
      questions: names.slice(0, 4).map((name) => `How many rows are in ${name}?`),
    },
  ];
}

function Welcome({ schema, busy, onAsk }) {
  return (
    <div className="welcome text-center py-4 px-2">
      <BsDatabaseGear size={40} className="text-primary mb-3" aria-hidden="true" />
      <h1 className="h3 fw-bold">Ask your database a question</h1>
      <p className="text-body-secondary mx-auto welcome-lead">
        Querent writes a read-only SQL query for your question, checks it, runs it, and shows you the
        results with the SQL it used. If a question is unclear, it asks before guessing.
        {schema && (
          <>
            {" "}
            Connected to <strong>{schema.database}</strong> ({schema.tables.length} tables).
          </>
        )}
      </p>

      <div className="row g-3 text-start mt-2">
        {examplesFor(schema).map((group) => (
          <div className="col-md-6" key={group.title}>
            <div className="card h-100 example-group">
              <div className="card-body">
                <h2 className="h6 text-body-secondary mb-2">{group.title}</h2>
                <div className="d-grid gap-2">
                  {group.questions.map((question) => (
                    <button
                      key={question}
                      type="button"
                      className="btn btn-sm btn-outline-primary text-start"
                      onClick={() => onAsk(question)}
                      disabled={busy}
                    >
                      {question}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default Welcome;
