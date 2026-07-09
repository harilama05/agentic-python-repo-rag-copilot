# Agentic Python Repo RAG Copilot

Agentic Python Repo RAG Copilot is an AI-powered assistant for understanding Python codebases. It indexes Python repositories, stores chunks/embeddings/code graph data in Supabase/PostgreSQL + pgvector, and answers codebase questions with source citations.

---

## Demo

| Chat Interface | Sources & Citations |
|:-:|:-:|
| ![Chat UI](docs/images/chat-ui.png) | ![Sources](docs/images/sources-panel.png) |

| Supabase Database |
|:-:|
| ![Supabase](docs/images/supabase-db.jpg) |

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
| LLM | DeepSeek (`deepseek-v4-flash`) |
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

Evaluated on **100 test cases** across **5 company repositories** (`taskflow_api`, `inventory_api`, `auth_service`, `payment_gateway`, `notification_service`) covering 7 query types and 3 difficulty levels. Retrieval mode: **Fast (RRF only)**, LLM: **DeepSeek-v4-flash**, LLM router: **enabled**.

#### Overall Metrics

| Metric | Score |
|---|---|
| **Query Type Accuracy** | 85.00% |
| **Avg Source Recall** | 87.00% |
| **Expected Sources All Found Rate** | 84.00% |
| **Avg Source Precision** | 59.52% |
| **Avg File Hit Rate** | 87.00% |
| **Answer Non-Empty Rate** | 100.00% |
| **Avg Keyword Recall** | 76.67% |
| **Avg Citation Validity** | 91.52% |
| **Avg Latency** | 2.69s |
| **Router Fallback Rate** | 3.00% |
| **LLM Failure Rate** | 0.00% |
| **Abstention Accuracy** | 100.00% |
| **Forbidden Keyword Hit Rate** | 0.00% |

![Overall Evaluation Metrics](docs/images/eval-overall-metrics.jpg)

#### Results by Query Type

| Query Type | Cases | Accuracy | Avg Source Recall | Avg Keyword Recall | Avg Latency |
|---|---|---|---|---|---|
| `explanation_query` | 25 | 96.0% | 92.0% | 90.7% | 2.71s |
| `location_query` | 20 | 90.0% | 97.5% | 87.5% | 2.08s |
| `reference_query` | 15 | 80.0% | 86.7% | 60.0% | 2.54s |
| `caller_query` | 10 | 70.0% | 80.0% | 73.3% | 3.29s |
| `count_query` | 10 | 100.0% | 100.0% | 100.0% | 1.43s |
| `impact_query` | 10 | 70.0% | 55.0% | 36.7% | 4.12s |
| `search_query` | 10 | 70.0% | 80.0% | 65.0% | 3.29s |

![Evaluation Results by Query Type](docs/images/eval-query-type-results.jpg)

#### Per-Repository Summary

| Repository | Cases | Query Type Acc | Avg Source Recall | Avg Precision | Avg Keyword Recall | Avg Latency |
|---|---|---|---|---|---|---|
| `taskflow_api` | 20 | 85.0% | 72.5% | 46.3% | 67.5% | 2.54s |
| `inventory_api` | 20 | 80.0% | 90.0% | 55.9% | 71.7% | 2.77s |
| `auth_service` | 20 | 95.0% | 82.5% | 65.1% | 75.8% | 2.67s |
| `payment_gateway` | 20 | 95.0% | 100.0% | 65.7% | 87.5% | 2.71s |
| `notification_service` | 20 | 70.0% | 90.0% | 64.5% | 80.8% | 2.74s |

![Per-Repository Evaluation Summary](docs/images/eval-repo-summary.jpg)

#### Results by Difficulty

| Difficulty | Cases | Accuracy | Avg Source Recall | Avg Keyword Recall | Avg Latency |
|---|---|---|---|---|---|
| `easy` | 45 | 95.6% | 94.4% | 90.0% | 2.20s |
| `medium` | 40 | 80.0% | 86.2% | 70.8% | 2.91s |
| `hard` | 15 | 66.7% | 66.7% | 52.2% | 3.56s |

