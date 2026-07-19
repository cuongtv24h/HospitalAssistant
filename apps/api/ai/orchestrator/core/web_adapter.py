"""Adapter exposing the LangGraph hospital agent through the web capability API."""

from __future__ import annotations

import os
import time
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List

import psycopg
from apps.api.foundation.knowledge.ingestion.persistence.postgres import psycopg_connection_url
from langchain_core.messages import HumanMessage

from apps.api.ai.orchestrator.core.agent import agent_graph
from apps.api.core.runtime_dependencies import create_jina_query_embedding_provider
from apps.api.foundation.appointments.tools.service import create_appointment_tools
from apps.api.foundation.appointments.tools.service import (
    GetAvailableSlotsInput,
    GetDoctorListInput,
    GetSpecialtyListInput,
)
from apps.api.foundation.operational_repository import OperationalRepository
from apps.api.foundation.session.service import SessionService
from apps.api.ai.providers.llm_provider import get_agent_llm_configs
from packages.contracts import (
    AI_PROVIDER_UNAVAILABLE,
    CATEGORY_AI,
    CATEGORY_SAFETY,
    CATEGORY_TOOL,
    OUT_OF_SCOPE,
    TOOL_TIMEOUT,
    make_error_envelope,
)

logger = logging.getLogger("uvicorn.error")


class _QueryEmbedder:
    def __init__(self) -> None:
        self._embed = create_jina_query_embedding_provider()

    def embed_query(self, query: str) -> List[float]:
        return self._embed(query)


@dataclass(frozen=True)
class AgentInformationResponse:
    result: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.result)


