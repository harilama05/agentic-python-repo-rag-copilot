# Agentic RAG Copilot for Python Repositories

A read-only AI copilot for Python repositories.

This project indexes Python repositories, retrieves relevant code and documentation, and answers repository questions using an agentic RAG pipeline. It supports code search, documentation QA, source-grounded answers, Cross-Encoder reranking, LLM-based query routing, and AST-based Graph RAG for code relationship and impact-analysis questions.

---

## Features

### Repository QA

The assistant can answer questions such as:

```text
Where is create_user implemented?
Where is create_user used?
What does UserService do?
Dự án này dùng để làm gì?
Tech stack của dự án là gì?
TaskService.create_task được gọi bởi ai?
Nếu xóa TaskService.create_task thì ảnh hưởng gì?
Nếu bỏ method tạo task thì chỗ nào bị ảnh hưởng?
```

The system supports both English and Vietnamese questions.

---

## Repository Modes

The current app supports two repository modes:

### 1. Custom Repo Mode

Use this mode to index a local Python repository by entering its local path.

Example:

```text
examples/sample_python_repo
```

### 2. Company Repo Mode

Use this mode to select a predefined company-style repository included in the project.

Example:

```text
TaskFlow API
```

This mode simulates how new interns or new team members can ask questions about existing company repositories.

---

## Current Input Scope

The current version indexes:

```text
.py files
README.md / README.markdown
docs/*.md / docs/*.markdown
```

It ignores files such as:

```text
.git/
.venv/
venv/
__pycache__/
node_modules/
dist/
build/
IDE/cache folders
binary or unsupported files
```

The app is read-only and does not execute user repository code.

---

## RAG Pipeline

The pipeline currently includes:

```text
Repository scan
→ Python AST parsing
→ Code/document chunking
→ Embedding
→ Chroma vector store
→ Hybrid retrieval
→ Optional Cross-Encoder reranking
→ LLM Query Router
→ Agent tool selection
→ Graph RAG when needed
→ Source excerpt construction
→ LLM grounded answer generation
→ Sources shown in UI
```

---

## Retrieval Modes

The app supports two retrieval modes.

### Fast Mode

Fast mode uses:

```text
Vector search
+ BM25
+ keyword score
+ symbol-aware score
```

This mode is faster and is suitable for most normal repository QA.

### Accurate Mode

Accurate mode uses:

```text
Hybrid retrieval
→ candidate chunks
→ Cross-Encoder reranking
→ final top-k chunks
```

This mode can improve retrieval quality, especially for ambiguous questions, but it is slower on CPU-only machines.

The Cross-Encoder is used only in retrieval/search steps. The rest of the pipeline, including LLM routing, Graph RAG, source excerpts, and answer generation, is shared by both Fast and Accurate modes.

---

## LLM Query Router

The system uses an LLM Query Router to understand each user question before selecting tools.

The router returns a query plan containing:

```text
query_type
symbol
rewritten_query
confidence
reason
```

Supported query types include:

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
```

Examples:

```text
"Where is create_task implemented?"
→ location_query
→ symbol: create_task

"TaskService.create_task được gọi bởi ai?"
→ caller_query
→ symbol: TaskService.create_task

"Nếu bỏ method tạo task thì chỗ nào bị ảnh hưởng?"
→ impact_query
→ symbol: None
→ rewritten_query: task creation method impact analysis
```

If the LLM router is unavailable or rate-limited, the system falls back to a rule-based router.

---

## Graph RAG / Code Graph

The project includes a lightweight AST-based Code Graph layer.

The graph contains:

```text
Nodes:
- functions
- classes
- methods

Edges:
- class contains method
- function/method calls function/method
```

Graph tools include:

```text
find_callers(symbol)
find_callees(symbol)
impact_analysis(symbol)
```

This enables questions such as:

```text
Who calls this method?
What functions does this function call?
What may be affected if this method is removed or changed?
```

Example:

```text
Question:
TaskService.create_task được gọi bởi ai?

