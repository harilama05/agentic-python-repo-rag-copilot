# Agentic Python Repo RAG Copilot

Agentic Python Repo RAG Copilot is an AI assistant for understanding Python codebases. It can index local company repositories, temporary public GitHub repositories, and ZIP uploads, then answer codebase questions using hybrid retrieval, pgvector embeddings, and a custom Python AST code graph.

The current version uses **FastAPI + Streamlit + static HTML/CSS/JS frontend** on top of **Supabase/PostgreSQL + pgvector**.

---

## Current Snapshot

This README is based on the latest reviewed repository snapshot.

Implemented:

- Streamlit UI for local/debug usage.
- Static frontend in `frontend/`.
- FastAPI backend in `api/`.
- Supabase/PostgreSQL metadata storage.
- PostgreSQL `pgvector` embedding storage.
- Python, Markdown, JSON, and TXT indexing.
- Persistent company repository workflow.
- Auto-discovered company repositories from `company_repos/`.
- `repo_config.json` support for company repo display name/description.
- Temporary GitHub repository ingestion.
- Temporary ZIP upload ingestion.
- Temporary repository lifecycle cleanup.
- In-memory API session store.
- Hybrid retrieval with vector search, BM25-style scoring, symbol matching, documentation/text search, and RRF fusion.
- Optional Cross-Encoder reranking in accurate mode.
- LLM query router/planner with fallback rules.
- Grounded answer generation with fallback behavior.
- Custom AST-based Code Graph RAG.
- Caller/callee/reference/impact/flow tools.
- Count query support through code graph symbol counting.
- LLM warning extraction in the API response.
- Frontend warning rendering for LLM fallback/rate-limit cases.
- NUL-byte sanitization for text-like content before PostgreSQL writes.
- Logging and evaluation scripts.

Not used as the main architecture:

- Qdrant
- Chroma
- Neo4j
- LangGraph
- Deep Agents

---

## High-Level Architecture

```text
User
  ↓
Streamlit UI / Static Frontend / FastAPI Client
  ↓
FastAPI API or Streamlit service call
  ↓
Session Store
  ↓
IndexedCodebase
  ↓
LLM Query Planner or fallback router
  ↓
Agent tools
  ├── Hybrid retriever
  ├── Code graph tools
  ├── File reader
  └── Count/symbol tools
  ↓
Supabase/PostgreSQL + pgvector
  ↓
Grounded answer + sources + raw_results + warnings
```

---

## Repository Modes

### 1. Company Repositories

Company repositories are persistent repositories managed by the project owner/admin.

Current folder:

```text
company_repos/
```

Current sample company repos:

```text
company_repos/taskflow_api
company_repos/inventory_api
```

Each repo may include:

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

To add a new company repo:

```text
1. Copy the source code into company_repos/<repo_id>
2. Optionally create company_repos/<repo_id>/repo_config.json
3. Run python -m scripts.index_company_repo <repo_id>
```

No Python code change is required for new company repos because `src/services/company_repos.py` auto-discovers folders under `company_repos/`.

### 2. Temporary GitHub Repositories

A public GitHub URL can be cloned and indexed temporarily.

Runtime files are stored under:

```text
data/runtime/github/
```

The repository is marked temporary and can be cleaned up later.

### 3. Temporary ZIP Repositories

A ZIP file can be uploaded and indexed temporarily.

Runtime files are stored under:

```text
data/runtime/uploads/
```

ZIP ingestion includes path traversal protection and file count/size checks.

---

## Supported Indexed File Types

| Extension | Source type | Purpose |
|---|---|---|
| `.py` | `code` | Python code, AST graph, symbols |
| `.md`, `.markdown` | `doc` | README, docs, guides |
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

Ignored lock/noisy files include:

```text
package-lock.json
yarn.lock
pnpm-lock.yaml
poetry.lock
pipfile.lock
```

The current file size limit is controlled by:

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

What is stored:

