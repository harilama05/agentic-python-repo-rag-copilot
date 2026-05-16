"""
📤 Upload Files — Streamlit page for uploading and indexing files.
"""

import streamlit as st

st.set_page_config(page_title="Upload Files", page_icon="📤", layout="wide")
st.title("📤 Upload Files")

st.markdown("Upload Python, Markdown, or text files to add to the index.")

uploaded_files = st.file_uploader(
    "Choose files",
    accept_multiple_files=True,
    type=["py", "md", "txt", "json", "yaml", "yml"],
)

if uploaded_files and st.button("📥 Upload & Index", type="primary"):
    indexed = st.session_state.get("indexed_codebase")

    if indexed is None:
        st.warning("⚠️ Please index a repository first (📁 Index Repository).")
    else:
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

                    st.success(
                        f"✅ {uploaded_file.name}: {len(chunks)} chunks indexed"
                    )

                except Exception as exc:
                    st.error(f"❌ {uploaded_file.name}: {exc}")
