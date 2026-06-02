# Agentic Python Repo RAG Copilot

Agentic Python Repo RAG Copilot is an AI-powered assistant for understanding Python codebases. It indexes Python repositories, stores chunks/embeddings/code graph data in Supabase/PostgreSQL + pgvector, and answers codebase questions with source citations.

---

## Demo

| Chat Interface | Sources & Citations |
|:-:|:-:|
| ![Chat UI](docs/images/chat-ui.png) | ![Sources](docs/images/sources-panel.png) |

| Supabase Database |
|:-:|
| ![Supabase](docs/images/supabase-db.png) |

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

- Hybrid retrieval: vector search (pgvector) + BM25 + symbol matching + documentation search, merged via Reciprocal Rank Fusion (RRF)
- Two retrieval modes: Fast (RRF only) and Accurate (RRF + Cross-Encoder reranking)
- Custom AST-based Code Graph RAG with callers, callees, impact analysis, and flow tracing
- LLM query router/planner (Gemini) with fallback rule-based routing, supporting 11 query types
- Multi-format indexing: Python (.py), Markdown (.md), JSON (.json), TXT (.txt)
- Three repository types: persistent company repos, temporary GitHub repos, temporary ZIP uploads
- DB-only runtime — after indexing, the backend reads only from PostgreSQL
- Grounded answer generation with source file citations and line ranges
- Vietnamese and English language support
- Evaluation suite for query accuracy, source recall/precision, citation validity

---

## Architecture

```mermaid
flowchart TB
    User([User])
    FE["Frontend / Streamlit"]
    API["FastAPI Backend"]
    Router["LLM Query Router"]

    subgraph Agent Tools
        Hybrid["Hybrid Retriever\n(Vector + BM25 + Symbol + Doc → RRF)"]
        Graph["Code Graph Tools\n(callers, callees, impact, flow)"]
        DB["DB Tools\n(read_file, count, references)"]
    end

    PG[("Supabase / PostgreSQL\n+ pgvector")]
    LLM["Gemini LLM"]
    Resp["Answer + Sources + Warnings"]

    User --> FE --> API --> Router
    Router --> Hybrid & Graph & DB
    Hybrid & Graph & DB --> PG
    PG --> LLM --> Resp --> FE
```

Core design: index-time reads source repositories; runtime/chat is DB-only.

---

## Pipeline

### Indexing Pipeline

```mermaid
flowchart LR
    A["Source Repo\n(.py .md .json .txt)"] --> B["File Scanner"]
    B --> C["AST Parser\n(functions, classes)"]
    C --> D["Chunker"]
    D --> E["Embeddings\n(all-MiniLM-L6-v2)"]
    C --> F["Code Graph Builder\n(call graph)"]
    E & F --> G[("PostgreSQL\nchunks · embeddings\ncode_nodes · code_edges")]
```

### Query/Chat Pipeline

```mermaid
flowchart LR
    Q["User Question"] --> R["Query Router\n(LLM / rule-based)"]
    R --> T["Agent Tool Selection"]
    T --> H["Hybrid Retrieval\n(Vector+BM25+Symbol+Doc)"]
    H --> RRF["RRF Fusion"]
    RRF --> RE{"Accurate\nmode?"}
    RE -- Yes --> CR["Cross-Encoder\nReranking"]
    RE -- No --> LLM["Gemini LLM"]
    CR --> LLM
    LLM --> A2["Answer + Sources"]
```

---

## Project Structure

```text
agentic-python-repo-rag-copilot/
├── backend/
│   ├── api/                    # FastAPI app + routes (chat, repos, health)
│   ├── app/                    # Streamlit debug UI
│   ├── src/
│   │   ├── agent_core/         # Agent orchestrator, query router, tools
│   │   ├── chunking/           # Code, markdown, text chunkers
│   │   ├── core/               # Config, constants, settings
│   │   ├── db/                 # SQLAlchemy session + models
│   │   ├── embeddings/         # sentence-transformers wrapper
│   │   ├── evaluation/         # Eval runner + metrics
│   │   ├── generation/         # Gemini LLM answer generation
│   │   ├── graph/              # AST-based code graph builder
│   │   ├── indexing/           # Full indexing pipeline
│   │   ├── ingestion/          # GitHub clone + ZIP extraction
│   │   ├── parsing/            # Python AST parser + file scanner
│   │   ├── reranking/          # Cross-Encoder reranker
│   │   ├── retrieval/          # Hybrid retriever (vector, BM25, RRF)
│   │   ├── services/           # Business logic (chat, repos, sessions)
│   │   └── storage/            # PostgreSQL storage + lifecycle
│   ├── scripts/                # CLI scripts (index, eval, cleanup, etc.)
│   ├── tests/                  # Unit tests
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── .env.example
├── company_repos/              # Persistent company repos (admin-managed)
├── frontend/                   # Static HTML/CSS/JS chat UI
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

## Docker Quick Start

### Prerequisites

- Docker Desktop
- Supabase/PostgreSQL database URL
- Gemini API key

### 1. Create backend environment file

```bash
cd backend
cp .env.example .env
# Edit backend/.env with your credentials
```

### 2. Build and initialize

```bash
# Build backend image
docker compose build api

