# === TASK:WP-305:START ===
"""Create-policy enforcement for WP-305.

Validates completeness of booking details, confirmation token verification,
and slot availability before invoking HIS.
"""

from __future__ import annotations

import time
from typing import Any, Optional
from packages.contracts import BookingFlowStateDTO
from apps.api.ai.orchestrator.appointment_booking.registry import validate_tool_input
from apps.api.foundation.appointments.tools.service import GetAvailableSlotsInput

class CreatePolicyError(Exception):
    """Exception raised when a create-policy check fails (4.2/4.3)."""
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)

def enforce_create_policy(
    state: BookingFlowStateDTO,
    appointment_tools: Any,
    *,
    expected_version: Optional[int] = None,
    expected_fingerprint: Optional[str] = None,
) -> None:
    """Enforce scheduling checks before HIS creation (4.2/4.3)."""
    
    # 1. Schema Validation (4.4)
    # Check if all material booking details are present
    if (not state.visit_type or not state.specialty_id or not state.doctor_id or 
        not state.slot_id or not state.patient_data or not state.confirmation_token):
        raise CreatePolicyError("INVALID_REQUEST", "Material booking details are missing.")
        
    # Validate the patient data fields specifically
    p = state.patient_data
    if not p.patient_name or not p.patient_phone or not p.patient_dob or not p.visit_reason:
        raise CreatePolicyError("INVALID_REQUEST", "Material patient details are missing.")
        
    if state.expires_at and state.expires_at < time.time():
        raise CreatePolicyError("DRAFT_EXPIRED", "The booking draft has expired.")

    # A confirmed status is necessary before evaluating the bound summary.
    if state.status != "confirmed" or not state.confirmation_token:
        raise CreatePolicyError("CONFIRMATION_REQUIRED", "Confirmation token is not verified.")
    if not state.confirmation_fingerprint:
        raise CreatePolicyError("CONFIRMATION_REQUIRED", "Confirmation fingerprint is missing.")
    if expected_version is not None and expected_version != state.version:
        raise CreatePolicyError("STALE_BOOKING_VERSION", "The booking summary is stale.")
    if expected_fingerprint is not None and expected_fingerprint != state.confirmation_fingerprint:
        raise CreatePolicyError("CONFIRMATION_MISMATCH", "The booking summary has changed.")
    if not state.idempotency_key:
        raise CreatePolicyError("IDEMPOTENCY_KEY_REQUIRED", "Idempotency key is required.")

    # 3. Check tool validation registry for create_appointment
    # (Construct arguments dictionary to validate against registry)
    args = {
        "doctor_id": state.doctor_id,
        "slot_id": state.slot_id,
        "patient_name": p.patient_name,
        "patient_phone": p.patient_phone,
        "patient_dob": p.patient_dob,
        "has_insurance": p.has_insurance,
        "visit_reason": p.visit_reason,
        "visit_type": state.visit_type,
        "confirmation_token": state.confirmation_token,
        "idempotency_key": state.idempotency_key
    }
    
    # This raises TypeError/ValueError if schema validation fails
    validate_tool_input("create_appointment", args)
    
    # 4. Check target slot availability (4.3)
    if hasattr(appointment_tools, "get_available_slots"):
        try:
            out = appointment_tools.get_available_slots(GetAvailableSlotsInput(doctor_id=state.doctor_id))
            slots = [s["slot_id"] for s in out.slots]
            if state.slot_id not in slots:
                raise CreatePolicyError("SLOT_UNAVAILABLE", "The target slot is already booked or inactive.")
        except CreatePolicyError:
            raise
        except Exception as exc:
            raise CreatePolicyError("INTEGRATION_UNAVAILABLE", "Unable to validate slot availability.") from exc
# === TASK:WP-305:END ===
