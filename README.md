# 🐍 Agentic RAG Codebase Assistant

Trợ lý AI thông minh cho các dự án Python, sử dụng kỹ thuật **Agentic RAG** (Retrieval-Augmented Generation) hiện đại.

Hệ thống quét mã nguồn Python, trích xuất hàm/lớp/phương thức bằng AST, đánh chỉ mục vào cơ sở dữ liệu vector, và trả lời câu hỏi về codebase thông qua các công cụ agent: tìm kiếm ngữ nghĩa, tra cứu symbol, truy vết tham chiếu, và đọc file.

---

## Tổng quan

Khi làm việc với một codebase Python mới, lập trình viên thường cần trả lời các câu hỏi như:

- Hàm này được định nghĩa ở đâu?
- Hàm này được sử dụng ở những đâu?
- Lớp này làm gì?
- Những file nào liên quan đến tính năng X?

Dự án này giải quyết vấn đề đó bằng cách biến một Python repository thành một cơ sở tri thức có thể tìm kiếm được.

```
Repo Python → Quét file → Phân tích AST → Trích xuất symbol
→ Chia chunk → Nhúng vector → Lưu ChromaDB
→ Tìm kiếm lai (Vector + BM25 + Symbol) → Hợp nhất RRF
→ Xếp hạng lại (Cross-Encoder) → Sinh câu trả lời (LLM)
```

---

## Tính năng chính

### 1. Quét Repository thông minh
- Quét đệ quy thư mục, hỗ trợ `.py`, `.md`, `.txt`, `.json`, `.yaml`
- Tự động bỏ qua `.git`, `__pycache__`, `.venv`, `node_modules`, v.v.

### 2. Phân tích AST (Abstract Syntax Tree)
- Trích xuất hàm, lớp, phương thức, import, docstring
- Trích xuất thêm **decorators** và **parameters**
- Xác định số dòng bắt đầu/kết thúc chính xác

### 3. Chia chunk thông minh (AST-aware Chunking)
- **Code**: Mỗi hàm/lớp/phương thức = 1 chunk với metadata preamble
- **Markdown**: Chia theo heading (`#`, `##`, v.v.)
- **Text**: Sliding-window với overlap và nhận diện ranh giới câu

### 4. Tìm kiếm lai (Hybrid Search)
| Chiến lược | Mô tả |
|-----------|-------|
| **Vector Search** | Tìm kiếm ngữ nghĩa qua ChromaDB (cosine similarity) |
| **BM25 Keyword** | Tìm kiếm từ khóa chính xác (rất hiệu quả cho tên hàm) |
| **Symbol Search** | Tra cứu trực tiếp metadata (nhanh nhất cho tên cụ thể) |
| **RRF Fusion** | Hợp nhất kết quả từ 3 chiến lược bằng Reciprocal Rank Fusion |

### 5. Xếp hạng lại (Reranking)
- **Cross-Encoder**: Chấm điểm từng cặp (query, document) cho độ chính xác cao
- **MMR**: Maximal Marginal Relevance — giảm trùng lặp trong kết quả

### 6. Công cụ Agent
| Công cụ | Chức năng |
|---------|----------|
| `search_code(query)` | Tìm kiếm lai toàn bộ codebase |
| `find_symbol(name)` | Tra cứu hàm/lớp/phương thức theo tên |
| `find_references(name)` | Tìm tất cả nơi sử dụng một symbol |
| `read_file(path, start, end)` | Đọc nội dung file theo dòng |

### 7. Pipeline Agent thông minh

```
Câu hỏi → Phân loại truy vấn → Chọn chiến lược tìm kiếm
→ Tìm kiếm lai → Xếp hạng lại → Sinh câu trả lời → Trích dẫn nguồn
```

Hỗ trợ 4 loại truy vấn:
- `location_query` — "Hàm X được định nghĩa ở đâu?"
- `reference_query` — "Hàm X được sử dụng ở đâu?"
- `explanation_query` — "Hàm X làm gì?"
- `search_query` — Tìm kiếm chung

### 8. Đánh giá chất lượng RAG
- Tự động tạo bộ test từ metadata đã index
- Metrics: Answer Relevancy, Retrieval Precision/Recall, Faithfulness
- Tích hợp RAGAS (tùy chọn)

---

## Kiến trúc dự án

