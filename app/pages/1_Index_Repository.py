"""
📁 Index Repository — Streamlit page for indexing a Python repo.
"""

import streamlit as st

st.set_page_config(page_title="Index Repository", page_icon="📁", layout="wide")
st.title("📁 Index Repository")

repo_path = st.text_input(
    "Repository path",
    value="data/repos/sample_python_repo",
    help="Enter the local path to a Python repository.",
)

col1, col2 = st.columns(2)

with col1:
    collection_name = st.text_input("Collection name (optional)", value="")

with col2:
    reset = st.checkbox("Reset index before indexing", value=True)

use_reranker = st.checkbox("Enable cross-encoder reranking", value=True)
use_llm = st.checkbox("Enable LLM answer generation", value=False,
                       help="Requires OPENAI_API_KEY in .env")

if st.button("🚀 Index Repository", type="primary"):
    with st.spinner("Indexing repository... This may take a minute."):
        try:
            from src.indexing.repo_indexer import index_repository

            indexed = index_repository(
                repo_path=repo_path,
                collection_name=collection_name or None,
                reset=reset,
                use_reranker=use_reranker,
                use_llm=use_llm,
            )

            st.session_state.indexed_codebase = indexed

            st.success("✅ Repository indexed successfully!")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Python files", indexed.file_count)
            with col2:
                st.metric("Code chunks", indexed.chunk_count)
            with col3:
                st.metric("Collection", indexed.collection_name)

        except Exception as exc:
            st.error(f"❌ Indexing failed: {exc}")
