import streamlit as st

from src.indexer import build_codebase_agent

from src.settings import RETRIEVAL_MODE_ACCURATE, RETRIEVAL_MODE_FAST

st.set_page_config(
    page_title="Agentic RAG Copilot for Python Repositories",
    page_icon="🐍",
    layout="wide",
)


st.title("🐍 Agentic RAG Copilot for Python Repositories")

st.markdown(
    """
A read-only AI copilot for Python repositories.

It scans a Python repo, chunks code using AST, indexes functions/classes/methods,
and answers codebase questions using agent tools.
"""
)


if "indexed_codebase" not in st.session_state:
    st.session_state.indexed_codebase = None

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


with st.sidebar:
    st.header("Repository Indexing")

    repo_mode = st.radio(
        "Repository mode",
        options=["Custom Repo", "Company Repo"],
        index=0,
    )

    if repo_mode == "Custom Repo":
        repo_path = st.text_input(
            "Python repo path",
            value="examples/sample_python_repo",
            help="Enter a local path to a Python repository.",
        )

        collection_name = st.text_input(
            "Collection name",
            value="custom_repo",
        )

    else:
        from src.company_repos import get_company_repo_options, get_company_repo

        company_options = get_company_repo_options()
        selected_name = st.selectbox(
            "Select company repo",
            options=list(company_options.keys()),
        )

        selected_repo_id = company_options[selected_name]
        selected_repo = get_company_repo(selected_repo_id)

        st.caption(selected_repo.description)

        repo_path = str(selected_repo.path)
        collection_name = selected_repo.repo_id

        st.write(f"Repo path: `{repo_path}`")

    retrieval_mode_label = st.selectbox(
        "Retrieval mode",
        options=[
            "Fast - Hybrid retrieval",
            "Accurate - Cross-Encoder reranking",
        ],
        help=(
            "Fast mode uses vector search + BM25 + keyword/symbol scoring. "
            "Accurate mode reranks retrieved candidates with a Cross-Encoder, "
            "which can improve relevance but is slower."
        ),
    )

    if retrieval_mode_label.startswith("Accurate"):
        retrieval_mode = RETRIEVAL_MODE_ACCURATE
    else:
        retrieval_mode = RETRIEVAL_MODE_FAST

    reset_collection = st.checkbox(
        "Reset collection before indexing",
        value=True,
    )
    use_llm = st.checkbox(
        "Use LLM grounded answer generation",
        value=False,
        help="Requires GEMINI_API_KEY in .env",
    )

    index_button = st.button("Index repository", type="primary")

    if index_button:
        with st.spinner("Indexing repository..."):
            try:
                indexed = build_codebase_agent(
                    repo_path=repo_path,
                    collection_name=collection_name,
                    reset_collection=reset_collection,
                    use_llm=use_llm,
                    retrieval_mode=retrieval_mode,
                )

                st.session_state.indexed_codebase = indexed
                st.session_state.chat_history = []

                st.success("Repository indexed successfully!")
                st.write(f"Python files indexed: {indexed.file_count}")
                st.write(f"Documentation files indexed: {indexed.doc_count}")
                st.write(f"Other files ignored: {indexed.ignored_file_count}")
                st.write(f"Total chunks: {indexed.chunk_count}")
                st.write(f"Collection: {indexed.collection_name}")
                st.write(f"Retrieval mode: {retrieval_mode}")

            except Exception as exc:
                st.error(f"Indexing failed: {exc}")

    st.divider()

    st.header("Example Questions")
    st.markdown(
        """
- Where is create_user implemented?
- Where is create_user used?
- What does UserService do?
- Find code related to user creation
        """
    )


indexed = st.session_state.indexed_codebase

if indexed is None:
    st.info("Index a Python repository from the sidebar to start.")
    st.stop()


st.subheader("Indexed Repository")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Python files", indexed.file_count)

with col2:
    st.metric("Docs", indexed.doc_count)

with col3:
    st.metric("Ignored files", indexed.ignored_file_count)

with col4:
    st.metric("Total chunks", indexed.chunk_count)

st.caption(f"Collection: {indexed.collection_name}")
st.caption(f"Retrieval mode: `{indexed.tools.retrieval_mode}`")


st.divider()

st.subheader("Ask about the codebase")

question = st.text_input(
    "Question",
    placeholder="Example: Where is create_user used?",
)

ask_button = st.button("Ask", type="primary")

if ask_button and question.strip():
    with st.spinner("Agent is working..."):
        response = indexed.agent.answer(question.strip())

    st.session_state.chat_history.append(response)


for response in reversed(st.session_state.chat_history):
    st.markdown("---")

    st.markdown(f"### Question")
    st.write(response.question)

    st.markdown("### Answer")
    st.markdown(response.answer)

    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("### Query Type")
        st.code(response.query_type)

    with col2:
        st.markdown("### Tools Used")
        for tool in response.tools_used:
            st.code(tool)

    st.markdown("### Sources")

    if response.sources:
        for idx, source in enumerate(response.sources, start=1):
            relative_path = source.get("relative_path", "")
            relative_path = relative_path.replace("\\", "/")

            line_start = source.get("line_start")
            line_end = source.get("line_end")

            symbol = source.get("symbol")
            source_type = source.get("type")

            if line_start == line_end:
                citation = f"{relative_path}:{line_start}"
            else:
                citation = f"{relative_path}:{line_start}-{line_end}"

            if symbol:
                label = f"`{citation}` — `{symbol}`"
            elif source_type:
                label = f"`{citation}` — {source_type}"
            else:
                label = f"`{citation}`"

            st.markdown(f"**{idx}. {label}**")

            try:
                file_content = indexed.tools.read_file(
                    file_path=relative_path,
                    start_line=line_start,
                    end_line=line_end,
                    context_lines=0,
                )

                with st.expander("View source excerpt"):
                    language = "python"

                    if str(relative_path).lower().endswith((".md", ".markdown")):
                        language = "markdown"

                    st.code(file_content["content"], language=language)

            except Exception:
                with st.expander("View source metadata"):
                    st.json(source)

    else:
        st.write("No sources found.")

    with st.expander("Raw Results"):
        st.json(response.raw_results)