# Agentic Python Repo RAG Copilot

Agentic Python Repo RAG Copilot is an AI assistant for understanding Python codebases.

The system can index Python repositories, retrieve relevant code/documentation, build a code graph, and answer questions using Retrieval-Augmented Generation (RAG), Graph RAG, hybrid retrieval, Cross-Encoder reranking, and an LLM-based query planner.

It currently supports these repository sources:

- Company repositories
- Custom local repositories
- Public GitHub repositories
- ZIP upload repositories

---

## Table of contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech stack](#tech-stack)
- [Project structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Install WSL2 on Windows](#install-wsl2-on-windows)
- [Install Docker Desktop](#install-docker-desktop)
- [Local setup](#local-setup)
- [Environment variables](#environment-variables)
- [Start PostgreSQL and Qdrant](#start-postgresql-and-qdrant)
- [Initialize the database](#initialize-the-database)
- [Run the app](#run-the-app)
- [How to use](#how-to-use)
- [Example questions](#example-questions)
- [Evaluation](#evaluation)
- [Useful scripts](#useful-scripts)
- [Git ignore policy](#git-ignore-policy)
- [Troubleshooting](#troubleshooting)
- [Current status](#current-status)
- [Planned improvements](#planned-improvements)

---

## Features

### 1. Multiple repository input modes

The app supports four repository sources.

#### Company Repo

Preconfigured repositories managed by the project owner/admin.

These are treated as persistent repositories.

#### Custom Repo

A local repository path on the user's machine.

Useful for local testing and development.

#### GitHub URL

A public GitHub repository URL.

The app clones the repository into:

```text
data/runtime/github/
```

This runtime folder is created automatically and should not be committed to Git.

#### ZIP Upload

A user can upload a `.zip` file containing a Python repository.

The app extracts the uploaded ZIP into:

```text
data/runtime/uploads/
```

Then it indexes the extracted repository like any other repo.

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

### 3. Hybrid retrieval

Fast mode uses a hybrid retrieval strategy:

- Qdrant vector search
- BM25 lexical scoring
- Keyword overlap scoring
- Symbol-aware scoring
- Documentation boosting for documentation queries

This is useful for fast, reasonably accurate codebase search.

---

### 4. Cross-Encoder reranking

Accurate mode adds Cross-Encoder reranking after initial retrieval.

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

The system uses the code graph instead of relying only on vector search.

---

### 6. Persistent metadata storage

The app stores structured repository metadata in PostgreSQL:

- Repositories
- Chunks
- Code graph nodes
- Code graph edges

This allows the app to persist repo metadata and reconstruct the code graph from the database after restart.

---

### 7. Vector storage with Qdrant

The app stores code/documentation embeddings in Qdrant.

A single Qdrant collection can store chunks from multiple repositories.

Each point includes metadata such as:

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

## Architecture

High-level flow:

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

Indexing flow:

```text
Repository source
    ↓
Scan Python files and Markdown docs
    ↓
Chunk code/docs
    ↓
Build AST code graph
    ↓
Store metadata in PostgreSQL
    ↓
Store embeddings in Qdrant
    ↓
Ready for Q&A
```

Repository input flow:

```text
Company Repo       → local predefined repo
Custom Repo        → local path
GitHub URL         → clone into data/runtime/github/
ZIP Upload         → extract into data/runtime/uploads/
```

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
│   ├── init_db.py
│   ├── run_eval.py
│   ├── test_storage_connections.py
│   ├── test_qdrant_vector_store.py
│   ├── test_github_ingestion.py
│   ├── test_zip_ingestion.py
│   ├── inspect_metadata_records.py
│   ├── inspect_qdrant_records.py
│   ├── test_load_code_graph_from_db.py
│   └── test_multi_intent_router.py
├── src/
│   ├── agent.py
│   ├── code_graph.py
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
│   ├── settings.py
│   ├── tools.py
│   ├── db/
│   ├── ingestion/
│   │   ├── github_ingestion.py
│   │   └── zip_ingestion.py
│   └── storage/
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
- Keep **Add shortcut to desktop** checked if you want
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

If Docker is not running, open Docker Desktop and wait until it is ready.

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

## Run the app

Start Streamlit:

```powershell
python -m streamlit run app/streamlit_app.py
```

Then open the Streamlit URL shown in the terminal.

---

## How to use

### Company Repo mode

Use this mode for predefined repositories inside the project.

Steps:

1. Select `Company Repo`
2. Choose a repository
3. Select retrieval mode:
   - Fast
   - Accurate
4. Click `Index repository`
5. Ask questions

Example:

```text
TaskService.create_task được gọi bởi ai?
```

---

### Custom Repo mode

Use this mode for a local path on your machine.

Steps:

1. Select `Custom Repo`
2. Enter a local repository path
3. Click `Index repository`
4. Ask questions

---

### GitHub URL mode

Use this mode for public GitHub repositories.

Steps:

1. Select `GitHub URL`
2. Enter a public GitHub repository URL

Example:

```text
https://github.com/owner/repo
```

3. Optionally enter a branch name
4. Click `Index repository`
5. Ask questions

The repository is cloned into:

```text
data/runtime/github/
```

This folder is created automatically and is ignored by Git.

---

### ZIP Upload mode

Use this mode for uploaded repository ZIP files.

Steps:

1. Select `ZIP Upload`
2. Upload a `.zip` file containing a Python repository
3. Click `Index repository`
4. Ask questions

The ZIP is extracted into:

```text
data/runtime/uploads/
```

This folder is created automatically and is ignored by Git.

---

## Retrieval modes

### Fast mode

Fast mode uses:

- Qdrant vector search
- BM25
- Keyword overlap
- Symbol-aware scoring
- Documentation boosting

This mode is faster and works well for most questions.

### Accurate mode

Accurate mode uses:

- Hybrid retrieval
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

---

### PostgreSQL or Qdrant connection refused

Error example:

```text
No connection could be made because the target machine actively refused it
```

Fix:

```powershell
docker compose up -d
python -m scripts.test_storage_connections
```

Also check that `.env` uses the correct PostgreSQL port.

---

### Port conflict with local PostgreSQL

If you already have PostgreSQL installed on your machine, port `5432` may be busy.

In that case, map Docker PostgreSQL to another host port, for example:

```yaml
ports:
  - "55432:5432"
```

Then update `.env`:

```env
DATABASE_URL=postgresql+psycopg://rag_user:rag_password@localhost:55432/rag_db
```

---

### Docker Desktop WSL2 issue

If Docker says it cannot connect to `dockerDesktopLinuxEngine`, try:

```powershell
wsl --shutdown
```

Then reopen Docker Desktop.

---

### Qdrant client/server version warning

You may see a warning if the Qdrant Python client version and server version are not close enough.

Usually this is a warning, not always a fatal error.

If it causes issues, align the Qdrant Docker image version and Python package version.

---

### Gemini API quota or key issue

If Gemini quota is exhausted or the API key is invalid, final LLM answer generation may fail.

The app can still return tool-based fallback answers if retrieval and graph tools work.

---

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

- Python code indexing
- Markdown documentation indexing
- PostgreSQL metadata storage
- Qdrant vector storage
- Fast hybrid retrieval
- Accurate Cross-Encoder reranking
- Graph RAG
- GitHub public repository ingestion
- ZIP upload repository ingestion
- Code graph persistence and reload from PostgreSQL
- LLM query planner
- Multi-intent query execution
- Streamlit UI
- Evaluation script

---

## Planned improvements

- Improve Streamlit UI/UX
- Add repository/session management
- Add admin repository management
- Add FastAPI backend
- Add separate frontend
- Deploy backend to Render
- Deploy frontend to Vercel
- Move PostgreSQL to Neon
- Move Qdrant to Qdrant Cloud
- Add background indexing jobs
- Add authentication
- Better support for larger repositories

---

## Deployment direction

The current version is designed to run locally with Docker.

A production deployment can use:

- Vercel for frontend
- Render for backend
- Neon for PostgreSQL
- Qdrant Cloud for vector database

In production, temporary repository cloning and ZIP extraction should happen on the backend server, while persistent metadata and vectors should be stored in cloud databases.

---

## License

This project is intended for educational and portfolio use.