Graph result:
TaskService.create_task is called by create_task in app/api/tasks.py.
```

For natural-language graph questions without an explicit symbol, the system first resolves the likely target symbol through repository search.

Example:

```text
Question:
Nếu bỏ method tạo task thì chỗ nào bị ảnh hưởng?

Router:
impact_query, symbol=None

Symbol resolution:
search_code("task creation method")
→ TaskService.create_task

Graph analysis:
impact_analysis("TaskService.create_task")
```

In Accurate mode, this symbol resolution step can use Cross-Encoder reranking.

---

## Source-Grounded Answers

The app displays sources separately from the generated answer.

Sources include:

```text
file path
line range
symbol name
source excerpt
```

Example:

```text
app/api/tasks.py:9-11 — create_task
app/services/task_service.py:11-17 — TaskService.create_task
```

The LLM answer is generated from retrieved context, graph results, and source excerpts.

If LLM answer generation is unavailable or rate-limited, the app shows a concise warning and falls back to a tool/retrieval-based answer.

---

## Tech Stack

```text
Python
Streamlit
ChromaDB
sentence-transformers
Cross-Encoder reranking
rank-bm25
Google Gemini API
Python AST
Pydantic / dataclasses
```

Main retrieval components:

```text
Bi-Encoder embeddings for semantic retrieval
BM25 for lexical retrieval
Cross-Encoder for optional reranking
AST-based code graph for Graph RAG
LLM Query Router for tool selection
```

---

## Project Structure

```text
.
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
│   ├── run_eval.py
│   ├── index_repo.py
│   ├── test_llm_router.py
│   └── test_code_graph.py
│
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
│   ├── evaluator.py
│   ├── indexer.py
│   ├── llm.py
│   ├── prompts.py
│   ├── query_router.py
│   ├── reranker.py
│   ├── retriever.py
│   ├── scanner.py
│   ├── settings.py
│   ├── tools.py
│   └── vector_store.py
│
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

---

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/your-username/agentic-python-repo-rag-copilot.git
cd agentic-python-repo-rag-copilot
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it on Windows:

```bash
.venv\Scripts\activate
```

Activate it on macOS/Linux:

```bash
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

If PyTorch is not installed correctly on a CPU-only machine, install the CPU build:

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

### 4. Create `.env`

Copy:

```bash
cp .env.example .env
```

On Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Example `.env`:

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-2.5-flash
LLM_BACKEND=gemini
```

You may use another supported Gemini model depending on your quota and availability.

---

## Run the App

```bash
python -m streamlit run app/streamlit_app.py
```

Then open the Streamlit URL shown in the terminal.

---

## How to Use

### 1. Select Repository Mode

Choose one:

```text
Custom Repo
Company Repo
```

### 2. Select Retrieval Mode

Choose one:

```text
Fast - Hybrid retrieval
Accurate - Cross-Encoder reranking
```

### 3. Index the Repository

Click:

```text
Index repository
```

The app will show:

```text
Python files indexed
Documentation files indexed
Ignored files
Total chunks
Collection name
Retrieval mode
```

### 4. Ask Questions

Example questions:

```text
Where is create_user implemented?
Where is create_user used?
What does UserService do?
Dự án này dùng để làm gì?
Where is create_task implemented?
TaskService.create_task được gọi bởi ai?
Nếu xóa TaskService.create_task thì ảnh hưởng gì?
Nếu bỏ method tạo task thì chỗ nào bị ảnh hưởng?
```

---

## Evaluation

The project includes a lightweight evaluation script for retrieval and agent workflow correctness.

Run:

```bash
python -m scripts.run_eval
```

The evaluation currently covers:

```text
code-level queries
documentation queries
Vietnamese and English questions
company repo questions
caller queries
impact-analysis queries
natural-language graph queries
```

Metrics:

```text
Query type accuracy
Average source recall
Expected sources all found rate
```

