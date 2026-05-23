# Agentic Python Repo RAG Copilot

Agentic Python Repo RAG Copilot is an AI-powered assistant for understanding Python codebases. It indexes Python repositories, stores chunks/embeddings/code graph data in Supabase/PostgreSQL + pgvector, and answers codebase questions with source citations.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | Python 3.10, FastAPI, Uvicorn |
| Debug UI | Streamlit |
| Frontend | Static HTML/CSS/JS |
| Database | Supabase / PostgreSQL + pgvector |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`, 384-dim) |
| Reranking | Cross-Encoder (`ms-marco-MiniLM-L-6-v2`) |
| LLM | Google Gemini (`gemini-2.5-flash`) |
| Code Graph | Custom AST-based (Python `ast` module) |
| BM25 | rank-bm25 |
| Infrastructure | Docker, Docker Compose |
| Frontend Deploy | Vercel (static site) |
| Backend Deploy | Render (web service) |

---

## Features

- FastAPI backend in `backend/api/`
- Static frontend in `frontend/`
- Streamlit debug UI in `backend/app/streamlit_app.py`
- Supabase/PostgreSQL metadata storage
- PostgreSQL `pgvector` embedding storage
- Python, Markdown, JSON, and TXT indexing
- Persistent company repositories indexed from local/admin `company_repos/`
- Temporary GitHub repository indexing
- Temporary ZIP repository indexing
- Temporary repo cleanup lifecycle
- DB-only runtime for repository content
- Hybrid retrieval with vector search, BM25-style retrieval, symbol scoring, documentation/text search, and RRF fusion
- Fast retrieval mode
- Accurate retrieval mode with Cross-Encoder reranking
- LLM query router/planner with fallback rules
- Grounded answer generation with fallback behavior
- Custom AST-based Code Graph RAG
- Graph tools for definitions, references, callers, callees, impact, and flow
- Count query support for files/functions/classes/methods
- LLM fallback/rate-limit warnings in `/chat`
- Frontend rendering for answer, query type, tools used, sources, raw results, and warnings
- NUL byte sanitization before PostgreSQL writes
- Docker-first local run

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

Core design:

```text
Index-time may read source repositories.
Runtime/chat is DB-only.
```

So `company_repos/` is only needed on the local/admin machine when indexing or re-indexing company repos. The deployed backend, for example on Render, should load and answer from Supabase/PostgreSQL + pgvector and does not need `company_repos/`.

---

## Pipeline

### Indexing Pipeline

When a repository is indexed, the following steps execute in order:

```text
Source Repository (Python / Markdown / JSON / TXT files)
  ↓
1. File Scanner
   Walks the repo directory, collects supported files, skips ignored directories/files.
  ↓
2. Python AST Parser
   Parses .py files into functions, classes, methods, and module-level code.
   Extracts symbol metadata (name, type, line range, docstring).
  ↓
3. Chunker
   Splits parsed symbols and documents into indexed chunks.
   Each chunk has: text, metadata (relative_path, line range, symbol info, source_type).
  ↓
4. Embedding Generator
   Generates vector embeddings for each chunk using sentence-transformers (all-MiniLM-L6-v2, 384-dim).
  ↓
5. Code Graph Builder
   Builds a directed graph of function/method calls using Python AST analysis.
   Nodes = functions/classes/methods. Edges = calls/contains relationships.
  ↓
6. Storage Writer
   Writes all data to Supabase/PostgreSQL:
   - repositories table: repo metadata
   - chunks table: chunk text + metadata
   - chunk_embeddings table: pgvector embeddings
   - code_nodes table: graph nodes
   - code_edges table: graph edges
   - index_jobs table: indexing job status
```

### Query/Chat Pipeline

When a user asks a question, the following steps execute:

```text
User Question
  ↓
1. Query Router (LLM or fallback rule-based)
   Classifies the question into a query type:
   documentation_query, location_query, reference_query,
   explanation_query, search_query, caller_query, callee_query,
   impact_query, flow_query, count_query, multi_intent_query
  ↓