![Evaluation Results by Difficulty](docs/images/eval-difficulty-results.jpg)

#### Top 10 Performers

| Case ID | Repository | Query Type | Difficulty | Source Recall | Keyword Recall | Latency |
|---|---|---|---|---|---|---|
| `payment_gateway_061` | `payment_gateway` | explanation | easy | 100.0% | 100.0% | 2.19s |
| `payment_gateway_062` | `payment_gateway` | explanation | easy | 100.0% | 100.0% | 2.51s |
| `payment_gateway_063` | `payment_gateway` | explanation | easy | 100.0% | 100.0% | 3.25s |
| `payment_gateway_066` | `payment_gateway` | location | easy | 100.0% | 100.0% | 1.90s |
| `payment_gateway_070` | `payment_gateway` | reference | easy | 100.0% | 100.0% | 2.01s |
| `auth_service_045` | `auth_service` | explanation | medium | 100.0% | 100.0% | 2.67s |
| `auth_service_048` | `auth_service` | location | easy | 100.0% | 100.0% | 1.87s |
| `auth_service_052` | `auth_service` | reference | medium | 100.0% | 100.0% | 2.59s |
| `inventory_api_022` | `inventory_api` | explanation | easy | 100.0% | 100.0% | 2.61s |
| `notification_service_088` | `notification_service` | location | easy | 100.0% | 100.0% | 2.08s |

#### Bottom 10 Performers

| Case ID | Repository | Query Type | Difficulty | Correct | Source Recall | Keyword Recall | Latency |
|---|---|---|---|---|---|---|---|
| `taskflow_api_015` | `taskflow_api` | impact | medium | ❌ | 0.0% | 0.0% | 3.36s |
| `notification_service_091` | `notification_service` | reference | medium | ❌ | 0.0% | 0.0% | 2.39s |
| `taskflow_api_011` | `taskflow_api` | reference | medium | ✅ | 0.0% | 0.0% | 1.94s |
| `taskflow_api_014` | `taskflow_api` | caller | hard | ✅ | 0.0% | 0.0% | 3.15s |
| `taskflow_api_016` | `taskflow_api` | impact | hard | ✅ | 0.0% | 0.0% | 4.52s |
| `taskflow_api_018` | `taskflow_api` | search | hard | ✅ | 0.0% | 0.0% | 2.70s |
| `inventory_api_035` | `inventory_api` | impact | medium | ✅ | 0.0% | 0.0% | 4.99s |
| `inventory_api_038` | `inventory_api` | search | hard | ✅ | 0.0% | 0.0% | 2.95s |
| `auth_service_043` | `auth_service` | explanation | easy | ✅ | 0.0% | 0.0% | 2.96s |
| `auth_service_055` | `auth_service` | impact | medium | ✅ | 0.0% | 0.0% | 3.79s |

> **Note:** Source Recall depends on the number of `expected_sources` in each eval case. Cases with 1 expected source yield 0% or 100%; cases with 2 expected sources can yield 0%, 50%, or 100%. `count_query` cases have no expected sources, so recall defaults to 100%.

#### Analysis & Key Observations

**Query Router Performance:**
The DeepSeek-v4-flash router achieves **85% overall accuracy** (85/100), demonstrating strong classification ability across 7 query types. High-frequency types like `explanation_query` (96%), `location_query` (90%), and `count_query` (100%) are classified almost flawlessly. The router struggles most with semantically ambiguous types — `impact_query` (70%), `search_query` (70%), and `caller_query` (70%) — where the boundary between "impact analysis" vs "explanation" or "caller" vs "reference" is often unclear from natural language alone. The **Router Fallback Rate of 3%** confirms that DeepSeek-v4-flash is highly reliable as a classification backbone, with rule-based fallback triggered in only 3 of 100 cases.

