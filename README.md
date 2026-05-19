# Agentic Python Repo RAG Copilot

Agentic Python Repo RAG Copilot is an AI assistant for understanding Python codebases.

The system can load already-indexed company repositories, temporarily index user-provided public GitHub repositories or ZIP uploads, retrieve relevant code/documentation, build and use a code graph, and answer repository questions using Retrieval-Augmented Generation (RAG), Graph RAG, RRF-based multi-source retrieval, Cross-Encoder reranking, and an LLM-based query planner.

Company repositories are indexed and re-indexed through internal scripts, not through the web UI. The web app is user-facing only.

---

## Table of contents

- [Features](#features)
- [Repository lifecycle](#repository-lifecycle)
- [Architecture](#architecture)
- [Retrieval pipeline](#retrieval-pipeline)
- [Query types](#query-types)
- [Tech stack](#tech-stack)
- [Project structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Install WSL2 on Windows](#install-wsl2-on-windows)
- [Install Docker Desktop](#install-docker-desktop)
- [Local setup](#local-setup)
- [Environment variables](#environment-variables)
- [Start PostgreSQL and Qdrant](#start-postgresql-and-qdrant)
- [Initialize the database](#initialize-the-database)
- [Index or update company repositories](#index-or-update-company-repositories)
- [Run the app](#run-the-app)
- [How to use](#how-to-use)
- [Example questions](#example-questions)
- [Evaluation](#evaluation)
- [Useful scripts](#useful-scripts)
- [Git ignore policy](#git-ignore-policy)
- [Troubleshooting](#troubleshooting)
- [Current status](#current-status)
- [Planned improvements](#planned-improvements)
- [Deployment direction](#deployment-direction)

---

## Features

### 1. User-facing repository modes

The web app supports three user-facing repository modes.

#### Company Repo

Loads an already-indexed persistent company repository from PostgreSQL and Qdrant.

Company repositories are indexed or re-indexed by an admin/developer using scripts, for example:

```powershell
python -m scripts.index_company_repo taskflow_api
```

The web app does not index company repositories directly.

#### GitHub URL

Temporarily clones and indexes a public GitHub repository.

The repository is cloned into:

```text
data/runtime/github/
```

GitHub URL repositories are treated as temporary user-provided data.

#### ZIP Upload

Temporarily extracts and indexes an uploaded `.zip` file containing a Python repository.

The ZIP is extracted into:

```text
data/runtime/uploads/
```

ZIP upload includes basic safety checks:

- Validates the ZIP file
- Prevents unsafe path traversal
- Limits total extracted size
- Limits number of files
- Automatically detects the repository root after extraction

---

### 2. Code-aware indexing

The project indexes:

- Python files
- Markdown documentation such as `README.md`
- Function chunks
- Class chunks
- Method chunks
- Documentation chunks
- File path metadata
- Line range metadata
- Symbol metadata
- Documentation heading metadata

---

### 3. RRF-based multi-source retrieval

Fast mode uses multi-source retrieval with Reciprocal Rank Fusion (RRF).

The retriever builds several ranked result lists:

- Qdrant vector search
- Full-repository BM25 search
- Symbol metadata search
- Documentation search for documentation queries

Then it fuses these ranked lists using RRF.

This avoids manually combining scores from different scales and makes retrieval more robust than a simple weighted score formula.

---

### 4. Cross-Encoder reranking

Accurate mode uses the same RRF retrieval pipeline to retrieve candidate chunks, then applies a Cross-Encoder reranker for final relevance ranking.

This mode is slower than Fast mode, but usually improves relevance for vague or natural-language questions.

---

### 5. Graph RAG

The system builds a code graph from Python AST analysis.

The graph can answer relationship questions such as:

- Who calls this function?
- What functions does this method call?
- What code may be affected if this method changes?
- Where is this symbol defined?

Example:

```text
TaskService.create_task được gọi bởi ai?
```

The system can answer this using the code graph instead of relying only on vector search.

---

### 6. Persistent metadata storage

PostgreSQL stores structured repository metadata:

- Repositories
- Chunks
- Code graph nodes
- Code graph edges

This allows the app to persist repository metadata and reconstruct the code graph from the database.

---

### 7. Vector storage with Qdrant

Qdrant stores code/documentation embeddings.

A single Qdrant collection can store chunks from multiple repositories. Each vector point includes metadata such as:

- `repo_id`
- `relative_path`
- `source_type`
- `symbol_name`
- `qualified_name`
- `start_line`
- `end_line`

---

### 8. LLM Query Planner

The app uses an LLM-based query planner.

Instead of only classifying a user question into one query type, it can decompose a complex question into multiple query plans.

Example question:

```text
ModelEvaluator được tạo ở đâu, mục đích code là gì?
```

Possible plans:

```json
{
  "plans": [
    {
      "query_type": "location_query",
      "symbol": "ModelEvaluator",
      "rewritten_query": "Where is ModelEvaluator defined?"
    },
    {
      "query_type": "explanation_query",
      "symbol": "ModelEvaluator",
      "rewritten_query": "What is the purpose of ModelEvaluator?"
    }
  ]
}
```

The agent executes each plan, merges sources, and produces a grounded answer.

Single-intent questions still work normally. They simply produce one query plan.

---

### 9. Grounded LLM answer generation

After retrieval or graph analysis, the app can use Gemini to generate a natural-language answer grounded in tool results.

If the LLM is unavailable or quota is exhausted, the app can still return fallback tool-based answers.

---

## Repository lifecycle

The project separates persistent company repositories from temporary user repositories.

### Company repositories

Company repositories are persistent.

They are indexed or updated with internal scripts:

```powershell
python -m scripts.index_company_repo taskflow_api
```

Company repositories use:

```text
is_persistent=True
source_type=company
```

Flow:

```text
Admin/developer runs indexing script
    ↓
Repository is scanned, chunked, embedded, and saved
    ↓
PostgreSQL stores metadata/chunks/code graph
    ↓
Qdrant stores vectors
    ↓
Web users can load the company repo and ask questions
```

When company code changes, run the same script again to re-index the selected repository.

This is currently a full re-index of the selected company repository, not incremental file-level indexing.

### Temporary user repositories

User-provided GitHub and ZIP repositories are temporary.

They use:

```text
is_persistent=False
source_type=github or zip_upload
expires_at=<timestamp>
```

Temporary repositories are cleaned up in two ways.

#### Immediate cleanup

When a user switches away from a temporary repository, the app removes the active temporary repository from:

- PostgreSQL
- Qdrant
- Runtime folders such as `data/runtime/github/` or `data/runtime/uploads/`

Example:

```text
ZIP Upload repo A
    ↓
User switches to Company Repo
    ↓
Repo A is deleted immediately
```

#### Expired cleanup

If the user closes the tab or the app crashes, immediate cleanup may not run.

Expired temporary repositories can be removed with:

```powershell
python -m scripts.cleanup_temporary_repos
```

Preview what would be deleted:

```powershell
python -m scripts.cleanup_temporary_repos --dry-run
```

List expired temporary repositories:

```powershell
python -m scripts.cleanup_temporary_repos --list
```

---

## Architecture

High-level Q&A flow:

```text
User question
    ↓
LLM Query Planner
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
Scan Python files and Markdown docs
    ↓
Chunk code/docs
    ↓
Build AST code graph
    ↓
Store metadata and graph in PostgreSQL
    ↓
Store embeddings in Qdrant
    ↓
Ready for web users to load and ask questions
```

Company repo loading flow:

```text
User selects Company Repo
    ↓
App lists persistent repositories from PostgreSQL
    ↓
User clicks Load repository
    ↓
App loads repo metadata from PostgreSQL
    ↓
App loads chunk text/metadata from PostgreSQL
    ↓
App rebuilds in-memory BM25 index
    ↓
App loads code graph from PostgreSQL
    ↓
App connects to Qdrant by repo_id
    ↓
App creates retriever/tools/agent in memory
    ↓
User asks questions
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
Build in-memory BM25 index
    ↓
Ask questions in current session
    ↓
Cleanup on switch or expiration
```

---

## Retrieval pipeline

The project uses RRF-based retrieval.

### Fast mode

Fast mode runs several retrieval sources independently:

```text
User query
    ↓
Vector search in Qdrant
Full-repository BM25 search
Symbol metadata search
Documentation search for documentation queries
    ↓
RRF fusion
    ↓
Top results
```

The final ranking score in Fast mode is the RRF score.

### Accurate mode

Accurate mode uses RRF to retrieve candidates, then reranks those candidates with a Cross-Encoder:

```text
User query
    ↓
Vector search + BM25 search + symbol search + documentation search
    ↓
RRF fusion
    ↓
Candidate chunks
    ↓
Cross-Encoder reranking
    ↓
Top results
```

### Why RRF?

Before RRF, the retriever used a weighted formula over vector score, BM25 score, keyword score, and symbol score.

RRF is better suited here because each retrieval source has different scoring scales. RRF uses rank positions instead of raw score magnitudes.

### Runtime scores

Scores such as BM25 score, RRF score, vector score, and Cross-Encoder score are query-time scores.

They are not stored permanently in the database.

PostgreSQL stores stable chunk text and metadata. Qdrant stores embeddings. Runtime retrieval computes scores for each user query.

---

## Query types

| Query type | Purpose |
|---|---|
| `documentation_query` | Project purpose, README, setup, usage, architecture overview |
| `location_query` | Where a function/class/method is defined or implemented |
| `explanation_query` | What a function/class/method does |
| `reference_query` | Where a symbol is used or referenced |
| `caller_query` | Who calls a function or method |
| `callee_query` | What a function or method calls |
| `impact_query` | What may be affected if a symbol changes |
| `flow_query` | Execution flow, request flow, or call chain |
| `search_query` | General semantic code search |
| `multi_intent_query` | A question decomposed into multiple query plans |

---

## Tech stack

- Python 3.10
- Streamlit
- PostgreSQL
- Qdrant
- SQLAlchemy
- Sentence Transformers
- BM25
- RRF retrieval
- Cross-Encoder reranking
- Gemini API
- Docker Compose
- Git
- WSL2 on Windows

---

## Project structure

```text
agentic-python-repo-rag-copilot/
├── app/
│   └── streamlit_app.py
├── data/
│   └── runtime/
│       ├── github/
│       └── uploads/
├── examples/
│   ├── sample_python_repo/
│   └── company_repos/
├── scripts/
│   ├── cleanup_temporary_repos.py
│   ├── index_company_repo.py
│   ├── init_db.py
│   ├── run_eval.py
│   ├── test_storage_connections.py
│   ├── test_qdrant_vector_store.py
│   ├── test_github_ingestion.py
│   ├── test_zip_ingestion.py
│   ├── test_load_existing_repo.py
│   ├── inspect_metadata_records.py
│   ├── inspect_qdrant_records.py
│   ├── test_load_code_graph_from_db.py
│   └── test_multi_intent_router.py
├── src/
│   ├── agent.py
│   ├── ast_parser.py
│   ├── chunker.py
│   ├── code_graph.py
│   ├── company_repos.py
│   ├── config.py
│   ├── constants.py
│   ├── doc_chunker.py
│   ├── embeddings.py
│   ├── indexer.py
│   ├── llm.py
│   ├── prompts.py
│   ├── qdrant_vector_store.py
│   ├── query_router.py
│   ├── reranker.py
│   ├── retriever.py
│   ├── scanner.py
│   ├── settings.py
│   ├── tools.py
│   ├── db/
│   ├── ingestion/
│   │   ├── github_ingestion.py
│   │   └── zip_ingestion.py
│   └── storage/
│       ├── metadata_store.py
│       └── repository_lifecycle.py
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Prerequisites

Install these before running the project locally:

- Python 3.10
- Git
- WSL2
- Docker Desktop
- Visual Studio Code or another code editor

On Windows, Docker Desktop should run with the WSL2 backend.

---

## Install WSL2 on Windows

Open PowerShell as Administrator and run:

```powershell
wsl --install
```

After installation, restart your computer if Windows asks you to.

Check WSL status:

```powershell
wsl --status
```

Update WSL if needed:

```powershell
wsl --update
```

If you already installed WSL before, make sure WSL2 is used:

```powershell
wsl --set-default-version 2
```

You can also install Ubuntu from the Microsoft Store if Windows does not install it automatically.

---

## Install Docker Desktop

Download and install Docker Desktop for Windows.

During Docker Desktop installation, use these options:

- Keep **Use WSL 2 instead of Hyper-V** checked
- Do not enable **Windows Containers** unless you specifically need it

After installation:

1. Open Docker Desktop
2. Wait until Docker Desktop is fully running
3. Go to **Settings**
4. Make sure **Use the WSL 2 based engine** is enabled
5. Click **Apply & Restart** if you changed anything

Check Docker from PowerShell:

```powershell
docker --version
docker ps
```

If Docker is not running, open Docker Desktop first.

---

## Local setup

### 1. Clone the repository

```powershell
git clone https://github.com/<your-username>/<your-repo>.git
cd agentic-python-repo-rag-copilot
```

### 2. Create a Python 3.10 virtual environment

```powershell
py -3.10 -m venv .venv
.venv\Scripts\activate
```

If `py -3.10` does not work, install Python 3.10 first or use:

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

## Environment variables

Create a `.env` file in the project root.

Example:

```env
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
LLM_BACKEND=gemini

DATABASE_URL=postgresql+psycopg://rag_user:rag_password@localhost:55432/rag_db

QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=
QDRANT_COLLECTION=code_chunks
```

Important:

- Do not commit `.env`
- Commit `.env.example` instead
- Make sure the PostgreSQL port matches your `docker-compose.yml`

Port examples:

If your `docker-compose.yml` maps PostgreSQL like this:

```yaml
ports:
  - "5432:5432"
```

use:

```env
DATABASE_URL=postgresql+psycopg://rag_user:rag_password@localhost:5432/rag_db
```

If your `docker-compose.yml` maps PostgreSQL like this:

```yaml
ports:
  - "55432:5432"
```

use:

```env
DATABASE_URL=postgresql+psycopg://rag_user:rag_password@localhost:55432/rag_db
```

---

## Start PostgreSQL and Qdrant

Make sure Docker Desktop is running.

Then run:

```powershell
docker compose up -d
```

Check running containers:

```powershell
docker ps
```

You should see containers for:

- PostgreSQL
- Qdrant

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
Collections: [...]
```

---

## Index or update company repositories

Company repositories are not indexed from the web UI.

Use the internal script:

```powershell
python -m scripts.index_company_repo taskflow_api
```

List configured company repositories:

```powershell
python -m scripts.index_company_repo --list
```

The same command is used for both first-time indexing and updating/re-indexing.

When re-indexing, the script:

1. Deletes old indexed data for the selected repository from PostgreSQL and Qdrant.
2. Scans the repository source code again.
3. Rebuilds code and documentation chunks.
4. Rebuilds the code graph.
5. Recreates embeddings.
6. Saves updated metadata, graph data, and vectors.

This is a full re-index of the selected company repository. Incremental file-level indexing is not implemented yet.

---

## Run the app

Start Streamlit:

```powershell
python -m streamlit run app/streamlit_app.py
```

Then open the Streamlit URL shown in the terminal.

---

## How to use

### Company Repo

Use this mode for already-indexed company repositories.

Steps:

1. Select `Company Repo`.
2. Choose an indexed company repository.
3. Select retrieval mode:
   - Fast
   - Accurate
4. Click `Load repository`.
5. Ask questions.

This mode does not index the repository again. It loads metadata and code graph data from PostgreSQL and uses Qdrant for vector retrieval.

---

### GitHub URL

Use this mode for public GitHub repositories.

Steps:

1. Select `GitHub URL`.
2. Enter a public GitHub repository URL.
3. Optionally enter a branch name.
4. Click `Index temporary repository`.
5. Ask questions.

The repository is cloned into:

```text
data/runtime/github/
```

This folder is created automatically and is ignored by Git.

GitHub URL repositories are temporary and can be cleaned up when switching repos or when expired.

---

### ZIP Upload

Use this mode for uploaded repository ZIP files.

Steps:

1. Select `ZIP Upload`.
2. Upload a `.zip` file containing a Python repository.
3. Click `Index temporary repository`.
4. Ask questions.

The ZIP is extracted into:

```text
data/runtime/uploads/
```

This folder is created automatically and is ignored by Git.

ZIP upload repositories are temporary and can be cleaned up when switching repos or when expired.

---

## Retrieval modes

### Fast mode

Fast mode uses:

- Qdrant vector search
- Full-repository BM25 search
- Symbol metadata search
- Documentation search for documentation queries
- RRF fusion

This mode is faster and works well for most questions.

### Accurate mode

Accurate mode uses:

- RRF candidate retrieval
- Cross-Encoder reranking

This mode is slower but usually improves result relevance.

---

## Example questions

### Project documentation

```text
Dự án này dùng để làm gì?
```

```text
What does this project do?
```

### Repository files

```text
Code này có những file chính nào?
```

```text
What are the main files in this project?
```

### Symbol location

```text
ModelEvaluator được tạo ở đâu?
```

```text
Where is ModelEvaluator defined?
```

### Symbol explanation

```text
ModelEvaluator có tác dụng gì?
```

```text
Explain ModelEvaluator.
```

### Multi-intent question

```text
ModelEvaluator được tạo ở đâu, mục đích code là gì?
```

The agent can decompose this into:

- `location_query`
- `explanation_query`

### Caller query

```text
TaskService.create_task được gọi bởi ai?
```

### Callee query

```text
TaskService.create_task gọi những hàm nào?
```

### Impact query

```text
Nếu xóa TaskService.create_task thì chỗ nào bị ảnh hưởng?
```

### Reference query

```text
ModelEvaluator được dùng ở đâu?
```

---

## Evaluation

Run the evaluation script:

```powershell
python -m scripts.run_eval
```

Example expected output:

```text
Overall Evaluation Summary
Number of cases:                 16
Query type accuracy:             100.00%
Average source recall:           100.00%
Expected sources all found rate: 100.00%
```

The current evaluation covers:

- Query type routing
- Source recall
- Expected source matching
- Graph RAG cases
- Documentation retrieval cases

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

### Test Qdrant vector store

```powershell
python -m scripts.test_qdrant_vector_store
```

### Inspect PostgreSQL metadata

```powershell
python -m scripts.inspect_metadata_records
```

### Inspect Qdrant records

```powershell
python -m scripts.inspect_qdrant_records
```

### Test loading code graph from PostgreSQL

```powershell
python -m scripts.test_load_code_graph_from_db
```

### Test GitHub ingestion

```powershell
python -m scripts.test_github_ingestion
```

### Test ZIP ingestion

```powershell
python -m scripts.test_zip_ingestion
```

### Test multi-intent router

```powershell
python -m scripts.test_multi_intent_router
```

---

## Git ignore policy

Do not commit local runtime data, secrets, virtual environments, or database storage.

Recommended `.gitignore` entries:

```gitignore
.venv/
.env
__pycache__/
*.pyc

data/runtime/
data/index/
data/chroma/

postgres_data/
qdrant_data/
```

Runtime folders such as these are created automatically:

```text
data/runtime/github/
data/runtime/uploads/
```

---

## Troubleshooting

### Docker API error

Error example:

```text
failed to connect to the docker API
```

Fix:

1. Open Docker Desktop
2. Wait until Docker is running
3. Run again:

```powershell
docker ps
docker compose up -d
```

### PostgreSQL or Qdrant connection refused

Fix:

```powershell
docker compose up -d
python -m scripts.test_storage_connections
```

Also check that `.env` uses the correct PostgreSQL port.

### Port conflict with local PostgreSQL

If you already have PostgreSQL installed on your machine, port `5432` may be busy.

Map Docker PostgreSQL to another host port, for example:

```yaml
ports:
  - "55432:5432"
```

Then update `.env`:

```env
DATABASE_URL=postgresql+psycopg://rag_user:rag_password@localhost:55432/rag_db
```

### Docker Desktop WSL2 issue

If Docker says it cannot connect to `dockerDesktopLinuxEngine`, try:

```powershell
wsl --shutdown
```

Then reopen Docker Desktop.

### Qdrant client/server version warning

You may see a warning if the Qdrant Python client version and server version are not close enough.

Usually this is a warning, not always a fatal error.

If it causes issues, align the Qdrant Docker image version and Python package version.

### Gemini API quota or key issue

If Gemini quota is exhausted or the API key is invalid, final LLM answer generation may fail.

The app can still return tool-based fallback answers if retrieval and graph tools work.

### No indexed company repositories found

Run the company repository indexing script first:

```powershell
python -m scripts.index_company_repo taskflow_api
```

Then restart or refresh the app and select `Company Repo`.

### ZIP upload cannot be indexed

Possible causes:

- The uploaded file is not a valid `.zip`
- The ZIP has no `.py` or `.md` files
- The ZIP is too large
- The ZIP contains unsafe paths

Use a smaller Python repository ZIP and try again.

---

## Notes about runtime folders

Runtime folders are not committed to Git.

They are created automatically when needed:

- GitHub repositories are cloned into `data/runtime/github/`
- ZIP uploads are extracted into `data/runtime/uploads/`

If these folders do not exist after cloning the project, that is normal.

---

## Current status

Implemented:

- User-facing Streamlit app
- Python code indexing
- Markdown documentation indexing
- PostgreSQL metadata storage
- Qdrant vector storage
- RRF-based multi-source retrieval
- Fast retrieval mode using RRF
- Accurate retrieval mode using RRF + Cross-Encoder reranking
- Graph RAG
- GitHub temporary repository ingestion
- ZIP upload temporary repository ingestion
- Company repository loading from PostgreSQL + Qdrant
- Company repository index/re-index script
- Temporary repository cleanup on switch
- Expired temporary repository cleanup script
- Code graph persistence and reload from PostgreSQL
- LLM query planner
- Multi-intent query execution
- Evaluation script

---

## Planned improvements

- FastAPI backend
- Separate frontend
- Cloud PostgreSQL with Neon
- Qdrant Cloud
- Deployment on Render/Vercel
- Background scheduled cleanup for expired temporary repositories
- Incremental indexing for company repositories
- Authentication and saved private user repositories
- Better support for larger repositories
- Optional MMR diversification for selected query types

---

## Deployment direction

The current version is designed to run locally with Docker.

A production deployment can use:

- Vercel for frontend
- Render for backend
- Neon for PostgreSQL
- Qdrant Cloud for vector database

In production, temporary repository cloning and ZIP extraction should happen on the backend server. Persistent metadata and vectors should be stored in cloud databases.

Company repository indexing can run as an internal script or scheduled job that writes to the same PostgreSQL and Qdrant instances used by the web app.

