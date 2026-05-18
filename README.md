# Agentic Python Repo RAG Copilot

Agentic Python Repo RAG Copilot is an AI assistant for understanding Python codebases.

The system indexes Python source code and documentation, builds a code graph, stores structured metadata in PostgreSQL, stores vector embeddings in Qdrant, and answers repository questions using Retrieval-Augmented Generation, Graph RAG, hybrid retrieval, Cross-Encoder reranking, and an LLM-based query planner.

It can answer questions such as:

- What does this project do?
- Where is `ModelEvaluator` defined?
- What does `ModelEvaluator` do?
- Who calls `TaskService.create_task`?
- What will be affected if `TaskService.create_task` is removed?
- Where is a function used?
- Explain this class and show where it is implemented.
- `ModelEvaluator` được tạo ở đâu, mục đích code là gì?

---

## Features

### Repository ingestion

The app can index repositories from multiple sources:

1. **Company repositories**
   - Preconfigured repositories managed by the project owner/admin.
   - Stored as persistent repositories.

2. **Custom local repositories**
   - A user can provide a local repository path.
   - Useful for local testing.

3. **Public GitHub repositories**
   - A user can enter a public GitHub URL.
   - The app clones the repository into `data/runtime/github/`.
   - Runtime GitHub folders are temporary and are not committed to Git.

---

## Core capabilities

### 1. Code-aware retrieval

The project indexes:

- Python files
- Markdown documentation such as `README.md`
- Function, class, and method chunks
- Metadata such as file path, line range, symbol name, symbol type, and heading

### 2. Hybrid retrieval

Fast mode uses:

- Qdrant vector search
- BM25 lexical scoring
- Keyword overlap scoring
- Symbol-aware scoring
- Documentation boosting for documentation queries

### 3. Cross-Encoder reranking

Accurate mode uses:

- Hybrid retrieval to collect candidates
- Cross-Encoder reranking to improve result relevance

This mode is slower than Fast mode but can improve answer quality for vague or natural-language questions.

### 4. Graph RAG

The system builds a code graph from Python AST analysis.

The graph supports:

- Finding callers of a symbol
- Finding callees of a symbol
- Analyzing impact if a function/class/method changes
- Resolving graph-related questions through retrieved symbols when the user does not provide an exact symbol

Example:

```text
TaskService.create_task được gọi bởi ai?
```

The system can answer this using the code graph instead of relying only on semantic search.

### 5. LLM Query Planner

The app uses an LLM-based query planner.

Instead of only classifying a question into one query type, the planner can decompose a user question into one or more query plans.

Example:

```text
ModelEvaluator được tạo ở đâu, mục đích code là gì?
```

The planner can produce:

```json
{
  "plans": [
    {
      "query_type": "location_query",
      "symbol": "ModelEvaluator"
    },
    {
      "query_type": "explanation_query",
      "symbol": "ModelEvaluator"
    }
  ]
}
```

Then the agent executes each plan, merges the sources, and generates a grounded answer.

Single-intent questions still work normally. They simply produce one query plan.

### 6. Grounded LLM answer generation

After retrieval or graph analysis, the system can use Gemini to generate a natural-language answer grounded in tool results.

If the LLM is unavailable or quota is exhausted, the app falls back to tool-based answers.

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

## Storage architecture

The project uses two storage layers.

### PostgreSQL

PostgreSQL stores structured metadata:

- Repositories
- Chunks
- Code graph nodes
- Code graph edges

This allows the system to persist repository metadata and reconstruct code graph data after restart.

### Qdrant

Qdrant stores vector embeddings for code and documentation chunks.

A single Qdrant collection can store chunks from multiple repositories. Each vector point is filtered by `repo_id`.

### Runtime folders

Runtime folders are created automatically when needed.

Example:

```text
data/runtime/github/
```

This folder contains cloned GitHub repositories during local indexing.

It should not be committed to Git.

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

---

## Project structure

```text
agentic-python-repo-rag-copilot/
├── app/
│   └── streamlit_app.py
├── data/
│   └── runtime/
│       └── github/
├── examples/
│   ├── sample_python_repo/
│   └── company_repos/
├── scripts/
│   ├── init_db.py
│   ├── run_eval.py
│   ├── test_storage_connections.py
│   ├── test_qdrant_vector_store.py
│   ├── test_github_ingestion.py
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
│   └── storage/
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Requirements

Install these first:

- Python 3.10
- Git
- Docker Desktop
- Visual Studio Code or another editor

Docker Desktop is required because PostgreSQL and Qdrant run in Docker containers during local development.

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

- Do not commit `.env`.
- Commit `.env.example` instead.
- Make sure the PostgreSQL port in `DATABASE_URL` matches your `docker-compose.yml`.
- If your Docker Compose maps `5432:5432`, use `localhost:5432`.
- If your Docker Compose maps `55432:5432`, use `localhost:55432`.

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

### 3. Install dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Start PostgreSQL and Qdrant

Make sure Docker Desktop is running.

```powershell
docker compose up -d
```

Check containers:

```powershell
docker ps
```

You should see containers for PostgreSQL and Qdrant.

### 5. Initialize database tables

```powershell
python -m scripts.init_db
```

### 6. Test storage connections

```powershell
python -m scripts.test_storage_connections
```

Expected output:

```text
PostgreSQL connection OK: 1
Qdrant connection OK
Collections: [...]
```

### 7. Run the Streamlit app

```powershell
python -m streamlit run app/streamlit_app.py
```

---

## How to use

### Company repository mode

Use this mode for predefined repositories inside the project.

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

### Custom local repository mode

Use this mode for a local path on your machine.

1. Select `Custom Repo`
2. Enter local repository path
3. Click `Index repository`
4. Ask questions

### GitHub URL mode

Use this mode for public GitHub repositories.

1. Select `GitHub URL`
2. Enter a public GitHub URL

Example:

```text
https://github.com/owner/repo
```

3. Optionally enter a branch
4. Click `Index repository`
5. Ask questions

The repository is cloned into:

```text
data/runtime/github/
```

This folder is created automatically and is ignored by Git.

---

## Retrieval modes

### Fast mode

Fast mode uses hybrid retrieval:

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

This mode is slower but often improves result quality.

---

## Example questions

### Project documentation

```text
Dự án này dùng để làm gì?
```

```text
What does this project do?
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

Runtime folders such as `data/runtime/github/` are created automatically when indexing GitHub repositories.

---

## Notes about LLM usage

The app can still return fallback tool-based answers when LLM generation is unavailable.

The LLM is used for:

- Query planning
- Query rewriting
- Final grounded answer generation

Local components are used for:

- Embeddings
- Vector search
- BM25
- Cross-Encoder reranking
- Code graph analysis
- Fallback answers

If Gemini quota is exhausted, the app may still answer using retrieval and graph tools, but the final answer may be less natural.

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
- Code graph persistence and reload from PostgreSQL
- LLM query planner
- Multi-intent query execution
- Streamlit UI
- Evaluation script

Planned improvements:

- ZIP upload ingestion
- FastAPI backend
- Frontend deployment
- Cloud PostgreSQL such as Neon
- Cloud Qdrant
- User/admin authentication
- Repository management dashboard
- Background indexing jobs
- Better support for larger repositories

---

## Deployment direction

The current version is designed to run locally with Docker.

A production deployment can use:

- Vercel for frontend
- Render for backend
- Neon for PostgreSQL
- Qdrant Cloud for vector database

In production, temporary repository cloning should happen on the backend server, while persistent metadata and vectors should be stored in cloud databases.

---

## License

This project is intended for educational and portfolio use.
