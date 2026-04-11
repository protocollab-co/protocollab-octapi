from __future__ import annotations

from dataclasses import dataclass

from app.models import SessionState


@dataclass
class SessionStoreError(Exception):
    code: str
    message: str


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}

    def create(self, session: SessionState) -> None:
        self._sessions[session.session_id] = session

    def get(self, session_id: str) -> SessionState:
        session = self._sessions.get(session_id)
        if session is None:
            raise SessionStoreError(code="not_found", message="Session not found.")
        return session

    def update(self, session: SessionState) -> None:
        self._sessions[session.session_id] = session

    def assert_not_exhausted(self, session: SessionState) -> None:
        if session.attempts >= session.max_attempts:
            raise SessionStoreError(
                code="attempt_limit_reached",
                message=f"Session exhausted: max attempts is {session.max_attempts}.",
            )

    def delete(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
