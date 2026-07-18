from apps.api.foundation.appointments.service import (
    AppointmentService,
    InternalMockHISClient,
    PatientAppointmentDataDTO,
)
from apps.mock_his.service import MockHISStore


def build_service():
    return AppointmentService(InternalMockHISClient(MockHISStore()))


def test_internal_gateway_reads_seeded_foundation_data_without_http():
    service = build_service()

    specialties = service.list_specialties(page=1, page_size=100, is_active=True)
    doctors = service.list_doctors(
        page=1,
        page_size=100,
        specialty_id="SP-CARD-GEN",
        is_active=True,
    )
    slots = service.list_available_slots("DOC-001", page=1, page_size=100)

    assert specialties.total == 5
    assert doctors.total == 3
    assert [slot.slot_id for slot in slots.items] == ["SL-001", "SL-013"]


def test_internal_gateway_creates_one_pending_appointment_per_idempotency_key():
    service = build_service()
    patient = PatientAppointmentDataDTO(
        name="Pilot User",
        phone="0900000099",
        dob="1990-01-01",
        has_insurance=True,
        visit_reason="Pilot booking",
        visit_type="first_visit",
    )

    first = service.create_appointment(
        doctor_id="DOC-001",
        slot_id="SL-001",
        patient=patient,
        confirmation_token="confirmed",
        idempotency_key="internal-gateway-test-key",
    )
    second = service.create_appointment(
        doctor_id="DOC-001",
        slot_id="SL-001",
        patient=patient,
        confirmation_token="confirmed",
        idempotency_key="internal-gateway-test-key",
    )

    assert first.status == "pending"
    assert second.appointment_id == first.appointment_id
    assert service.get_appointment(first.appointment_id).status == "pending"
