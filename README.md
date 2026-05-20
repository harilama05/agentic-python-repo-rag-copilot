# Agentic Python Repo RAG Copilot

Agentic Python Repo RAG Copilot is an AI assistant for understanding Python codebases. It can load a pre-indexed company repository, temporarily index a public GitHub repository or ZIP upload, retrieve relevant code/docs/config/text chunks, use an AST-based code graph, and answer repository questions with citations.

The current version uses **Supabase/PostgreSQL + pgvector** as the single database/storage layer for metadata, chunks, graph data, and embeddings.

---

## Current status

Implemented:

- Streamlit UI for local/demo usage
- FastAPI backend API
- Supabase/PostgreSQL metadata storage
- Supabase/PostgreSQL `pgvector` embedding storage
- Python, Markdown, JSON, and TXT indexing
- Temporary GitHub repository ingestion
- Temporary ZIP upload ingestion
- Persistent company repository indexing
- In-memory session store for loaded repositories
- RRF-based multi-source retrieval
- Optional Cross-Encoder accurate reranking mode
- LLM query router with fallback routing
- Grounded answer generation with fallback behavior
- Custom AST-based Code Graph RAG
- Caller/callee/impact analysis for Python symbols
- Code graph persistence in PostgreSQL
- Repository lifecycle cleanup for temporary repositories
- Logging
- Extended evaluation metrics
- NUL byte sanitization before writing text into PostgreSQL
- FastAPI CORS support for future frontend integration

Not currently used:

- Qdrant
- Chroma
- LangGraph
- Deep Agents
- Neo4j

The project has a custom agent workflow and a custom AST-based code graph.

---

## What the project does

The app helps answer questions such as:

```text
Where is create_task implemented?
Where is create_task used?
What does TaskService.create_task do?
What calls TaskService.create_task?
What does TaskService.create_task call?
If I change create_task, what might be affected?
Where is JSON indexing mentioned?
Where is text file indexing mentioned?
```

For code relationship questions, it uses the Python AST code graph.

For semantic questions, it uses vector retrieval, BM25-style retrieval, symbol metadata, documentation/text retrieval, RRF fusion, and optional reranking.

---

## High-level architecture

```text
User
  ↓
Streamlit UI / FastAPI API
  ↓
Session Store
  ↓
Loaded IndexedCodebase
  ↓
LLM Router or Fallback Router
  ↓
Query Plan
  ↓
Tools:
  - Semantic/vector retriever
  - BM25/keyword retriever
  - Symbol/reference search
  - Code graph tools
  - File reader
  ↓
Grounded Answer Generator / Fallback Answer
  ↓
Answer + sources
```

---

## Storage architecture

The current version uses Supabase/PostgreSQL for all persistent database storage.

Main tables:

```text
repositories       -> repository metadata
chunks             -> indexed code/doc/json/text chunks
chunk_embeddings   -> embeddings stored with pgvector
code_nodes         -> AST code graph nodes
code_edges         -> AST code graph edges
index_jobs         -> indexing job metadata, if used
```

### What is stored in Supabase/PostgreSQL

```text
Repository metadata
Chunk text
Chunk citation metadata
Vector embeddings
Code graph nodes
Code graph edges
Temporary repo metadata
Expiration timestamps for temporary repos
```

### What is still local

Temporary GitHub/ZIP source files are still stored locally while the session/repo is active:

```text
data/runtime/github/
data/runtime/uploads/
```

These files are needed because the app may need to read the original source file for excerpts, citations, and debugging.

### What is not stored

The current design does not need to store full chat history in the database.

---

## Repository types

### 1. Company repository

Company repositories are persistent.

Example:

```text
taskflow_api
```

They use:

```text
source_type = company
is_persistent = true
expires_at = null
```

Company repositories are indexed by script, not directly by public UI/API.

```powershell
python -m scripts.index_company_repo taskflow_api
```

### 2. GitHub temporary repository

A user can provide a public GitHub URL. The app clones and indexes it temporarily.

GitHub temporary repositories use:

```text
source_type = github
is_persistent = false
expires_at = set
```

The cloned source is stored under:

```text
data/runtime/github/
```

### 3. ZIP temporary repository

A user can upload a ZIP file. The app extracts and indexes it temporarily.

ZIP temporary repositories use:

```text
source_type = zip_upload
is_persistent = false
expires_at = set
```

The extracted source is stored under:

```text
data/runtime/uploads/
```

---

## Supported indexed file types

The indexer currently supports:

| File type | Source type | Purpose |
|---|---:|---|
| `.py` | `code` | Python functions, classes, methods, AST graph |
| `.md`, `.markdown` | `doc` | README, guides, docs, changelogs, architecture notes |
| `.json` | `json` | Config files, structured metadata, examples |
| `.txt` | `text` | Notes, simple documentation, plain text resources |

