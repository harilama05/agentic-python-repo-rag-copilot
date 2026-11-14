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

Open http://localhost:5173. Keep **both terminals/tasks running** while using the app. Stop each server with **Ctrl+C** in its terminal, or terminate its VS Code task. These instructions start existing environments; use [the Docker quick start](../README.md#quick-start) for an isolated setup from the repository configuration.

Check http://localhost:8000/health if the frontend reports an API connection error. `ERR_CONNECTION_REFUSED` at port 5173 means the frontend server is unreachable; `Failed to fetch` can also mean an unreachable backend or a CORS/network problem. Confirm the server logs before changing credentials. API key errors occur after a request reaches the backend/model service.

Restart the backend after changing its environment. If both sample repos are already indexed, ordinary startup does not require re-indexing them.

## Indexing limits

The current pipeline is intended for local exploration; no large-repository capacity or timing guarantee has been measured.

| Area | Current behavior |
|---|---|
| Public GitHub clone | Shallow clone (`--depth 1`), with a 240-second clone timeout |
| GitHub size cap | `MAX_GITHUB_REPO_MB` is declared in settings but not enforced by ingestion; it is not a working 100 MB limit |
| ZIP extraction | At most 5,000 archive entries and 100 MiB of declared uncompressed content |
| Supported files | Python, Markdown, JSON and TXT; known dependency/build directories and selected lockfiles are skipped |
| Per-file size | No enforced limit by default (`MAX_INDEX_FILE_BYTES=None` in [constants](../backend/src/core/constants.py)) |
| Memory and embeddings | Source snapshots, chunks and resulting embeddings are retained in memory; embeddings run locally on CPU and DB writes use batches of 64 |
| Request lifecycle | Clone/index completes inside the HTTP request; no background worker, progress polling, cancellation or resume mechanism |
| Updates | Re-indexing replaces the selected repository index; there is no changed-files-only incremental index |

The relevant code is [GitHub ingestion](../backend/src/ingestion/github_ingestion.py), [ZIP validation](../backend/src/ingestion/zip_ingestion.py), [indexing](../backend/src/indexing/codebase_indexer.py) and [vector storage](../backend/src/storage/supabase_vector_store.py). Background jobs, bounded batch processing and incremental updates remain future work. A large repo can exhaust memory/storage or exceed a deployment proxy timeout even when the model key works.

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

Set `DATABASE_URL` and `OPENAI_API_KEY` in the backend host's environment/secrets. Use `LLM_BACKEND=openai`, `OPENAI_MODEL=gpt-6-luna`, `OPENAI_REASONING_EFFORT=low` and `AGENT_MODE=loop`, matching [the environment template](../backend/.env.example). The local ignored `backend/.env` is not uploaded by Git. The static frontend must never receive these credentials.

For a Vercel static frontend, use [frontend](../frontend) as the root. Update the hardcoded backend destination in [vercel.json](../frontend/vercel.json) to your own deployed API. Localhost uses port 8000 directly; hosted pages use the `/api` proxy.

Index company repos against the deployment database before loading them. API workers need model weights available at runtime. Sessions are process-local; shared sessions, authentication, and multi-user hardening require further work before a public deployment.

For committing and pushing the source changes, see [the GitHub guide](./github.md).
