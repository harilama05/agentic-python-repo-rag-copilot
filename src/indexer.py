from src.llm import GeminiLLM
from dataclasses import dataclass
from pathlib import Path

from src.ast_parser import parse_python_file
from src.chunker import build_code_chunks
from src.retriever import CodeRetriever
from src.scanner import scan_python_files
from src.tools import CodebaseTools
from src.vector_store import CodeVectorStore
from src.agent import CodebaseAgent
from src.config import INDEX_DIR


@dataclass
class IndexedCodebase:
    repo_path: Path
    collection_name: str
    file_count: int
    chunk_count: int
    vector_store: CodeVectorStore
    retriever: CodeRetriever
    tools: CodebaseTools
    agent: CodebaseAgent


def make_collection_name(repo_path: str | Path) -> str:
    """
    Create a safe Chroma collection name from repo folder name.
    """
    repo_path = Path(repo_path).resolve()
    name = repo_path.name.lower().replace(" ", "_").replace("-", "_")

    # Chroma collection names should be simple and at least 3 chars.
    if len(name) < 3:
        name = f"repo_{name}"

    return name


def build_codebase_agent(
    repo_path: str | Path,
    collection_name: str | None = None,
    reset_collection: bool = True,
    use_llm: bool = False,
) -> IndexedCodebase:
    """
    Scan, parse, chunk, embed, and index a Python repo.
    Then return a ready-to-use CodebaseAgent.
    """
    repo_path = Path(repo_path).resolve()

    if not repo_path.exists():
        raise FileNotFoundError(f"Repo path does not exist: {repo_path}")

    if not repo_path.is_dir():
        raise NotADirectoryError(f"Repo path is not a directory: {repo_path}")

    python_files = scan_python_files(repo_path)

    all_chunks = []

    for file_path in python_files:
        parsed_file = parse_python_file(file_path)
        chunks = build_code_chunks(parsed_file, repo_root=repo_path)
        all_chunks.extend(chunks)

    if collection_name is None:
        collection_name = make_collection_name(repo_path)

    vector_store = CodeVectorStore(
        persist_dir=INDEX_DIR / "chroma",
        collection_name=collection_name,
    )

    if reset_collection:
        vector_store.reset_collection()

    vector_store.add_chunks(all_chunks)

    retriever = CodeRetriever(vector_store)
    tools = CodebaseTools(retriever=retriever, repo_root=repo_path)

    llm = GeminiLLM() if use_llm else None

    agent = CodebaseAgent(
        tools=tools,
        llm=llm,
        use_llm=use_llm,
    )

    return IndexedCodebase(
        repo_path=repo_path,
        collection_name=collection_name,
        file_count=len(python_files),
        chunk_count=len(all_chunks),
        vector_store=vector_store,
        retriever=retriever,
        tools=tools,
        agent=agent,
    )