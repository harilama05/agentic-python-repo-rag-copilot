# Agentic RAG Copilot for Python Codebases

A read-only Agentic RAG copilot for Python repositories.

This project scans a Python codebase, extracts functions/classes/methods using Python AST, indexes code chunks into a vector database, and answers codebase questions using agent tools such as semantic code search, symbol lookup, reference tracing, and file reading.

The goal is to help developers understand and navigate unfamiliar Python repositories faster.

---

## Overview

When working with a new Python codebase, developers often need to answer questions such as:

```text
Where is this function implemented?
Where is this function used?
What does this class do?
Which files are related to a feature?
Where does the request flow start?
```

This project solves that problem by turning a Python repository into a searchable knowledge base.

The system:

```text
Python repo
→ scan .py files
→ parse with Python AST
→ extract functions/classes/methods
→ create code chunks with metadata
→ embed chunks
→ store in ChromaDB
→ retrieve relevant code
→ use agent tools to answer questions with citations
```

---

## Current Status

This is the current MVP version.

Implemented:

- Python repository scanning
- AST-based code parsing
- Function/class/method extraction
- Code chunking with metadata
- Local vector indexing with ChromaDB
- Local CPU embeddings with sentence-transformers
- Hybrid retrieval:
  - semantic vector search
  - keyword matching
  - symbol-aware reranking
- Agent tools:
  - `search_code(query)`
  - `find_symbol(symbol_name)`
  - `find_references(symbol_name)`
  - `read_file(file_path, start_line, end_line)`
- Rule-based agent workflow
- Streamlit UI
- File path and line number citations

Not yet implemented:

- LLM-based natural language answer generation
- Evaluation metrics
- Large real-world repository benchmarking
- Incremental indexing
- Multi-language support
- Automatic code editing

---

## Features

### 1. Python Repository Scanner

Scans a local Python repository and collects valid `.py` files while ignoring unnecessary folders such as:

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

---

### 2. AST-Aware Code Parsing

Uses Python's built-in `ast` module to extract:

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
  "file_path": "app/services/user_service.py",
  "symbol_name": "create_user",
  "qualified_name": "create_user",
  "symbol_type": "function",
  "start_line": 1,
  "end_line": 5
}
```

---

### 3. Code Chunking

Each function, class, or method becomes a searchable chunk.

A chunk contains:

- source code
- file path
- symbol name
- symbol type
- start line
- end line
- parent class, if available
- docstring, if available
- imports, if available

Example chunk:

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

### 4. Vector Search

Code chunks are embedded using a local sentence-transformers model and stored in ChromaDB.

Default embedding model:

```text
sentence-transformers/all-MiniLM-L6-v2
```

This runs on CPU and does not require CUDA or GPU.

---

### 5. Hybrid Retrieval

Pure vector search is often not enough for code because code search needs exact symbol matching.

This project combines:

```text
final_score =
    vector_score
  + keyword_score
  + symbol_score
```

This helps prioritize exact symbols like:

```text
create_user
UserService
get_user
```

over loosely related chunks.

---

### 6. Agent Tools

The system exposes several code navigation tools.

#### `search_code(query)`

Finds code chunks related to a natural language query.

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
→ search code / find symbol / trace references / read file
→ return grounded answer with sources
```

For example, when the user asks:

```text
Where is create_user used?
```

The system does not only run semantic search. It chooses the reference tracing tool:

```text
find_references("create_user")
```

This makes the system more suitable for codebase navigation than a normal document RAG chatbot.

---

## Example Questions

You can ask:

```text
Where is create_user implemented?

Where is create_user used?

What does UserService do?

Find code related to user creation
```

Example output:

```text
Question:
Where is create_user used?

Answer:
I found `create_user` in these locations:
- `app/main.py:1` (reference) — `from app.services.user_service import create_user`
- `app/main.py:5` (reference) — `user = create_user("alice@example.com")`
- `app/services/user_service.py:1` (definition) — `def create_user(email: str) -> dict:`

Tools used:
- find_references("create_user")

Sources:
- app/main.py:1
- app/main.py:5
- app/services/user_service.py:1
```

---

## Project Architecture

```text
Python Repository
        |
        v
Repo Scanner
        |
        v
Python AST Parser
        |
        v
Function/Class/Method Chunks
        |
        v
Embedding Model
        |
        v
Chroma Vector Database
        |
        v
Hybrid Retriever
        |
        v
Agent Tools
        |
        v
Rule-Based Agent
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
→ parse each file with AST
→ extract symbols
→ build code chunks
→ embed chunks
→ store chunks in ChromaDB
```

### Online Query Pipeline

```text
user question
→ classify query type
→ select tool
→ retrieve relevant code
→ return answer with citations
```

Supported query types:

```text
location_query
reference_query
explanation_query
search_query
```

Example:

```text
Question:
Where is create_user implemented?

Query type:
location_query

Tool used:
find_symbol("create_user")
```

---

## Tech Stack

- Python 3.10
- Streamlit
- ChromaDB
- sentence-transformers
- PyTorch CPU
- Python AST
- NumPy
- scikit-learn
- Pydantic

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
    embeddings.py
    vector_store.py
    retriever.py
    tools.py
    agent.py
    indexer.py
    evaluator.py
    prompts.py

  scripts/
    __init__.py
    index_repo.py
    run_eval.py

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

## Running the App

Start the Streamlit UI:

```bash
python -m streamlit run app/streamlit_app.py
```

Then open:

```text
http://localhost:8501
```

In the sidebar, enter a Python repository path.

Example:

```text
data/repos/sample_python_repo
```

Then click:

```text
Index repository
```

After indexing, ask questions such as:

```text
Where is create_user implemented?
Where is create_user used?
What does UserService do?
Find code related to user creation
```

---

## Running from Script

You can also test the system without the UI:

```bash
python -m scripts.index_repo
```

This indexes the sample repository and runs several test questions.

---

## Sample Output

```text
Question:
Where is create_user implemented?

Query type:
location_query

Tools used:
- find_symbol("create_user")

Answer:
`create_user` is defined in:
- `app/services/user_service.py:1-5` — `create_user` (function)

Sources:
- app/services/user_service.py:1-5
```

```text
Question:
Where is create_user used?

Query type:
reference_query

Tools used:
- find_references("create_user")

Answer:
I found `create_user` in these locations:
- `app/main.py:1` (reference)
- `app/main.py:5` (reference)
- `app/services/user_service.py:1` (definition)

Sources:
- app/main.py:1
- app/main.py:5
- app/services/user_service.py:1
```

---

## Limitations

- Supports Python codebases only
- Current agent workflow is rule-based
- Current response generation is not yet LLM-powered
- Reference search uses lightweight text matching
- It is not a full language server
- It does not modify code
- It does not create pull requests
- Large repositories may take longer to index on CPU

---

## Future Improvements

Planned improvements:

- Add LLM-based natural language answer generation
- Add retrieval evaluation metrics:
  - retrieval hit rate
  - citation accuracy
  - answer groundedness
- Improve reference tracing with AST-based call detection
- Add FastAPI route analysis
- Add better UI for retrieved chunks and tool traces
- Add incremental indexing
- Add support for larger real-world repositories
- Add optional OpenAI/Gemini embedding backend

---

## What This Project Demonstrates

This project demonstrates:

- RAG system design
- Code-aware retrieval
- AST-based parsing
- Vector database usage
- Hybrid retrieval
- Agent tool design
- Source-grounded answers
- Streamlit application development
- AI engineering workflow for codebase understanding

---
