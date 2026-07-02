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

## Key Techniques

### Hybrid Retrieval & Reciprocal Rank Fusion (RRF)

The system combines **4 retrieval strategies** to maximize recall across different query types:

| Strategy | How it works | Best for |
|---|---|---|
| **Vector Search** (pgvector) | Embeds the query using `all-MiniLM-L6-v2` (384-dim), then performs cosine similarity search against pre-indexed chunk embeddings stored in PostgreSQL | Semantic/conceptual queries — "What does this function do?" |
| **BM25** (rank-bm25) | Classic term-frequency based ranking on tokenized chunk text | Exact keyword matches — "Find code with `restock`" |
| **Symbol Matching** | Exact match against function/class names extracted during AST parsing | Direct symbol lookups — "Where is `create_task`?" |
| **Documentation Search** | Searches indexed Markdown/TXT documentation chunks | Setup/config questions — "How to deploy?" |

Results from all 4 strategies are merged using **Reciprocal Rank Fusion (RRF)**:

```
RRF_score(doc) = Σ  1 / (k + rank_i(doc))
```

where `k` is a constant (default 60) and `rank_i(doc)` is the rank of the document in the i-th retrieval list. RRF produces a single unified ranking without requiring score normalization across different retrieval methods.

### Cross-Encoder Reranking

In **Accurate mode**, after RRF fusion, the top candidates are reranked using a Cross-Encoder model (`ms-marco-MiniLM-L-6-v2`). Unlike bi-encoder embeddings (which encode query and document independently), the Cross-Encoder processes the `(query, document)` pair jointly, producing more accurate relevance scores at the cost of higher latency.

### Code Graph RAG

The system builds a **call graph** at index time using Python's `ast` module:

1. **AST Parsing** — each `.py` file is parsed into an Abstract Syntax Tree; all function/method definitions and class definitions are extracted as **nodes**
2. **Call Edge Extraction** — for each function body, all `ast.Call` nodes are resolved to determine which functions are called, creating **directed edges** (caller → callee)
3. **Graph Storage** — nodes and edges are stored in PostgreSQL tables (`code_nodes`, `code_edges`), enabling runtime graph traversal without re-parsing source files

At query time, the agent uses graph tools for structural queries:

| Tool | Description | Graph Operation |
|---|---|---|
| `get_callers` | Who calls function X? | Reverse edge traversal (incoming edges) |
| `get_callees` | What does function X call? | Forward edge traversal (outgoing edges) |
| `impact_analysis` | What is affected if X changes? | Transitive forward closure (BFS/DFS) |
| `flow_tracing` | Trace execution from X | Ordered forward path traversal |

### LLM Query Router

Each user question is classified into one of **11 query types** before retrieval. The system uses a **two-tier routing** strategy:

1. **LLM Router (primary)** — sends the question to Gemini with a structured prompt, asking it to classify the query type and extract key entities (function names, class names, keywords)
2. **Rule-based Router (fallback)** — if the LLM router fails or is disabled, a regex/keyword-based classifier handles routing (e.g., questions starting with "Where is" → `location_query`, "Who calls" → `caller_query`)

The router output determines which **agent tools** are invoked: hybrid retrieval for semantic queries, graph tools for structural queries, or DB tools for count/reference queries.

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

### Evaluation Methodology

#### Eval Case Design

Each eval case in `eval_cases.json` defines:

| Field | Purpose |
|---|---|
| `question` | The natural-language query to test |
| `expected_query_type` | The correct query type classification (e.g., `explanation_query`, `caller_query`) |
| `expected_sources` | File paths (with optional line ranges) that the answer **must** cite |
| `expected_files` | Files that **should** appear in retrieved sources |
| `expected_keywords` | Keywords that **must** appear in the generated answer |
| `difficulty` | `easy` / `medium` / `hard` — for stratified analysis |

The eval suite indexes each repository from scratch, runs all questions through the full pipeline (router → retrieval → LLM generation), and compares outputs against expected values.

#### Metric Definitions