class AgentInformationAssistanceAdapter:
    """Translate the PC-01 request DTO to the project's LangGraph state."""

    def __init__(self, *, appointment_tools: Any = None) -> None:
        if not os.environ.get("DATABASE_URL"):
            raise ValueError("DATABASE_URL is required for the hospital agent")
        self._llm_configs = get_agent_llm_configs()
        self._embedder = _QueryEmbedder()
        repository = OperationalRepository(os.environ["DATABASE_URL"])
        self._session_service = SessionService(repository=repository)
        self._appointment_tools = appointment_tools or create_appointment_tools()

    @staticmethod
    def _initial_state() -> Dict[str, Any]:
        return {
            "messages": [],
            "safety_result": None,
            "clarification_count": 0,
            "observations": [],
            "appointment_observations": [],
            "citations": [],
            "call_fingerprints": [],
            "max_tool_calls": int(os.environ.get("AGENT_MAX_TOOL_CALLS", "5")),
            "call_count": 0,
            "elapsed_time_seconds": 0.0,
            "deadline_timestamp": 0.0,
            "final_response": None,
            "degradation_status": {},
            "repair_attempted": False,
            "grounding_retry_reasons": [],
            "booking_result": None,
            "booking_flow_ref": None,
            "booking_flow_version": 0,
            "booking_choices": [],
            "booking_step": None,
            "force_search_required": False,
            "current_action": None,
        }

    def _hydrate_canonical_booking(self, state: Dict[str, Any], session_id: str) -> None:
        """Restore durable booking state independently of LangGraph memory."""
        draft = self._session_service.load_booking_draft(session_id)
        if draft is None or draft.status in {"created", "cancelled", "expired"}:
            return
        state["booking_flow_ref"] = draft.flow_id
        state["booking_flow_version"] = draft.version
        state["booking_step"] = draft.current_step
        try:
            if draft.current_step == "specialty":
                state["booking_choices"] = self._appointment_tools.get_specialty_list(
                    GetSpecialtyListInput(active_only=True)
                ).specialties
            elif draft.current_step == "doctor" and draft.specialty_id:
                state["booking_choices"] = self._appointment_tools.get_doctor_list(
                    GetDoctorListInput(specialty_id=draft.specialty_id, active_only=True)
                ).doctors
            elif draft.current_step == "slot" and draft.doctor_id:
                state["booking_choices"] = self._appointment_tools.get_available_slots(
                    GetAvailableSlotsInput(doctor_id=draft.doctor_id)
                ).slots
        except Exception:
            # Canonical state remains usable even when a read-only choice refresh
            # is temporarily unavailable.
            state["booking_choices"] = []

    def execute(self, request: Any) -> AgentInformationResponse:
        request_started_at = time.monotonic()
        logger.info("agent_trace %s", json.dumps({
            "event": "request.start",
            "session_id": request.session_id,
            "capability": "information_assistance",
        }))
        config = {
            "configurable": {
                "thread_id": request.session_id,
                # Generic OpenAI-compatible runtime configuration. This can
                # point at Groq, Gemini or OpenRouter in the configured
                # fallback order; it is never returned to a client.
                "llm_candidates": self._llm_configs,
                "jina_api_key": os.environ.get("JINA_API_KEY"),
                "embedder": self._embedder,
                "top_n": int(os.environ.get("RAG_TOP_N", "5")),
                "session_service": self._session_service,
                "appointment_tools": self._appointment_tools,
                "current_user_message": request.message,
            }
        }
        snapshot = agent_graph.get_state(config)
        state = dict(snapshot.values) if snapshot.values else self._initial_state()
        self._hydrate_canonical_booking(state, request.session_id)
        state["messages"] = list(state.get("messages", [])) + [HumanMessage(content=request.message)]
        state["final_response"] = None
        state["deadline_timestamp"] = time.time() + float(
            os.environ.get("AGENT_EXECUTION_TIMEOUT_SECONDS", "60")
        )

        database_started_at = time.monotonic()
        with psycopg.connect(
            psycopg_connection_url(os.environ["DATABASE_URL"]), prepare_threshold=None
        ) as connection:
            with connection.cursor() as cursor:
                logger.info("agent_trace %s", json.dumps({
                    "event": "database.connected",
                    "session_id": request.session_id,
                    "elapsed_ms": round((time.monotonic() - database_started_at) * 1000, 2),
                }))
                config["configurable"]["db_cursor"] = cursor
                state = agent_graph.invoke(state, config)

        risk = (state.get("safety_result") or {}).get("risk", "LOW")
        answer = state.get("final_response") or "Tôi không có đủ thông tin để trả lời câu hỏi này."
        booking_result = state.get("booking_result") or {}
        current_action = state.get("current_action")
        terminal_failure = (state.get("degradation_status") or {}).get("terminal_failure")
        scope_refused = bool((state.get("degradation_status") or {}).get("scope_refused"))
        active_booking_turn = bool(state.get("booking_step")) and current_action in {
            "start_booking", "advance_booking", "clarify"
        }
        if risk == "HIGH":
            outcome = "emergency_rerouted"
        elif risk == "CAUTION":
            outcome = "clarification_required"
        elif scope_refused:
            outcome = "refused"
        elif booking_result or active_booking_turn:
            outcome = "appointment_pending" if booking_result.get("appointment") else "booking_in_progress"
        elif terminal_failure or answer == "Tôi không có đủ thông tin để trả lời câu hỏi này.":
            outcome = "fallback"
        else:
            outcome = "answered"

        is_booking = bool(booking_result) or active_booking_turn
        citations = []
        seen = set()
        if not is_booking:
            for citation in state.get("citations", []):
                sid = str(citation.get("source_id") or "")
                if not sid or sid in seen:
                    continue
                seen.add(sid)

                kind = citation.get("source_kind") or ("web" if citation.get("url") or citation.get("source_url") else "document")
                title = citation.get("title") or citation.get("display_name") or sid
                display_name = citation.get("display_name") or title
                url = citation.get("url") or citation.get("source_url")
                if url and not (str(url).startswith("http://") or str(url).startswith("https://")):
                    url = None

                item = {
                    "source_id": sid,
                    "source_kind": kind,
                    "title": title,
                    "display_name": display_name,
                    "excerpt": citation.get("matched_text") or citation.get("excerpt") or "",
                    "version": citation.get("version") or "1.0",
                    "publisher": citation.get("publisher") or "Bệnh viện Tim Hà Nội",
                    "effective_date": citation.get("effective_date"),
                    "crawled_at": citation.get("crawled_at"),
                }
                if kind == "web" and url:
                    item["url"] = url
                elif kind == "document":
                    item["url"] = None

                citations.append(item)


        grounded = bool(citations)
        error = None
        if scope_refused:
            error = make_error_envelope(
                code=OUT_OF_SCOPE,
                message="Request is outside the supported Bệnh viện Tim Hà Nội scope",
                category=CATEGORY_SAFETY,
                trace_id=request.session_id,
                retryable=False,
                fallback=answer,
            ).to_dict()
        elif terminal_failure:
            provider_failure = terminal_failure == "providers_exhausted"
            error = make_error_envelope(
                code=AI_PROVIDER_UNAVAILABLE if provider_failure else TOOL_TIMEOUT,
                message=terminal_failure,
                category=CATEGORY_AI if provider_failure else CATEGORY_TOOL,
                trace_id=request.session_id,
                retryable=True,
                fallback=answer,
            ).to_dict()
        response = AgentInformationResponse(
            {
                "outcome": outcome,
                "message": answer,
                "citations": citations,
                "suggested_actions": [
                    {
                        **action,
                        "action_id": action.get("action_id") or action.get("type") or f"booking-action-{index}",
                    }
                    for index, action in enumerate(booking_result.get("suggested_actions") or [])
                    if isinstance(action, dict) and action.get("label")
                ],
                "disclaimers": [
                    "Đây là thông tin tham khảo và không thay thế tư vấn y tế trực tiếp."
                ],
                "conversation_state": {
                    "risk": risk,
                    "mode": "booking" if is_booking else "information",
                    "booking_flow_ref": state.get("booking_flow_ref"),
                    "booking_flow_version": state.get("booking_flow_version", 0),
                    "current_step": state.get("booking_step"),
                },
                "explainability": None if is_booking else {
                    "grounded": grounded,
                    "confidence": "high" if grounded else "low",
                    "source_count": len(citations),
                    **({"fallback_reason": terminal_failure} if terminal_failure else {}),
                },
                "error": error,
            }
        )
        logger.info("agent_trace %s", json.dumps({
            "event": "request.complete",
            "session_id": request.session_id,
            "outcome": outcome,
            "elapsed_ms": round((time.monotonic() - request_started_at) * 1000, 2),
        }))
        return response


def build_agent_information_assistance_adapter(*, appointment_tools: Any = None) -> AgentInformationAssistanceAdapter:
    return AgentInformationAssistanceAdapter(appointment_tools=appointment_tools)


__all__ = [
    "AgentInformationAssistanceAdapter",
    "AgentInformationResponse",
    "build_agent_information_assistance_adapter",
]
