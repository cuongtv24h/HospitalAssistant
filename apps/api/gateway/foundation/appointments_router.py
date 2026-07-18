"""Lightweight Foundation appointment APIs; no AI reasoning."""

from fastapi import APIRouter, HTTPException, Query

from apps.api.foundation.appointments.service import AppointmentService, AppointmentServiceError

router = APIRouter(prefix="/v1/foundation", tags=["foundation-appointments"])
_appointment_service = AppointmentService()


def set_appointment_service(service: AppointmentService) -> None:
    """Inject the shared in-process appointment service during app startup."""
    global _appointment_service
    _appointment_service = service


def service() -> AppointmentService:
    return _appointment_service

def failure(exc):
    raise HTTPException(503, "appointment foundation data is unavailable") from exc

@router.get("/specialties")
def specialties():
    try:
        return service().list_specialties(page=1, page_size=100, is_active=True).to_dict()
    except AppointmentServiceError as exc: failure(exc)

@router.get("/doctors")
def doctors(specialty_id: str = Query(min_length=1)):
    try:
        return service().list_doctors(page=1, page_size=100, specialty_id=specialty_id, is_active=True).to_dict()
    except AppointmentServiceError as exc: failure(exc)

@router.get("/doctors/{doctor_id}/available-slots")
def slots(doctor_id: str):
    try:
        return service().list_available_slots(doctor_id=doctor_id, page=1, page_size=100).to_dict()
    except AppointmentServiceError as exc: failure(exc)