The Markdown scanner indexes all `.md` and `.markdown` files that are not ignored.

---

## Ignored files and directories

Ignored directories include typical generated/runtime folders such as:

```text
.git/
.venv/
venv/
__pycache__/
.pytest_cache/
.mypy_cache/
.ruff_cache/
.idea/
.vscode/
dist/
build/
node_modules/
```

Ignored filenames include noisy lock files such as:

```text
package-lock.json
yarn.lock
pnpm-lock.yaml
poetry.lock
pipfile.lock
```

The optional file size limit is controlled by:

```python
MAX_INDEX_FILE_BYTES = None
```

Set it to an integer byte value to skip very large files. For example:

```python
MAX_INDEX_FILE_BYTES = 2 * 1024 * 1024
```

---

## NUL byte sanitization

PostgreSQL text fields cannot store NUL bytes (`\x00`). Some text-like files, especially files with unusual encoding, can contain NUL bytes.

The current version sanitizes NUL bytes in:

```text
src/parsing/text_parser.py
src/parsing/json_parser.py
src/storage/supabase_vector_store.py
src/storage/metadata/chunk_mixin.py
src/storage/metadata/utils.py
```

This prevents errors such as:

```text
PostgreSQL text fields cannot contain NUL (0x00) bytes
```

---

## Retrieval pipeline

### Fast mode

Fast mode uses multi-source retrieval and RRF fusion.

```text
Question
  ↓
Vector search
BM25/keyword search
Symbol metadata search
Documentation/text search
  ↓
RRF fusion
  ↓
Top chunks
```

### Accurate mode

Accurate mode adds Cross-Encoder reranking after initial retrieval.

```text
Question
  ↓
RRF candidate retrieval
  ↓
Cross-Encoder reranking
  ↓
Top chunks
```

---

## Code Graph RAG

The project builds a custom AST-derived code graph for Python repositories.

The graph stores:

```text
functions
classes
methods
contains edges
calls edges
file paths
line ranges
qualified names
```

It supports questions such as:

```text
Where is create_task used?
Who calls TaskService.create_task?
What does TaskService.create_task call?
What is impacted if create_task changes?
```

This is custom Code Graph RAG. It is not LangGraph, Neo4j, or a graph database.

---

## Agent workflow

The agent workflow is custom Python code.

It includes:

```text
LLM query router
Fallback router
Tool execution
Retrieval tools
Graph tools
Grounded answer generator
Fallback answer behavior
```

LangGraph is not required for the current implementation. LangGraph could be added later as an optional workflow orchestrator, but the current project already has an agentic workflow through query planning, tool routing, retrieval, graph tools, and answer generation.

---

## Tech stack

Core:

```text
Python 3.10
Streamlit
FastAPI
SQLAlchemy
psycopg
Supabase PostgreSQL
pgvector
sentence-transformers
Cross-Encoder reranking
Gemini API
```

Storage:

```text
Supabase/PostgreSQL
pgvector
```

No longer used in the main storage path:

```text
Qdrant
Chroma
```

---

## Project structure

```text
agentic-python-repo-rag-copilot/
├── api/
│   ├── main.py
│   ├── schemas.py
│   └── routes/
│       ├── chat.py
│       ├── health.py
│       ├── repositories.py
│       └── temporary_repos.py
│
├── app/
│   └── streamlit_app.py
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
│   ├── init_db.py
│   ├── run_eval.py
│   ├── test_load_existing_repo.py
│   └── test_storage_connections.py
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
│   ├── parsing/
│   ├── reranking/
│   ├── retrieval/
│   ├── services/
│   └── storage/
│       ├── lifecycle/
│       ├── metadata/
│       └── supabase_vector_store.py
│
├── tests/
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
├── .env.docker.example
└── README.md
```

---

## Environment variables

Create a `.env` file in the project root.

Do not commit `.env`.

### Supabase cloud example

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
LLM_BACKEND=gemini

SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_publishable_key_here

DATABASE_URL=postgresql+psycopg://postgres.your-project-ref:your_database_password@your-supabase-pooler-host:5432/postgres?sslmode=require

EMBEDDING_DIMENSION=384
CORS_ALLOW_ORIGINS=http://localhost:5173,http://localhost:3000,http://localhost:8501
```

Important:

```text
SUPABASE_KEY is not the PostgreSQL password.
DATABASE_URL must use the database password from Supabase.
For SQLAlchemy + psycopg, prefer postgresql+psycopg://...
```

### Local Docker PostgreSQL example

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
LLM_BACKEND=gemini

DATABASE_URL=postgresql+psycopg://rag_user:rag_password@localhost:55432/rag_db

EMBEDDING_DIMENSION=384
CORS_ALLOW_ORIGINS=http://localhost:5173,http://localhost:3000,http://localhost:8501
```