```text
Repository metadata
Chunk text
Chunk citation metadata
Vector embeddings
Code graph nodes
Code graph edges
Temporary repository expiration metadata
```

What remains local:

```text
company_repos/
data/runtime/github/
data/runtime/uploads/
frontend/
```

The API session store is currently in memory. If the backend process restarts, sessions are lost and repos need to be loaded again.

---

## Code Graph RAG

The project builds an AST-based graph from Python files.

Graph nodes include:

```text
function
class
method
```

Graph edges include:

```text
contains
calls
```

Code graph features include:

```text
find definitions
find references
find callers
find callees
impact analysis
flow analysis
symbol counting
```

Example questions:

```text
Where is create_task implemented?
Where is create_task used?
Who calls TaskService.create_task?
What does TaskService.create_task call?
What may be affected if create_task changes?
How many functions are in this repo?
có mấy hàm trong repo này
```

---

## Count Query Behavior

The current code includes:

```text
QUERY_TYPE_COUNT = "count_query"
```

and a graph-backed tool:

```text
count_symbols(symbol_type)
```

This means count-style questions can be answered from the code graph instead of semantic retrieval.

Examples:

```text
how many functions are in this repository?
count classes
có mấy hàm trong repo này
có bao nhiêu class
```

Current caveat: the fallback router contains deterministic count rules, and the LLM router/planner prompt includes `count_query`. However, if the LLM planner still returns `search_query`, the answer may still go through semantic retrieval. For maximum stability, add a pre-router deterministic check for count/list-symbol questions before calling the LLM planner.

---

## Frontend

The repository includes a static frontend:

```text
frontend/
├── index.html
├── script.js
├── styles.css
└── logo_chatbot.jpg
```

The frontend currently uses:

```javascript
const USE_MOCK = false;
const API_BASE_URL = "http://localhost:8000";
```

Frontend features:

- Loads company repos from `GET /company-repos`
- Loads selected company repo through `POST /company-repos/{repo_id}/load`
- Indexes temporary GitHub repos through `POST /temporary-repos/github`
- Uploads temporary ZIP repos through `POST /temporary-repos/zip`
- Chats through `POST /chat`
- Stores `session_id`
- Displays repository stats in the sidebar
- Renders answer blocks in a Streamlit-like report layout:
  - Question
  - LLM warnings
  - Answer
  - Query Type
  - Tools Used
  - Sources
  - Raw Results
- Displays status messages inline in the chat header

Run frontend:

```powershell
cd frontend
python -m http.server 5173
```

Open:

```text
http://localhost:5173
```

---

## Streamlit UI

Run:

```powershell
python -m streamlit run app\streamlit_app.py
```

Open:

```text
http://localhost:8501
```

Streamlit is useful for debugging because it exposes answer, query type, tools used, sources, and raw results.

---

## FastAPI Backend

Run:

```powershell
uvicorn api.main:app --reload --reload-dir api --reload-dir src --reload-exclude "logs/*" --reload-exclude "*.log"
```

Open API docs:

```text
http://127.0.0.1:8000/docs
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

---

## API Endpoints

### Health

```http
GET /health
```

### List company repos

```http
GET /company-repos
```

Returns persistent repositories already indexed in PostgreSQL.

### Load company repo

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

The response includes:

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

### Temporary GitHub repo

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

### Temporary ZIP repo

```http
POST /temporary-repos/zip
```

Multipart form-data fields:

```text
file
session_id optional
retrieval_mode
use_llm
use_llm_router
```

### Delete temporary repo

```http
DELETE /temporary-repos/{repo_id}
```

Optional query parameter:

```text
session_id
```

---

## Environment Variables

Create `.env` in the root folder.

### Supabase cloud example

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

Do not commit real `.env` secrets.

---

## Local Setup

```powershell
git clone https://github.com/harilama05/agentic-python-repo-rag-copilot.git
cd agentic-python-repo-rag-copilot

py -3.10 -m venv .venv
.venv\Scripts\activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Create `.env`, then test DB:

```powershell
python -m scripts.test_storage_connections
```

Expected:

```text
Supabase PostgreSQL (...) connection OK: 1
pgvector extension enabled: True
```

Initialize DB:

```powershell
python -m scripts.init_db
```

---

## Index Company Repositories

List discovered company repos:

```powershell
python -m scripts.index_company_repo --list
```

Index TaskFlow API:

```powershell
python -m scripts.index_company_repo taskflow_api
```

Index Inventory API:

```powershell
python -m scripts.index_company_repo inventory_api
```

Re-index after changing any `.py`, `.md`, `.json`, or `.txt` file:

```powershell
python -m scripts.index_company_repo <repo_id>
```

This deletes old indexed data for that `repo_id`, scans current files, rebuilds chunks, rebuilds the code graph, regenerates embeddings, and writes the updated state to PostgreSQL/pgvector.

---

## Full Local Run

Terminal 1: backend

```powershell
cd "...\agentic-python-repo-rag-copilot"
.venv\Scripts\activate
uvicorn api.main:app --reload --reload-dir api --reload-dir src --reload-exclude "logs/*" --reload-exclude "*.log"
```

Terminal 2: frontend

```powershell
cd "...\agentic-python-repo-rag-copilot\frontend"
python -m http.server 5173
```

Open:

```text
http://localhost:5173
```

Optional Streamlit:

```powershell
python -m streamlit run app\streamlit_app.py
```

---

## Inspect Database

List repositories:

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

Count chunks and embeddings:

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

Inspect code graph:

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

---

## Cleanup Temporary Repositories

List temporary repos:

```powershell
python -m scripts.cleanup_temporary_repos --list
```

Dry run:

```powershell
python -m scripts.cleanup_temporary_repos --dry-run
```

Execute cleanup:

```powershell
python -m scripts.cleanup_temporary_repos
```

---

## Evaluation

Run:

```powershell
python -m scripts.run_eval
```

The evaluation prints:

```text
Average source precision
Average citation validity
Average latency seconds
Answer non-empty rate
Router fallback rate
LLM failure rate
```

---

## Docker

The repo includes Docker files:

```text
Dockerfile
docker-compose.yml
docker/postgres/init/01_enable_vector.sql
```

For Supabase cloud, Docker Desktop is not required.

For local PostgreSQL/pgvector:

```powershell
docker compose --profile db up -d postgres
```

Use a local `DATABASE_URL`, then run:

```powershell
python -m scripts.test_storage_connections
python -m scripts.init_db
```

---

## Git Hygiene

Do not commit:

```text
.env
.venv/
logs/
data/runtime/
data/indexes/
data/repos/
__pycache__/
*.pyc
*.sqlite
*.sqlite3
*.db
.git/ inside exported ZIP files
```

The reviewed ZIP still contains `.env`, `.git/`, `data/runtime/`, and `__pycache__/` artifacts. Clean these before sharing a public ZIP.

Recommended before commit:

```powershell
git status
git add .
git status
git commit -m "Update Agentic RAG copilot"
git push origin main
```

---

## Known Current Limitations

1. **Session store is in memory.**  
   Backend reloads clear active FastAPI sessions.

2. **The uploaded ZIP contains local artifacts.**  
   `.env`, `.git/`, `data/runtime/`, and `__pycache__/` should be removed from public ZIP exports.

3. **No external auth layer yet.**  
   Do not deploy publicly without authentication and rate limiting.

4. **`requirements.txt` may still include unused dependencies.**  
   If Chroma is no longer used, clean it up later.

---

## Roadmap

Recommended next improvements:

```text
1. Add Redis or another persistent session store.
2. Add pytest tests for API, routing, scanner, chunking, storage, and graph tools.
3. Clean runtime artifacts from exported ZIPs.
4. Add deployment docs for backend/frontend.
5. Add authentication if deployed publicly.
6. Add incremental indexing for larger repos.
7. Remove unused dependencies.
```