```
agentic-python-codebase-rag/
├── app/                          # Giao diện Streamlit
│   ├── streamlit_app.py          # Ứng dụng chính (all-in-one)
│   └── pages/                    # Các trang phụ
│
├── api/                          # REST API (FastAPI)
│   ├── main.py                   # App assembly + CORS
│   ├── routes_health.py          # GET /health
│   ├── routes_indexing.py        # POST /api/index/repository
│   ├── routes_upload.py          # POST /api/upload/file
│   └── routes_chat.py            # POST /api/chat/ask
│
├── src/                          # Thư viện lõi
│   ├── config.py                 # Cấu hình trung tâm (pydantic-settings)
│   ├── schemas.py                # Data models chuẩn (Pydantic)
│   ├── constants.py              # Hằng số toàn cục
│   │
│   ├── ingestion/                # Thu thập dữ liệu
│   │   ├── scanner.py            # Quét thư mục repo
│   │   ├── file_loader.py        # Đọc file an toàn
│   │   ├── file_type_detector.py # Phát hiện loại file
│   │   ├── upload_handler.py     # Xử lý file upload
│   │   └── document_registry.py  # Theo dõi file đã index (SHA-256)
│   │
│   ├── parsing/                  # Phân tích cú pháp
│   │   ├── ast_parser.py         # Python AST parser
│   │   ├── markdown_parser.py    # Markdown parser
│   │   ├── text_parser.py        # Plain text parser
│   │   ├── json_parser.py        # JSON parser
│   │   └── yaml_parser.py        # YAML parser
│   │
│   ├── chunking/                 # Chia nhỏ nội dung
│   │   ├── code_chunker.py       # AST-aware (1 symbol = 1 chunk)
│   │   ├── text_chunker.py       # Sliding-window + overlap
│   │   └── markdown_chunker.py   # Header-aware chunking
│   │
│   ├── embeddings/               # Nhúng vector
│   │   ├── embedding_model.py    # SentenceTransformer wrapper
│   │   └── embedding_cache.py    # Cache embeddings trên disk
│   │
│   ├── storage/                  # Lưu trữ
│   │   ├── vector_store.py       # ChromaDB (cosine similarity)
│   │   ├── keyword_store.py      # BM25 keyword search
│   │   ├── file_store.py         # Nội dung file (JSON)
│   │   └── metadata_store.py     # Metadata chunk (JSON)
│   │
│   ├── retrieval/                # Tìm kiếm
│   │   ├── vector_search.py      # Tìm kiếm ngữ nghĩa
│   │   ├── keyword_search.py     # Tìm kiếm từ khóa BM25
│   │   ├── symbol_search.py      # Tra cứu symbol
│   │   ├── rrf.py                # Reciprocal Rank Fusion
│   │   ├── query_transform.py    # Phân loại & biến đổi truy vấn
│   │   ├── hybrid_search.py      # Điều phối tìm kiếm lai
│   │   └── retriever.py          # Facade chính
│   │
│   ├── reranking/                # Xếp hạng lại
│   │   ├── cross_encoder_reranker.py  # Cross-encoder
│   │   ├── mmr.py                # Maximal Marginal Relevance
│   │   └── reranker.py           # Điều phối 2 giai đoạn
│   │
│   ├── agent/                    # Agent thông minh
│   │   ├── state.py              # AgentState TypedDict
│   │   ├── tool_schemas.py       # OpenAI function-calling schemas
│   │   ├── tools.py              # Triển khai công cụ
│   │   ├── router.py             # Phân loại & định tuyến
│   │   └── graph.py              # State machine pipeline
│   │
│   ├── generation/               # Sinh câu trả lời
│   │   ├── prompts.py            # System & user prompt templates
│   │   ├── context_builder.py    # Xây dựng ngữ cảnh cho LLM
│   │   ├── answer_generator.py   # Gọi LLM (OpenAI-compatible)
│   │   └── citation_builder.py   # Xây dựng trích dẫn nguồn
│   │
│   ├── evaluation/               # Đánh giá chất lượng
│   │   ├── metrics.py            # Metrics tùy chỉnh
│   │   ├── ragas_eval.py         # Tích hợp RAGAS
│   │   ├── eval_runner.py        # Chạy đánh giá hàng loạt
│   │   └── testset_builder.py    # Tự động tạo bộ test
│   │
│   ├── metadata/                 # Quản lý metadata
│   │   ├── id_generator.py       # Content-addressable chunk IDs
│   │   ├── metadata_builder.py   # Xây metadata cho ChromaDB
│   │   └── access_policy.py      # Chính sách truy cập
│   │
│   ├── security/                 # Bảo mật
│   │   ├── file_validator.py     # Kiểm tra file upload
│   │   ├── path_guard.py         # Chống path traversal
│   │   └── permission_filter.py  # Lọc kết quả theo quyền
│   │
│   └── observability/            # Quan sát & debug
│       ├── logger.py             # Structured logging
│       ├── traces.py             # Tracing nhẹ
│       └── usage_tracker.py      # Theo dõi sử dụng
│
├── scripts/                      # Scripts CLI
│   ├── index_repo.py             # Index repo từ command line
│   ├── seed_sample_repo.py       # Tạo repo mẫu để test
│   ├── rebuild_index.py          # Xây lại index từ đầu
│   └── run_eval.py               # Chạy đánh giá tự động
│
├── docker/                       # Docker
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── data/                         # Dữ liệu
│   ├── repos/                    # Repo được index
│   ├── uploads/                  # File upload
│   ├── indexes/                  # Chỉ mục (ChromaDB, BM25, metadata)
│   └── eval/                     # Kết quả đánh giá
│
├── requirements.txt
├── pyproject.toml
├── .env.example
└── .gitignore
```

