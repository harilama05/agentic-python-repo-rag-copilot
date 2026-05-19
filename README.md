# Agentic Python Repo RAG Copilot

Agentic Python Repo RAG Copilot is an AI assistant for understanding Python codebases.

The project can load already-indexed company repositories, temporarily index user-provided public GitHub repositories or ZIP uploads, retrieve relevant code/documentation/config/text files, build and use a Python code graph, and answer repository questions using Agentic RAG, Graph RAG, RRF-based retrieval, Cross-Encoder reranking, and an LLM query planner.

The current version includes:

- Streamlit user-facing app
- FastAPI backend API
- Service layer for repository/session/chat workflows
- PostgreSQL metadata storage
- Qdrant vector storage
- Python/Markdown/JSON/TXT indexing
- RRF multi-source retrieval
- Cross-Encoder accurate mode
- Graph RAG for caller/callee/impact queries
- Logging
- Extended evaluation metrics
- Company repository indexing through scripts
- Temporary GitHub/ZIP repository ingestion and cleanup

Company repositories are indexed and re-indexed through internal scripts, not through the web UI or public API.

---

## Table of contents

- [Current status](#current-status)
- [Architecture overview](#architecture-overview)
- [Repository modes](#repository-modes)
- [Indexed file types](#indexed-file-types)
- [Retrieval pipeline](#retrieval-pipeline)
- [Graph RAG](#graph-rag)
- [FastAPI backend](#fastapi-backend)
- [API endpoints](#api-endpoints)
- [Project structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Environment variables](#environment-variables)
- [Local setup](#local-setup)
- [Start PostgreSQL and Qdrant](#start-postgresql-and-qdrant)
- [Initialize the database](#initialize-the-database)
- [Index or update company repositories](#index-or-update-company-repositories)
- [Run Streamlit app](#run-streamlit-app)
- [Run FastAPI backend](#run-fastapi-backend)
- [Test API endpoints](#test-api-endpoints)
- [Evaluation](#evaluation)
- [Logging](#logging)
- [Useful scripts](#useful-scripts)
- [Git ignore policy](#git-ignore-policy)
- [Recommended git workflow](#recommended-git-workflow)
- [Troubleshooting](#troubleshooting)
- [Next step](#next-step)
- [Planned improvements](#planned-improvements)
- [Deployment direction](#deployment-direction)

---

## Current status

Implemented:

- User-facing Streamlit app
- FastAPI backend API
- API route modules for health, company repos, temporary repos, and chat
- CORS configuration for local frontend development
- Centralized FastAPI error handling
- Service layer for repository loading/indexing, sessions, and chat
- In-memory session store for local/API runtime state
- Python code indexing
- Markdown documentation indexing
- JSON file indexing
- TXT file indexing
- PostgreSQL metadata/chunk/graph storage
- Qdrant vector storage
- RRF-based multi-source retrieval
- Fast retrieval mode using RRF
- Accurate retrieval mode using RRF + Cross-Encoder reranking
- Graph RAG for caller, callee, and impact analysis
- Reference query behavior that treats definitions separately from usages
- Citation/source metadata using `line_start` and `line_end`
- Router metadata preserved in `raw_results`
- LLM router fallback handling
- Grounded LLM answer generation with fallback behavior
- GitHub temporary repository ingestion
- ZIP upload temporary repository ingestion
- Company repository loading from PostgreSQL + Qdrant
- Company repository index/re-index script
- Temporary repository cleanup on repository switch or explicit cleanup
- Expired temporary repository cleanup script
- Code graph persistence and reload from PostgreSQL
- LLM query planner with multi-intent support
- Application logging to terminal and `logs/app.log`
- Extended evaluation metrics:
  - source precision
  - citation validity
  - latency
  - answer non-empty rate
  - router fallback rate
  - LLM failure rate

The backend API is now ready to connect to a separate frontend.

---

## Architecture overview

High-level Q&A flow:

```text
User question
    ↓
Frontend / Streamlit / API
    ↓
Session Store
    ↓
Loaded IndexedCodebase
    ↓
LLM Query Planner / fallback router
    ↓
One or more QueryPlans
    ↓
Agent tool execution
    ↓
Retriever / Graph tools / File reader
    ↓
PostgreSQL + Qdrant
    ↓
Grounded answer generation
    ↓
Answer with sources
```

Company repository indexing flow:

```text
Admin/developer script
    ↓
Configured company repo
    ↓
Scan Python, Markdown, JSON, and TXT files
    ↓
Parse/chunk code, docs, config, and text files
    ↓
Build AST code graph
    ↓
Store metadata/chunks/graph in PostgreSQL
    ↓
Store embeddings in Qdrant
    ↓
Ready for Streamlit/API users to load and ask questions
```

Company repository loading flow:

```text
User/API loads Company Repo
    ↓
Load repository metadata from PostgreSQL
    ↓
Load chunks from PostgreSQL
    ↓
Rebuild in-memory BM25 index
    ↓
Load code graph from PostgreSQL
    ↓
Connect to Qdrant by repo_id
    ↓
Create retriever/tools/agent in memory
    ↓
Bind IndexedCodebase to session_id
    ↓
Answer questions
```

Temporary repository flow:

```text
GitHub URL or ZIP Upload
    ↓
Clone/extract into data/runtime/
    ↓
Scan/chunk/embed/build graph
    ↓
Save temporary metadata and vectors
    ↓
Create in-memory session
    ↓
Answer questions
    ↓
Cleanup on switch, explicit cleanup, or expiration
```

---

## Repository modes

### Company Repo

Loads an already-indexed persistent company repository from PostgreSQL and Qdrant.

Company repositories use:

```text
is_persistent=True
source_type=company
```

Company repositories are indexed or re-indexed by an admin/developer using:

```powershell
python -m scripts.index_company_repo taskflow_api
```

The Streamlit UI and FastAPI backend only load company repositories. They do not expose public company indexing endpoints.

### GitHub URL

Temporarily clones and indexes a public GitHub repository.

GitHub temporary repositories use:

```text
is_persistent=False
source_type=github
```

They are cloned into:

```text
data/runtime/github/
```

### ZIP Upload

Temporarily extracts and indexes an uploaded `.zip` file containing a Python repository.

ZIP temporary repositories use:

```text
is_persistent=False
source_type=zip_upload
```

They are extracted into:

```text
data/runtime/uploads/
```

ZIP upload includes basic safety checks such as path traversal protection and file count/size limits.

---

## Indexed file types

The indexer currently supports:

| File type | Purpose |
|---|---|
| `.py` | Python code, functions, classes, methods, graph analysis |
| `.md`, `.markdown` | README and documentation |
| `.json` | Config files, sample data, metadata, structured text |
| `.txt` | Plain text notes, docs, prompts, simple text resources |

UI/API stats expose:

```text
Python files
Docs/Text files
JSON files
Ignored files
Total chunks
```

`Docs/Text files` means:

```text
Markdown docs + TXT files
```

---

## Retrieval pipeline

The project uses RRF-based retrieval.

### Fast mode

Fast mode runs multiple retrieval sources independently:

```text
User query
    ↓
Qdrant vector search
Full-repository BM25 search
Symbol metadata search
Documentation/text search for documentation queries
    ↓
RRF fusion
    ↓
Top results
```

The final ranking score in Fast mode is the RRF score.

### Accurate mode

Accurate mode uses RRF to retrieve candidate chunks and then reranks them with a Cross-Encoder:

```text
User query
    ↓
Vector search + BM25 search + symbol search + documentation/text search
    ↓
RRF fusion
    ↓
Candidate chunks
    ↓
Cross-Encoder reranking
    ↓
Top results
```

### Runtime scores

Scores such as BM25 score, RRF score, vector score, and Cross-Encoder score are query-time scores.

They are not stored permanently in PostgreSQL.

PostgreSQL stores stable chunk text and metadata. Qdrant stores embeddings.

---

## Graph RAG

The project builds a lightweight Python code graph from AST analysis.

Graph RAG supports:

- Caller queries
- Callee queries
- Impact analysis
- Symbol relationship questions

Examples:

```text
TaskService.create_task được gọi bởi ai?
```

```text
TaskService.create_task gọi những hàm nào?
```

```text
TaskService.create_task nếu xóa thì sẽ ảnh hưởng gì?
```

Graph results return citation metadata such as:

```json
{
  "relative_path": "app/api/tasks.py",
  "line_start": 9,
  "line_end": 11,
  "symbol": "create_task",
  "type": "function",
  "source_role": "caller"
}
```

---

## FastAPI backend

The backend is implemented with FastAPI.

Main responsibilities:

- List indexed company repositories
- Load company repositories into sessions
- Index temporary GitHub repositories
- Index temporary ZIP repositories
- Answer chat questions against a loaded session
- Cleanup temporary repositories
- Return clean API errors
- Provide CORS support for a future frontend

The backend uses an in-memory session store:

```text
session_id -> IndexedCodebase
```

This is enough for local development and demo. If the backend restarts, in-memory sessions are lost. Company repositories can be loaded again from PostgreSQL + Qdrant.

For production, Redis or another external session store would be better.

---

## API endpoints

### Health

```http
GET /health
```

Expected response:

```json
{
  "status": "ok"
}
```

### List company repositories

```http
GET /company-repos
```

Returns indexed persistent company repositories from PostgreSQL.

### Load company repository

```http
POST /company-repos/{repo_id}/load
```

Example body:

```json
{
  "retrieval_mode": "fast",
  "use_llm": true,
  "use_llm_router": true
}
```

`session_id` is optional. If omitted, the API creates one and returns it.

Example response:

```json
{
  "session_id": "generated-session-id",
  "repo_id": "taskflow_api",
  "repo_name": "TaskFlow API",
  "source_type": "company",
  "is_persistent": true,
  "local_path": "examples/company_repos/taskflow_api",
  "collection_name": "taskflow_api",
  "file_count": 3,
  "doc_count": 1,
  "text_count": 1,
  "docs_text_count": 2,
  "json_count": 1,
  "ignored_file_count": 1,
  "chunk_count": 14,
  "retrieval_mode": "fast"
}
```

### Index temporary GitHub repository

```http
POST /temporary-repos/github
```

Example body:

```json
{
  "github_url": "https://github.com/owner/repo",
  "branch": null,
  "retrieval_mode": "fast",
  "use_llm": true,
  "use_llm_router": true
}
```

`session_id` is optional. If omitted, the API creates one and returns it.

### Index temporary ZIP repository

```http
POST /temporary-repos/zip
```

Uses multipart form-data:

```text
file: repo.zip
session_id: optional
retrieval_mode: fast
use_llm: true
use_llm_router: true
```

### Chat

```http
POST /chat
```

Example body:

```json
{
  "session_id": "your-session-id",
  "question": "Where is create_task used?"
}
```

Expected response:

```json
{
  "session_id": "your-session-id",
  "question": "Where is create_task used?",
  "query_type": "reference_query",
  "answer": "...",
  "tools_used": [],
  "sources": [],
  "raw_results": {}
}
```

### Cleanup temporary repository

```http
DELETE /temporary-repos/{repo_id}?session_id=your-session-id
```

Response:

```json
{
  "repo_id": "zip_code_xxx",
  "session_id": "your-session-id",
  "deleted": true
}
```

---

## Project structure

```text
agentic-python-repo-rag-copilot/
├── api/
│   ├── main.py
│   ├── schemas.py
│   ├── __init__.py
│   └── routes/
│       ├── chat.py
│       ├── health.py
│       ├── repositories.py
│       ├── temporary_repos.py
│       └── __init__.py
│
├── app/
│   ├── streamlit_app.py
│   └── __init__.py
│
├── data/
│   └── eval_cases.json
│
├── examples/
│   ├── sample_python_repo/
│   └── company_repos/
│       └── taskflow_api/
│
├── scripts/
│   ├── cleanup_temporary_repos.py
│   ├── index_company_repo.py
│   ├── index_repo.py
│   ├── init_db.py
│   ├── inspect_db_tables.py
│   ├── inspect_metadata_records.py
│   ├── inspect_qdrant_records.py
│   ├── run_eval.py
│   ├── test_github_ingestion.py
│   ├── test_llm_router.py
│   ├── test_load_code_graph_from_db.py
│   ├── test_load_existing_repo.py
│   ├── test_qdrant_vector_store.py
│   ├── test_storage_connections.py
│   └── test_zip_ingestion.py
│
├── src/
│   ├── agent_core/
│   ├── chunking/
│   ├── core/
│   ├── db/
│   ├── embeddings/
│   ├── evaluation/
│   ├── generation/
│   ├── graph/
│   ├── indexing/
│   ├── ingestion/
│   ├── observability/
│   ├── parsing/
│   ├── reranking/
│   ├── retrieval/
│   ├── services/
│   └── storage/
│
├── tests/
│   ├── test_chunker.py
│   └── test_scanner.py
│
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Prerequisites

Install these before running locally:

- Python 3.10
- Git
- Docker Desktop
- WSL2 on Windows
- Visual Studio Code or another code editor

---

## Environment variables

Create a `.env` file in the project root.

The project root is the folder containing:

```text
README.md
requirements.txt
docker-compose.yml
.env.example
api/
app/
src/
scripts/
```

Example `.env`:

```env
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
LLM_BACKEND=gemini

DATABASE_URL=postgresql+psycopg://rag_user:rag_password@localhost:55432/rag_db

QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
QDRANT_COLLECTION=code_chunks

CORS_ALLOW_ORIGINS=http://localhost:5173,http://localhost:3000
```

Do not commit `.env`.

Commit `.env.example` instead.

---

## Local setup

### 1. Clone repository

```powershell
git clone https://github.com/<your-username>/<your-repo>.git
cd agentic-python-repo-rag-copilot
```

### 2. Create virtual environment

```powershell
py -3.10 -m venv .venv
.venv\Scripts\activate
```

If `py -3.10` does not work:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

---

## Start PostgreSQL and Qdrant

Make sure Docker Desktop is running.

Then run:

```powershell
docker compose up -d
```

Check containers:

```powershell
docker ps
```

You should see PostgreSQL and Qdrant containers.

---

## Initialize the database

Create database tables:

```powershell
python -m scripts.init_db
```

Test storage connections:

```powershell
python -m scripts.test_storage_connections
```

Expected output:

```text
PostgreSQL connection OK: 1
Qdrant connection OK
```

---

## Index or update company repositories

Company repositories are not indexed from the web UI or public API.

Use:

```powershell
python -m scripts.index_company_repo taskflow_api
```

List configured company repositories:

```powershell
python -m scripts.index_company_repo --list
```

The same command is used for both first-time indexing and full re-indexing.

When re-indexing, the script:

1. Deletes old indexed data for the selected repository from PostgreSQL and Qdrant.
2. Scans Python, Markdown, JSON, and TXT files.
3. Rebuilds chunks.
4. Rebuilds the code graph.
5. Recreates embeddings.
6. Saves updated metadata, graph data, and vectors.

This is currently a full re-index of the selected company repository. Incremental file-level indexing is planned for later.

---

## Run Streamlit app

Start the app:

```powershell
python -m streamlit run app/streamlit_app.py
```

Use the sidebar to choose:

- Company Repo
- GitHub URL
- ZIP Upload

### Company Repo

1. Select `Company Repo`.
2. Choose an indexed company repository.
3. Select retrieval mode.
4. Click `Load repository`.
5. Ask questions.

### GitHub URL

1. Select `GitHub URL`.
2. Enter a public GitHub repository URL.
3. Optionally enter a branch.
4. Click `Index temporary repository`.
5. Ask questions.

### ZIP Upload

1. Select `ZIP Upload`.
2. Upload a `.zip` file containing a Python repository.
3. Click `Index temporary repository`.
4. Ask questions.

---

## Run FastAPI backend

Start the API:

```powershell
uvicorn api.main:app --reload --reload-dir api --reload-dir src --reload-exclude "logs/*" --reload-exclude "*.log"
```

The API runs at:

```text
http://127.0.0.1:8000
```

Open Swagger UI:

```text
http://127.0.0.1:8000/docs
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected:

```json
{
  "status": "ok"
}
```

---

## Test API endpoints

### List company repositories

```powershell
Invoke-RestMethod http://127.0.0.1:8000/company-repos
```

### Load company repository

```powershell
$response = Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/company-repos/taskflow_api/load `
  -ContentType "application/json" `
  -Body '{"retrieval_mode":"fast","use_llm":true,"use_llm_router":true}'

$response
$sessionId = $response.session_id
```

### Chat with loaded repository

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/chat `
  -ContentType "application/json" `
  -Body (@{
    session_id = $sessionId
    question = "Where is create_task used?"
  } | ConvertTo-Json)
```

### Test JSON indexing

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/chat `
  -ContentType "application/json" `
  -Body (@{
    session_id = $sessionId
    question = "Where is json indexing mentioned?"
  } | ConvertTo-Json)
```

### Test TXT indexing

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/chat `
  -ContentType "application/json" `
  -Body (@{
    session_id = $sessionId
    question = "Where is text file indexing mentioned?"
  } | ConvertTo-Json)
```

### Cleanup temporary repository

```powershell
Invoke-RestMethod `
  -Method Delete `
  -Uri "http://127.0.0.1:8000/temporary-repos/REPO_ID?session_id=$sessionId"
```

### Test clean error response

```powershell
try {
  Invoke-RestMethod `
    -Method Post `
    -Uri http://127.0.0.1:8000/chat `
    -ContentType "application/json" `
    -Body '{"session_id":"fake-session","question":"Where is create_task used?"}'
} catch {
  $_.ErrorDetails.Message
}
```

Expected shape:

```json
{
  "error": "bad_request",
  "detail": "No repository is loaded for this session. Load a company repository or index a temporary repository first."
}
```

---

## Evaluation

Run:

```powershell
python -m scripts.run_eval
```

The evaluation checks:

- Query type routing
- Source recall
- Source precision
- Citation validity
- Latency
- Answer non-empty rate
- Router fallback rate
- LLM failure rate
- Graph caller/callee/impact cases
- Documentation retrieval
- Multi-intent planning

Expected result should be close to or equal to:

```text
Query type accuracy: 100.00%
Average source recall: 100.00%
Expected sources all found rate: 100.00%
Average citation validity: 100.00%
Answer non-empty rate: 100.00%
```

`Average source precision` may be lower than 100% if the answer returns useful extra sources that are not listed in the expected eval sources.

---

## Logging

Application logs are written to:

```text
logs/app.log
```

Logs are also printed to the terminal.

The logger uses rotation, so logs do not grow forever. The intended logging style is operational metadata, not full chat history.

Examples of logged metadata:

```text
session_id
repo_id
source_type
retrieval_mode
query_type
source_count
tool_count
error messages
```

Do not commit logs.

`.gitignore` should include:

```gitignore
logs/
*.log
```

When running FastAPI in development, use:

```powershell
uvicorn api.main:app --reload --reload-dir api --reload-dir src --reload-exclude "logs/*" --reload-exclude "*.log"
```

This avoids reload noise caused by log file changes.

---

## Useful scripts

### Initialize database

```powershell
python -m scripts.init_db
```

### Test storage connections

```powershell
python -m scripts.test_storage_connections
```

### Index or update a company repository

```powershell
python -m scripts.index_company_repo taskflow_api
```

### List configured company repositories

```powershell
python -m scripts.index_company_repo --list
```

### Cleanup expired temporary repositories

```powershell
python -m scripts.cleanup_temporary_repos
```

### Dry-run temporary cleanup

```powershell
python -m scripts.cleanup_temporary_repos --dry-run
```

### List expired temporary repositories

```powershell
python -m scripts.cleanup_temporary_repos --list
```

### Test loading an existing indexed repo

```powershell
python -m scripts.test_load_existing_repo
```

When prompted, enter:

```text
taskflow_api
```

### Inspect PostgreSQL metadata

```powershell
python -m scripts.inspect_metadata_records
```

### Inspect Qdrant records

```powershell
python -m scripts.inspect_qdrant_records
```

### Test LLM router

```powershell
python -m scripts.test_llm_router
```

---

## Git ignore policy

Do not commit local runtime data, secrets, virtual environments, cache files, logs, or generated tree files.

Recommended `.gitignore`:

```gitignore
.venv/
.env
__pycache__/
*.pyc
data/runtime/
project_tree.txt
logs/
*.log
postgres_data/
qdrant_data/
```

Before committing, check:

```powershell
git status
```

Make sure these are not staged:

```text
.venv/
.env
__pycache__/
*.pyc
data/runtime/
project_tree.txt
logs/
*.log
```

If `.venv` was accidentally staged:

```powershell
git reset
```

Then ensure `.venv/` is in `.gitignore`, and run:

```powershell
git add .
```

If needed:

```powershell
git rm -r --cached .venv
```

---

## Recommended git workflow

After backend/API tests pass:

```powershell
git status
```

Add only project files, not local runtime or secrets:

```powershell
git add README.md
git add api
git add app
git add src
git add scripts
git add data/eval_cases.json
git add .gitignore
git add .env.example
git add requirements.txt
git add docker-compose.yml
```

Commit:

```powershell
git commit -m "Complete FastAPI backend and extended indexing support"
```

Push:

```powershell
git push
```

If `git status` shows `.venv`, `.env`, `logs`, or `data/runtime`, do not commit yet. Fix `.gitignore` first.

---

## Troubleshooting

### Git warns LF will be replaced by CRLF

This is a line ending warning on Windows, not a runtime error.

You can ignore it, or add `.gitattributes`:

```gitattributes
* text=auto
*.py text eol=lf
*.md text eol=lf
*.yml text eol=lf
*.yaml text eol=lf
*.json text eol=lf
*.txt text eol=lf
```

### Accidentally added `.venv`

Run:

```powershell
git reset
```

Add `.venv/` to `.gitignore`, then stage again.

### Docker API error

Open Docker Desktop first, then run:

```powershell
docker ps
docker compose up -d
```

### PostgreSQL or Qdrant connection refused

Start containers:

```powershell
docker compose up -d
```

Then test:

```powershell
python -m scripts.test_storage_connections
```

### No indexed company repositories found

Run:

```powershell
python -m scripts.index_company_repo taskflow_api
```

Then reload Streamlit or call the API again.

### Gemini API key issue

Make sure `.env` in the project root has:

```env
GEMINI_API_KEY=your_key
```

Restart Streamlit/API after changing `.env`.

### API starts but `/company-repos` is empty

Make sure:

1. PostgreSQL container is running.
2. Database tables are initialized.
3. Company repo has been indexed:

```powershell
python -m scripts.index_company_repo taskflow_api
```

### API reloads repeatedly while logging

Use:

```powershell
uvicorn api.main:app --reload --reload-dir api --reload-dir src --reload-exclude "logs/*" --reload-exclude "*.log"
```

---

## Next step

The backend/API is now ready for frontend integration.

Recommended frontend stack:

```text
React + Vite + TypeScript
```

Frontend flow:

```text
GET /company-repos
POST /company-repos/{repo_id}/load
Store session_id
POST /chat
Render answer + sources
```

After Company Repo + Chat works, add:

```text
GitHub URL indexing
ZIP upload indexing
Temporary repo cleanup
```

---

## Planned improvements

- Production-ready React frontend
- Deployment to Render/Vercel
- Neon PostgreSQL
- Qdrant Cloud
- Background scheduled cleanup for expired temporary repositories
- Incremental indexing for company repositories
- Authentication and saved private user repositories
- Redis session store for deployed backend
- Better support for larger repositories
- Optional MMR diversification for selected query types
- More automated tests

---

## Deployment direction

The current version is designed to run locally with Docker.

A production deployment can use:

- Render for FastAPI backend
- Vercel for frontend
- Neon for PostgreSQL
- Qdrant Cloud for vector database
- Redis or another external store for API sessions

In production:

- Temporary repository cloning and ZIP extraction should happen on the backend server.
- Persistent metadata and vectors should be stored in cloud databases.
- Company repository indexing can run as an internal script or scheduled job.
- Temporary repository cleanup should run as a scheduled job.
- API CORS origins should be restricted to the deployed frontend domain.

