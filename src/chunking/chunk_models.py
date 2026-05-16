"""
Internal chunk models for the chunking pipeline.

These bridge the gap between parsing output and the canonical ``Chunk``
schema used for indexing.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class ChunkResult:
    """Intermediate result from a chunker before conversion to ``Chunk``."""
    text: str  # Rich text with metadata preamble
    content: str  # Raw code or text
    symbol_name: Optional[str] = None
    qualified_name: Optional[str] = None
    symbol_type: Optional[str] = None
    start_line: int = 0
    end_line: int = 0
    parent: Optional[str] = None
    docstring: Optional[str] = None
    extra_metadata: Dict[str, Any] = field(default_factory=dict)
