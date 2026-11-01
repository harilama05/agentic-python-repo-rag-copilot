# Running and deployment

[Back to README](../README.md)

## Existing local environment

Use the project's installed virtual environment. In VS Code on Windows, **Terminal > Run Task** offers `Run backend` and `Run frontend` from [the task configuration](../.vscode/tasks.json).

Alternatively, run these in separate PowerShell terminals from the repository root:

```powershell
& ./.venv/Scripts/python.exe -m uvicorn api.main:app --app-dir backend --host 127.0.0.1 --port 8000
```

```powershell
& ./.venv/Scripts/python.exe -m http.server 5173 --bind 127.0.0.1 --directory frontend
```

Open http://localhost:5173. Stop each server with **Ctrl+C** in its terminal, or terminate its VS Code task. These instructions start existing environments; use [the Docker quick start](../README.md#quick-start) for an isolated setup from the repository configuration.

## Docker options

Run Compose commands from `backend/`.

| Purpose | Command |
|---|---|
| Check PostgreSQL connectivity and pgvector | `docker compose run --rm api python -m scripts.test_storage_connections` |
| List source repos available for indexing | `docker compose run --rm api python -m scripts.index_company_repo --list` |
| Streamlit debug UI on port 8501 | `docker compose --profile app up streamlit` |
| API and Streamlit together | `docker compose --profile app up` |
| Follow API logs | `docker compose logs -f api` |
| Inspect DB tables | `docker compose run --rm api python -m scripts.inspect_db_tables` |
| Clean expired temporary repos | `docker compose run --rm api python -m scripts.cleanup_temporary_repos` |
| Stop containers | `docker compose down` |

The frontend's Python HTTP server runs separately; stop it with Ctrl+C.

### Local PostgreSQL instead of Supabase

In `backend/.env`, set:

```dotenv
DATABASE_URL=postgresql+psycopg://rag_user:rag_password@postgres:5432/rag_db
```

Then:

```sh
docker compose --profile db up -d postgres
docker compose run --rm api python -m scripts.init_db
```

The hostname `postgres` works between Compose services. A backend running directly on the host uses `localhost:55432` for this database.

### Add a persistent repo

Copy it into [company_repos](../company_repos) as `company_repos/<repo_id>`. Optionally add `repo_config.json` with a display name and description, then run:

```sh
docker compose run --rm api python -m scripts.index_company_repo <repo_id>
```

Re-indexing replaces that repo's existing index. Source files are needed during indexing, but chat loads stored snapshots from PostgreSQL.

## Deployment configuration

These are configuration pointers, not a claim that the current version has been deployed or load-tested.

| Backend setting | Value |
|---|---|
| Service root | `backend` |
| Build | Install [requirements](../backend/requirements.txt) with platform-appropriate packages; [the Dockerfile](../backend/Dockerfile) shows the Linux filtering and CPU PyTorch index |
| Start | `python -m uvicorn api.main:app --host 0.0.0.0 --port $PORT` |
| Environment | PostgreSQL URI, OpenAI settings, and `CORS_ALLOW_ORIGINS` for the frontend origin |

For a Vercel static frontend, use [frontend](../frontend) as the root. Update the hardcoded backend destination in [vercel.json](../frontend/vercel.json) to your own deployed API. Localhost uses port 8000 directly; hosted pages use the `/api` proxy.

Index company repos against the deployment database before loading them. API workers need model weights available at runtime. Sessions are process-local; shared sessions, authentication, and multi-user hardening require further work before a public deployment.
