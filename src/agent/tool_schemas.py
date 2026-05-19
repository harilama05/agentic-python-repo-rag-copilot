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
                "used, referenced, or called in the codebase."
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
            "name": "find_callees",
            "description": (
                "Use the code graph to find functions/classes/methods that a "
                "specific function or method calls."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol_name": {
                        "type": "string",
                        "description": "The function or method name to inspect.",
                    },
                },
                "required": ["symbol_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "impact_analysis",
            "description": (
                "Use the code graph to find callers that may be affected if a "
                "specific function, class, or method changes."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol_name": {
                        "type": "string",
                        "description": "The symbol name to analyze.",
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Caller traversal depth (default 2).",
                        "default": 2,
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