| Metric | Formula | What it measures |
|---|---|---|
| **Query Type Accuracy** | `correct_classifications / total_cases` | How well the LLM router classifies question intent |
| **Source Recall** | `matched_expected_sources / total_expected_sources` | Whether the system finds **all** relevant source files |
| **Source Precision** | `matched_actual_sources / total_actual_sources` | Whether returned sources are **relevant** (not noisy) |
| **File Hit Rate** | `expected_files_found / total_expected_files` | Whether the correct files appear in retrieval results |
| **Keyword Recall** | `found_keywords / total_expected_keywords` | Whether the answer mentions key concepts/identifiers |
| **Citation Validity** | `valid_citations / total_citations` | Whether cited file paths and line ranges actually exist |
| **Answer Non-Empty Rate** | `non_empty_answers / total_cases` | Whether the LLM generates a substantive response |
| **Router Fallback Rate** | `fallback_used / total_cases` | How often the rule-based fallback replaces the LLM router |
| **LLM Failure Rate** | `llm_errors / total_cases` | How often LLM generation fails entirely |
| **Latency** | `end_time - start_time` (seconds) | End-to-end response time per query |

### Benchmark Results

Evaluated on **10 test cases** across **2 company repositories** (`taskflow_api`, `inventory_api`) covering 7 query types. Retrieval mode: **Fast (RRF only)**, LLM router: **enabled**.

#### Overall Metrics

| Metric | Score |
|---|---|
| **Query Type Accuracy** | 80.00% |
| **Avg Source Recall** | 85.00% |
| **Expected Sources All Found Rate** | 70.00% |
| **Avg Source Precision** | 64.45% |
| **Avg File Hit Rate** | 90.00% |
| **Answer Non-Empty Rate** | 100.00% |
| **Avg Keyword Recall** | 79.17% |
| **Avg Citation Validity** | 93.56% |
| **Avg Latency** | 2.87s |
| **Router Fallback Rate** | 10.00% |
| **LLM Failure Rate** | 0.00% |

![Overall Evaluation Metrics](docs/images/eval-overall-metrics.png)

#### Per-Case Results

| Case ID | Query Type | Correct | Source Recall | Source Precision | Keyword Recall | Citation Valid | Latency |
|---|---|---|---|---|---|---|---|
| `taskflow_01` | explanation | ✅ | 100.0% | 85.7% | 100.0% | 100.0% | 2.41s |
| `taskflow_02` | location | ✅ | 100.0% | 100.0% | 100.0% | 100.0% | 1.98s |
| `taskflow_03` | reference | ✅ | 100.0% | 75.0% | 100.0% | 100.0% | 2.15s |
| `taskflow_04` | caller | ✅ | 100.0% | 80.0% | 100.0% | 85.7% | 3.22s |
| `taskflow_05` | count | ✅ | 100.0% | 0.0% | 100.0% | 100.0% | 1.53s |
| `inventory_01` | explanation | ✅ | 100.0% | 85.7% | 75.0% | 100.0% | 2.67s |
| `inventory_02` | location | ✅ | 50.0% | 66.7% | 100.0% | 85.7% | 2.34s |
| `inventory_03` | explanation | ✅ | 100.0% | 80.0% | 66.7% | 90.0% | 3.45s |
| `inventory_04` | impact | ❌ | 100.0% | 71.4% | 50.0% | 85.7% | 4.12s |
| `inventory_05` | search | ❌ | 0.0% | 0.0% | 0.0% | 88.5% | 4.87s |

> **Note:** Source Recall depends on the number of `expected_sources` in each eval case. Cases with 1 expected source yield 0% or 100%; cases with 2 expected sources can yield 0%, 50%, or 100%. `taskflow_05` has no expected sources (count query), so recall defaults to 100%.

![Per-Case Evaluation Results](docs/images/eval-per-case-heatmap.png)

#### Results by Query Type

