"""
Các mô hình Pydantic được dùng chung trong toàn bộ quy trình pipeline.

Đây là các mô hình dữ liệu chuẩn cho các thành phần: 
- các tệp đã phân tích (documents)
- các đoạn mã (chunks)
- kết quả tìm kiếm (search results), v.v.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Các Enum ─────────────────────────────────────────────────────────────

class FileType(str, Enum):
    PYTHON = "python"
    MARKDOWN = "markdown"
    TEXT = "text"
    JSON = "json"
    YAML = "yaml"
    UNKNOWN = "unknown"


class SymbolType(str, Enum):
    FUNCTION = "function"
    ASYNC_FUNCTION = "async_function"
    CLASS = "class"
    METHOD = "method"
    ASYNC_METHOD = "async_method"
    MODULE = "module"


class ChunkType(str, Enum):
    CODE = "code"
    TEXT = "text"
    MARKDOWN = "markdown"


class SourceType(str, Enum):
    REPO = "repo"
    UPLOAD = "upload"


# ── Document models ──────────────────────────────────────────────────

class ParsedDocument(BaseModel):
    """Represents a parsed file with its content and extracted symbols."""
    file_path: str
    relative_path: str
    file_type: FileType
    source_code: str
    symbols: List[CodeSymbol] = Field(default_factory=list)
    imports: List[CodeImport] = Field(default_factory=list)
    syntax_error: Optional[str] = None
    source: SourceType = SourceType.REPO


class CodeImport(BaseModel):
    """An import statement extracted from a Python file."""
    module: Optional[str] = None
    name: str
    alias: Optional[str] = None
    line: int


class CodeSymbol(BaseModel):
    """A symbol (function/class/method) extracted from source code."""
    name: str
    qualified_name: str
    symbol_type: SymbolType
    file_path: str
    start_line: int
    end_line: int
    docstring: Optional[str] = None
    parent: Optional[str] = None
    decorators: List[str] = Field(default_factory=list)
    parameters: List[str] = Field(default_factory=list)


# ── Chunk models ─────────────────────────────────────────────────────

class Chunk(BaseModel):
    """A single chunk of content ready for embedding and indexing."""
    chunk_id: str
    text: str  # text không nhất thiết chỉ là code gốc. Nó có thể được thêm metadata phía trên để model hiểu tốt hơn.
    content: str  #  nội dung gốc của file
    chunk_type: ChunkType # Để biết đây là code, text hay markdown để có cách xử lý phù hợp
    metadata: Dict[str, Any] = Field(default_factory=dict) # Metadata như đường dẫn file, tên hàm, dòng bắt đầu/kết thúc, ...


# ── Các mô hình tìm kiếm / truy xuất ────────────────────────────────────────

class SearchResult(BaseModel):
    """Một kết quả tìm kiếm đơn lẻ từ bất kỳ chiến lược tìm kiếm nào."""
    chunk_id: str
    text: str
    content: str = "" # Nội dung gốc của file
    metadata: Dict[str, Any] = Field(default_factory=dict) # Metadata như đường dẫn file, tên hàm, dòng bắt đầu/kết thúc, ...
    score: float = 0.0 # Điểm số tìm kiếm


class RerankedResult(BaseModel):
    """Một kết quả tìm kiếm sau khi đã được xếp hạng lại."""
    chunk_id: str
    text: str
    content: str = "" # Nội dung gốc của file
    metadata: Dict[str, Any] = Field(default_factory=dict) # Metadata như đường dẫn file, tên hàm, dòng bắt đầu/kết thúc, ...
    vector_score: float = 0.0 # Điểm từ vector search
    keyword_score: float = 0.0 # Điểm từ BM25 keyword search
    symbol_score: float = 0.0 # Điểm từ symbol search
    rerank_score: float = 0.0 # Điểm từ cross-encoder reranker
    final_score: float = 0.0 # Điểm cuối cùng sau khi fusion


# ── Các mô hình Agent / chat ─────────────────────────────────────────────

class ChatMessage(BaseModel):
    role: str  # "user", "assistant", "system"
    content: str # Nội dung tin nhắn


class AgentResponse(BaseModel):
    """Phản hồi cuối cùng từ RAG Agent."""
    question: str # Câu hỏi của người dùng
    answer: str # Câu trả lời từ agent
    sources: List[Dict[str, Any]] = Field(default_factory=list) # Nguồn đã được retrieve
    citations: List[str] = Field(default_factory=list) # Trích dẫn từ các nguồn retrieved
    tools_used: List[str] = Field(default_factory=list) # Các công cụ đã sử dụng
    query_type: str = "" # Loại truy vấn
    raw_results: Dict[str, Any] = Field(default_factory=dict)
    token_usage: Dict[str, int] = Field(default_factory=dict)


# ── Các mô hình đánh giá ───────────────────────────────────────────────

class EvalCase(BaseModel):
    """Một test case đánh giá."""
    question: str # Câu hỏi
    expected_answer: str # Câu trả lời mong đợi
    expected_sources: List[str] = Field(default_factory=list) # Nguồn mong đợi
    tags: List[str] = Field(default_factory=list) # Các tags để phân loại


class EvalResult(BaseModel):
    """Kết quả đánh giá."""
    question: str # Câu hỏi đánh giá
    generated_answer: str # Câu trả lời được sinh ra
    expected_answer: str # Câu trả lời mong đợi
    sources_retrieved: List[str] = Field(default_factory=list) # Nguồn được retrieve
    metrics: Dict[str, float] = Field(default_factory=dict) # Các metrics đánh giá


# Fix forward references
ParsedDocument.model_rebuild()
