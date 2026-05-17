# Agentic RAG Copilot for Python Repositories

A two-mode Agentic RAG copilot for Python repositories.

This project helps users understand Python repositories faster by indexing both source code and project documentation. It supports custom user-provided Python repos and predefined company Python repos. The system retrieves relevant code/docs, uses agent tools, and generates grounded answers with file path and line number citations.

---

## Overview

Developers, interns, or new team members often need to answer questions like:

```text
What does this project do?
How do I set up this repository?
Where is this function implemented?
Where is this function used?
What does this class do?
Which files are related to a feature?
```

This project turns a Python repository into a searchable knowledge base.

It indexes:

```text
1. Python source code
   - .py files
   - functions
   - classes
   - methods
   - imports
   - line numbers

2. Repository documentation
   - README.md
   - docs/*.md
   - docs/*.markdown
```

Then it uses hybrid retrieval and agent tools to answer questions with grounded sources.

---

## Repository Modes

The system supports two repository modes.

### 1. Custom Repo Mode

Users can enter a local Python repository path manually.

Example:

```text
D:\Work\some_python_repo
```

The system indexes that repository and allows users to ask questions about its code and documentation.

### 2. Company Repo Mode

Users can select a predefined company Python repository from the UI.

Example:

```text
TaskFlow API
```

Company repos use the same indexing and retrieval pipeline as custom repos. The only difference is that their paths are registered in the project.

---

## Current Status

This is the current MVP/portfolio version.

Implemented:

- Custom Repo Mode
- Company Repo Mode
- Python repository scanning
- Markdown documentation scanning
- AST-based Python code parsing
- Function/class/method extraction
- README/docs chunking
- Code chunking with metadata
- Local vector indexing with ChromaDB
- Local CPU embeddings with `sentence-transformers`
- Hybrid retrieval:
  - semantic vector search
  - BM25 lexical scoring
  - keyword matching
  - symbol-aware reranking
- Agent tools:
  - `search_code(query)`
  - `find_symbol(symbol_name)`
  - `find_references(symbol_name)`
  - `read_file(file_path, start_line, end_line)`
- Rule-based agent routing
- Optional Gemini LLM grounded answer generation
- Streamlit UI
- File path and line number citations
- Source excerpt viewer in UI
- Lightweight evaluation script

Not yet implemented:

- Multi-language codebase support
- Jupyter notebook indexing
- Dockerfile/YAML/JSON/config indexing
- Full language-server-level reference tracing
- Incremental indexing
- Large real-world repository benchmarking
- Automatic code editing
- Pull request generation

---

## Features

### 1. Python Repository Scanner

The system scans a local repository and collects valid Python files while ignoring unnecessary folders such as:

```text
.git/
.venv/
venv/
__pycache__/
.pytest_cache/
.mypy_cache/
dist/
build/
```

Indexed code files:

```text
*.py
```

Ignored code/file types include:

```text
.ipynb
.js
.ts
.java
.go
.cpp
.html
.css
.json
.yaml
.yml
Dockerfile
requirements.txt
pyproject.toml
.env
binary files
image files
```

These files are ignored by the current version unless explicitly supported later.

---

### 2. Markdown Documentation Scanner

The system also indexes project documentation from:

```text
README.md
README.markdown
docs/*.md
docs/*.markdown
```

This allows users to ask project-level and onboarding questions such as:

```text
What does this project do?
How do I set up this project?
What is the tech stack?
What should a new intern read first?
Dự án này dùng để làm gì?
Cách setup project này như thế nào?
```

If a repository does not contain README/docs, the app still works in code-only mode.

---

### 3. AST-Aware Code Parsing

The system uses Python's built-in `ast` module to extract:

- top-level functions
- async functions
- classes
- class methods
- imports
- docstrings
- line numbers

Example extracted metadata:

```json
{
  "source_type": "code",
  "file_path": "app/services/user_service.py",
  "symbol_name": "create_user",
  "qualified_name": "create_user",
  "symbol_type": "function",
  "start_line": 1,
  "end_line": 5
}
```

---

### 4. Code Chunking

Each Python function, class, or method becomes a searchable chunk.

