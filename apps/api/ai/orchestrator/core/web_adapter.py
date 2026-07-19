"""Adapter exposing the LangGraph hospital agent through the web capability API."""

from __future__ import annotations

import os
import time
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List

import psycopg
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
        with psycopg.connect(os.environ["DATABASE_URL"]) as connection:
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
        active_booking_turn = bool(state.get("booking_step")) and current_action in {
            "start_booking", "advance_booking", "clarify"
        }
        if risk == "HIGH":
            outcome = "emergency_rerouted"
        elif risk == "CAUTION":
            outcome = "clarification_required"
        elif booking_result or active_booking_turn:
            outcome = "appointment_pending" if booking_result.get("appointment") else "booking_in_progress"
        elif answer == "Tôi không có đủ thông tin để trả lời câu hỏi này.":
            outcome = "fallback"
        else:
            outcome = "answered"

        citations = []
        seen = set()
        for citation in state.get("citations", []):
            source_id = str(citation.get("source_id") or citation.get("chunk_id") or "")
            if not source_id or source_id in seen:
                continue
            seen.add(source_id)
            source_path = str(citation.get("source_path") or "")
            citations.append(
                {
                    "source_id": source_id,
                    "title": Path(source_path).name or source_id,
                    "source_type": "hospital_knowledge",
                    "excerpt": citation.get("matched_text") or "",
                    "version": citation.get("version") or "",
                }
            )

        grounded = bool(citations)
        is_booking = bool(booking_result) or active_booking_turn
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
                },
                "error": None,
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
