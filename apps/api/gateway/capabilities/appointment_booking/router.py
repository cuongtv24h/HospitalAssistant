# === TASK:WP-403:START ===
"""FastAPI router for the PC-03 Appointment Booking capability.

The module exposes the canonical public endpoint
``POST /v1/capabilities/appointment-booking:execute`` and adapts request
JSON to the WP-305 appointment-booking pipeline without changing the
pipeline's public contracts.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator

from apps.api.core.runtime_persistence import (
    append_assistant_turn,
    append_user_turn,
    get_operational_runtime,
    write_audit,
    write_booking_audit,
)
from apps.api.ai.orchestrator.appointment_booking.pipeline import (
    AppointmentBookingPipeline,
    AppointmentBookingRequest,
    BookingOutcome,
)
from packages.contracts import BookingFlowStateDTO
from apps.api.core.settings import Settings
import logging

CAPABILITY_NAME = "appointment_booking"
CAPABILITY_ROUTE = "/v1/capabilities/appointment-booking:execute"
VALID_RESPONSE_MODES = {"sync", "stream"}
MAX_MESSAGE_LENGTH = 4000
MAX_HISTORY_TURNS = 20

router = APIRouter()
_default_pipeline = AppointmentBookingPipeline()


class AppointmentBookingExecuteRequest(BaseModel):
    """Gateway request DTO for PC-03.

    JSON fields stay snake_case and are mapped directly to the canonical
    ``AppointmentBookingRequest`` consumed by the orchestrator.
    """

    request_id: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)
    message: str = Field(default="", max_length=MAX_MESSAGE_LENGTH)
    conversation_history: List[Dict[str, str]] = Field(default_factory=list)
    response_mode: str = "sync"
    client_context: Dict[str, Any] = Field(default_factory=dict)
    form_data: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        if value is not None and not value.strip() and value != "":
            raise ValueError("message must be non-empty if provided")
        return value

    @field_validator("conversation_history")
    @classmethod
    def validate_conversation_history(
        cls, value: List[Dict[str, str]]
    ) -> List[Dict[str, str]]:
        if len(value) > MAX_HISTORY_TURNS:
            raise ValueError("conversation_history cannot exceed 20 turns")
        return value

    @field_validator("response_mode")
    @classmethod
    def validate_response_mode(cls, value: str) -> str:
        if value not in VALID_RESPONSE_MODES:
            raise ValueError("response_mode must be sync or stream")
        return value

    def to_pipeline_request(self) -> AppointmentBookingRequest:
        """Convert the gateway DTO to the WP-305 pipeline DTO."""
        return AppointmentBookingRequest(
            request_id=self.request_id,
            session_id=self.session_id,
            message=self.message,
            form_data=self.form_data,
        )


def set_appointment_booking_pipeline(pipeline: AppointmentBookingPipeline) -> None:
    """Replace the module-level pipeline; intended for tests/application wiring."""
    global _default_pipeline
    _default_pipeline = pipeline


def is_create_confirmation_attempt(payload: AppointmentBookingExecuteRequest) -> bool:
    """Return whether the request is attempting the confirmed create step."""
    message = payload.message.strip().lower()
    return payload.form_data.get("confirmed") is True or message in {
        "confirm",
        "confirmed",
        "yes",
        "đồng ý",
        "xac nhan",
        "xác nhận",
    }



def build_capability_response_envelope(
    *,
    pipeline_response: Any,
    request_id: str,
    trace_id: str,
) -> Dict[str, Any]:
    """Build the canonical capability response envelope for PC-03."""
    result = pipeline_response.to_dict()
    for nullable_key in ("appointment", "error"):
        result.setdefault(nullable_key, None)

    error_payload = result.get("error")
    if error_payload and isinstance(error_payload, dict) and "error" in error_payload:
        errors = [error_payload["error"]]
    elif error_payload:
        errors = [error_payload]
    else:
        errors = []

    return {
        "trace_id": trace_id,
        "request_id": request_id,
        "capability": CAPABILITY_NAME,
        "outcome": result.get("outcome"),
        "result": result,
        "explainability": result.get("explainability"),
        "warnings": result.get("warnings", []),
        "errors": errors,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def build_sse_stream(envelope: Dict[str, Any]) -> str:
    """Render a deterministic SSE stream with the same semantic envelope."""
    import json

    ack = {"trace_id": envelope["trace_id"], "capability": CAPABILITY_NAME}
    completed = envelope
    return (
        f"event: ack\ndata: {json.dumps(ack, ensure_ascii=False)}\n\n"
        f"event: completed\ndata: {json.dumps(completed, ensure_ascii=False)}\n\n"
    )


@router.post(CAPABILITY_ROUTE, response_model=None)
async def execute_appointment_booking(
    payload: AppointmentBookingExecuteRequest,
    request: Request,
):
    """Execute the PC-03 Appointment Booking capability."""
    # 5.4 respect enable_agentic_booking configuration
    settings = Settings()
    if not settings.enable_agentic_booking:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Agentic appointment booking is disabled."
        )

    trace_id = request.headers.get("x-trace-id") or str(uuid.uuid4())
    idempotency_key = request.headers.get("idempotency-key")
    if is_create_confirmation_attempt(payload) and not idempotency_key:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Idempotency-Key header is required for appointment create confirmation",
        )
    if is_create_confirmation_attempt(payload):
        expected_version = payload.form_data.get("expected_version")
        expected_fingerprint = payload.form_data.get("confirmation_fingerprint")
        if not isinstance(expected_version, int) or not isinstance(expected_fingerprint, str) or not expected_fingerprint:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Current booking version and confirmation fingerprint are required; reload the summary.",
            )
    if idempotency_key:
        payload.form_data.setdefault("idempotency_key", idempotency_key)

    runtime = get_operational_runtime(request)
    append_user_turn(runtime, payload.session_id, payload.message or "appointment booking request", client_context=payload.client_context, intent=CAPABILITY_NAME)

    # 5.3 Fallback to Mock HIS whenever the Supabase database is unavailable.
    state = None
    if runtime is not None:
        try:
            state = runtime.sessions.load_booking_draft(payload.session_id)
        except Exception:
            logging.getLogger(__name__).warning("Supabase database unavailable; falling back to in-memory draft")

    if not state:
        state = BookingFlowStateDTO(
            session_id=payload.session_id,
            flow_id=f"flow-{uuid.uuid4()}",
            version=0,
            status="collecting",
            current_step="visit_type"
        )

    # Convert request and pass state
    pipeline_request = payload.to_pipeline_request()
    pipeline_request = AppointmentBookingRequest(
        request_id=pipeline_request.request_id,
        session_id=pipeline_request.session_id,
        message=pipeline_request.message,
        state=state,
        form_data=pipeline_request.form_data
    )

    create_attempt = is_create_confirmation_attempt(payload)
    if create_attempt:
        write_booking_audit(runtime, "security", payload.session_id, "appointment_create_attempt", "appointment", details={"capability": CAPABILITY_NAME, "idempotency_key_present": bool(idempotency_key)})

    try:
        pipeline_response = _default_pipeline.execute(pipeline_request)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    # Save session state with database fallback
    if runtime is not None:
        try:
            if pipeline_response.outcome == "created" and pipeline_response.appointment:
                appt_id = pipeline_response.appointment.get("appointment_id", "")
                runtime.sessions.close_booking_draft(payload.session_id, appt_id)
            elif pipeline_response.conversation_state.status == "cancelled":
                runtime.sessions.clear_booking_draft(payload.session_id)
            elif state.flow_id and state.version >= 0:
                saved = runtime.sessions.update_booking_draft_cas(
                    payload.session_id,
                    pipeline_response.conversation_state,
                    expected_version=state.version,
                )
                if not saved:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Booking draft was updated by another request; reload and retry.",
                    )
            else:
                runtime.sessions.create_booking_draft(payload.session_id, pipeline_response.conversation_state)
        except HTTPException:
            raise
        except Exception:
            logging.getLogger(__name__).warning("Failed to persist booking draft state to database")

    envelope = build_capability_response_envelope(
        pipeline_response=pipeline_response,
        request_id=payload.request_id,
        trace_id=trace_id,
    )
    if create_attempt:
        outcome = "success" if envelope.get("result", {}).get("appointment") else "failure"
        write_booking_audit(runtime, "security", payload.session_id, f"appointment_create_{outcome}", "appointment", details={"capability": CAPABILITY_NAME, "idempotency_key_present": bool(idempotency_key)}, outcome=outcome)
    append_assistant_turn(runtime, payload.session_id, CAPABILITY_NAME, envelope, tools=[{"name": "appointment_tools"}])

    if payload.response_mode == "stream":
        return StreamingResponse(
            iter([build_sse_stream(envelope)]),
            media_type="text/event-stream",
            headers={"x-trace-id": trace_id},
        )

    return JSONResponse(content=envelope, headers={"x-trace-id": trace_id})


@router.get("/v1/capabilities/appointment-booking/session/{session_id}")
async def get_booking_session_state(session_id: str, request: Request):
    """Retrieve the current active booking draft for the session to resume in UI (6.1)."""
    runtime = get_operational_runtime(request)
    state = None
    if runtime is not None:
        try:
            state = runtime.sessions.load_booking_draft(session_id)
        except Exception:
            logging.getLogger(__name__).warning("Supabase database unavailable; fallback to None state")

    if not state:
        state = BookingFlowStateDTO(
            session_id=session_id,
            flow_id=f"flow-{uuid.uuid4()}",
            version=0,
            status="collecting",
            current_step="visit_type"
        )

    return JSONResponse(
        content={
            "session_id": session_id,
            "conversation_state": state.to_dict()
        },
        headers={"x-trace-id": request.headers.get("x-trace-id") or str(uuid.uuid4())}
    )


__all__ = [
    "CAPABILITY_NAME",
    "CAPABILITY_ROUTE",
    "AppointmentBookingExecuteRequest",
    "build_capability_response_envelope",
    "is_create_confirmation_attempt",
    "build_sse_stream",
    "execute_appointment_booking",
    "router",
    "set_appointment_booking_pipeline",
]
# === TASK:WP-403:END ===