Current result:

```text
Overall Evaluation Summary
Number of cases:                 16
Query type accuracy:             100.00%
Average source recall:           100.00%
Expected sources all found rate: 100.00%

Evaluation Summary - sample_python_repo
Number of cases:                 6
Query type accuracy:             100.00%
Average source recall:           100.00%
Expected sources all found rate: 100.00%

Evaluation Summary - taskflow_api
Number of cases:                 10
Query type accuracy:             100.00%
Average source recall:           100.00%
Expected sources all found rate: 100.00%
```

The reported result is measured only on a curated evaluation set across the included sample repositories. It should not be interpreted as universal accuracy on arbitrary real-world repositories.

The evaluation focuses on:

```text
query routing correctness
source retrieval correctness
graph query source coverage
file path and line number correctness
```

It does not yet fully evaluate:

```text
LLM answer quality
hallucination rate
large production repositories
latency
multi-user behavior
```

---

## Example Pipeline Behavior

### Documentation Question

```text
Question:
Dự án này dùng để làm gì?

Router:
documentation_query

Tool:
search_code(...)

Answer:
The assistant answers using README/project documentation sources.
```

### Caller Query

```text
Question:
TaskService.create_task được gọi bởi ai?

Router:
caller_query

Tool:
find_callers("TaskService.create_task")

Answer:
TaskService.create_task is called by create_task in app/api/tasks.py.
```

### Impact Query

```text
Question:
TaskService.create_task nếu xóa thì sẽ ảnh hưởng gì?

Router:
impact_query

Tool:
impact_analysis("TaskService.create_task")

Answer:
The API handler create_task may be affected because it creates TaskService and calls service.create_task(...).
```

### Natural-Language Graph Query

```text
Question:
Nếu bỏ method tạo task thì chỗ nào bị ảnh hưởng?

Router:
impact_query
symbol=None

Symbol resolution:
search_code("task creation method")

Resolved symbol:
TaskService.create_task

Tool:
impact_analysis("TaskService.create_task")
```

---

## Limitations

Current limitations:

```text
- Only Python source files are parsed as code.
- Markdown documentation support is limited to README and docs/*.md.
- The code graph is static and AST-based.
- It does not execute repository code.
- Dynamic Python calls may not be fully resolved.
- Cross-file/type inference is lightweight.
- LLM routing and answer generation depend on Gemini API quota.
- No persistent database layer yet.
- No GitHub URL ingestion yet.
- No ZIP upload ingestion yet.
- No FastAPI backend or separate frontend yet.
```

The current app is a local Streamlit-based prototype with strong RAG and code understanding features, not a fully deployed production system.

---

## Roadmap

Planned next improvements:

```text
1. Remove unused legacy code after LLM Query Router migration
2. Add GitHub public repository URL ingestion
3. Add ZIP upload ingestion
4. Add persistent metadata database
5. Add persistent vector database
6. Add FastAPI backend
7. Add separate frontend
8. Add admin/user roles
9. Store company repositories in database
10. Add deployment support
```

Future product architecture:

```text
Frontend
→ FastAPI backend
→ repository ingestion service
→ metadata database
→ vector database
→ LLM Query Router
→ hybrid retrieval / Cross-Encoder reranking
→ Graph RAG
→ source-grounded LLM answer
```

---

## Safety and Repository Handling

The system is read-only.

It does not:

```text
execute repository code
modify repository files
run tests from user repositories
install packages from indexed repositories
```

It only reads supported text files, chunks them, embeds them, and uses them for retrieval and question answering.

---

## Notes on LLM Quota

The app uses Gemini for:

```text
LLM Query Router
LLM grounded answer generation
```

This means one user question may require multiple LLM calls.

If the model is rate-limited or quota is exhausted, the app falls back to tool/retrieval-based answers and shows a concise warning in the UI. Detailed provider errors are kept in Raw Results for debugging.
