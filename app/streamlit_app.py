"""
Agentic RAG Codebase Assistant - Streamlit Demo App

A complete multi-page Streamlit application for indexing Python codebases
and asking questions about them using modern RAG techniques.
"""

import streamlit as st
import time
from pathlib import Path

# ── Page config ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="Agentic RAG Codebase Assistant",
    page_icon="🐍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Global */
    .stApp { background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%); }

    /* Header styling */
    h1 { color: #e0e0ff !important; text-shadow: 0 0 20px rgba(100,100,255,0.3); }
    h2, h3 { color: #c8c8ff !important; }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
        border-right: 1px solid rgba(100,100,255,0.2);
    }
    [data-testid="stSidebar"] h1,
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3 {
        color: #a0a0ff !important;
    }

    /* Chat messages */
    .stChatMessage { border-radius: 12px; }

    /* Metrics */
    [data-testid="stMetric"] {
        background: rgba(100,100,255,0.1);
        border: 1px solid rgba(100,100,255,0.2);
        border-radius: 12px;
        padding: 12px;
    }

    /* Buttons */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border: none;
        border-radius: 8px;
        font-weight: 600;
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #764ba2 0%, #667eea 100%);
        box-shadow: 0 4px 15px rgba(102,126,234,0.4);
    }

    /* Expanders */
    .streamlit-expanderHeader {
        background: rgba(100,100,255,0.05);
        border-radius: 8px;
    }

    /* Code blocks */
    .stCodeBlock { border-radius: 8px; }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 8px 16px;
    }

    /* Info/Success/Warning boxes */
    .stAlert { border-radius: 10px; }

    /* Divider */
    hr { border-color: rgba(100,100,255,0.2) !important; }
