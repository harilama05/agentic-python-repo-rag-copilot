# Agentic Python Repo RAG Copilot

Agentic Python Repo RAG Copilot is an AI assistant for understanding Python codebases. It can index Python repositories, store their chunks/embeddings/code graph in Supabase/PostgreSQL + pgvector, and answer codebase questions with source citations.

The current project is split into:

```text
backend/        FastAPI backend, Streamlit debug UI, RAG/indexing/storage code
frontend/       Static HTML/CSS/JS frontend
company_repos/  Local/admin-only source repositories used for company repo indexing
```

The important current design decision is:

```text
Index-time may read source repositories.
Runtime/chat is DB-only.
```

That means `company_repos/` is only needed on the local/admin machine when indexing or re-indexing company repos. The deployed backend, for example on Render, should load and answer from Supabase/PostgreSQL + pgvector and does not need `company_repos/`.

---

## Current Features

Implemented in the current repository snapshot:

- FastAPI backend in `backend/api/`
- Static frontend in `frontend/`
- Streamlit debug UI in `backend/app/streamlit_app.py`
- Backend deploy layout under `backend/`
- Supabase/PostgreSQL metadata storage
- PostgreSQL `pgvector` embedding storage
- Python, Markdown, JSON, and TXT indexing
- Persistent company repositories indexed from local/admin `company_repos/`
- Auto-discovery of company repos from `company_repos/<repo_id>`
- Optional `repo_config.json` per company repo
- Temporary GitHub repository indexing
- Temporary ZIP repository indexing
- Temporary repo cleanup lifecycle
- In-memory session store
- Hybrid retrieval:
  - pgvector semantic search
  - BM25-style retrieval
  - symbol scoring
  - documentation/text search
  - RRF fusion
- Fast retrieval mode
- Accurate retrieval mode with Cross-Encoder reranking
- LLM query router/planner with fallback rules
- Grounded answer generation with fallback behavior
- Custom AST-based Code Graph RAG
- Graph tools for definitions, references, callers, callees, impact, and flow
- Count query support for files/functions/classes/methods
- DB-only runtime tools:
  - `read_file` reads reconstructed text from indexed DB chunks
  - `find_references` scans indexed chunks instead of local files
  - `count_files` counts indexed files from chunk metadata
- LLM fallback/rate-limit warnings in `/chat`
- Frontend rendering for:
  - Question
  - Answer
  - Query Type
  - Tools Used
  - Sources
  - Raw Results
  - LLM warnings
- NUL byte sanitization before PostgreSQL writes
- Logging and evaluation scripts

Not used as the main architecture:

```text
Qdrant
Chroma as active vector storage
Neo4j
LangGraph
Deep Agents
```

---

## Architecture

```text
User
  ↓
Frontend / Streamlit / API client
  ↓
FastAPI or Streamlit service call
  ↓
Session Store
  ↓
Loaded IndexedCodebase
  ↓
LLM Query Planner or fallback router
  ↓
Agent tools
  ├── Hybrid retriever
  ├── DB-only read_file / reference scan / file count
  ├── Code graph tools
  └── Count/symbol tools
  ↓
Supabase/PostgreSQL + pgvector
  ↓
Answer + sources + raw_results + warnings
```

### Index-time vs runtime

```text
Index-time:
  company_repos/<repo_id> or GitHub clone or ZIP extraction
  ↓
  scan supported files
  ↓
  chunk + embed + build code graph
  ↓
  store data in Supabase/PostgreSQL + pgvector

Runtime/chat:
  load repository snapshot from DB
  ↓
  read chunks/embeddings/code graph from DB
  ↓
  answer questions without reading local source repo folders
```

---

## Repository Types

### 1. Company repositories

Company repositories are persistent repos managed by the project owner/admin.

They live locally at:

```text
company_repos/<repo_id>
```

Current sample company repos:

```text
company_repos/taskflow_api
company_repos/inventory_api
```

Each company repo may include:

```text
repo_config.json
```

Example:

```json
{
  "name": "TaskFlow API",
  "description": "TaskFlow API"
}
```

Company repo rules:

```text
source_type = company
is_persistent = true
expires_at = null
```

To add a new company repo:

```text
1. Copy source code into company_repos/<repo_id>
2. Optionally create company_repos/<repo_id>/repo_config.json
3. From backend/, run python -m scripts.index_company_repo <repo_id>
```

After indexing, the deployed backend does not need the local source folder to answer questions.

### 2. Temporary GitHub repositories

GitHub repos are indexed temporarily through the API/frontend.