A code chunk contains:

- source code
- file path
- symbol name
- symbol type
- start line
- end line
- parent class, if available
- docstring, if available
- imports, if available

Example code chunk:

```text
File: app/services/user_service.py
Symbol: create_user
Type: function
Lines: 1-5

Code:
def create_user(email: str) -> dict:
    return {
        "email": email,
        "is_active": True,
    }
```

---

### 5. Documentation Chunking

Markdown files are chunked by headings and line ranges.

Example documentation chunk metadata:

```json
{
  "source_type": "doc",
  "relative_path": "README.md",
  "heading": "Purpose",
  "symbol_type": "documentation",
  "start_line": 5,
  "end_line": 8
}
```

Example citation:

```text
README.md:5-8 — Purpose
```

---

### 6. Embeddings and Vector Store

Code and documentation chunks are embedded using a local sentence-transformers model and stored in ChromaDB.

Default embedding model:

```text
sentence-transformers/all-MiniLM-L6-v2
```

This runs on CPU and does not require CUDA or GPU.

---

### 7. Hybrid Retrieval

Pure vector search is often not enough for code, because code search needs exact symbol matching.

This project combines:

```text
Vector Search
+ BM25 Lexical Search
+ Keyword Matching
+ Symbol-Aware Reranking
```

The final retrieval score combines:

```text
semantic similarity
BM25 lexical score
keyword overlap
symbol match score
```

This helps prioritize identifiers such as:

```text
create_user
UserService
TaskService
create_task
access_token
verify_password
```

---

### 8. Agent Tools

The system exposes several repository navigation tools.

#### `search_code(query)`

Searches across indexed repository chunks, including both code and documentation.

Example:

```text
Find code related to user creation
```

#### `find_symbol(symbol_name)`

Finds where a function, class, or method is defined.

Example:

```text
find_symbol("create_user")
```

#### `find_references(symbol_name)`

Finds where a symbol appears in the codebase.

Example:

```text
find_references("create_user")
```

#### `read_file(file_path, start_line, end_line)`

Reads a file or a specific line range with line numbers.

Example:

```text
read_file("app/services/user_service.py", 1, 5)
```

---

## Why This Is Agentic RAG

A basic RAG chatbot usually follows this flow:

```text
question → retrieve documents → generate answer
```

This project follows a tool-based workflow:

```text
question
→ classify query type
→ choose the right tool
→ search docs/code or call code navigation tools
→ construct grounded context
→ generate or return an answer with sources
```

For example:

```text
Where is create_user used?
```

The system does not only run semantic search. It chooses the reference tracing tool:

```text
find_references("create_user")
```

For documentation questions such as:

```text
Dự án này dùng để làm gì?
```

The system retrieves relevant README/docs chunks.

This makes the system more suitable for Python repository onboarding and codebase understanding than a normal document RAG chatbot.

---

## Supported Query Types

The agent currently routes questions into:

```text
documentation_query
location_query
reference_query
explanation_query
search_query
```

Examples:

```text
Dự án này dùng để làm gì?
→ documentation_query

Where is create_user implemented?
→ location_query

Where is create_user used?
→ reference_query

What does UserService do?
→ explanation_query

Find code related to user creation
→ search_query
```

---

## Example Questions

You can ask project-level questions:

```text
Dự án này dùng để làm gì?
Cách setup project này như thế nào?
Tech stack của dự án là gì?
Intern mới nên đọc gì trước?
What does this project do?
How do I set up this project?
```

You can also ask code-level questions:

```text
Where is create_user implemented?

Where is create_user used?

What does UserService do?

UserService làm gì?

Find code related to user creation

create_user được dùng ở đâu?

Where is create_task implemented?

What does TaskService do?
```

---

## Example Output

### Code Question

```text
Question:
Where is create_user used?

Answer:
I found `create_user` in these locations:
- `app/main.py:1` imports `create_user`
- `app/main.py:5` calls `create_user`
- `app/services/user_service.py:1` defines `create_user`

Tools used:
- find_references("create_user")

Sources:
1. app/main.py:1 — reference
2. app/main.py:5 — reference
3. app/services/user_service.py:1 — definition
```

