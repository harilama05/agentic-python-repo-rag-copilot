import streamlit as st

from src.indexer import build_codebase_agent


st.set_page_config(
    page_title="Agentic RAG Copilot for Python Codebases",
    page_icon="🐍",
    layout="wide",
)


st.title("🐍 Agentic RAG Copilot for Python Codebases")

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

    repo_path = st.text_input(
        "Python repo path",
        value="examples/sample_python_repo",
        help="Enter a local path to a Python repository.",
    )

    collection_name = st.text_input(
        "Collection name",
        value="sample_python_repo",
    )

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
                )

                st.session_state.indexed_codebase = indexed
                st.session_state.chat_history = []

                st.success("Repository indexed successfully!")
                st.write(f"Files: {indexed.file_count}")
                st.write(f"Chunks: {indexed.chunk_count}")
                st.write(f"Collection: {indexed.collection_name}")

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

col1, col2, col3 = st.columns(3)

with col1:
    st.metric("Python files", indexed.file_count)

with col2:
    st.metric("Code chunks", indexed.chunk_count)

with col3:
    st.metric("Collection", indexed.collection_name)


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
        for source in response.sources:
            relative_path = source.get("relative_path")
            line_start = source.get("line_start")
            line_end = source.get("line_end")

            if line_start == line_end:
                citation = f"{relative_path}:{line_start}"
            else:
                citation = f"{relative_path}:{line_start}-{line_end}"

            st.write(f"- `{citation}`")
    else:
        st.write("No sources found.")

    with st.expander("Raw Results"):
        st.json(response.raw_results)