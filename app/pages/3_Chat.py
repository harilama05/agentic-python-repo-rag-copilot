"""
💬 Chat — Streamlit page for asking questions about the codebase.
"""

import streamlit as st

st.set_page_config(page_title="Chat", page_icon="💬", layout="wide")
st.title("💬 Chat with your Codebase")

# Initialize chat history
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

indexed = st.session_state.get("indexed_codebase")

if indexed is None:
    st.warning("⚠️ Please index a repository first (📁 Index Repository).")
    st.stop()

st.markdown(f"**Indexed:** {indexed.collection_name} "
            f"({indexed.file_count} files, {indexed.chunk_count} chunks)")

# Example questions
with st.expander("💡 Example Questions"):
    st.markdown("""
    - Where is `create_user` defined?
    - Where is `UserService` used?
    - What does `build_code_chunks` do?
    - Find code related to authentication
    - Explain the `scan_repository` function
    """)

# Chat input
question = st.chat_input("Ask about the codebase...")

if question:
    # Display user message
    with st.chat_message("user"):
        st.write(question)

    # Generate response
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = indexed.agent.invoke(question)

        st.markdown(response.answer)

        # Show metadata in expanders
        with st.expander("🔧 Tools Used"):
            for tool in response.tools_used:
                st.code(tool)

        with st.expander("📌 Sources"):
            if response.citations:
                for citation in response.citations:
                    st.write(f"- `{citation}`")
            else:
                st.write("No sources found.")

        if response.token_usage:
            with st.expander("📊 Token Usage"):
                st.json(response.token_usage)

    # Save to history
    st.session_state.chat_history.append({
        "question": question,
        "response": response,
    })

# Show history
if st.session_state.chat_history:
    st.divider()
    st.subheader("📜 Conversation History")

    for i, entry in enumerate(reversed(st.session_state.chat_history[:-1])):
        with st.expander(f"Q: {entry['question'][:80]}..."):
            st.markdown(entry["response"].answer)