</style>
""", unsafe_allow_html=True)

# ── Session state ────────────────────────────────────────────────────
if "indexed_codebase" not in st.session_state:
    st.session_state.indexed_codebase = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "active_page" not in st.session_state:
    st.session_state.active_page = "home"

# ── Sidebar navigation ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("## Navigation")

    if st.button("🏠 Home", use_container_width=True, key="nav_home"):
        st.session_state.active_page = "home"
    if st.button("📁 Index Repository", use_container_width=True, key="nav_index"):
        st.session_state.active_page = "index"
    if st.button("📤 Upload Files", use_container_width=True, key="nav_upload"):
        st.session_state.active_page = "upload"
    if st.button("💬 Chat", use_container_width=True, key="nav_chat"):
        st.session_state.active_page = "chat"
    if st.button("📊 Evaluation", use_container_width=True, key="nav_eval"):
        st.session_state.active_page = "eval"

    st.divider()

    # Status indicator
    idx = st.session_state.indexed_codebase
    if idx:
        st.success(f"**Indexed:** {idx.collection_name}")
        st.caption(f"{idx.file_count} files | {idx.chunk_count} chunks")
    else:
        st.warning("No codebase indexed")

    st.divider()
    st.caption("Built with Hybrid Search + RRF + Cross-Encoder Reranking")


# ══════════════════════════════════════════════════════════════════════
# PAGE: HOME
# ══════════════════════════════════════════════════════════════════════
def page_home():
    st.title("🐍 Agentic RAG Codebase Assistant")

    st.markdown("""
    An **agentic AI copilot** for Python codebases powered by state-of-the-art RAG techniques.
    """)

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("""
        ### 🔍 Hybrid Search
        - **Vector search** (semantic)
        - **BM25** (keyword/lexical)
        - **Symbol search** (metadata)
        - **RRF** fusion
        """)

    with col2:
        st.markdown("""
        ### 🧠 Smart Processing
        - **AST-aware chunking**
        - **Cross-encoder reranking**
        - **MMR diversity**
        - **Incremental indexing**
        """)

    with col3:
        st.markdown("""
        ### 🤖 Agentic Pipeline
        - Query classification
        - Tool-based retrieval
        - LLM answer generation
        - Source citations
        """)

    st.divider()

    st.markdown("""
    ### 🚀 Quick Start
    1. Click **📁 Index Repository** to index a Python codebase
    2. Then click **💬 Chat** to ask questions about the code
    """)

    # Quick index with sample repo
    st.divider()
    st.subheader("⚡ Quick Demo")

    if st.button("🎯 Index Sample Repository & Start Chatting", type="primary"):
        _do_index("data/repos/sample_python_repo", None, True, False, False)
        if st.session_state.indexed_codebase:
            st.session_state.active_page = "chat"
            st.rerun()


# ══════════════════════════════════════════════════════════════════════
# PAGE: INDEX REPOSITORY
# ══════════════════════════════════════════════════════════════════════
def _do_index(repo_path, collection_name, reset, use_reranker, use_llm):
    """Shared indexing logic."""
    with st.spinner("🔄 Indexing repository... This may take a minute."):
        try:
            from src.indexing.repo_indexer import index_repository

            start_time = time.time()
            indexed = index_repository(
                repo_path=repo_path,
                collection_name=collection_name or None,
                reset=reset,
                use_reranker=use_reranker,
                use_llm=use_llm,
            )
            elapsed = time.time() - start_time

            st.session_state.indexed_codebase = indexed
            st.session_state.chat_history = []

            st.success(f"Repository indexed successfully! ({elapsed:.1f}s)")

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📄 Files", indexed.file_count)
            with col2:
                st.metric("🧩 Chunks", indexed.chunk_count)
            with col3:
                st.metric("📦 Collection", indexed.collection_name)

        except Exception as exc:
            st.error(f"Indexing failed: {exc}")
            import traceback
            st.code(traceback.format_exc())


def page_index():
    st.title("📁 Index Repository")
    st.markdown("Scan, parse, chunk, embed, and index a Python codebase.")

    repo_path = st.text_input(
        "Repository path",
        value="data/repos/sample_python_repo",
        help="Enter the local path to a Python repository.",
    )

    col1, col2 = st.columns(2)
    with col1:
        collection_name = st.text_input(
            "Collection name (optional)",
            value="",
            help="Leave empty to auto-generate from repo name.",
        )
    with col2:
        reset = st.checkbox("Reset index", value=True,
                           help="Delete existing index before re-indexing")

    col3, col4 = st.columns(2)
    with col3:
        use_reranker = st.checkbox(
            "Enable cross-encoder reranking", value=False,
            help="Uses cross-encoder/ms-marco-MiniLM-L-6-v2 for precision reranking. "
                 "Slower but more accurate.",
        )
    with col4:
        use_llm = st.checkbox(
            "Enable LLM generation", value=False,
            help="Requires OPENAI_API_KEY in .env file. "
                 "Without this, raw retrieved context is shown.",
        )

    if st.button("🚀 Index Repository", type="primary"):
        if not repo_path.strip():
            st.warning("Please enter a repository path.")
        elif not Path(repo_path).exists():
            st.error(f"Path does not exist: {repo_path}")
        else:
            _do_index(repo_path, collection_name, reset, use_reranker, use_llm)


# ══════════════════════════════════════════════════════════════════════
# PAGE: UPLOAD FILES
# ══════════════════════════════════════════════════════════════════════
def page_upload():
    st.title("📤 Upload Files")
    st.markdown("Upload individual Python, Markdown, or text files to add to the index.")

    indexed = st.session_state.indexed_codebase
    if indexed is None:
        st.warning("⚠️ Please index a repository first (📁 Index Repository)")
        return

    uploaded_files = st.file_uploader(
        "Choose files",
        accept_multiple_files=True,
        type=["py", "md", "txt", "json", "yaml", "yml"],
    )

    if uploaded_files and st.button("📥 Upload & Index", type="primary"):
        for uploaded_file in uploaded_files:
            with st.spinner(f"Processing {uploaded_file.name}..."):
                try:
                    from src.ingestion.upload_handler import handle_upload
                    from src.indexing.upload_indexer import index_uploaded_file
                    from src.indexing.indexer import Indexer

                    saved_path = handle_upload(
                        filename=uploaded_file.name,
                        file_obj=uploaded_file,
                    )

                    indexer = Indexer(
                        vector_store=indexed.vector_store,
                        keyword_store=indexed.keyword_store,
                        metadata_store=indexed.metadata_store,
                        file_store=indexed.file_store,
                    )

                    chunks = index_uploaded_file(indexer, saved_path)
                    st.success(f"✅ {uploaded_file.name}: {len(chunks)} chunks indexed")

                except Exception as exc:
                    st.error(f"❌ {uploaded_file.name}: {exc}")


# ══════════════════════════════════════════════════════════════════════
# PAGE: CHAT
# ══════════════════════════════════════════════════════════════════════
def page_chat():
    st.title("💬 Chat with your Codebase")

    indexed = st.session_state.indexed_codebase
    if indexed is None:
        st.warning("⚠️ Please index a repository first.")
        if st.button("⚡ Quick Index Sample Repo", type="primary"):
            _do_index("data/repos/sample_python_repo", None, True, False, False)
            st.rerun()
        return

    # Info bar
    st.caption(
        f"**{indexed.collection_name}** | "
        f"{indexed.file_count} files | "
        f"{indexed.chunk_count} chunks"
    )

    # Example questions
    with st.expander("💡 Example Questions", expanded=False):
        example_cols = st.columns(2)
        examples = [
            "Where is create_user defined?",
            "What does UserService do?",
            "Where is create_user used?",
            "Find code related to password hashing",
            "Explain the validate_email function",
            "What classes are in models.py?",
        ]
        for i, ex in enumerate(examples):
            col = example_cols[i % 2]
            with col:
                if st.button(f"📌 {ex}", key=f"ex_{i}", use_container_width=True):
                    st.session_state["_pending_question"] = ex

    st.divider()

    # Display chat history
    for entry in st.session_state.chat_history:
        with st.chat_message("user"):
            st.write(entry["question"])

        with st.chat_message("assistant", avatar="🤖"):
            st.markdown(entry["answer"])

            # Metadata in columns
            meta_col1, meta_col2 = st.columns([1, 2])
            with meta_col1:
                st.caption(f"**Type:** `{entry.get('query_type', 'N/A')}`")
            with meta_col2:
                tools = entry.get("tools_used", [])
                if tools:
                    st.caption(f"**Tools:** {', '.join(f'`{t}`' for t in tools)}")

            # Sources
            citations = entry.get("citations", [])
            if citations:
                with st.expander(f"📌 {len(citations)} source(s)"):
                    for c in citations:
                        st.code(c, language=None)

    # Chat input
    pending = st.session_state.pop("_pending_question", None)
    question = st.chat_input("Ask about the codebase...") or pending

    if question:
        # Show user message
        with st.chat_message("user"):
            st.write(question)

        # Generate response
        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("🔍 Searching & analyzing..."):
                start_time = time.time()
                response = indexed.agent.invoke(question)
                elapsed = time.time() - start_time

            st.markdown(response.answer)

            # Metadata
            meta_col1, meta_col2, meta_col3 = st.columns(3)
            with meta_col1:
                st.caption(f"**Query type:** `{response.query_type}`")
            with meta_col2:
                st.caption(f"**Latency:** {elapsed:.2f}s")
            with meta_col3:
                if response.tools_used:
                    st.caption(f"**Tools:** {len(response.tools_used)}")

            # Tools used
            if response.tools_used:
                with st.expander("🔧 Tools Used"):
                    for tool in response.tools_used:
                        st.code(tool, language=None)

            # Sources / citations
            if response.citations:
                with st.expander(f"📌 {len(response.citations)} Source(s)"):
                    for citation in response.citations:
                        st.code(citation, language=None)

            # Token usage
            if response.token_usage:
                with st.expander("📊 Token Usage"):
                    st.json(response.token_usage)

        # Save to history
        st.session_state.chat_history.append({
            "question": question,
            "answer": response.answer,
            "query_type": response.query_type,
            "tools_used": response.tools_used,
            "citations": response.citations,
            "sources": response.sources,
        })


# ══════════════════════════════════════════════════════════════════════
# PAGE: EVALUATION
# ══════════════════════════════════════════════════════════════════════
def page_eval():
    st.title("📊 RAG Evaluation")

    indexed = st.session_state.indexed_codebase
    if indexed is None:
        st.warning("⚠️ Please index a repository first.")
        return

    st.markdown("Generate test cases from indexed symbols and measure retrieval quality.")

    col1, col2 = st.columns(2)
    with col1:
        num_cases = st.slider("Number of test cases", 3, 30, 10)
    with col2:
        st.metric("Indexed chunks", indexed.chunk_count)

    if st.button("🧪 Generate & Run Evaluation", type="primary"):
        with st.spinner("Generating test cases and running evaluation..."):
            try:
                from src.evaluation.testset_builder import build_testset
                from src.evaluation.eval_runner import EvalRunner

                cases = build_testset(
                    metadata_store=indexed.metadata_store,
                    num_cases=num_cases,
                )

                st.info(f"Generated {len(cases)} test cases")

                runner = EvalRunner(indexed.agent)
                results = runner.run(cases)

                # Compute averages
                all_metrics = [r.metrics for r in results]
                if all_metrics:
                    avg_metrics = {}
                    for key in all_metrics[0]:
                        values = [m.get(key, 0) for m in all_metrics]
                        avg_metrics[key] = sum(values) / len(values)

                    st.subheader("Average Metrics")
                    metric_cols = st.columns(len(avg_metrics))
                    for col, (name, value) in zip(metric_cols, avg_metrics.items()):
                        with col:
                            display_name = name.replace("_", " ").title()
                            st.metric(display_name, f"{value:.1%}")

                st.subheader("Detailed Results")
                for i, result in enumerate(results):
                    with st.expander(
                        f"{'✅' if result.metrics.get('retrieval_recall', 0) > 0.5 else '❌'} "
                        f"Case {i+1}: {result.question[:50]}..."
                    ):
                        st.markdown(f"**Question:** {result.question}")
                        st.markdown(f"**Generated Answer:**")
                        st.text(result.generated_answer[:300])
                        st.markdown(f"**Expected:** {result.expected_answer}")

                        if result.sources_retrieved:
                            st.markdown(f"**Retrieved sources:** {', '.join(result.sources_retrieved[:5])}")

                        st.json(result.metrics)

            except Exception as exc:
                st.error(f"Evaluation failed: {exc}")
                import traceback
                st.code(traceback.format_exc())


# ══════════════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════════════
page_map = {
    "home": page_home,
    "index": page_index,
    "upload": page_upload,
    "chat": page_chat,
    "eval": page_eval,
}

page_fn = page_map.get(st.session_state.active_page, page_home)
page_fn()