Rules:

```text
source_type = github
is_persistent = false
expires_at != null
```

Runtime clone folder:

```text
backend/data/runtime/github/
```

### 3. Temporary ZIP repositories

ZIP uploads are indexed temporarily through the API/frontend.

Rules:

```text
source_type = zip_upload
is_persistent = false
expires_at != null
```

Runtime extraction folder:

```text
backend/data/runtime/uploads/
```

GitHub/ZIP user flows are intentionally temporary. Persistent storage is reserved for company repos indexed by the admin/local workflow.

---

## Supported Indexed Files

| Extension | Source type | Purpose |
|---|---|---|
| `.py` | `code` | Python source, functions/classes/methods, code graph |
| `.md`, `.markdown` | `doc` | README, docs, setup, architecture, onboarding |
| `.json` | `json` | Config and structured metadata |
| `.txt` | `text` | Notes and plain text docs |

Ignored directories include:

```text
.git
.venv
venv
__pycache__
.pytest_cache
.mypy_cache
.ruff_cache
.idea
.vscode
dist
build
node_modules
```

Ignored noisy files include:

```text
package-lock.json
yarn.lock
pnpm-lock.yaml
poetry.lock
pipfile.lock
```

The file size limit is controlled by:

```python
MAX_INDEX_FILE_BYTES = None
```

`None` means no per-file indexing size limit.

---

## Storage Model

Main PostgreSQL tables:

```text
repositories
chunks
chunk_embeddings
code_nodes
code_edges
index_jobs
```

Stored in Supabase/PostgreSQL:

```text
Repository metadata
Chunk text
Chunk metadata
Vector embeddings
Code graph nodes
Code graph edges
Temporary repo expiration metadata
```

The runtime answer system reads from:

```text
chunks
chunk_embeddings
code_nodes
code_edges
repositories
```

The local source repo folder is not the runtime source of truth. The indexed database snapshot is.

---

## Project Structure

```text
agentic-python-repo-rag-copilot/
├── backend/
│   ├── api/
│   │   ├── main.py
│   │   ├── schemas.py
│   │   └── routes/
│   │       ├── chat.py
│   │       ├── health.py
│   │       ├── repositories.py
│   │       └── temporary_repos.py
│   │
│   ├── app/
│   │   └── streamlit_app.py
│   │
│   ├── data/
│   │   └── eval_cases.json
│   │
│   ├── docker/
│   │   └── postgres/init/01_enable_vector.sql
│   │
│   ├── scripts/
│   │   ├── cleanup_temporary_repos.py
│   │   ├── index_company_repo.py
│   │   ├── init_db.py
│   │   ├── run_eval.py
│   │   └── test_storage_connections.py
│   │
│   ├── src/
│   │   ├── agent_core/
│   │   ├── chunking/
│   │   ├── core/
│   │   ├── db/
│   │   ├── embeddings/
│   │   ├── evaluation/
│   │   ├── generation/
│   │   ├── graph/
│   │   ├── indexing/
│   │   ├── ingestion/
│   │   ├── observability/
│   │   ├── parsing/
│   │   ├── reranking/
│   │   ├── retrieval/
│   │   ├── services/
│   │   └── storage/
│   │
│   ├── tests/
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── requirements.txt
│   └── .env.example
│
├── company_repos/
│   ├── taskflow_api/
│   └── inventory_api/
│
├── frontend/
│   ├── index.html
│   ├── script.js
│   ├── styles.css
│   └── logo_chatbot.jpg
│
├── .dockerignore
├── .gitignore
└── README.md
```

---

## Environment Variables

Create `.env` inside `backend/`:

```text
backend/.env
```

Use `backend/.env.example` as a template.

Example for Supabase cloud:

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
LLM_BACKEND=gemini

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_publishable_key_here

DATABASE_URL=postgresql+psycopg://postgres.your-project-ref:your_password@your-supabase-pooler-host:5432/postgres?sslmode=require

EMBEDDING_DIMENSION=384
CORS_ALLOW_ORIGINS=http://localhost:5173,http://localhost:3000,http://localhost:8501
```

Do not commit real `.env` values.

---

## Local Setup

From the repository root:

```powershell
cd agentic-python-repo-rag-copilot

py -3.10 -m venv .venv
.venv\Scripts\activate

cd backend
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Create `.env`:

```powershell
Copy-Item .env.example .env
```

Edit `.env` with your Gemini and database values.

---

## Database Setup

From `backend/`:

```powershell
python -m scripts.test_storage_connections
```

Expected:

```text
connection OK: 1
pgvector extension enabled: True
```

Initialize database schema:

```powershell
python -m scripts.init_db
```

This creates or verifies the required PostgreSQL tables and pgvector extension.

---

## Index Company Repositories

Company repos are located outside `backend/`:

```text
company_repos/
```

`backend/src/core/config.py` resolves them as:

```python
COMPANY_REPOS_DIR = PROJECT_ROOT.parent / "company_repos"
```

So from `backend/`, list company repos:

```powershell
python -m scripts.index_company_repo --list
```

Index the sample repos:

```powershell
python -m scripts.index_company_repo taskflow_api
python -m scripts.index_company_repo inventory_api
```

Re-index after changing source files:

```powershell
python -m scripts.index_company_repo <repo_id>
```

Re-indexing deletes the old indexed data for that `repo_id`, scans the current source repo, rebuilds chunks, embeddings, and code graph, then writes the new snapshot to Supabase/PostgreSQL.

---

## DB-only Runtime Test

Use this test to prove that Render does not need `company_repos/`.

From the project root after indexing:

```powershell
Rename-Item company_repos company_repos_backup
```

Run backend:

```powershell
cd backend
uvicorn api.main:app --reload --reload-dir api --reload-dir src --reload-exclude "logs/*" --reload-exclude "*.log"
```

Load a company repo and chat from the frontend or API.

Example questions:

```text
What does create_task do?
Where is create_task used?
có mấy file python
có mấy hàm trong repo này
```

If these work, runtime is reading from DB chunks/embeddings/code graph, not local source folders.

Restore the folder after testing:

```powershell
cd ..
Rename-Item company_repos_backup company_repos
```

---

## Run FastAPI Backend

From `backend/`:

```powershell
uvicorn api.main:app --reload --reload-dir api --reload-dir src --reload-exclude "logs/*" --reload-exclude "*.log"
```

Open:

```text
http://127.0.0.1:8000/docs
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

---

## Run Frontend

From the project root:

```powershell
cd frontend
python -m http.server 5173
```

Open:

```text
http://localhost:5173
```

The frontend currently points to:

```javascript
const API_BASE_URL = "http://localhost:8000";
```

For production, update `frontend/script.js` to your deployed backend URL.

---

## Run Streamlit Debug UI

From `backend/`:

```powershell
python -m streamlit run app\streamlit_app.py
```

Open:

```text
http://localhost:8501
```

Streamlit is useful for inspecting query type, tools used, sources, and raw results.

---

## API Endpoints

### Health

```http
GET /health
```

### List company repositories

```http
GET /company-repos
```

Returns persistent repositories already indexed in PostgreSQL.

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

The response includes `session_id`.

### Chat

```http
POST /chat
```

Example body:

```json
{
  "session_id": "your-session-id",
  "question": "What does create_task do?"
}
```

Response fields:

```text
session_id
question
query_type
answer
tools_used
sources
raw_results
warnings
```

### Temporary GitHub repository

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

GitHub repos are temporary:

```text
is_persistent = false
expires_at != null
```

### Temporary ZIP repository

```http
POST /temporary-repos/zip
```

Multipart form fields:

```text
file
session_id optional
retrieval_mode
use_llm
use_llm_router
```

ZIP repos are temporary:

```text
is_persistent = false
expires_at != null
```

### Delete temporary repository

```http
DELETE /temporary-repos/{repo_id}
```

Optional query parameter:

```text
session_id
```

---

## Query Types

The agent supports these query categories:

```text
documentation_query
location_query
reference_query
explanation_query
search_query
caller_query
callee_query
impact_query
flow_query
count_query
multi_intent_query
```

Examples:

```text
What does create_task do?
Where is create_task implemented?
Where is create_task used?
Who calls create_task?
What does create_task call?
What is affected if create_task changes?
có mấy file python
có mấy hàm trong repo này
```

---

## Inspect Database

From `backend/`.

### List repositories

```powershell
@'
from sqlalchemy import text
from src.db.session import get_db_session

with get_db_session() as s:
    rows = s.execute(text("""
        SELECT repo_id, name, source_type, is_persistent,
               file_count, doc_count, ignored_file_count,
               chunk_count, expires_at, created_at
        FROM repositories
        ORDER BY created_at DESC
        LIMIT 20
    """)).mappings().all()

for row in rows:
    print(dict(row))
'@ | python -
```

### Count chunks and embeddings

```powershell
@'
from sqlalchemy import text
from src.db.session import get_db_session

