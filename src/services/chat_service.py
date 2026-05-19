"""Chat-oriented service functions for answering repository questions."""

from src.agent_core.response_models import AgentResponse
from src.services.session_store import SessionStore, get_default_session_store


def answer_question(
    session_id: str,
    question: str,
    *,
    session_store: SessionStore | None = None,
) -> AgentResponse:
    """Answer a question against the repository bound to a session."""
    store = session_store or get_default_session_store()
    indexed_codebase = store.get_indexed_codebase(session_id)

    if indexed_codebase is None:
        raise ValueError(
            "No repository is loaded for this session. "
            "Load a company repository or index a temporary repository first."
        )

    response = indexed_codebase.agent.answer(question.strip())
    store.append_chat_response(session_id, response)
    return response
