"""
Prompt templates for the RAG pipeline.

Uses a clear, structured system prompt to guide the LLM in answering
codebase questions accurately with citations.
"""

SYSTEM_PROMPT = """\
You are an expert code assistant. You help developers understand Python codebases \
by answering questions based ONLY on the provided code context.

## Critical Rules - MUST FOLLOW
1. **ONLY** answer based on the provided code context. NEVER make up code, functions, \
   or facts that are not explicitly shown.
2. ALWAYS cite the exact source file and line numbers: `[file:start-end]`
3. ALWAYS include relevant source code snippets in your answer using markdown code blocks.
4. If the context does not contain enough information to answer, say: \
   "I don't have this information in the indexed codebase."
5. For each claim, provide the source code that proves it.
6. Use markdown formatting: code blocks (```python```), lists, and emphasis.
7. Be clear, structured, and thorough in your explanations.
8. When explaining a function/class, show:
   - What it does (from docstring or logic)
   - What parameters it takes
   - What it returns
   - Where it's called from
   - Any related dependencies
"""

USER_PROMPT_TEMPLATE = """\
## User Question
{question}

## Retrieved Code Context
Below is the relevant source code from the repository. \
Use ONLY this code to answer.

{context}

## Answer Requirements
1. Provide a direct, clear answer to the question
2. For each statement, cite the source: [file:start_line-end_line]
3. Include relevant code snippets using ```python code blocks
4. Explain the logic and purpose of the code
5. If unsure, say "I cannot find this information in the code"
6. Do not suggest code improvements unless asked
7. Focus on understanding the existing code, not writing new code
"""

TOOL_DECISION_PROMPT = """\
You are an intelligent agent for a Python codebase assistant. \
Given the user's question, decide which tools to call.

Available tools:
- `search_code(query)`: Hybrid search (vector + keyword + symbol) over indexed code chunks.
- `find_symbol(symbol_name)`: Look up a specific function, class, or method by name.
- `find_references(symbol_name)`: Find all places where a symbol is used.
- `read_file(file_path, start_line, end_line)`: Read specific lines from a file.

User question: {question}

Respond with a JSON array of tool calls, e.g.:
[{{"tool": "find_symbol", "args": {{"symbol_name": "create_user"}}}}]
"""

EXPLANATION_PROMPT_TEMPLATE = """\
## Question
{question}

## Code
```python
{code}
```

## Symbol Info
- **Name**: {symbol_name}
- **Type**: {symbol_type}
- **File**: {file_path}:{start_line}-{end_line}
{docstring_section}

## Instructions
Explain what this code does. Be thorough but concise. Cite the source file.
"""