### Docker container example

`.env.docker.example` should use the Docker service name:

```env
DATABASE_URL=postgresql+psycopg://rag_user:rag_password@postgres:5432/rag_db
```

Inside Docker, the database host is `postgres`. Outside Docker, the database host is usually `localhost`.

---

## Local setup

### 1. Clone repository

```powershell
git clone https://github.com/harilama05/agentic-python-repo-rag-copilot.git
cd agentic-python-repo-rag-copilot
```

To clone a specific branch:

```powershell
git clone -b newbranch --single-branch https://github.com/harilama05/agentic-python-repo-rag-copilot.git
```

### 2. Create virtual environment

```powershell
py -3.10 -m venv .venv
.venv\Scripts\activate
```

If `py -3.10` is not available:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Create `.env`

Create `.env` in the project root using the examples above.

---

## Supabase setup

In Supabase:

1. Create a project.
2. Open **Connect** and copy the PostgreSQL connection string.
3. Use the pooler connection string if recommended.
4. Use the database password, not the Supabase API key.
5. Put the final SQLAlchemy URL into `.env` as `DATABASE_URL`.

Test:

```powershell
python -m scripts.test_storage_connections
```

Expected:

```text
Supabase PostgreSQL (...) connection OK: 1
pgvector extension enabled: True
```

Initialize tables:

```powershell
python -m scripts.init_db
```

---

## Optional local Docker database

If you want a local PostgreSQL database instead of Supabase cloud:

```powershell
docker compose --profile db up -d postgres
```

Then use:

```env
DATABASE_URL=postgresql+psycopg://rag_user:rag_password@localhost:55432/rag_db
```

Test:

```powershell
python -m scripts.test_storage_connections
```

---

## Index company repository

Index or re-index the sample company repository:

```powershell
python -m scripts.index_company_repo taskflow_api
```

This will:

```text
delete old index data for the repo
scan supported files
build chunks
build code graph
create embeddings
write repositories/chunks/embeddings/code graph into Supabase/PostgreSQL
```

The script uses `reset_collection=True`, which means it resets embeddings for the repo before writing the new index.

Although the name says `collection`, in the pgvector version it means:

```text
delete old vectors/embeddings for this repo_id
```

---

## Load an existing indexed repository

```powershell
python -m scripts.test_load_existing_repo
```

When prompted, enter:

```text
taskflow_api
```

---

## Run evaluation

```powershell
python -m scripts.run_eval
```

The evaluation checks:

```text
query type routing
source recall
source precision
citation validity
latency
answer non-empty rate
router fallback rate
LLM failure rate
graph caller/callee/impact behavior
```

---

## Run Streamlit UI

```powershell
python -m streamlit run app\streamlit_app.py
```

Then open:

```text
http://localhost:8501
```

Test flows:

```text
Company Repo
GitHub URL
ZIP Upload
```

Suggested UI tests:

```text
Where is create_task used?
Where is create_task implemented?
Where is json indexing mentioned?
Where is text file indexing mentioned?
What does TaskService.create_task do?
```

---

## Run FastAPI backend

```powershell
uvicorn api.main:app --reload --reload-dir api --reload-dir src --reload-exclude "logs/*" --reload-exclude "*.log"
```

API docs:

```text
http://127.0.0.1:8000/docs
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

---

## FastAPI endpoints

### Health

```http
GET /health
```

### List company repositories

```http
GET /company-repos
```

### Load company repository

```http
POST /company-repos/{repo_id}/load
```

Example:

```json
{
  "retrieval_mode": "fast",
  "use_llm": true,
  "use_llm_router": true
}
```

The API returns a `session_id`.

### Chat

```http
POST /chat
```

Example:

```json
{
  "session_id": "your-session-id",
  "question": "Where is create_task used?"
}
```

### Temporary GitHub repo

```http
POST /temporary-repos/github
```

Example:

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

Uses multipart form-data.

### Cleanup temporary repo

```http
DELETE /temporary-repos/{repo_id}
```

---

## Check what is stored in the database

The project uses `get_db_session()` as a context manager. Use `with get_db_session() as session:`.

### List repositories

```powershell
@'
from sqlalchemy import text
from src.db.session import get_db_session

with get_db_session() as s:
    rows = s.execute(text("""
        SELECT
            repo_id,
            name,
            source_type,
            is_persistent,
            file_count,
            doc_count,
            ignored_file_count,
            chunk_count,
            expires_at,
            created_at
        FROM repositories
        ORDER BY created_at DESC
        LIMIT 20
    """)).mappings().all()

for r in rows:
    print(dict(r))
