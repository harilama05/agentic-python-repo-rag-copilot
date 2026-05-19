"""
Streamlit UI for indexing and chatting with a codebase.

The app supports three ingestion paths:
- Local repository path
- Public GitHub repository URL
- Uploaded ZIP repository
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

import streamlit as st


st.set_page_config(
    page_title="Codebase RAG Copilot",
    page_icon="RAG",
    layout="wide",
    initial_sidebar_state="expanded",
)


st.markdown(
    """
    <style>
    .stApp {
        background: #f7f8fb;
    }
    section[data-testid="stSidebar"] {
        background: #ffffff;
        border-right: 1px solid #e5e7eb;
    }
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
        max-width: 1180px;
    }
    [data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        padding: 12px 14px;
    }
    div[data-testid="stExpander"] {
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
    }
    .small-muted {
        color: #6b7280;
        font-size: 0.88rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def _init_state() -> None:
    defaults = {
        "indexed_codebase": None,
        "chat_history": [],
        "last_index_summary": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _clear_chat() -> None:
    st.session_state.chat_history = []


def _set_indexed_codebase(indexed, elapsed: float) -> None:
    st.session_state.indexed_codebase = indexed
    st.session_state.chat_history = []
    st.session_state.last_index_summary = {
        "collection_name": indexed.collection_name,
        "file_count": indexed.file_count,
        "chunk_count": indexed.chunk_count,
        "elapsed": elapsed,
    }


def _run_index_job(label: str, job: Callable[[], object]) -> None:
    with st.status(label, expanded=True) as status:
        try:
            start_time = time.time()
            indexed = job()
            elapsed = time.time() - start_time
            _set_indexed_codebase(indexed, elapsed)
            status.update(label="Indexing completed", state="complete")
        except Exception as exc:
            status.update(label="Indexing failed", state="error")
            st.error(str(exc))
            with st.expander("Traceback"):
                import traceback

                st.code(traceback.format_exc())


def _render_sidebar() -> None:
    indexed = st.session_state.indexed_codebase

    with st.sidebar:
        st.title("Codebase RAG")
        st.caption("Index a repository, then ask questions about the code.")

        st.divider()
        st.subheader("Index status")

        if indexed is None:
            st.warning("No repository indexed")
        else:
            st.success(indexed.collection_name)
            st.metric("Files", indexed.file_count)
            st.metric("Chunks", indexed.chunk_count)

            if st.button("Clear chat", use_container_width=True):
                _clear_chat()
                st.rerun()

        st.divider()
        st.subheader("Runtime")
        st.caption("Supported ingestion extensions: .py, .md, .json, .txt")
        st.caption("LLM generation requires OPENAI_API_KEY.")


def _render_index_summary() -> None:
    summary = st.session_state.last_index_summary
    if not summary:
        return

    st.success(
        "Indexed "
        f"{summary['collection_name']} in {summary['elapsed']:.1f}s"
    )
    col1, col2, col3 = st.columns(3)
    col1.metric("Files", summary["file_count"])
    col2.metric("Chunks", summary["chunk_count"])
    col3.metric("Collection", summary["collection_name"])


def _render_indexing_panel() -> None:
    st.header("Index")

    with st.expander("Indexing options", expanded=True):
        opt1, opt2, opt3, opt4 = st.columns(4)
        with opt1:
            collection_name = st.text_input("Collection name", value="")
        with opt2:
            reset = st.checkbox("Reset index", value=True)
        with opt3:
            use_reranker = st.checkbox("Use reranker", value=False)
        with opt4:
            use_llm = st.checkbox("Use LLM", value=False)

    local_tab, github_tab, zip_tab = st.tabs(["Local path", "GitHub", "ZIP upload"])

    with local_tab:
        st.subheader("Local repository")
        repo_path = st.text_input(
            "Repository path",
            value="data/repos/sample_python_repo",
            key="local_repo_path",
        )

        if st.button("Index local repository", type="primary", key="index_local"):
            path = Path(repo_path).expanduser()
            if not repo_path.strip():
                st.warning("Enter a repository path.")
            elif not path.exists():
                st.error(f"Path does not exist: {path}")
            else:
                from src.indexing.repo_indexer import index_repository

                _run_index_job(
                    "Indexing local repository...",
                    lambda: index_repository(
                        repo_path=path,
                        collection_name=collection_name or None,
                        reset=reset,
                        use_reranker=use_reranker,
                        use_llm=use_llm,
                    ),
                )

    with github_tab:
        st.subheader("GitHub repository")
        github_url = st.text_input(
            "GitHub URL",
            placeholder="https://github.com/owner/repository",
        )
        branch = st.text_input("Branch", value="", placeholder="main")
        force_refresh = st.checkbox("Refresh clone", value=True)

        if st.button("Clone and index GitHub repository", type="primary"):
            if not github_url.strip():
                st.warning("Enter a GitHub repository URL.")
            else:
                from src.indexing.ingestion_indexer import index_github_repository

                _run_index_job(
                    "Cloning and indexing GitHub repository...",
                    lambda: index_github_repository(
                        github_url=github_url,
                        branch=branch.strip() or None,
                        collection_name=collection_name or None,
                        force_refresh=force_refresh,
                        reset=reset,
                        use_reranker=use_reranker,
                        use_llm=use_llm,
                    ),
                )

    with zip_tab:
        st.subheader("ZIP repository")
        uploaded_zip = st.file_uploader(
            "Upload a repository ZIP",
            type=["zip"],
            accept_multiple_files=False,
        )
        force_refresh_zip = st.checkbox("Refresh extracted ZIP", value=True)

        if st.button("Extract and index ZIP", type="primary"):
            if uploaded_zip is None:
                st.warning("Choose a ZIP file first.")
            else:
                from src.indexing.ingestion_indexer import index_zip_bytes

                zip_bytes = uploaded_zip.getvalue()
                _run_index_job(
                    "Extracting and indexing ZIP repository...",
                    lambda: index_zip_bytes(
                        filename=uploaded_zip.name,
                        zip_bytes=zip_bytes,
                        collection_name=collection_name or None,
                        force_refresh=force_refresh_zip,
                        reset=reset,
                        use_reranker=use_reranker,
                        use_llm=use_llm,
                    ),
                )

    _render_index_summary()


def _render_examples() -> None:
    indexed = st.session_state.indexed_codebase
    if indexed is None:
        return

    examples = [
        "Where is create_user defined?",
        "Who calls create_user?",
        "What does UserService.create_user call?",
        "What may be affected if User changes?",
        "Explain the main service flow.",
        "Find code related to validation.",
    ]

    with st.expander("Example questions"):
        cols = st.columns(2)
        for index, question in enumerate(examples):
            with cols[index % 2]:
                if st.button(question, key=f"example_{index}", use_container_width=True):
                    st.session_state.pending_question = question


def _render_chat_history() -> None:
    for entry in st.session_state.chat_history:
        with st.chat_message("user"):
            st.write(entry["question"])

        with st.chat_message("assistant"):
            st.markdown(entry["answer"])

            meta_cols = st.columns([1, 1, 2])
            meta_cols[0].caption(f"Type: {entry.get('query_type') or 'unknown'}")
            meta_cols[1].caption(f"Latency: {entry.get('elapsed', 0):.2f}s")
            tools = entry.get("tools_used", [])
            if tools:
                meta_cols[2].caption(f"Tools: {', '.join(tools)}")

            citations = entry.get("citations", [])
            if citations:
                with st.expander(f"Sources ({len(citations)})"):
                    for citation in citations:
                        st.code(citation, language=None)


def _render_chat_panel() -> None:
    st.header("Chat")

    indexed = st.session_state.indexed_codebase
    if indexed is None:
        st.info("Index a local path, GitHub repository, or ZIP repository first.")
        return

    st.caption(
        f"Active collection: {indexed.collection_name} | "
        f"{indexed.file_count} files | {indexed.chunk_count} chunks"
    )

    _render_examples()
    _render_chat_history()

    pending_question = st.session_state.pop("pending_question", None)
    question = st.chat_input("Ask about the indexed codebase") or pending_question

    if not question:
        return

    with st.chat_message("user"):
        st.write(question)

    with st.chat_message("assistant"):
        with st.spinner("Searching and generating answer..."):
            start_time = time.time()
            response = indexed.agent.invoke(question)
            elapsed = time.time() - start_time

        st.markdown(response.answer)

        col1, col2, col3 = st.columns([1, 1, 2])
        col1.caption(f"Type: {response.query_type or 'unknown'}")
        col2.caption(f"Latency: {elapsed:.2f}s")
        if response.tools_used:
            col3.caption(f"Tools: {', '.join(response.tools_used)}")

        if response.citations:
            with st.expander(f"Sources ({len(response.citations)})"):
                for citation in response.citations:
                    st.code(citation, language=None)

        if response.token_usage:
            with st.expander("Token usage"):
                st.json(response.token_usage)

    st.session_state.chat_history.append(
        {
            "question": question,
            "answer": response.answer,
            "query_type": response.query_type,
            "tools_used": response.tools_used,
            "citations": response.citations,
            "sources": response.sources,
            "elapsed": elapsed,
        }
    )


def main() -> None:
    _init_state()
    _render_sidebar()

    st.title("Codebase RAG Copilot")
    st.markdown(
        '<p class="small-muted">Index Python repositories from local disk, '
        "GitHub, or ZIP upload, then ask grounded questions with citations.</p>",
        unsafe_allow_html=True,
    )

    index_col, chat_col = st.columns([0.95, 1.05], gap="large")

    with index_col:
        _render_indexing_panel()

    with chat_col:
        _render_chat_panel()


if __name__ == "__main__":
    main()