### Documentation Question

```text
Question:
Dự án này dùng để làm gì?

Answer:
Dự án này giúp các nhóm tạo, cập nhật, phân công và theo dõi các nhiệm vụ trong quá trình làm việc.

Sources:
1. README.md:5-8 — Purpose
```

---

## Source Citations

The UI shows sources separately below each answer.

Code citations use:

```text
path/to/file.py:start-end — symbol_name
```

Example:

```text
app/services/user_service.py:1-5 — create_user
```

Reference citations use:

```text
path/to/file.py:line — reference
```

Example:

```text
app/main.py:5 — reference
```

Documentation citations use:

```text
README.md:start-end — heading
```

Example:

```text
README.md:5-8 — Purpose
```

The UI also provides a source excerpt viewer so users can inspect the exact code or documentation lines used to support the answer.

---

## Project Architecture

```text
Python Repository
        |
        v
Repo Scanner
        |
        +-------------------+
        |                   |
        v                   v
Python AST Parser      Markdown Scanner
        |                   |
        v                   v
Code Chunks           Documentation Chunks
        |                   |
        +---------+---------+
                  |
                  v
          Embedding Model
                  |
                  v
         Chroma Vector Store
                  |
                  v
          Hybrid Retriever
                  |
                  v
             Agent Tools
                  |
                  v
      Optional Gemini LLM Generation
                  |
                  v
             Streamlit UI
```

---

## RAG Pipeline

### Offline Indexing Pipeline

```text
repo path
→ scan Python files
→ scan README/docs files
→ parse Python files with AST
→ extract functions/classes/methods
→ chunk README/docs by headings
→ embed all chunks
→ store chunks in ChromaDB
```

### Online Query Pipeline

```text
user question
→ classify query type
→ select retrieval/tool strategy
→ retrieve relevant code/docs
→ construct context
→ generate or return answer
→ show sources with file path and line number
```

---

## Tech Stack

- Python 3.10
- Streamlit
- ChromaDB
- sentence-transformers
- PyTorch CPU
- Python AST
- rank-bm25
- Google Gemini API
- NumPy
- scikit-learn
- Pydantic
- python-dotenv

This project does not require GPU or CUDA.

---

## Project Structure

```text
agentic-python-codebase-rag/
  app/
    __init__.py
    streamlit_app.py

  src/
    __init__.py
    config.py
    scanner.py
    ast_parser.py
    chunker.py
    doc_chunker.py
    embeddings.py
    vector_store.py
    retriever.py
    tools.py
    agent.py
    indexer.py
    evaluator.py
    prompts.py
    llm.py
    company_repos.py

  scripts/
    __init__.py
    index_repo.py
    run_eval.py

  examples/
    sample_python_repo/
    company_repos/
      taskflow_api/

  data/
    repos/
    indexes/
    eval_cases.json

  tests/
    test_scanner.py
    test_chunker.py

  notebooks/
    experiments.ipynb

  requirements.txt
  README.md
  .env.example
  .gitignore
```

---

## Installation

Clone the repository:

```bash
git clone https://github.com/your-username/agentic-python-codebase-rag.git
cd agentic-python-codebase-rag
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Upgrade pip:

```bash
python -m pip install --upgrade pip
```

Install dependencies:

```bash
pip install -r requirements.txt
```

If PyTorch or torchvision is missing, install the CPU version:

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

Check that CUDA is not required:

```bash
python -c "import torch; print(torch.cuda.is_available())"
```

Expected output:

```text
False
```

This is normal. The project runs on CPU.

---

## Environment Variables

Create a `.env` file from `.env.example`:

```powershell
Copy-Item .env.example .env
```

Example `.env`:

```env
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash
LLM_BACKEND=gemini
```

Do not commit `.env` to GitHub.

Make sure `.gitignore` contains:

```gitignore
.env
```

If LLM generation is disabled in the UI, the project can still run using the rule-based agent workflow.

---

## Running the App

Start the Streamlit UI:

```bash
python -m streamlit run app/streamlit_app.py
```

Then open:

```text
http://localhost:8501
```

In the sidebar, choose a repository mode:

```text
Custom Repo
Company Repo
```

### Custom Repo Mode

Enter a local Python repository path:

```text
examples/sample_python_repo
```

Then click:

```text
Index repository
```

### Company Repo Mode

Select a predefined company repository:

```text
TaskFlow API
```

Then click:

```text
Index repository
```

After indexing, ask questions about the repository.

If you want LLM-generated grounded answers, enable:

```text
Use LLM grounded answer generation
```

This requires a valid `GEMINI_API_KEY` in `.env`.

---

## UI Metrics

After indexing, the UI displays:

```text
Python files
Docs
Ignored files
Total chunks
Collection
```

This helps users understand what the system indexed and what it ignored.

Currently indexed:

```text
.py files
README.md
docs/*.md
docs/*.markdown
```

Other file types are counted as ignored files.

---

## Running from Script

You can test the system without the UI:

```bash
python -m scripts.index_repo
```

This indexes the sample repository and runs several test questions.

---

## Evaluation

The project includes a lightweight evaluation script for retrieval and agent workflow correctness.

Run:

```bash
python -m scripts.run_eval
```

The current evaluation is performed on a curated set of repository QA cases across two sample Python repositories:

- `sample_python_repo`
- `taskflow_api`

The evaluation covers both code-level and documentation-level questions, including:

- function implementation lookup
- reference tracing
- class explanation
- README/documentation retrieval
- Vietnamese and English questions
- Custom Repo-style sample repository
- Company Repo-style sample repository

### Metrics

The evaluation reports:

- **Query type accuracy**: whether the agent routes the question to the correct query type
- **Average source recall**: whether the expected source locations are retrieved
- **Expected sources all found rate**: whether all expected sources for each case are found

### Current Result

```text
Overall Evaluation Summary
Number of cases:                 13
Query type accuracy:             100.00%
Average source recall:           100.00%
Expected sources all found rate: 100.00%

Evaluation Summary - sample_python_repo
Number of cases:                 6
Query type accuracy:             100.00%
Average source recall:           100.00%
Expected sources all found rate: 100.00%

Evaluation Summary - taskflow_api
Number of cases:                 7
Query type accuracy:             100.00%
Average source recall:           100.00%
Expected sources all found rate: 100.00%
```

### Notes

The current evaluation focuses on:

- query routing correctness
- source retrieval correctness
- file path and line number citation correctness

It does not yet evaluate:

- LLM answer quality
- large real-world repositories
- hallucination rate
- latency
- production-scale robustness

The reported 100% result is measured only on the curated sample evaluation set, not on arbitrary real-world repositories.

---

## Limitations

- Supports Python source files only for code-level parsing
- Supports Markdown documentation only for docs-level retrieval
- Does not currently index Jupyter notebooks
- Does not currently index Dockerfile, YAML, JSON, requirements.txt, or pyproject.toml
- Current agent routing is mostly rule-based
- Reference search uses lightweight text matching
- It is not a full language server
- It does not modify code
- It does not create pull requests
- Large repositories may take longer to index on CPU
- Gemini API availability may vary depending on quota and model demand
- Current evaluation is based on a small sample repository

---

## Future Improvements

Planned improvements:

- Add larger real-world Python repository evaluation
- Add LLM answer quality evaluation
- Add support for requirements.txt and pyproject.toml indexing
- Add Dockerfile and YAML config indexing
- Add Jupyter notebook `.ipynb` support
- Improve reference tracing with AST-based call detection
- Add FastAPI route analysis
- Add query decomposition for flow questions
- Add MMR or cross-encoder reranking
- Add better UI for retrieved chunks and tool traces
- Add incremental indexing
- Add support for multiple repositories
- Add optional OpenAI/Gemini embedding backend
- Add deployment instructions

---

## What This Project Demonstrates

This project demonstrates:

- RAG system design
- Agentic tool routing
- Code-aware retrieval
- AST-based parsing
- Documentation-aware retrieval
- Vector database usage
- BM25 lexical retrieval
- Hybrid retrieval
- Source-grounded answers
- Streamlit application development
- AI engineering workflow for repository onboarding and codebase understanding