2. Agent Tool Selection
   Based on query type, the agent selects appropriate tools:
   - search_code: hybrid retrieval (vector + BM25 + symbol + doc search + RRF fusion)
   - read_file: DB-only file content reader
   - get_definition / get_references / get_callers / get_callees: code graph tools
   - get_impact / get_flow: impact analysis and flow tracing
   - count_files / count_functions / count_classes: counting tools
  ↓
3. Hybrid Retrieval (for search_code)
   ┌─ Vector search (pgvector cosine similarity)
   ├─ BM25 search (full-text keyword matching)
   ├─ Symbol search (function/class name matching)
   └─ Documentation search (for documentation queries)
   → Reciprocal Rank Fusion (RRF) merges all ranked lists
  ↓
4. Cross-Encoder Reranking (accurate mode only)
   Reranks RRF results using cross-encoder/ms-marco-MiniLM-L-6-v2
  ↓
5. LLM Answer Generation
   Generates a grounded answer using Gemini with retrieved context.
   Falls back to raw results if LLM is unavailable or rate-limited.
  ↓
6. Response
   Returns: answer, query_type, tools_used, sources, raw_results, warnings
```

---

## Repository Types

### Company repositories

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
3. From backend/, run:
   docker compose run --rm api python -m scripts.index_company_repo <repo_id>
```

After indexing, the deployed backend does not need the local source folder to answer questions.

### Temporary GitHub repositories

GitHub repos are indexed temporarily through the API/frontend.

```text
source_type = github
is_persistent = false
expires_at != null
```

### Temporary ZIP repositories

ZIP uploads are indexed temporarily through the API/frontend.

```text
source_type = zip_upload
is_persistent = false
expires_at != null
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

Ignored directories:

```text
.git
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

The file size limit is controlled by:

```python
MAX_INDEX_FILE_BYTES = None
```

`None` means no per-file indexing size limit.

---

## Storage Model

Main PostgreSQL tables:

```text
repositories       Repo metadata (repo_id, name, source_type, is_persistent, chunk_count, ...)
chunks             Chunk text + metadata (relative_path, line range, symbol info, source_type)
chunk_embeddings   pgvector embeddings (384-dim vectors)
code_nodes         Code graph nodes (functions, classes, methods)
code_edges         Code graph edges (calls, contains)
index_jobs         Indexing job tracking (status, timestamps)
```

Runtime reads from:

```text
repositories
chunks
chunk_embeddings
code_nodes
code_edges
```

The local source repo folder is not the runtime source of truth. The indexed database snapshot is.

---

## Project Structure

