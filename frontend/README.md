# Querent frontend

React 19 + Vite single-page app for Querent. See the
[project README](../README.md) for setup and
[docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) for how it fits together.

```bash
npm install
cp .env.example .env    # VITE_API_URL=http://127.0.0.1:8000
npm run dev             # http://localhost:5173
npm test                # Vitest: conversation storage, result presentation, API client
npm run lint
npm run build
```

`VITE_API_URL` is compiled into the bundle and visible to anyone, so never put
secrets in a `VITE_*` variable.

## Layout

| Path | Contents |
|---|---|
| `src/App.jsx` | Conversations, the single in-flight request (with cancel), theme, health polling |
| `src/services/api.js` | `fetch` wrapper; failures become `ApiError` with a `code` (`network`, `timeout`, `cancelled`, or the backend's error code) |
| `src/lib/conversations.js` | localStorage format, migration from the first version's history, follow-up context |
| `src/lib/results.js` | Whether a result is a single number, a chart or a table; number formatting |
| `src/components/Turn.jsx` | One question and its answer, rendered per backend `status` |
| `src/components/ResultView.jsx` | Table / chart switch, truncation notice, CSV, refresh |
| `src/components/ResultChart.jsx` | Chart.js bar or line, one measure at a time (loaded on demand) |
| `src/components/SqlPanel.jsx` | Generated vs executed SQL, copy, edit and run |
| `src/components/SchemaExplorer.jsx` | Live schema with keys, relationships and value hints |
