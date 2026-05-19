"""In-memory session store for UI-agnostic runtime state.

This store replaces direct reliance on `st.session_state` for API flows while
remaining simple enough for local single-process use.
"""

from dataclasses import dataclass, field
from threading import RLock
from typing import Dict, List, Optional

from src.agent_core.response_models import AgentResponse
from src.indexing.models import IndexedCodebase


@dataclass
class SessionState:
    """Mutable per-session runtime state."""

    session_id: str
    indexed_codebase: Optional[IndexedCodebase] = None
    active_temp_repo_id: Optional[str] = None
    chat_history: List[AgentResponse] = field(default_factory=list)


class SessionStore:
    """Thread-safe in-memory session store for API and service workflows."""

    def __init__(self):
        self._sessions: Dict[str, SessionState] = {}
        self._lock = RLock()

    def get_or_create_session(self, session_id: str) -> SessionState:
        """Return an existing session or create a new one."""
        with self._lock:
            session = self._sessions.get(session_id)

            if session is None:
                session = SessionState(session_id=session_id)
                self._sessions[session_id] = session

            return session

    def get_indexed_codebase(self, session_id: str) -> Optional[IndexedCodebase]:
        """Return the indexed codebase for a session, if any."""
        return self.get_or_create_session(session_id).indexed_codebase

    def set_indexed_codebase(
        self,
        session_id: str,
        indexed_codebase: IndexedCodebase,
    ) -> SessionState:
        """Set the active indexed codebase for a session."""
        session = self.get_or_create_session(session_id)
        session.indexed_codebase = indexed_codebase
        return session

    def get_active_temp_repo_id(self, session_id: str) -> Optional[str]:
        """Return the active temporary repository id for a session."""
        return self.get_or_create_session(session_id).active_temp_repo_id

    def set_active_temp_repo_id(self, session_id: str, repo_id: Optional[str]) -> SessionState:
        """Set or clear the active temporary repository id for a session."""
        session = self.get_or_create_session(session_id)
        session.active_temp_repo_id = repo_id
        return session

    def clear_chat_history(self, session_id: str) -> SessionState:
        """Clear accumulated chat history for a session."""
        session = self.get_or_create_session(session_id)
        session.chat_history = []
        return session

    def append_chat_response(self, session_id: str, response: AgentResponse) -> SessionState:
        """Append one agent response to a session's chat history."""
        session = self.get_or_create_session(session_id)
        session.chat_history.append(response)
        return session

    def get_chat_history(self, session_id: str) -> List[AgentResponse]:
        """Return the session's chat history."""
        return list(self.get_or_create_session(session_id).chat_history)

    def clear_session(self, session_id: str) -> None:
        """Delete a session from the in-memory store."""
        with self._lock:
            self._sessions.pop(session_id, None)


_DEFAULT_SESSION_STORE = SessionStore()


def get_default_session_store() -> SessionStore:
    """Return the default process-local session store."""
    return _DEFAULT_SESSION_STORE