```text
agentic-python-repo-rag-copilot/
├── backend/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── chat.py              Chat endpoint
│   │   │   ├── health.py            Health check endpoint
│   │   │   ├── repositories.py      Company repo endpoints
│   │   │   └── temporary_repos.py   GitHub/ZIP temp repo endpoints
│   │   ├── main.py                  FastAPI app assembly, CORS, error handlers
│   │   └── schemas.py               Pydantic request/response schemas
│   ├── app/
│   │   └── streamlit_app.py         Streamlit debug UI
│   ├── data/
│   │   └── eval_cases.json          Evaluation test cases
│   ├── docker/
│   │   └── postgres/init/           PostgreSQL init scripts
│   ├── scripts/
│   │   ├── index_company_repo.py    Index/re-index company repos
│   │   ├── init_db.py               Initialize DB tables + pgvector
│   │   ├── run_eval.py              Run evaluation suite
│   │   ├── cleanup_temporary_repos.py  Clean expired temp repos
│   │   ├── inspect_db_tables.py     Inspect DB tables
│   │   ├── test_storage_connections.py  Test DB connection
│   │   └── ...                      Other test/debug scripts
│   ├── src/
│   │   ├── agent_core/
│   │   │   ├── agent.py             Main agentic RAG agent
│   │   │   ├── query_router.py      LLM query planner + fallback rules
│   │   │   ├── response_models.py   AgentResponse dataclass
│   │   │   └── tools.py             Agent tools (search, graph, count, read_file)
│   │   ├── chunking/                Text chunking strategies
│   │   ├── core/
│   │   │   ├── config.py            Filesystem paths configuration
│   │   │   ├── constants.py         Shared constants (query types, file extensions, etc.)
│   │   │   └── settings.py          Runtime settings (embedding, retrieval, env vars)
│   │   ├── db/                      SQLAlchemy session + DB models
│   │   ├── embeddings/              Embedding generation (sentence-transformers)
│   │   ├── evaluation/
│   │   │   ├── eval_runner.py       Evaluation case loader + evaluate_response
│   │   │   └── metrics.py           Extended metrics (latency, precision, citation, etc.)
│   │   ├── generation/              LLM answer generation (Gemini)
│   │   ├── graph/
│   │   │   └── code_graph.py        AST-based code graph builder
│   │   ├── indexing/
│   │   │   ├── codebase_indexer.py   Full indexing pipeline orchestrator
│   │   │   ├── codebase_loader.py    DB-based codebase loader
│   │   │   └── models.py            IndexedCodebase dataclass
│   │   ├── ingestion/               GitHub clone + ZIP extraction
│   │   ├── observability/           Logging configuration
│   │   ├── parsing/                 Python AST parser + file scanner
│   │   ├── reranking/               Cross-Encoder reranking
│   │   ├── retrieval/
│   │   │   ├── retriever.py         RRF hybrid retriever
│   │   │   ├── bm25_search.py       BM25 keyword search
│   │   │   ├── documentation_search.py  Documentation-specific search
│   │   │   ├── symbol_search.py     Symbol name search
│   │   │   └── rrf.py               Reciprocal Rank Fusion
│   │   ├── services/
│   │   │   ├── chat_service.py      Chat business logic
│   │   │   ├── company_repos.py     Company repo discovery + catalog
│   │   │   ├── repository_service.py  Repo loading, indexing, lifecycle
│   │   │   └── session_store.py     In-memory session management
│   │   └── storage/                 PostgreSQL storage + lifecycle
│   ├── tests/
│   │   ├── test_chunker.py
│   │   └── test_scanner.py
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
│   ├── logo_chatbot.jpg
│   └── vercel.json
│
├── .dockerignore
├── .gitignore
└── README.md
```

---

## Environment Variables

