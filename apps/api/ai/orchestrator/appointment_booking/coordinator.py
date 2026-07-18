# === TASK:WP-305:START ===
"""Deterministic Booking Coordinator for WP-305.

Implements transition logic, missing-field calculation, confirmation fingerprinting,
and validation against current foundation observations.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from typing import Any, Dict, List, Literal, Optional

from packages.contracts import BookingFlowStateDTO, PatientAppointmentDataDTO
from apps.api.foundation.appointments.tools.service import (
    GetSpecialtyListInput,
    GetDoctorListInput,
    GetAvailableSlotsInput,
)

class DeterministicBookingCoordinator:
    def __init__(self, appointment_tools: Any) -> None:
        self._tools = appointment_tools

    def calculate_fingerprint(self, state: BookingFlowStateDTO) -> str:
        p = state.patient_data
        p_dict = p.to_dict() if p else {}
        p_str = "|".join(
            f"{k}:{p_dict.get(k)}"
            for k in sorted(["patient_name", "patient_phone", "patient_dob", "has_insurance", "visit_reason"])
        )
        raw = f"{state.visit_type}|{state.specialty_id}|{state.doctor_id}|{state.slot_id}|{p_str}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def generate_confirmation_summary(self, state: BookingFlowStateDTO) -> str:
        p = state.patient_data
        specialty_name = state.specialty_id or "Chưa chọn"
        doctor_name = state.doctor_id or "Chưa chọn"
        slot_text = state.slot_id or "Chưa chọn"

        try:
            specialties = self._tools.get_specialty_list(
                GetSpecialtyListInput(active_only=True)
            ).specialties
            specialty = next(
                (item for item in specialties if item.get("specialty_id") == state.specialty_id),
                None,
            )
            if specialty:
                specialty_name = specialty.get("name") or specialty_name
        except Exception:
            pass

        try:
            doctors = self._tools.get_doctor_list(
                GetDoctorListInput(specialty_id=state.specialty_id, active_only=True)
            ).doctors
            doctor = next(
                (item for item in doctors if item.get("doctor_id") == state.doctor_id),
                None,
            )
            if doctor:
                doctor_name = " ".join(
                    part for part in (doctor.get("title"), doctor.get("full_name")) if part
                ) or doctor_name
        except Exception:
            pass

        try:
            slots = self._tools.get_available_slots(
                GetAvailableSlotsInput(doctor_id=state.doctor_id or "")
            ).slots
            slot = next(
                (item for item in slots if item.get("slot_id") == state.slot_id),
                None,
            )
            if slot:
                slot_text = " · ".join(
                    part for part in (slot.get("date"), slot.get("time"), slot.get("room")) if part
                ) or slot_text
        except Exception:
            pass

        visit_type_label = {
            "first_visit": "Khám lần đầu",
            "follow_up": "Tái khám",
        }.get(state.visit_type, state.visit_type or "Chưa chọn")
        insurance_label = "Có BHYT" if p and p.has_insurance else "Không có BHYT"
        return (
            "Vui lòng xác nhận thông tin đặt lịch:\n"
            f"- Loại khám: {visit_type_label}\n"
            f"- Chuyên khoa: {specialty_name}\n"
            f"- Bác sĩ: {doctor_name}\n"
            f"- Thời gian: {slot_text}\n"
            f"- Người khám: {p.patient_name if p else 'Chưa cung cấp'}\n"
            f"- Ngày sinh: {p.patient_dob if p else 'Chưa cung cấp'}\n"
            f"- Số điện thoại: {p.patient_phone if p else 'Chưa cung cấp'}\n"
            f"- BHYT: {insurance_label}\n"
            f"- Lý do khám: {p.visit_reason if p else 'Chưa cung cấp'}"
        )

    def process_turn(
        self,
        current_state: BookingFlowStateDTO,
        form_data: Dict[str, Any],
        message: str = ""
    ) -> BookingFlowStateDTO:
        # 1. Check expiry
        if current_state.expires_at > 0 and current_state.expires_at < time.time():
            return BookingFlowStateDTO(
                session_id=current_state.session_id,
                flow_id=current_state.flow_id,
                version=current_state.version + 1,
                status="expired",
                current_step="visit_type",
                last_error_code="DRAFT_EXPIRED"
            )

        # 2. Check explicit cancellation
        cancellation_words = {"hủy", "cancel", "cancellation", "ngừng"}
        if message.strip().lower() in cancellation_words or form_data.get("cancelled") is True:
            return BookingFlowStateDTO(
                session_id=current_state.session_id,
                flow_id=current_state.flow_id,
                version=current_state.version + 1,
                status="cancelled",
                current_step="visit_type"
            )

        # 3. Merge form data
        visit_type = form_data.get("visit_type") or current_state.visit_type
        specialty_id = form_data.get("specialty_id") or current_state.specialty_id
        doctor_id = form_data.get("doctor_id") or current_state.doctor_id
        slot_id = form_data.get("slot_id") or current_state.slot_id

        # Merge collected fields
        collected_fields = dict(current_state.collected_fields)
        allowed_patient_fields = {"patient_name", "patient_phone", "patient_dob", "has_insurance", "visit_reason"}
        for k in allowed_patient_fields:
            if k in form_data:
                collected_fields[k] = form_data[k]

        # 4. Validations & Monotonic resets
        last_error_code = None

        # A. Visit type validation
        if visit_type and visit_type not in ("first_visit", "follow_up"):
            last_error_code = "INVALID_VISIT_TYPE"
            visit_type = None

        # If visit_type is changed or cleared, we must invalidate everything after it
        if current_state.visit_type is not None and visit_type != current_state.visit_type:
            specialty_id = None
            doctor_id = None
            slot_id = None

        # B. Specialty validation
        if specialty_id:
            # Validate specialty_id exists
            if hasattr(self._tools, "get_specialty_list"):
                try:
                    out = self._tools.get_specialty_list(GetSpecialtyListInput(active_only=True))
                    specialties = [s["specialty_id"] for s in out.specialties]
                    if specialty_id not in specialties:
                        last_error_code = "INVALID_SPECIALTY"
                        specialty_id = None
                except Exception:
                    last_error_code = "INVALID_SPECIALTY"
                    specialty_id = None

            # Reset subsequent fields on change
            if current_state.specialty_id is not None and specialty_id != current_state.specialty_id:
                doctor_id = None
                slot_id = None

        # C. Doctor validation
        if doctor_id:
            if not specialty_id:
                # Can't select doctor without specialty
                last_error_code = "INVALID_DOCTOR"
                doctor_id = None
            else:
                if hasattr(self._tools, "get_doctor_list"):
                    try:
                        out = self._tools.get_doctor_list(GetDoctorListInput(specialty_id=specialty_id, active_only=True))
                        doctors = [d["doctor_id"] for d in out.doctors]
                        if doctor_id not in doctors:
                            last_error_code = "INVALID_DOCTOR"
                            doctor_id = None
                    except Exception:
                        last_error_code = "INVALID_DOCTOR"
                        doctor_id = None
            # Reset subsequent slot field
            if current_state.doctor_id is not None and doctor_id != current_state.doctor_id:
                slot_id = None

        # D. Slot validation
        if slot_id:
            if not doctor_id:
                # Can't select slot without doctor
                last_error_code = "SLOT_UNAVAILABLE"
                slot_id = None
            else:
                if hasattr(self._tools, "get_available_slots"):
                    try:
                        out = self._tools.get_available_slots(GetAvailableSlotsInput(doctor_id=doctor_id))
                        slots = [s["slot_id"] for s in out.slots]
                        if slot_id not in slots:
                            last_error_code = "SLOT_UNAVAILABLE"
                            slot_id = None
                    except Exception:
                        last_error_code = "SLOT_UNAVAILABLE"
                        slot_id = None

        # 5. Missing-field calculation for patient_data
        missing_fields = []
        patient_data = None
        
        # Check patient details only if slot is selected
        if slot_id:
            for field_name in ["patient_name", "patient_phone", "patient_dob", "has_insurance", "visit_reason"]:
                if field_name not in collected_fields or collected_fields[field_name] is None:
                    missing_fields.append(field_name)
            
            if not missing_fields:
                patient_data = PatientAppointmentDataDTO(
                    patient_name=str(collected_fields["patient_name"]),
                    patient_phone=str(collected_fields["patient_phone"]),
                    patient_dob=str(collected_fields["patient_dob"]),
                    has_insurance=bool(collected_fields["has_insurance"]),
                    visit_reason=str(collected_fields["visit_reason"])
                )

        # 6. Determine current step
        if not visit_type:
            current_step = "visit_type"
        elif not specialty_id:
            current_step = "specialty"
        elif not doctor_id:
            current_step = "doctor"
        elif not slot_id:
            current_step = "slot"
        elif missing_fields:
            current_step = "patient_data"
        else:
            current_step = "confirmation"

        # 7. Build draft state to calculate fingerprint
        draft_before_confirmation = BookingFlowStateDTO(
            session_id=current_state.session_id,
            flow_id=current_state.flow_id,
            version=current_state.version + 1,
            status=current_state.status,
            step=current_step,
            current_step=current_step,
            visit_type=visit_type,
            specialty_id=specialty_id,
            doctor_id=doctor_id,
            slot_id=slot_id,
            selected_specialty_id=specialty_id,
            selected_doctor_id=doctor_id,
            selected_slot_id=slot_id,
            collected_fields=collected_fields,
            patient_data=patient_data,
            missing_fields=missing_fields,
            confirmation_token=current_state.confirmation_token,
            confirmation_fingerprint=current_state.confirmation_fingerprint,
            idempotency_key=current_state.idempotency_key,
            created_appointment_id=current_state.created_appointment_id,
            created_at=current_state.created_at,
            updated_at=time.time(),
            expires_at=current_state.expires_at,
            last_error_code=last_error_code
        )

        # A confirmation token is generated only if we are in the confirmation step
        confirmation_token = current_state.confirmation_token
        confirmation_fingerprint = current_state.confirmation_fingerprint
        idempotency_key = current_state.idempotency_key

        if current_step == "confirmation":
            new_fingerprint = self.calculate_fingerprint(draft_before_confirmation)
            
            # Invalidate confirmation and rotate token/fingerprint on change
            if new_fingerprint != current_state.confirmation_fingerprint or not confirmation_token:
                confirmation_token = f"confirm-{uuid.uuid4()}"
                confirmation_fingerprint = new_fingerprint
                idempotency_key = form_data.get("idempotency_key") or f"booking-{current_state.session_id}-{uuid.uuid4()}"
                status = "collecting"
            else:
                status = current_state.status
        else:
            # Reset confirmation fields if we moved back
            confirmation_token = None
            confirmation_fingerprint = None
            idempotency_key = None
            status = "collecting"

        return BookingFlowStateDTO(
            session_id=current_state.session_id,
            flow_id=current_state.flow_id,
            version=current_state.version + 1,
            status=status,
            step=current_step,
            current_step=current_step,
            visit_type=visit_type,
            specialty_id=specialty_id,
            doctor_id=doctor_id,
            slot_id=slot_id,
            selected_specialty_id=specialty_id,
            selected_doctor_id=doctor_id,
            selected_slot_id=slot_id,
            collected_fields=collected_fields,
            patient_data=patient_data,
            missing_fields=missing_fields,
            confirmation_token=confirmation_token,
            confirmation_fingerprint=confirmation_fingerprint,
            idempotency_key=idempotency_key,
            created_appointment_id=current_state.created_appointment_id,
            created_at=current_state.created_at,
            updated_at=time.time(),
            expires_at=current_state.expires_at,
            last_error_code=last_error_code
        )
# === TASK:WP-305:END ===
