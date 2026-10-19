# Deploying Querent

Three free-tier services, about 30 minutes in total:

| Part | Service | Why |
|---|---|---|
| Database | [Aiven](https://aiven.io) for MySQL | A real MySQL 8 server, with encrypted connections |
| Backend | [Render](https://render.com) | Runs the FastAPI app from this repo using `render.yaml` |
| Frontend | [Vercel](https://vercel.com) | Builds and hosts the React app |

Free plans change; check each service's current pricing when you sign up.
On Render's free plan the backend sleeps after about 15 minutes without
visitors, and the first request after that takes up to a minute while it
wakes. The frontend shows "Checking connection..." during that time.

Only the generated sample data goes online. Never point a public demo at real
data.

## 1. Database (Aiven)

1. Sign up at aiven.io and create a **MySQL** service on the **free** plan.
   Pick a region near you.
2. When it's running, open the service's **Overview** page and note:
   **Host**, **Port**, **User** (`avnadmin`) and **Password**.
3. Download the **CA certificate** (`ca.pem`) from the same page.
4. Load the tables and sample data, and create the read-only user, from your
   own computer. In a **new** PowerShell window:

   ```powershell
   cd C:\Users\Hp\OneDrive\Desktop\projects\AI-SQL-Assistant\backend
   venv\Scripts\activate

   # These apply to this window only and override backend\.env
   $env:DB_HOST = "mysql-xxxx.aivencloud.com"      # from Aiven
   $env:DB_PORT = "12345"                          # from Aiven
   $env:DB_ADMIN_USER = "avnadmin"
   $env:DB_ADMIN_PASSWORD = "the Aiven password"
   $env:DB_SSL_CA = "C:\Users\Hp\Downloads\ca.pem" # where you saved it
   $env:DB_NAME = "ai_data_analyst"
   $env:DB_USER = "querygenie_ro"
   $env:DB_PASSWORD = "a NEW password, 12+ characters"   # for the read-only user

   python -m scripts.setup_db
   python -m scripts.check_db
   ```

   `check_db` should print `read-only=True` and six tables. Keep the new
   read-only password; Render needs it in step 2. Then close the window so
   these settings disappear.

## 2. Backend (Render)

1. Sign up at render.com with your GitHub account.
2. **New → Blueprint**, choose the `text-to-sql` repository. Render reads
   `render.yaml` and creates a web service called `querent-api`.
3. Fill in the values it asks for:

   | Variable | Value |
   |---|---|
   | `GEMINI_API_KEY` | your Gemini key |
   | `DB_HOST`, `DB_PORT` | from Aiven |
   | `DB_PASSWORD` | the read-only user's password from step 1 |
   | `DB_SSL_CA` | open `ca.pem` in Notepad, copy everything (including the `BEGIN`/`END` lines) and paste |
   | `ALLOWED_ORIGINS` | `http://localhost:5173` for now; you'll change it in step 4 |

4. Click **Apply** and wait for the deploy to finish (a few minutes).
5. Copy the service URL, e.g. `https://querent-api.onrender.com`, and open
   `<that URL>/health`. You should see `"database": {"ok": true, ...}`.

## 3. Frontend (Vercel)

1. Sign up at vercel.com with your GitHub account.
2. **Add New → Project**, import the `text-to-sql` repository.
3. Set **Root Directory** to `frontend`. Vercel detects Vite by itself.
4. Under **Environment Variables**, add `VITE_API_URL` = your Render URL,
   **without** a trailing slash.
5. **Deploy**, then copy your site's URL, e.g. `https://querent.vercel.app`.

## 4. Connect the two

1. In Render, open `querent-api` → **Environment**, set `ALLOWED_ORIGINS` to
   your Vercel URL (no trailing slash) and save. Render redeploys.
2. Open your Vercel URL. The dot in the top bar turns green once the backend
   is awake. Ask a question.
3. Add the link to the README (there's a commented-out placeholder at the
   top) and to your resume.

## Costs and limits

- The Gemini key is used by everyone who visits. On the free tier the worst
  case is reaching the daily limit; if billing is on for your key, set a
  budget alert in Google Cloud.
- Each visitor can ask 20 questions per minute (`RATE_LIMIT_PER_MINUTE`).
- Each query is limited to 5 seconds and 500 rows.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| "API unreachable" in the top bar | Backend still waking up (wait a minute), or `VITE_API_URL` is wrong. Changing it needs a Vercel redeploy |
| Browser console shows a CORS error | `ALLOWED_ORIGINS` doesn't exactly match the Vercel URL (check `https`, no trailing slash) |
| "Database unavailable" | Wrong `DB_HOST`/`DB_PORT`/`DB_PASSWORD`, or `DB_SSL_CA` was pasted incompletely. Render's logs show the MySQL error |
| "AI model is not available" | Invalid key, or the model is overloaded; Render's logs show Google's message |
| Certificate error mentioning the hostname | Set `DB_SSL_VERIFY_HOSTNAME=false` (the certificate is still checked) |