for repo_id in ["taskflow_api", "inventory_api"]:
    with get_db_session() as s:
        chunks = s.execute(
            text("SELECT COUNT(*) FROM chunks WHERE repo_id = :repo_id"),
            {"repo_id": repo_id},
        ).scalar()

        embeddings = s.execute(
            text("SELECT COUNT(*) FROM chunk_embeddings WHERE repo_id = :repo_id"),
            {"repo_id": repo_id},
        ).scalar()

    print(repo_id)
    print("chunks:", chunks)
    print("embeddings:", embeddings)
'@ | python -
```

### Inspect code graph

```powershell
@'
from sqlalchemy import text
from src.db.session import get_db_session

repo_id = "taskflow_api"

with get_db_session() as s:
    rows = s.execute(text("""
        SELECT qualified_name, node_type, relative_path, start_line, end_line
        FROM code_nodes
        WHERE repo_id = :repo_id
        ORDER BY relative_path, start_line
        LIMIT 50
    """), {"repo_id": repo_id}).mappings().all()

for row in rows:
    print(dict(row))
'@ | python -
```

### Check temporary repos

```powershell
@'
from sqlalchemy import text
from src.db.session import get_db_session

with get_db_session() as s:
    rows = s.execute(text("""
        SELECT repo_id, source_type, is_persistent, expires_at, created_at
        FROM repositories
        WHERE source_type IN ('github', 'zip_upload')
        ORDER BY created_at DESC
        LIMIT 20
    """)).mappings().all()

for row in rows:
    print(dict(row))
'@ | python -
```

Expected for GitHub/ZIP:

```text
is_persistent = False
expires_at != None
```

Expected for company repos:

```text
is_persistent = True
expires_at = None
```

---

## Evaluation

From `backend/`:

```powershell
python -m scripts.run_eval
```

Evaluation includes:

```text
Query type routing
Source precision
Citation validity
Latency
Answer non-empty rate
Router fallback rate
LLM failure rate
Graph caller/callee/impact behavior
```

---

## Cleanup Temporary Repositories

From `backend/`:

```powershell
python -m scripts.cleanup_temporary_repos --list
python -m scripts.cleanup_temporary_repos --dry-run
python -m scripts.cleanup_temporary_repos
```

---

## Docker

The backend includes:

```text
backend/Dockerfile
backend/docker-compose.yml
backend/docker/postgres/init/01_enable_vector.sql
```

For local PostgreSQL/pgvector:

```powershell
cd backend
docker compose --profile db up -d postgres
```

For API/Streamlit containers:

```powershell
cd backend
docker compose --profile app up --build
```

If you use Supabase cloud, Docker Desktop is not required.

---

## Render Deployment

Recommended backend deployment settings:

```text
Root Directory: backend
Build Command: pip install -r requirements.txt
Start Command: python -m uvicorn api.main:app --host 0.0.0.0 --port $PORT
```

Set environment variables on Render:

```text
GEMINI_API_KEY
GEMINI_MODEL
LLM_BACKEND
DATABASE_URL
EMBEDDING_DIMENSION
CORS_ALLOW_ORIGINS
```

Do not deploy `company_repos/` to Render. Company repos should be indexed from your local/admin machine into the same Supabase database used by Render.

Frontend can be deployed separately as a static site. Update `API_BASE_URL` in `frontend/script.js` to the Render backend URL.

---

## Important Runtime Rule

The backend answers from the **latest indexed snapshot** in Supabase/PostgreSQL.

If source code changes:

```text
1. Update the local/admin repo under company_repos/<repo_id>
2. Run python -m scripts.index_company_repo <repo_id> from backend/
3. Refresh frontend/load repo again
```

If you do not re-index, the deployed backend will keep answering from the previous DB snapshot.

This is expected behavior for a DB-backed RAG system.

---

## Known Notes

- Runtime is DB-only for repository content, but indexing still needs source files.
- `company_repos/` is local/admin-only and should not be required for Render runtime.
- GitHub and ZIP repos are temporary by design.
- The API session store is in memory. Backend restarts clear active sessions.
- `frontend/script.js` has a hardcoded local API URL by default.
- The uploaded ZIP may contain local artifacts such as `.git/`, `.env`, `backend/data/runtime/`, `backend/logs/`, and `__pycache__/`. Do not include those in public ZIP exports.

---

## Git Hygiene

Do not commit:

```text
.env
backend/.env
.venv/
backend/logs/
backend/data/runtime/
backend/data/indexes/
backend/data/repos/
__pycache__/
*.pyc
*.sqlite
*.sqlite3
*.db
```