All variables are set in `backend/.env`. See `backend/.env.example` for a template.

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Google Gemini API key |
| `GEMINI_MODEL` | No | Gemini model name (default: `gemini-2.5-flash`) |
| `LLM_BACKEND` | No | LLM backend to use (default: `gemini`) |
| `DATABASE_URL` | Yes | PostgreSQL connection string with `psycopg` driver |
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_KEY` | Yes | Supabase publishable API key |
| `EMBEDDING_DIMENSION` | No | Embedding vector dimension (default: `384`) |
| `CORS_ALLOW_ORIGINS` | No | Comma-separated allowed CORS origins |

---

# Docker Quick Start

This is the recommended local setup. You do **not** need a local Python virtual environment when running the backend with Docker.

## Prerequisites

- Docker Desktop
- Supabase/PostgreSQL database URL
- Gemini API key

## 1. Create backend environment file

From the repository root:

```powershell
cd backend
Copy-Item .env.example .env
```

Edit `backend/.env`:

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

## 2. Build backend image

```powershell
docker compose build api
```

If dependencies were changed, rebuild without cache:

```powershell
docker compose build --no-cache api
```

## 3. Test database connection

```powershell
docker compose run --rm api python -m scripts.test_storage_connections
```

Expected:

```text
connection OK: 1
pgvector extension enabled: True
```

## 4. Initialize database

Run once for a new database:

```powershell
docker compose run --rm api python -m scripts.init_db
```

This creates/verifies the required PostgreSQL tables and pgvector extension.

## 5. Index company repositories

Company repos are outside `backend/`, under:

```text
company_repos/
```

The `docker-compose.yml` mounts `../company_repos` into the API container as `/company_repos:ro`. You can index with Docker:

```powershell
docker compose run --rm api python -m scripts.index_company_repo --list
docker compose run --rm api python -m scripts.index_company_repo taskflow_api
docker compose run --rm api python -m scripts.index_company_repo inventory_api
```

After indexing, company repo data is stored in Supabase/PostgreSQL. Runtime no longer needs the source folder.

## 6. Run backend API

```powershell
docker compose --profile app up api
```

Open:

```text
http://localhost:8000/docs
```

Health check:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

## 7. Run frontend

Open a second terminal from the repository root:

```powershell
cd frontend
python -m http.server 5173
```

Open:

```text
http://localhost:5173
```

The frontend points to:

```javascript
const API_BASE_URL = "http://localhost:8000";
```

For production, change it to your deployed backend URL.

---

## Docker Commands

### Stop containers

```powershell
cd backend
docker compose down
```

### Rebuild backend image

```powershell
cd backend
docker compose build --no-cache api
```

### Run backend logs

```powershell
cd backend
docker compose logs -f api
```

### Run one backend command

```powershell
cd backend
docker compose run --rm api python -m scripts.test_storage_connections
```

### Run Streamlit with Docker

```powershell
cd backend
docker compose --profile app up streamlit
```

Open:

```text
http://localhost:8501
```

### Run API and Streamlit together

```powershell
cd backend
docker compose --profile app up
```

---

## Optional: Local PostgreSQL with Docker

If you do not use Supabase cloud, you can run PostgreSQL/pgvector locally.

In `backend/.env`, use the internal Docker hostname:

```env
DATABASE_URL=postgresql+psycopg://rag_user:rag_password@postgres:5432/rag_db
```

Start Postgres:

```powershell
cd backend
docker compose --profile db up -d postgres
```

Then initialize:

```powershell
docker compose run --rm api python -m scripts.test_storage_connections
docker compose run --rm api python -m scripts.init_db
```

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
docker compose --profile app up api
```

Open the frontend or call the API and ask:

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

## FastAPI Endpoints

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

GitHub repos are temporary:

```text
is_persistent = false
expires_at != null
```

### Temporary ZIP repository

