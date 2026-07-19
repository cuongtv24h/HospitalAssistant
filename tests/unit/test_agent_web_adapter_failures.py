from types import SimpleNamespace
from unittest.mock import MagicMock

from apps.api.ai.orchestrator.core import web_adapter


def test_execution_budget_failure_is_not_reported_as_answered(monkeypatch):
    adapter = web_adapter.AgentInformationAssistanceAdapter.__new__(
        web_adapter.AgentInformationAssistanceAdapter
    )
    adapter._llm_configs = []
    adapter._embedder = MagicMock()
    adapter._session_service = MagicMock()
    adapter._session_service.load_booking_draft.return_value = None
    adapter._appointment_tools = MagicMock()

    monkeypatch.setattr(
        web_adapter.agent_graph,
        "get_state",
        lambda config: SimpleNamespace(values={}),
    )
    monkeypatch.setattr(
        web_adapter.agent_graph,
        "invoke",
        lambda state, config: {
            **state,
            "safety_result": {"risk": "LOW"},
            "final_response": "Xin lỗi, thời gian thực thi của tác vụ đã vượt quá giới hạn cho phép.",
            "degradation_status": {
                "terminal_failure": "execution_budget_exhausted"
            },
            "citations": [],
        },
    )

    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.cursor.return_value.__enter__.return_value = MagicMock()
    monkeypatch.setattr(web_adapter.psycopg, "connect", lambda *args, **kwargs: connection)
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/hospital")

    response = adapter.execute(
        SimpleNamespace(session_id="session-budget", message="BHYT thế nào?")
    ).to_dict()

    assert response["outcome"] == "fallback"
    assert response["explainability"]["fallback_reason"] == "execution_budget_exhausted"
    assert response["error"]["error"]["code"] == "TOOL_TIMEOUT"
    assert response["error"]["error"]["retryable"] is True


def test_scope_refusal_is_exposed_as_refused_without_citations(monkeypatch):
    adapter = web_adapter.AgentInformationAssistanceAdapter.__new__(
        web_adapter.AgentInformationAssistanceAdapter
    )
    adapter._llm_configs = []
    adapter._embedder = MagicMock()
    adapter._session_service = MagicMock()
    adapter._session_service.load_booking_draft.return_value = None
    adapter._appointment_tools = MagicMock()

    monkeypatch.setattr(
        web_adapter.agent_graph,
        "get_state",
        lambda config: SimpleNamespace(values={}),
    )
    monkeypatch.setattr(
        web_adapter.agent_graph,
        "invoke",
        lambda state, config: {
            **state,
            "safety_result": {"risk": "LOW"},
            "final_response": "Ngoài phạm vi",
            "degradation_status": {"scope_refused": True},
            "citations": [],
        },
    )

    connection = MagicMock()
    connection.__enter__.return_value = connection
    connection.cursor.return_value.__enter__.return_value = MagicMock()
    monkeypatch.setattr(web_adapter.psycopg, "connect", lambda *args, **kwargs: connection)
    monkeypatch.setenv("DATABASE_URL", "postgresql://localhost/hospital")

    response = adapter.execute(
        SimpleNamespace(session_id="session-scope", message="Viết code Python")
    ).to_dict()

    assert response["outcome"] == "refused"
    assert response["citations"] == []
    assert response["error"]["error"]["code"] == "OUT_OF_SCOPE"
    assert response["error"]["error"]["retryable"] is False
