"""
Tool schemas — describes each tool for the LLM's function-calling interface.

These are OpenAI function-calling compatible schemas.
"""

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": (
                "Search the indexed codebase using hybrid search "
                "(vector + keyword + symbol). Returns relevant code chunks."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query (natural language or code identifier).",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default 5).",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_symbol",
            "description": (
                "Look up a specific function, class, or method by its exact name. "
                "Faster and more precise than search_code for known symbol names."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol_name": {
                        "type": "string",
                        "description": "The name of the function, class, or method.",
                    },
                },
                "required": ["symbol_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_references",
            "description": (
                "Find all places where a symbol (function/class/method) is "
                "used or referenced in the codebase."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol_name": {
                        "type": "string",
                        "description": "The symbol name to find references for.",
                    },
                },
                "required": ["symbol_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read a specific line range from a file in the repository."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to the file.",
                    },
                    "start_line": {
                        "type": "integer",
                        "description": "Start line number (1-indexed).",
                    },
                    "end_line": {
                        "type": "integer",
                        "description": "End line number (1-indexed).",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
]