**Retrieval Quality — Hybrid Strategy Effectiveness:**
- **Source Recall (87%)** demonstrates that the hybrid retrieval pipeline (Vector + BM25 + Symbol + Doc → RRF) successfully locates the expected source files in the majority of cases. `payment_gateway` achieves a perfect 100% recall, likely due to its well-structured codebase with clear function naming. In contrast, `taskflow_api` (72.5%) shows the lowest recall — closer inspection reveals that several `caller_query` and `impact_query` cases fail because these queries require graph traversal to discover indirect callers, which the current RRF-only mode does not fully leverage
- **Source Precision (59.5%)** reflects a known trade-off of the RRF fusion strategy: by merging results from 4 retrieval sources (Vector, BM25, Symbol, Doc), the system prioritizes comprehensive recall at the expense of precision. The `count_query` cases contribute 0% precision (no actual sources returned for count questions), which further lowers the aggregate
- **File Hit Rate (87%)** confirms that even when exact source matching fails, the retrieval pipeline still surfaces the correct files — suggesting that the hybrid approach effectively covers different retrieval modalities

**Answer Generation Quality:**
- **Keyword Recall (76.7%)** indicates that DeepSeek-v4-flash covers most expected concepts in its generated answers, but there is a clear performance gradient by difficulty: `easy` cases achieve 90% keyword recall vs `hard` cases at only 52.2%. The weakest area is `impact_query` (36.7% avg keyword recall) where the model must reason about downstream effects — a task that requires deep understanding of code dependencies
- **Citation Validity (91.5%)** is high across all repositories, validating the grounded generation approach where the LLM is constrained to cite only from retrieved chunks. The remaining 8.5% invalid citations are typically caused by line range drift (the model cites slightly incorrect line numbers within the correct file)
- **Answer Non-Empty Rate (100%)** and **LLM Failure Rate (0%)** confirm that DeepSeek-v4-flash produces consistent, non-empty responses across all 100 cases with zero generation failures

**Safety & Guardrails:**
- **Abstention Accuracy (100%)**: The system correctly abstains from answering when the context is insufficient, preventing harmful hallucinations
- **Forbidden Keyword Hit Rate (0%)**: DeepSeek-v4-flash successfully avoids using any restricted or deprecated terms, adhering strictly to the coding standards defined in the system prompt

**Difficulty Analysis:**
Performance degrades gracefully with increasing difficulty:
- **Easy** (45 cases): 95.6% accuracy, 94.4% recall, 2.20s avg latency — the system handles straightforward questions about function definitions and locations with near-perfect accuracy
- **Medium** (40 cases): 80.0% accuracy, 86.2% recall, 2.91s avg latency — slight degradation on questions requiring cross-file reasoning (e.g., `caller_query`, `reference_query`)
- **Hard** (15 cases): 66.7% accuracy, 66.7% recall, 3.56s avg latency — significant drop on complex queries requiring graph traversal (`impact_query`) or semantic matching with non-obvious terms (`search_query` for conceptual rather than literal matches)

This gradient is expected and healthy — it shows the system is not overfitting to simple cases while still providing useful answers on harder questions.

**Latency Profile:**
- `count_query` (1.43s avg) is fastest because it uses direct database aggregation without retrieval
- `location_query` (2.08s) and `reference_query` (2.54s) are moderately fast, leveraging symbol matching for direct lookups
- `impact_query` (4.12s) is slowest due to graph traversal and broader retrieval scope
- Overall **2.69s average** is well within acceptable interactive response times for a code copilot

**Per-Repository Comparison:**
`payment_gateway` leads with 95% accuracy and 100% recall, benefiting from clean code structure and explicit function naming. `auth_service` also performs well (95% accuracy) thanks to well-documented authentication patterns. `notification_service` has the lowest accuracy (70%) — this repository contains more complex multi-service interactions (email + push + device registration) that challenge both the router's classification and the retriever's ability to identify relevant sources across multiple service files.

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