```http
POST /temporary-repos/zip
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

The agent supports:

```text
documentation_query    Ask about project docs, README, setup, architecture
location_query         Where is a function/class implemented?
reference_query        Where is a symbol used/referenced?
explanation_query      What does a function/class do?
search_query           Find code related to a keyword/concept
caller_query           Who calls this function?
callee_query           What does this function call?
impact_query           What is affected if this function changes?
flow_query             Trace the execution flow through functions
count_query            How many files/functions/classes/methods?
multi_intent_query     Combined questions requiring multiple tools
```

Example questions:

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

Run these from `backend/`.

### List repositories

```powershell
docker compose run --rm api python -m scripts.inspect_db_tables
```

You can also query manually inside a container:

```powershell
docker compose run --rm api python -c "from sqlalchemy import text; from src.db.session import get_db_session; s=get_db_session().__enter__(); rows=s.execute(text('SELECT repo_id, name, source_type, is_persistent, chunk_count FROM repositories ORDER BY created_at DESC LIMIT 20')).mappings().all(); [print(dict(r)) for r in rows]"
```

### Count chunks and embeddings

```powershell
docker compose run --rm api python -c "from sqlalchemy import text; from src.db.session import get_db_session; s=get_db_session().__enter__(); repo_id='taskflow_api'; print('chunks', s.execute(text('SELECT COUNT(*) FROM chunks WHERE repo_id=:repo_id'), {'repo_id': repo_id}).scalar()); print('embeddings', s.execute(text('SELECT COUNT(*) FROM chunk_embeddings WHERE repo_id=:repo_id'), {'repo_id': repo_id}).scalar())"
```

---

## Evaluation

### Overview

The evaluation suite measures how accurately the agent answers codebase questions. It tests:

- **Query type accuracy**: Does the router classify the question correctly?
- **Source recall**: Are the expected source files/lines found?
- **Source precision**: How many returned sources are relevant?
- **Citation validity**: Do cited files and line ranges actually exist?
- **Answer quality**: Is the answer non-empty? Does it contain expected keywords?
- **Latency**: How long does each question take?
- **Router fallback rate**: How often does the LLM router fall back to rules?
- **LLM failure rate**: How often does LLM generation fail?

### Running evaluation

From `backend/`:

```powershell
docker compose run --rm api python -m scripts.run_eval
```

### Eval cases format

Eval cases are defined in `backend/data/eval_cases.json`. Each case is a JSON object:

```json
{
  "id": "taskflow_01",
  "repo_id": "taskflow_api",
  "repo_path": "company_repos/taskflow_api",
  "question": "What does create_task do?",
  "expected_query_type": "explanation_query",
  "expected_sources": ["app/api/tasks.py"],
  "expected_files": ["app/api/tasks.py", "app/services/task_service.py"],
  "expected_keywords": ["create_task", "title", "assignee"],
  "forbidden_keywords": [],
  "requires_abstention": false,
  "difficulty": "easy",
  "reference_answer": null,
  "max_latency_seconds": null
}
```

| Field | Required | Description |
|---|---|---|
| `id` | Yes | Unique case identifier |
| `repo_id` | Yes | Repository ID (matches company repo folder name) |
| `repo_path` | Yes | Path to the repository (relative to backend/) |
| `question` | Yes | The question to ask |
| `expected_query_type` | Yes | Expected query type classification |
| `expected_sources` | Yes | Expected source citations (file paths with optional line ranges) |
| `expected_files` | No | Expected file paths in the response |
| `expected_keywords` | No | Keywords that should appear in the answer |
| `forbidden_keywords` | No | Keywords that should NOT appear in the answer |
| `requires_abstention` | No | If true, the agent should refuse to answer |
| `difficulty` | No | Case difficulty label |
| `reference_answer` | No | Reference answer for comparison |
| `max_latency_seconds` | No | Maximum acceptable latency |

### Adding new eval cases

1. Add a new JSON object to `backend/data/eval_cases.json`
2. Set `repo_path` to the company repo path (e.g., `company_repos/taskflow_api`)
3. Run the evaluation:

```powershell
docker compose run --rm api python -m scripts.run_eval
```

---

## Cleanup Temporary Repositories

From `backend/`:

```powershell
docker compose run --rm api python -m scripts.cleanup_temporary_repos --list
docker compose run --rm api python -m scripts.cleanup_temporary_repos --dry-run
docker compose run --rm api python -m scripts.cleanup_temporary_repos
```

---

## Deployment

### Backend: Render

Recommended backend settings:

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
SUPABASE_URL
SUPABASE_KEY
```

Do not deploy `company_repos/` to Render. Company repos should be indexed from your local/admin machine into the same Supabase database used by Render.

### Frontend: Vercel

The frontend includes a `vercel.json` that rewrites `/api/*` requests to the Render backend.

Deploy steps:

1. Import the `frontend/` directory as a Vercel project
2. Framework preset: Other (static site)
3. Root directory: `frontend`
4. The `vercel.json` rewrites handle API proxying automatically

For local development, update `API_BASE_URL` in `frontend/script.js`:

```javascript
const API_BASE_URL = "http://localhost:8000";
```

For production, change it to your deployed backend URL or use the Vercel rewrite.

---

## Git Hygiene

Do not commit:

```text
.env
backend/.env
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

Recommended commit flow:

```powershell
git status
git add README.md backend/requirements.txt
git status
git commit -m "Update Docker quick start and backend dependencies"
git push origin main
```

If you changed other Docker files, also add them:

```powershell
git add backend/Dockerfile backend/docker-compose.yml
```