'@ | python -
```

### List chunks for a repo

```powershell
@'
from sqlalchemy import text
from src.db.session import get_db_session

repo_id = "taskflow_api"

with get_db_session() as s:
    rows = s.execute(text("""
        SELECT
            source_type,
            relative_path,
            start_line,
            end_line,
            symbol_name,
            qualified_name,
            symbol_type,
            heading
        FROM chunks
        WHERE repo_id = :repo_id
        ORDER BY source_type, relative_path, start_line
    """), {"repo_id": repo_id}).mappings().all()

for r in rows:
    print(dict(r))
'@ | python -
```

### Compare chunks and embeddings

```powershell
@'
from sqlalchemy import text
from src.db.session import get_db_session

repo_id = "taskflow_api"

with get_db_session() as s:
    chunks = s.execute(
        text("SELECT COUNT(*) FROM chunks WHERE repo_id = :repo_id"),
        {"repo_id": repo_id},
    ).scalar()

    embeddings = s.execute(
        text("SELECT COUNT(*) FROM chunk_embeddings WHERE repo_id = :repo_id"),
        {"repo_id": repo_id},
    ).scalar()

print("chunks:", chunks)
print("embeddings:", embeddings)
'@ | python -
```

### Check temporary GitHub/ZIP repos

```powershell
@'
from sqlalchemy import text
from src.db.session import get_db_session

with get_db_session() as s:
    rows = s.execute(text("""
        SELECT
            repo_id,
            name,
            source_type,
            is_persistent,
            chunk_count,
            local_path,
            expires_at,
            created_at
        FROM repositories
        WHERE source_type IN ('github', 'zip_upload')
        ORDER BY created_at DESC
        LIMIT 20
    """)).mappings().all()

for r in rows:
    print(dict(r))
'@ | python -
```

Temporary repos should have:

```text
is_persistent = false
expires_at != null
```

### Test vector search directly

```powershell
@'
from src.storage.supabase_vector_store import SupabaseCodeVectorStore

store = SupabaseCodeVectorStore(repo_id="taskflow_api")
results = store.search_text("create_task", top_k=5)

for r in results:
    print(r["score"], r["relative_path"], r["source_type"], r.get("qualified_name"))
'@ | python -
```

---

## Cleanup temporary repositories

List or clean temporary repositories:

```powershell
python -m scripts.cleanup_temporary_repos --list
python -m scripts.cleanup_temporary_repos --dry-run
python -m scripts.cleanup_temporary_repos
```

---

## Git workflow

Check branch:

```powershell
git branch --show-current
```

Commit:

```powershell
git add .
git commit -m "Clean Supabase pgvector storage and indexing workflow"
```

Push current branch:

```powershell
git push origin newbranch
```

Push local `newbranch` to remote `main`:

```powershell
git push origin newbranch:main
```

Do not commit:

```text
.env
.venv/
logs/
data/runtime/
__pycache__/
*.pyc
_updates/
_nul_updates/
check_db.py
```

---

## Troubleshooting

### `DATABASE_URL is not set`

Create `.env` or set the variable in the current PowerShell session:

```powershell
$env:DATABASE_URL="postgresql+psycopg://..."
```

### `password authentication failed for user postgres`

The Supabase database password is wrong, or the connection string is wrong.

Use the connection string from Supabase Dashboard → Connect.

Do not use `SUPABASE_KEY` as the database password.

### `pgvector extension enabled: False`

Run:

```powershell
python -m scripts.init_db
```

or ensure the project has permission to run:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### `PostgreSQL text fields cannot contain NUL (0x00) bytes`

This means some indexed text contained `\x00`.

The current version sanitizes NUL bytes before writing to PostgreSQL. Re-run the failed indexing after applying the latest parser/storage changes.

### VS Code/Pylance cannot resolve `src...` imports

Open VS Code at the project root and add:

```json
{
  "python.analysis.extraPaths": [
    "."
  ]
}
```

Select the correct `.venv` interpreter.

### Docker local Postgres does not start

The compose file uses profiles. Start DB with:

```powershell
docker compose --profile db up -d postgres
```

### CRLF/LF warnings on Windows

Warnings like this are not fatal:

```text
LF will be replaced by CRLF
```

You can ignore them, or add `.gitattributes` later.

---

## Roadmap

Recommended next steps:

```text
1. Finalize Streamlit demo flow
2. Finish FastAPI backend tests
3. Build a React/Vite frontend
4. Connect frontend to FastAPI
5. Deploy backend
6. Deploy frontend
7. Add README screenshots/demo video
```

Optional later improvements:

```text
LangGraph workflow orchestration
Redis session store
Incremental indexing
Better code file intent routing
Production vector indexes for pgvector
Authentication
Saved user repositories
Better frontend UX
```

---

## License

This project is intended for educational and portfolio use.