# Test database connection
docker compose run --rm api python -m scripts.test_storage_connections

# Initialize database (run once)
docker compose run --rm api python -m scripts.init_db
```

### 3. Index company repositories

```bash
# List available repos
docker compose run --rm api python -m scripts.index_company_repo --list

# Index repos
docker compose run --rm api python -m scripts.index_company_repo taskflow_api
docker compose run --rm api python -m scripts.index_company_repo inventory_api
```

To add a new company repo: copy source code into `company_repos/<repo_id>`, optionally create `repo_config.json`, then run the index command above.

### 4. Run the app

```bash
# Start backend API → http://localhost:8000
docker compose --profile app up api

# In another terminal — start frontend → http://localhost:5173
cd frontend
python -m http.server 5173
```

Streamlit debug UI:

```bash
docker compose --profile app up streamlit
# → http://localhost:8501
```

### Optional: Local PostgreSQL

If you do not use Supabase cloud, set `DATABASE_URL=postgresql+psycopg://rag_user:rag_password@postgres:5432/rag_db` in `.env`, then:

```bash
docker compose --profile db up -d postgres
docker compose run --rm api python -m scripts.init_db
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/company-repos` | List indexed company repositories |
| `POST` | `/company-repos/{repo_id}/load` | Load a company repo session |
| `POST` | `/chat` | Ask a question (requires `session_id`) |
| `POST` | `/temporary-repos/github` | Index a GitHub repo (temporary) |
| `POST` | `/temporary-repos/zip` | Upload & index a ZIP repo (temporary) |
| `DELETE` | `/temporary-repos/{repo_id}` | Delete a temporary repo |

Full interactive docs at `http://localhost:8000/docs`.

---

## Query Types

The agent supports the following query types, classified by the LLM router or fallback rules:

| Query Type | Description | Example |
|---|---|---|
| `documentation_query` | Project docs, README, setup | "How to set up the project?" |
| `location_query` | Where is a function/class? | "Where is create_task implemented?" |
| `reference_query` | Where is a symbol used? | "Where is create_task used?" |
| `explanation_query` | What does something do? | "What does create_task do?" |
| `search_query` | Find code by keyword/concept | "Find code related to authentication" |
| `caller_query` | Who calls a function? | "Who calls create_task?" |
| `callee_query` | What does a function call? | "What does create_task call?" |
| `impact_query` | Impact of changing a function | "What is affected if create_task changes?" |
| `flow_query` | Trace execution flow | "Trace the flow of create_task" |
| `count_query` | Count files/functions/classes | "How many Python files?" |
| `multi_intent_query` | Combined questions | "Where is create_task and who calls it?" |

---

## Evaluation

Run the evaluation suite:

```bash
docker compose run --rm api python -m scripts.run_eval
```

Eval cases are defined in `backend/data/eval_cases.json`. Metrics include query type accuracy, source recall/precision, citation validity, answer quality, and latency.

---

## Deployment

### Backend: Render

| Setting | Value |
|---|---|
| Root Directory | `backend` |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python -m uvicorn api.main:app --host 0.0.0.0 --port $PORT` |

Set all environment variables on Render. Do not deploy `company_repos/` — index from your local machine into the same Supabase database.

### Frontend: Vercel

1. Import `frontend/` as a Vercel project (Framework: Other / static site, Root: `frontend`)
2. The `vercel.json` rewrites `/api/*` to the Render backend automatically

For local development, `API_BASE_URL` in `frontend/script.js` defaults to `http://localhost:8000`.

---

## Useful Docker Commands

```bash
docker compose down                              # Stop all containers
docker compose build --no-cache api              # Rebuild without cache
docker compose logs -f api                       # View backend logs
docker compose --profile app up                  # Run API + Streamlit together
docker compose run --rm api python -m scripts.cleanup_temporary_repos  # Cleanup expired repos
docker compose run --rm api python -m scripts.inspect_db_tables        # Inspect DB
```