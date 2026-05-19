import streamlit as st

from src.settings import RETRIEVAL_MODE_ACCURATE, RETRIEVAL_MODE_FAST
from src.constants import (
    REPO_SOURCE_GITHUB,
    REPO_SOURCE_ZIP_UPLOAD,
)
from src.ingestion.zip_ingestion import ingest_zip_bytes
from src.ingestion.github_ingestion import clone_github_repo
from src.indexer import build_codebase_agent, load_existing_codebase_agent
from src.storage.repository_lifecycle import (
    cleanup_temporary_repository,
    list_persistent_repositories,
)


def cleanup_active_temporary_repo() -> None:
    active_temp_repo_id = st.session_state.get("active_temp_repo_id")

    if not active_temp_repo_id:
        return

    deleted = cleanup_temporary_repository(active_temp_repo_id)

    if deleted:
        st.session_state.active_temp_repo_id = None


st.set_page_config(
    page_title="Agentic RAG Copilot for Python Repositories",
    page_icon="🐍",
    layout="wide",
)


st.title("🐍 Agentic RAG Copilot for Python Repositories")

st.markdown(
    """
A read-only AI copilot for Python repositories.

It can load already-indexed company repositories, or temporarily index a public
GitHub repository / uploaded ZIP file for the current session.
"""
)


if "indexed_codebase" not in st.session_state:
    st.session_state.indexed_codebase = None

if "active_temp_repo_id" not in st.session_state:
    st.session_state.active_temp_repo_id = None

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


