from fastapi.testclient import TestClient

from apps.api.main import app


def test_foundation_appointment_endpoints_use_internal_mock_his_gateway():
    with TestClient(app) as client:
        specialties = client.get("/v1/foundation/specialties")
        doctors = client.get("/v1/foundation/doctors", params={"specialty_id": "SP-CARD-GEN"})
        slots = client.get("/v1/foundation/doctors/DOC-001/available-slots")

    assert specialties.status_code == 200
    assert specialties.json()["total"] == 5
    assert doctors.status_code == 200
    assert doctors.json()["total"] == 3
    assert slots.status_code == 200
    assert [item["slot_id"] for item in slots.json()["items"]] == ["SL-001", "SL-013"]