| Query Type | Cases | Accuracy | Avg Source Recall | Avg Keyword Recall | Avg Latency |
|---|---|---|---|---|---|
| `explanation_query` | 3 | 100.0% | 100.0% | 80.6% | 2.84s |
| `location_query` | 2 | 100.0% | 75.0% | 100.0% | 2.16s |
| `reference_query` | 1 | 100.0% | 100.0% | 100.0% | 2.15s |
| `caller_query` | 1 | 100.0% | 100.0% | 100.0% | 3.22s |
| `count_query` | 1 | 100.0% | 100.0% | 100.0% | 1.53s |
| `impact_query` | 1 | 0.0% | 100.0% | 50.0% | 4.12s |
| `search_query` | 1 | 0.0% | 0.0% | 0.0% | 4.87s |

![Evaluation Results by Query Type](docs/images/eval-query-type-results.png)

#### Per-Repository Summary

| Repository | Cases | Query Type Acc | Avg Source Recall | Avg Precision | Avg Latency |
|---|---|---|---|---|---|
| `taskflow_api` | 5 | 100.0% | 100.0% | 68.1% | 2.26s |
| `inventory_api` | 5 | 60.0% | 70.0% | 60.8% | 3.49s |

#### Analysis & Key Observations

**Query Router Performance:**
The LLM router (Gemini) achieves **80% overall accuracy** (8/10), correctly classifying all common query types: `explanation`, `location`, `reference`, `caller`, and `count`. The two misclassifications occur on `impact_query` and `search_query` — these are semantically ambiguous types where the boundary between "impact analysis" vs "explanation" and "search" vs "reference" is less clear-cut. The **Router Fallback Rate of 10%** indicates the LLM router is generally reliable, with rule-based fallback rarely needed.

**Retrieval Quality — Hybrid Strategy Effectiveness:**
- **Source Recall (85%)** shows the hybrid retrieval (Vector + BM25 + Symbol + Doc → RRF) successfully locates most expected source files. `taskflow_api` achieves perfect 100% recall across all 5 cases thanks to the **symbol matching** strategy. The main weakness is `inventory_05` (`search_query` for "restock") where retrieval failed entirely — BM25 and vector search missed the `needs_restock` method because the query term "restock" differs from the actual symbol name
- **Source Precision (64.5%)** indicates noticeable noise in retrieved results — the system returns extra sources beyond what's strictly expected. This is a known trade-off: RRF fusion favors recall over precision, and the hybrid approach sometimes surfaces loosely related chunks. Note: `count_query` and `search_query` cases contribute 0% precision (no matched sources), which lowers the overall average
- **File Hit Rate (90%)** confirms the retrieval pipeline surfaces the correct files even when exact source matching is imperfect

**Answer Generation Quality:**
- **Keyword Recall (79.2%)** shows the LLM (Gemini) covers most expected concepts in its answers, though there is room for improvement. The complete miss on `inventory_05` (0% keyword recall) directly follows from the retrieval failure — with no relevant sources retrieved, the LLM cannot produce an answer containing the expected keywords (`needs_restock`, `reorder_threshold`). Cases like `inventory_04` (50%) show that even when sources are found, the LLM may not always mention all expected technical terms
- **Citation Validity (93.6%)** is high, meaning nearly all source citations point to real files with valid line ranges — this validates the grounded generation approach where the LLM is constrained to cite from retrieved chunks
- **Answer Non-Empty Rate (100%)** and **LLM Failure Rate (0%)** confirm robust end-to-end generation

**Latency Profile:**
- Simple queries (`count_query`: 1.53s, `location_query`: 1.98s) are fast because they use direct DB lookups or symbol matching with minimal retrieval overhead
- Complex queries (`impact_query`: 4.12s, `search_query`: 4.87s) are slower due to graph traversal and broader retrieval scope
- Average latency of **2.87s** is acceptable for an interactive copilot, and could be further reduced by switching to the **Fast retrieval mode** (RRF-only, skipping Cross-Encoder reranking)

**Per-Repository Comparison:**
`taskflow_api` (100% query type accuracy, 100% recall) significantly outperforms `inventory_api` (60% accuracy, 70% recall). This is expected because `taskflow_api` has a simpler code structure with clearer function naming conventions, making both routing and retrieval more straightforward. The `inventory_api` contains more complex domain logic (restock thresholds, stock updates) and the more difficult query types (`impact_query`, `search_query`), which challenge both the router's classification ability and the retriever's semantic understanding.

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