---

## Công nghệ sử dụng

| Thành phần | Công nghệ |
|-----------|-----------|
| Ngôn ngữ | Python 3.11+ |
| Giao diện | Streamlit |
| REST API | FastAPI + Uvicorn |
| Vector DB | ChromaDB |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) |
| Reranking | Cross-Encoder (ms-marco-MiniLM-L-6-v2) |
| Keyword Search | rank-bm25 |
| LLM | OpenAI-compatible (GPT, Ollama, LM Studio) |
| Data Models | Pydantic v2 |
| Cấu hình | pydantic-settings + .env |
| Logging | structlog |
| Đánh giá | RAGAS (tùy chọn) |

> Dự án chạy hoàn toàn trên **CPU**, không yêu cầu GPU hay CUDA.

---

## Cài đặt

```bash
# Clone repo
git clone https://github.com/your-username/agentic-python-codebase-rag.git
cd agentic-python-codebase-rag

# Tạo môi trường ảo
python -m venv .venv

# Kích hoạt (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Cài đặt dependencies
pip install -r requirements.txt
```

Cấu hình (tùy chọn):
```bash
# Sao chép file cấu hình mẫu
cp .env.example .env

# Thêm API key nếu muốn dùng LLM sinh câu trả lời
# OPENAI_API_KEY=sk-...
```

---

## Chạy ứng dụng

### Streamlit UI (khuyên dùng)

```bash
python -m streamlit run app/streamlit_app.py
```

Mở trình duyệt tại `http://localhost:8501`

### REST API

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

API docs tại `http://localhost:8000/docs`

### Command Line

```bash
# Tạo repo mẫu để test
python -m scripts.seed_sample_repo

# Index một repository
python -m scripts.index_repo --repo data/repos/sample_python_repo

# Chạy đánh giá
python -m scripts.run_eval --repo data/repos/sample_python_repo
```

---

## Ví dụ sử dụng

### Câu hỏi: "Hàm create_user được sử dụng ở đâu?"

```
Loại truy vấn: reference_query
Công cụ: find_references("create_user")

Kết quả:
- service.py:12 (định nghĩa) — def create_user(name, email)
- main.py:5   (tham chiếu)  — user = create_user("Alice", "alice@example.com")
```

### Câu hỏi: "Lớp UserService làm gì?"

```
Loại truy vấn: explanation_query
Công cụ: find_symbol("UserService") → search_code("UserService")

Kết quả: Hiển thị mã nguồn và docstring của lớp UserService
với trích dẫn file:dòng chính xác.
```

---

## Kỹ thuật RAG hiện đại

| Kỹ thuật | Vị trí | Mục đích |
|----------|--------|----------|
| AST-based Chunking | `chunking/code_chunker.py` | Chunk theo đơn vị ngữ nghĩa |
| Hybrid Search | `retrieval/hybrid_search.py` | Kết hợp Vector + BM25 + Symbol |
| Reciprocal Rank Fusion | `retrieval/rrf.py` | Hợp nhất rankings từ nhiều nguồn |
| Cross-Encoder Reranking | `reranking/cross_encoder_reranker.py` | Xếp hạng chính xác cao |
| Maximal Marginal Relevance | `reranking/mmr.py` | Đa dạng hóa kết quả |
| Incremental Indexing | `indexing/incremental_indexer.py` | Chỉ re-index file thay đổi |
| Agentic Pipeline | `agent/graph.py` | State machine: route → retrieve → rerank → generate |
| Embedding Cache | `embeddings/embedding_cache.py` | Tránh re-embed chunks không đổi |

---

## Hạn chế hiện tại

- Chỉ hỗ trợ codebase Python
- Agent workflow dựa trên luật (chưa dùng LLM để chọn tool)
- Tìm kiếm tham chiếu dùng regex (chưa dùng AST-based call graph)
- Không chỉnh sửa code, không tạo pull request
- Repo lớn có thể mất thời gian index trên CPU

---

## Giấy phép

MIT License
