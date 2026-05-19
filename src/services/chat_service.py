"""Chat-oriented service functions for answering repository questions."""

from src.agent_core.response_models import AgentResponse
from src.observability.logger import get_logger
from src.services.session_store import SessionStore, get_default_session_store


logger = get_logger(__name__)


def answer_question(
    session_id: str,
    question: str,
    *,
    session_store: SessionStore | None = None,
) -> AgentResponse:
    """Answer a question against the repository bound to a session."""
    store = session_store or get_default_session_store()
    cleaned_question = question.strip()

    if not cleaned_question:
        raise ValueError("Question must not be empty.")

    indexed_codebase = store.get_indexed_codebase(session_id)

    if indexed_codebase is None:
        logger.warning(
            "Chat request failed because no repository is loaded for session",
            extra={
                "session_id": session_id,
            },
        )

        raise ValueError(
            "No repository is loaded for this session. "
            "Load a company repository or index a temporary repository first."
        )

    logger.info(
        "Answering question",
        extra={
            "session_id": session_id,
            "repo_id": indexed_codebase.repo_id,
            "source_type": indexed_codebase.source_type,
            "retrieval_mode": indexed_codebase.tools.retrieval_mode,
            "question_length": len(cleaned_question),
        },
    )

    try:
        response = indexed_codebase.agent.answer(cleaned_question)
        store.append_chat_response(session_id, response)

        logger.info(
            "Question answered",
            extra={
                "session_id": session_id,
                "repo_id": indexed_codebase.repo_id,
                "query_type": response.query_type,
                "source_count": len(response.sources),
                "tool_count": len(response.tools_used),
                "llm_enabled": response.raw_results.get("llm_enabled"),
                "router": response.raw_results.get("router")
                or response.raw_results.get("query_plan", {}).get("router"),
            },
        )

        return response

    except Exception:
        logger.exception(
            "Question answering failed",
            extra={
                "session_id": session_id,
                "repo_id": indexed_codebase.repo_id,
            },
        )
        raise
