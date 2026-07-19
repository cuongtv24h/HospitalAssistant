# === TASK:WP-305:START ===
"""Appointment booking orchestration pipeline for PC-03.

The pipeline collects appointment data across turns, asks for explicit
confirmation, and only then invokes the injected appointment creation tool.
Substantive behavior lives in this snake_case leaf module per WP-305-R1.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Literal, Optional, Protocol, runtime_checkable

from apps.api.foundation.appointments.tools.service import CreateAppointmentInput
from packages.contracts import BookingFlowStateDTO, PatientAppointmentDataDTO

BookingStep = Literal[
    "visit_type",
    "specialty",
    "doctor",
    "slot",
    "patient_data",
    "confirmation",
    "created",
]
BookingOutcome = Literal[
    "collecting",
    "confirmation_required",
    "created",
    "error",
]

REQUIRED_PATIENT_FIELDS = ("patient_name", "patient_phone", "patient_dob", "has_insurance", "visit_reason")
ALLOWED_VISIT_TYPES = ("first_visit", "follow_up")
CONFIRMATION_WORDS = {"confirm", "confirmed", "yes", "đồng ý", "xac nhan", "xác nhận"}




@dataclass(frozen=True)
class AppointmentBookingRequest:
    """PC-03 orchestration request."""

    request_id: str
    session_id: str
    message: str = ""
    state: Optional[BookingFlowStateDTO] = None
    form_data: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AppointmentBookingResponse:
    """PC-03 orchestration response."""

    outcome: BookingOutcome
    message: str
    conversation_state: BookingFlowStateDTO
    appointment: Optional[Dict[str, Any]] = None
    suggested_actions: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "outcome": self.outcome,
            "message": self.message,
            "conversation_state": self.conversation_state.to_dict(),
            "suggested_actions": list(self.suggested_actions),
        }
        if self.appointment is not None:
            result["appointment"] = dict(self.appointment)
        if self.error is not None:
            result["error"] = dict(self.error)
        return result


@runtime_checkable
class AppointmentCreationToolProtocol(Protocol):
    """Injected WP-203 appointment creation tool interface."""

    def create_appointment(self, input_data: CreateAppointmentInput) -> Any:
        """Create an appointment only after explicit confirmation."""
        ...


def _normalise_state(request: AppointmentBookingRequest) -> BookingFlowStateDTO:
    return request.state or BookingFlowStateDTO(
        session_id=request.session_id,
        flow_id=f"flow-{uuid.uuid4()}",
        version=0,
        status="collecting",
        step="visit_type",
        current_step="visit_type",
    )


def _is_confirmed(message: str, form_data: Dict[str, Any]) -> bool:
    if form_data.get("confirmed") is True:
        return True
    return message.strip().lower() in CONFIRMATION_WORDS


def _appointment_to_dict(appointment: Any) -> Dict[str, Any]:
    if isinstance(appointment, dict):
        return dict(appointment)
    if hasattr(appointment, "to_dict"):
        return appointment.to_dict()
    return {
        "appointment_id": appointment.appointment_id,
        "doctor_id": appointment.doctor_id,
        "slot_id": appointment.slot_id,
        "status": appointment.status,
    }


def _confirmation_summary(state: BookingFlowStateDTO) -> str:
    patient = state.patient_data
    patient_text = patient.to_dict() if patient else {}
    return (
        "Vui lòng xác nhận thông tin đặt lịch: "
        f"loại khám={state.visit_type}, chuyên khoa={state.specialty_id}, "
        f"bác sĩ={state.doctor_id}, khung giờ={state.slot_id}, "
        f"bệnh nhân={patient_text}."
    )


from apps.api.ai.orchestrator.appointment_booking.coordinator import DeterministicBookingCoordinator
from apps.api.ai.orchestrator.appointment_booking.policy import enforce_create_policy, CreatePolicyError

class AppointmentBookingPipeline:
    """Collect, confirm, then create pending appointment for PC-03."""

    def __init__(self, *, appointment_tools: Optional[AppointmentCreationToolProtocol] = None) -> None:
        self._appointment_tools = appointment_tools

    def execute(self, request: AppointmentBookingRequest) -> AppointmentBookingResponse:
        """Advance the booking state by one turn using DeterministicBookingCoordinator."""
        state = _normalise_state(request)
        data = dict(request.form_data)
        confirmation_attempt = _is_confirmed(request.message, data)

        # Confirmation is bound to the previously displayed canonical draft.
        # Never merge resent booking fields into the same turn that creates it.
        transition_data = data
        if confirmation_attempt and request.state is not None:
            transition_data = {
                key: data[key]
                for key in ("confirmed", "idempotency_key", "expected_version", "confirmation_fingerprint")
                if key in data
            }

        coordinator = DeterministicBookingCoordinator(self._appointment_tools)

        try:
            new_state = (
                state
                if confirmation_attempt and request.state is not None
                else coordinator.process_turn(state, transition_data, request.message)
            )

            if new_state.status == "expired":
                return AppointmentBookingResponse(
                    outcome="error",
                    message="Phiên đặt lịch đã hết hạn. Vui lòng bắt đầu lại.",
                    conversation_state=new_state,
                    error={"code": "DRAFT_EXPIRED", "message": "Draft booking session has expired."}
                )

            if new_state.status == "cancelled":
                return AppointmentBookingResponse(
                    outcome="collecting",
                    message="Yêu cầu đặt lịch đã được hủy.",
                    conversation_state=new_state
                )

            if new_state.current_step == "visit_type":
                return self._ask(new_state, "Bạn muốn đặt lịch khám lần đầu hay tái khám?", "collect_visit_type")

            elif new_state.current_step == "specialty":
                return self._ask(new_state, "Vui lòng chọn chuyên khoa cần khám.", "collect_specialty")

            elif new_state.current_step == "doctor":
                return self._ask(new_state, "Vui lòng chọn bác sĩ phù hợp.", "collect_doctor")

            elif new_state.current_step == "slot":
                if new_state.last_error_code == "SLOT_UNAVAILABLE":
                    return AppointmentBookingResponse(
                        outcome="error",
                        message="Khung giờ này đã được đặt hoặc không khả dụng. Vui lòng chọn khung giờ khác.",
                        conversation_state=new_state,
                        suggested_actions=[{"type": "refresh_slots", "doctor_id": new_state.doctor_id}],
                        error={"code": "SLOT_UNAVAILABLE", "message": "The selected slot is no longer available."},
                    )
                return self._ask(new_state, "Vui lòng chọn khung giờ khám còn trống.", "collect_slot")

            elif new_state.current_step == "patient_data":
                field_labels = {
                    "patient_name": "họ tên",
                    "patient_phone": "số điện thoại",
                    "patient_dob": "ngày sinh",
                    "has_insurance": "thông tin BHYT",
                    "visit_reason": "lý do khám hoặc tình trạng cần khám",
                }
                missing_labels = [field_labels[field] for field in new_state.missing_fields if field in field_labels]
                if missing_labels:
                    missing_text = ", ".join(missing_labels)
                    message = f"Đã lưu các thông tin bạn cung cấp. Vui lòng bổ sung: {missing_text}."
                else:
                    message = "Vui lòng cung cấp họ tên, số điện thoại, ngày sinh, BHYT và lý do khám hoặc tình trạng cần khám."
                return self._ask(new_state, message, "collect_patient_data")

            elif new_state.current_step == "confirmation":
                if confirmation_attempt:
                    confirmed_state = replace(new_state, status="confirmed")
                    return self._create_pending_appointment(
                        confirmed_state,
                        expected_version=data.get("expected_version"),
                        expected_fingerprint=data.get("confirmation_fingerprint"),
                    )

                summary = coordinator.generate_confirmation_summary(new_state)
                return AppointmentBookingResponse(
                    outcome="confirmation_required",
                    message=summary,
                    conversation_state=new_state,
                    suggested_actions=[{"type": "confirm", "label": "Xác nhận đặt lịch"}],
                )

            confirmed_state = replace(new_state, status="confirmed")
            return self._create_pending_appointment(confirmed_state)

        except CreatePolicyError as exc:
            if exc.code == "SLOT_UNAVAILABLE":
                recovered_state = replace(
                    state,
                    version=state.version + 1,
                    status="collecting",
                    step="slot",
                    current_step="slot",
                    slot_id=None,
                    selected_slot_id=None,
                    confirmation_token=None,
                    confirmation_fingerprint=None,
                    idempotency_key=None,
                    last_error_code="SLOT_UNAVAILABLE",
                )
                return AppointmentBookingResponse(
                    outcome="error",
                    message="Khung giờ này đã được đặt hoặc không khả dụng. Vui lòng chọn khung giờ khác.",
                    conversation_state=recovered_state,
                    suggested_actions=[{"type": "refresh_slots", "doctor_id": state.doctor_id}],
                    error={"code": "SLOT_UNAVAILABLE", "message": exc.message}
                )
            elif exc.code == "CONFIRMATION_REQUIRED":
                return AppointmentBookingResponse(
                    outcome="confirmation_required",
                    message="Yêu cầu xác nhận trước khi đặt lịch.",
                    conversation_state=state,
                )
            return AppointmentBookingResponse(
                outcome="error",
                message=exc.message,
                conversation_state=state,
                error={"code": exc.code, "message": exc.message}
            )
        except Exception as exc:
            return AppointmentBookingResponse(
                outcome="error",
                message="Không thể xử lý đặt lịch ở thời điểm này.",
                conversation_state=state,
                error={"code": "APPOINTMENT_BOOKING_FAILED", "message": str(exc)},
            )

    def _create_pending_appointment(
        self,
        state: BookingFlowStateDTO,
        *,
        expected_version: Optional[int] = None,
        expected_fingerprint: Optional[str] = None,
    ) -> AppointmentBookingResponse:
        if self._appointment_tools is None:
            raise RuntimeError("appointment creation tool is not configured")

        # Enforce create policy checks (4.2/4.3/4.4)
        enforce_create_policy(
            state,
            self._appointment_tools,
            expected_version=expected_version,
            expected_fingerprint=expected_fingerprint,
        )

        created = self._appointment_tools.create_appointment(
            CreateAppointmentInput(
                doctor_id=state.doctor_id,
                slot_id=state.slot_id,
                patient_name=state.patient_data.patient_name,
                patient_phone=state.patient_data.patient_phone,
                patient_dob=state.patient_data.patient_dob,
                has_insurance=state.patient_data.has_insurance,
                visit_reason=state.patient_data.visit_reason,
                visit_type=state.visit_type,  # type: ignore[arg-type]
                confirmation_token=state.confirmation_token or "confirmed",
                idempotency_key=state.idempotency_key,
            )
        )
        appointment = _appointment_to_dict(created)
        final_state = replace(
            state,
            status="created",
            step="created",
            current_step="created",
            created_appointment_id=appointment.get("appointment_id"),
        )
        return AppointmentBookingResponse(
            outcome="created",
            message=f"Đã tạo lịch hẹn trạng thái pending. Mã lịch hẹn: {appointment.get('appointment_id')}.",
            conversation_state=final_state,
            appointment=appointment,
            suggested_actions=[{"type": "lookup", "appointment_id": appointment.get("appointment_id")}],
        )

    def _ask(self, state: BookingFlowStateDTO, message: str, action: str) -> AppointmentBookingResponse:
        return AppointmentBookingResponse(
            outcome="collecting",
            message=message,
            conversation_state=state,
            suggested_actions=[{"type": "provide", "field": action}],
        )


def run_appointment_booking(
    request: AppointmentBookingRequest,
    *,
    appointment_tools: Optional[AppointmentCreationToolProtocol] = None,
) -> AppointmentBookingResponse:
    """One-shot wrapper for appointment booking orchestration."""
    return AppointmentBookingPipeline(appointment_tools=appointment_tools).execute(request)


__all__ = [
    "AppointmentBookingPipeline",
    "AppointmentBookingRequest",
    "AppointmentBookingResponse",
    "BookingFlowStateDTO",
    "PatientAppointmentDataDTO",
    "run_appointment_booking",
]
# === TASK:WP-305:END ===