with st.sidebar:
    st.header("Repository")

    repo_mode = st.radio(
        "Repository mode",
        options=[
            "Company Repo",
            "GitHub URL",
            "ZIP Upload",
        ],
        index=0,
    )

    index_button = False
    load_existing_button = False
    selected_existing_repo_id = None

    if repo_mode == "Company Repo":
        persistent_repos = list_persistent_repositories()

        if not persistent_repos:
            st.warning(
                "No indexed company repositories found. "
                "Run the company repo indexing script first."
            )
        else:
            repo_options = {
                f"{repo.repo_name} | {repo.repo_id} | chunks={repo.chunk_count}": repo.repo_id
                for repo in persistent_repos
            }

            selected_label = st.selectbox(
                "Company repository",
                options=list(repo_options.keys()),
            )

            selected_existing_repo_id = repo_options[selected_label]

        st.caption(
            "Company repositories are loaded from PostgreSQL + Qdrant. "
            "They are indexed or re-indexed with an internal script, not from this UI."
        )

    elif repo_mode == "GitHub URL":
        github_url = st.text_input(
            "GitHub public repository URL",
            placeholder="https://github.com/owner/repo",
        )

        github_branch = st.text_input(
            "Branch (optional)",
            value="",
            help="Leave empty to use the default branch.",
        )

        st.caption(
            "Only public GitHub repositories are supported. "
            "This repository will be indexed temporarily."
        )

    elif repo_mode == "ZIP Upload":
        uploaded_zip = st.file_uploader(
            "Upload a Python repository ZIP file",
            type=["zip"],
        )

        st.caption(
            "Upload a .zip file containing a Python repository. "
            "The extracted files are stored temporarily in data/runtime/uploads/."
        )

    retrieval_mode_label = st.radio(
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

    reset_collection = True
    use_llm_router = True
    use_llm = True

    if repo_mode == "Company Repo":
        load_existing_button = st.button("Load repository", type="primary")
    else:
        index_button = st.button("Index temporary repository", type="primary")

    if load_existing_button:
        if not selected_existing_repo_id:
            st.error("Please select an indexed company repository.")
            st.stop()

        try:
            cleanup_active_temporary_repo()

            with st.spinner("Loading indexed repository from database..."):
                indexed = load_existing_codebase_agent(
                    repo_id=selected_existing_repo_id,
                    retrieval_mode=retrieval_mode,
                    use_llm=use_llm,
                    use_llm_router=use_llm_router,
                )

            st.session_state.indexed_codebase = indexed
            st.session_state.chat_history = []
            st.session_state.active_temp_repo_id = None

            st.success("Repository loaded successfully!")
            st.write(f"Repo ID: {indexed.repo_id}")
            st.write(f"Source type: {indexed.source_type}")
            st.write(f"Persistent: {indexed.is_persistent}")
            st.write(f"Python files indexed: {indexed.file_count}")
            st.write(f"Documentation files indexed: {indexed.doc_count}")
            st.write(f"Other files ignored: {indexed.ignored_file_count}")
            st.write(f"Total chunks: {indexed.chunk_count}")
            st.write(f"Collection: {indexed.collection_name}")
            st.write(f"Retrieval mode: {retrieval_mode}")

        except Exception as exc:
            st.error(f"Load failed: {exc}")

    if index_button:
        try:
            github_url_for_metadata = None
            branch_for_metadata = None
            commit_hash_for_metadata = None

            if repo_mode == "GitHub URL":
                if not github_url.strip():
                    st.error("Please enter a GitHub repository URL.")
                    st.stop()

                cleanup_active_temporary_repo()

                with st.spinner("Cloning GitHub repository..."):
                    ingested_repo = clone_github_repo(
                        github_url=github_url,
                        branch=github_branch.strip() or None,
                    )

                repo_path = str(ingested_repo.local_path)
                collection_name = ingested_repo.repo_id

                repo_id = ingested_repo.repo_id
                repo_name = ingested_repo.name
                source_type = REPO_SOURCE_GITHUB
                is_persistent = False

                github_url_for_metadata = ingested_repo.github_url
                branch_for_metadata = ingested_repo.branch
                commit_hash_for_metadata = ingested_repo.commit_hash

            elif repo_mode == "ZIP Upload":
                if uploaded_zip is None:
                    st.error("Please upload a ZIP file.")
                    st.stop()

                cleanup_active_temporary_repo()

                with st.spinner("Extracting ZIP repository..."):
                    ingested_repo = ingest_zip_bytes(
                        filename=uploaded_zip.name,
                        zip_bytes=uploaded_zip.getvalue(),
                    )

                repo_path = str(ingested_repo.local_path)
                collection_name = ingested_repo.repo_id

                repo_id = ingested_repo.repo_id
                repo_name = ingested_repo.name
                source_type = REPO_SOURCE_ZIP_UPLOAD
                is_persistent = False

            else:
                st.error("This mode does not support temporary indexing.")
                st.stop()

            with st.spinner("Indexing temporary repository..."):
                indexed = build_codebase_agent(
                    repo_path=repo_path,
                    collection_name=collection_name,
                    reset_collection=reset_collection,
                    use_llm=use_llm,
                    retrieval_mode=retrieval_mode,
                    use_llm_router=use_llm_router,
                    repo_id=repo_id,
                    repo_name=repo_name,
                    source_type=source_type,
                    is_persistent=is_persistent,
                    local_path=repo_path,
                    github_url=github_url_for_metadata,
                    branch=branch_for_metadata,
                    commit_hash=commit_hash_for_metadata,
                    save_metadata=True,
                )

            st.session_state.indexed_codebase = indexed
            st.session_state.chat_history = []

            if indexed.source_type in {REPO_SOURCE_GITHUB, REPO_SOURCE_ZIP_UPLOAD}:
                st.session_state.active_temp_repo_id = indexed.repo_id
            else:
                st.session_state.active_temp_repo_id = None

            st.success("Temporary repository indexed successfully!")
            st.write(f"Repo ID: {indexed.repo_id}")
            st.write(f"Source type: {indexed.source_type}")
            st.write(f"Persistent: {indexed.is_persistent}")
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
- What does this project do?
- Where is `ModelEvaluator` defined?
- What does `ModelEvaluator` do?
- Who calls `TaskService.create_task`?
- `ModelEvaluator` được tạo ở đâu, mục đích code là gì?
        """
    )


indexed = st.session_state.indexed_codebase

if indexed is None:
    st.info("Load a company repository or index a temporary repository from the sidebar to start.")
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

st.caption(
    f"Repo ID: `{indexed.repo_id}` | "
    f"Source: `{indexed.source_type}` | "
    f"Collection: `{indexed.collection_name}` | "
    f"Retrieval mode: `{indexed.tools.retrieval_mode}`"
)


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

    st.markdown("### Question")
    st.write(response.question)

    st.markdown("### Answer")

    query_plan = response.raw_results.get("query_plan", {})

    if query_plan.get("router") == "fallback_rule":
        st.warning(
            "LLM Query Router is currently unavailable or rate-limited. "
            "The system is using the fallback rule-based router."
        )

    if response.raw_results.get("llm_enabled") is False:
        st.warning(
            "LLM answer generation is currently unavailable or rate-limited. "
            "Showing the fallback tool/retrieval-based answer."
        )

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
