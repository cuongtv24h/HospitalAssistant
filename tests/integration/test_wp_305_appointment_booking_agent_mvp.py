# === TASK:WP-305:START ===
import pytest
from unittest.mock import MagicMock
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from apps.api.ai.orchestrator.core import agent_graph
from apps.api.ai.orchestrator.core.agent import classify_action, direct_safety_node, llm_node, tool_node
from packages.contracts import BookingFlowStateDTO

def test_explicit_booking_start_is_forced_to_stateful_tool_not_discovery(monkeypatch):
    mock_chat = MagicMock()

    first_resp = AIMessage(content="")
    first_resp.tool_calls = [{
        "name": "get_specialty_list",
        "args": {"active_only": True},
        "id": "call-3"
    }]

    second_resp = AIMessage(content="Vui lòng chọn chuyên khoa.")
    mock_chat.invoke.side_effect = [first_resp, second_resp]

    monkeypatch.setattr(
        "apps.api.ai.orchestrator.core.agent.ChatOpenAI",
        lambda **kwargs: MagicMock(bind_tools=lambda tools: mock_chat)
    )

    # Mock safety to return LOW
    mock_provider = MagicMock()
    mock_provider.evaluate_safety.return_value = MagicMock(risk="LOW", to_dict=lambda: {"risk": "LOW"})
    monkeypatch.setattr(
        "apps.api.ai.orchestrator.core.agent.OpenAIProvider",
        lambda api_key: mock_provider
    )

    class SpecialtyOutput:
        specialties = [{"specialty_id": "SP-CARD", "name": "Tim mạch"}]

    tools = MagicMock()
    tools.get_specialty_list.return_value = SpecialtyOutput()
    sessions = MagicMock()
    sessions.load_booking_draft.return_value = None

    msg = HumanMessage(content="Tôi muốn đặt lịch khám tim mạch")
    state = {
        "messages": [msg],
        "safety_result": None,
        "clarification_count": 0,
        "observations": [],
        "citations": [],
        "call_fingerprints": [],
        "max_tool_calls": 5,
        "call_count": 0,
        "elapsed_time_seconds": 0.0,
        "deadline_timestamp": 9999999999.0,
        "final_response": None,
        "degradation_status": {},
        "repair_attempted": False
    }

    config = {
        "configurable": {
            "thread_id": "test-thread-8",
            "openai_api_key": "fake",
            "appointment_tools": tools,
            "session_service": sessions,
        }
    }

    res = agent_graph.invoke(state, config)
    assert "lần đầu hay tái khám" in res["final_response"].lower()
    assert res["booking_step"] == "visit_type"
    tools.get_specialty_list.assert_not_called()
    sessions.create_booking_draft.assert_called_once()


def test_validated_doctor_choices_are_supplied_to_next_model_turn(monkeypatch):
    captured = {}
    response = AIMessage(content="")
    response.tool_calls = [{
        "name": "continue_appointment_booking",
        "args": {"doctor_id": "DOC-001"},
        "id": "call-doctor",
    }]

    class BoundModel:
        def invoke(self, messages):
            captured["messages"] = messages
            return response

    monkeypatch.setattr(
        "apps.api.ai.orchestrator.core.agent.ChatOpenAI",
        lambda **kwargs: MagicMock(bind_tools=lambda tools: captured.update({"tools": tools}) or BoundModel()),
    )
    state = {
        "messages": [HumanMessage(content="Nguyễn Minh An")],
        "booking_choices": [{"doctor_id": "DOC-001", "full_name": "Nguyễn Minh An"}],
        "booking_step": "doctor",
        "call_fingerprints": [],
        "call_count": 0,
        "max_tool_calls": 5,
        "elapsed_time_seconds": 0.0,
        "deadline_timestamp": 9999999999.0,
        "repair_attempted": False,
    }

    result = llm_node(state, {"configurable": {"openai_api_key": "fake"}})

    system_text = "\n".join(str(message.content) for message in captured["messages"])
    assert "DOC-001" in system_text
    assert "Nguyễn Minh An" in system_text
    assert [tool.name for tool in captured["tools"]] == ["continue_appointment_booking"]
    assert result["messages"][-1].tool_calls[0]["name"] == "continue_appointment_booking"


def test_structured_doctor_selection_advances_to_slots():
    class SpecialtyOutput:
        specialties = [{"specialty_id": "SP-CARD-GEN", "name": "Tim mạch tổng quát"}]

    class DoctorOutput:
        doctors = [{"doctor_id": "DOC-001", "full_name": "Nguyễn Minh An"}]

    class SlotOutput:
        slots = [{"slot_id": "SL-001", "doctor_id": "DOC-001", "date": "2026-08-04", "time": "08:00"}]

    tools = MagicMock()
    tools.get_specialty_list.return_value = SpecialtyOutput()
    tools.get_doctor_list.return_value = DoctorOutput()
    tools.get_available_slots.return_value = SlotOutput()
    sessions = MagicMock()
    sessions.load_booking_draft.return_value = BookingFlowStateDTO(
        session_id="test-thread-doctor",
        flow_id="flow-doctor",
        version=2,
        status="collecting",
        current_step="doctor",
        step="doctor",
        visit_type="first_visit",
        specialty_id="SP-CARD-GEN",
    )
    sessions.update_booking_draft_cas.return_value = True

    tool_request = AIMessage(content="")
    tool_request.tool_calls = [{
        "name": "continue_appointment_booking",
        "args": {"doctor_id": "DOC-001"},
        "id": "doctor-selection",
    }]
    state = {
        "messages": [HumanMessage(content="Nguyễn Minh An"), tool_request],
        "booking_choices": [{"doctor_id": "DOC-001", "full_name": "Nguyễn Minh An"}],
        "booking_result": None,
        "observations": [],
        "call_count": 0,
    }
    config = {
        "configurable": {
            "thread_id": "test-thread-doctor",
            "current_user_message": "Nguyễn Minh An",
            "appointment_tools": tools,
            "session_service": sessions,
        }
    }

    result = tool_node(state, config)

    assert result["booking_result"]["choice_type"] == "slot"
    assert result["booking_result"]["items"][0]["slot_id"] == "SL-001"
    assert result["booking_flow_version"] == 3
    # Called only by the coordinator to revalidate the canonical specialty.
    assert tools.get_specialty_list.call_count == 1


def test_llm_structured_first_visit_advances_to_doctors():
    class SpecialtyOutput:
        specialties = [{"specialty_id": "SP-CARD-GEN", "name": "Tim mạch tổng quát"}]

    class DoctorOutput:
        doctors = [{"doctor_id": "DOC-001", "full_name": "Nguyễn Minh An"}]

    tools = MagicMock()
    tools.get_specialty_list.return_value = SpecialtyOutput()
    tools.get_doctor_list.return_value = DoctorOutput()
    sessions = MagicMock()
    sessions.load_booking_draft.return_value = BookingFlowStateDTO(
        session_id="test-thread-visit-type",
        flow_id="flow-visit-type",
        version=1,
        status="collecting",
        current_step="visit_type",
        step="visit_type",
        specialty_id="SP-CARD-GEN",
    )
    sessions.update_booking_draft_cas.return_value = True

    wrong_tool_request = AIMessage(content="")
    wrong_tool_request.tool_calls = [{
        "name": "continue_appointment_booking",
        "args": {"visit_type": "first_visit"},
        "id": "visit-type-call",
    }]
    state = {
        "messages": [HumanMessage(content="Tôi khám lần đầu"), wrong_tool_request],
        "booking_choices": [{"specialty_id": "SP-CARD-GEN", "name": "Tim mạch tổng quát"}],
        "booking_result": None,
        "observations": [],
        "call_count": 0,
    }
    config = {
        "configurable": {
            "thread_id": "test-thread-visit-type",
            "current_user_message": "Tôi khám lần đầu",
            "appointment_tools": tools,
            "session_service": sessions,
        }
    }

    result = tool_node(state, config)

    assert result["booking_result"]["choice_type"] == "doctor"
    assert result["booking_result"]["items"][0]["doctor_id"] == "DOC-001"
    assert result["booking_flow_version"] == 2


def test_read_only_doctor_question_preserves_active_booking_state():
    class DoctorOutput:
        doctors = [{"doctor_id": "DOC-001", "full_name": "Nguyễn Minh An"}]

    tools = MagicMock()
    tools.get_doctor_list.return_value = DoctorOutput()
    sessions = MagicMock()
    tool_request = AIMessage(content="")
    tool_request.tool_calls = [{
        "name": "get_doctor_list",
        "args": {"specialty_id": "SP-CARD-GEN"},
        "id": "doctor-information",
    }]
    original_choices = [{"specialty_id": "SP-CARD-GEN", "name": "Tim mạch tổng quát"}]
    state = {
        "messages": [HumanMessage(content="Khoa này có những bác sĩ nào?"), tool_request],
        "booking_result": None,
        "booking_step": "doctor",
        "booking_choices": original_choices,
        "observations": [],
        "appointment_observations": [],
        "call_count": 0,
    }
    config = {
        "configurable": {
            "thread_id": "test-thread-read-only",
            "appointment_tools": tools,
            "session_service": sessions,
        }
    }

    result = tool_node(state, config)

    assert result["booking_result"] is None
    assert result["booking_step"] == "doctor"
    assert result["booking_choices"] == original_choices
    assert result["appointment_observations"][0]["tool"] == "get_doctor_list"
    sessions.load_booking_draft.assert_not_called()


def test_routine_booking_answer_bypasses_semantic_emergency_clarification():
    state = {
        "messages": [HumanMessage(content="Khám lần đầu")],
        "booking_step": "visit_type",
        "safety_result": None,
        "clarification_count": 0,
    }

    result = direct_safety_node(state, {"configurable": {"thread_id": "booking-safety"}})

    assert result["safety_result"]["risk"] == "LOW"
    assert result["safety_result"]["reason_code"] == "ROUTINE_BOOKING_TURN"
    assert classify_action(result) == "advance_booking"


def test_slot_id_selection_is_classified_as_booking_advance():
    state = {
        "messages": [HumanMessage(content="Tôi chọn SL-001")],
        "booking_step": "slot",
        "booking_choices": [{
            "slot_id": "SL-001",
            "doctor_id": "DOC-001",
            "date": "2026-08-04",
            "time": "08:00",
        }],
    }

    assert classify_action(state) == "advance_booking"


def test_patient_declaration_with_insurance_is_not_misrouted_to_rag():
    state = {
        "messages": [HumanMessage(content="Tôi là Nguyễn Văn A, sinh ngày 01/01/1990, số 0901234567, có BHYT, lý do khám định kỳ")],
        "booking_step": "patient_data",
    }

    assert classify_action(state) == "advance_booking"


def test_knowledge_question_during_patient_step_remains_read_only_interruption():
    state = {
        "messages": [HumanMessage(content="Khám BHYT cần mang giấy tờ gì?")],
        "booking_step": "patient_data",
    }

    assert classify_action(state) == "search_knowledge"


def test_later_step_slot_is_not_saved_while_selecting_doctor():
    class SpecialtyOutput:
        specialties = [{"specialty_id": "SP-CARD-GEN", "name": "Tim mạch tổng quát"}]

    class DoctorOutput:
        doctors = [{"doctor_id": "DOC-001", "full_name": "Nguyễn Minh An"}]

    class SlotOutput:
        slots = [{"slot_id": "SL-001", "doctor_id": "DOC-001", "date": "2026-08-04", "time": "08:00"}]

    tools = MagicMock()
    tools.get_specialty_list.return_value = SpecialtyOutput()
    tools.get_doctor_list.return_value = DoctorOutput()
    tools.get_available_slots.return_value = SlotOutput()
    sessions = MagicMock()
    sessions.load_booking_draft.return_value = BookingFlowStateDTO(
        session_id="sequential-booking",
        flow_id="flow-sequential",
        version=2,
        status="collecting",
        current_step="doctor",
        step="doctor",
        visit_type="first_visit",
        specialty_id="SP-CARD-GEN",
    )
    sessions.update_booking_draft_cas.return_value = True
    tool_request = AIMessage(content="", tool_calls=[{
        "name": "continue_appointment_booking",
        "args": {"doctor_id": "DOC-001", "slot_id": "SL-001"},
        "id": "doctor-and-slot",
    }])

    result = tool_node(
        {
            "messages": [HumanMessage(content="Chọn bác sĩ An lúc 8 giờ"), tool_request],
            "booking_result": None,
            "booking_step": "doctor",
            "booking_choices": [{"doctor_id": "DOC-001", "full_name": "Nguyễn Minh An"}],
            "observations": [],
            "appointment_observations": [],
            "call_count": 0,
        },
        {"configurable": {
            "thread_id": "sequential-booking",
            "current_user_message": "Chọn bác sĩ An lúc 8 giờ",
            "appointment_tools": tools,
            "session_service": sessions,
        }},
    )

    next_state = result["booking_result"]["conversation_state"]
    assert next_state["current_step"] == "slot"
    assert next_state["doctor_id"] == "DOC-001"
    assert next_state["slot_id"] is None


def test_start_booking_ignores_eager_later_fields_from_model():
    tools = MagicMock()
    sessions = MagicMock()
    sessions.load_booking_draft.return_value = None
    tool_request = AIMessage(content="", tool_calls=[{
        "name": "continue_appointment_booking",
        "args": {"visit_type": "first_visit", "doctor_id": "DOC-001"},
        "id": "eager-start",
    }])

    result = tool_node(
        {
            "messages": [HumanMessage(content="Đặt lịch khám lần đầu với bác sĩ An"), tool_request],
            "booking_result": None,
            "booking_step": None,
            "booking_choices": [],
            "observations": [],
            "appointment_observations": [],
            "call_count": 0,
        },
        {"configurable": {
            "thread_id": "sequential-start",
            "current_user_message": "Đặt lịch khám lần đầu với bác sĩ An",
            "appointment_tools": tools,
            "session_service": sessions,
        }},
    )

    next_state = result["booking_result"]["conversation_state"]
    assert next_state["current_step"] == "visit_type"
    assert next_state["visit_type"] is None
    assert next_state["doctor_id"] is None


def test_explicit_new_booking_replaces_stale_patient_data_draft():
    tools = MagicMock()
    sessions = MagicMock()
    sessions.load_booking_draft.return_value = BookingFlowStateDTO(
        session_id="restart-booking",
        flow_id="stale-flow",
        version=5,
        status="collecting",
        current_step="patient_data",
        step="patient_data",
        visit_type="first_visit",
        specialty_id="SP-HTN",
        doctor_id="DOC-009",
        slot_id="SL-011",
    )
    tool_request = AIMessage(content="", tool_calls=[{
        "name": "continue_appointment_booking",
        "args": {},
        "id": "restart-stale-flow",
    }])

    result = tool_node(
        {
            "messages": [HumanMessage(content="Đặt lịch khám bệnh"), tool_request],
            "current_action": "start_booking",
            "booking_result": None,
            "booking_step": "patient_data",
            "booking_choices": [],
            "observations": [],
            "appointment_observations": [],
            "call_count": 0,
        },
        {"configurable": {
            "thread_id": "restart-booking",
            "current_user_message": "Đặt lịch khám bệnh",
            "appointment_tools": tools,
            "session_service": sessions,
        }},
    )

    next_state = result["booking_result"]["conversation_state"]
    assert next_state["current_step"] == "visit_type"
    assert next_state["specialty_id"] is None
    assert next_state["doctor_id"] is None
    assert next_state["slot_id"] is None
    sessions.clear_booking_draft.assert_called_once_with("restart-booking")
    sessions.create_booking_draft.assert_called_once()


def test_continue_booking_phrase_resumes_active_draft():
    state = {
        "messages": [HumanMessage(content="Tiếp tục đặt lịch")],
        "booking_step": "doctor",
    }

    assert classify_action(state) == "advance_booking"


def test_saved_transition_survives_temporary_choice_loading_failure():
    class SpecialtyOutput:
        specialties = [{"specialty_id": "SP-CARD-GEN", "name": "Tim mạch tổng quát"}]

    tools = MagicMock()
    tools.get_specialty_list.return_value = SpecialtyOutput()
    tools.get_doctor_list.side_effect = RuntimeError("reference service unavailable")
    sessions = MagicMock()
    sessions.load_booking_draft.return_value = BookingFlowStateDTO(
        session_id="choice-failure",
        flow_id="flow-choice-failure",
        version=1,
        status="collecting",
        current_step="visit_type",
        step="visit_type",
        specialty_id="SP-CARD-GEN",
    )
    sessions.update_booking_draft_cas.return_value = True
    tool_request = AIMessage(content="", tool_calls=[{
        "name": "continue_appointment_booking",
        "args": {"visit_type": "first_visit"},
        "id": "first-visit-choice-failure",
    }])

    result = tool_node(
        {
            "messages": [HumanMessage(content="Tôi khám lần đầu"), tool_request],
            "booking_result": None,
            "booking_step": "visit_type",
            "booking_choices": [],
            "observations": [],
            "appointment_observations": [],
            "call_count": 0,
        },
        {"configurable": {
            "thread_id": "choice-failure",
            "current_user_message": "Tôi khám lần đầu",
            "appointment_tools": tools,
            "session_service": sessions,
        }},
    )

    booking_result = result["booking_result"]
    assert booking_result["conversation_state"]["current_step"] == "doctor"
    assert booking_result["conversation_state"]["visit_type"] == "first_visit"
    assert "Đã lưu bước vừa rồi" in booking_result["message"]
    assert booking_result["choice_load_error"] == "RuntimeError"
    sessions.update_booking_draft_cas.assert_called_once()


def test_patient_data_reaches_confirmation_without_creating_before_human_approval():
    class SpecialtyOutput:
        specialties = [{"specialty_id": "SP-CARD-GEN", "name": "Tim mạch tổng quát"}]

    class DoctorOutput:
        doctors = [{"doctor_id": "DOC-001", "full_name": "Nguyễn Minh An"}]

    class SlotOutput:
        slots = [{"slot_id": "SL-001", "doctor_id": "DOC-001", "date": "2026-08-03", "time": "08:00"}]

    tools = MagicMock()
    tools.get_specialty_list.return_value = SpecialtyOutput()
    tools.get_doctor_list.return_value = DoctorOutput()
    tools.get_available_slots.return_value = SlotOutput()
    sessions = MagicMock()
    sessions.load_booking_draft.return_value = BookingFlowStateDTO(
        session_id="patient-confirmation",
        flow_id="flow-patient-confirmation",
        version=4,
        status="collecting",
        current_step="patient_data",
        step="patient_data",
        visit_type="first_visit",
        specialty_id="SP-CARD-GEN",
        doctor_id="DOC-001",
        slot_id="SL-001",
    )
    sessions.update_booking_draft_cas.return_value = True
    tool_request = AIMessage(content="", tool_calls=[{
        "name": "continue_appointment_booking",
        "args": {
            "patient_name": "Nguyễn Văn A",
            "patient_phone": "0901234567",
            "patient_dob": "1990-01-01",
            "has_insurance": True,
            "visit_reason": "Khám định kỳ",
        },
        "id": "patient-data",
    }])

    result = tool_node(
        {
            "messages": [HumanMessage(content="Tôi là Nguyễn Văn A, sinh 01/01/1990, số 0901234567, có BHYT, khám định kỳ"), tool_request],
            "booking_result": None,
            "booking_step": "patient_data",
            "booking_choices": [],
            "observations": [],
            "appointment_observations": [],
            "call_count": 0,
        },
        {"configurable": {
            "thread_id": "patient-confirmation",
            "current_user_message": "Tôi là Nguyễn Văn A, sinh 01/01/1990, số 0901234567, có BHYT, khám định kỳ",
            "appointment_tools": tools,
            "session_service": sessions,
        }},
    )

    booking_result = result["booking_result"]
    assert booking_result["outcome"] == "confirmation_required"
    assert booking_result["conversation_state"]["current_step"] == "confirmation"
    assert booking_result["suggested_actions"] == [{"type": "confirm", "label": "Xác nhận đặt lịch"}]
    assert "Nguyễn Văn A" in booking_result["message"]
    tools.create_appointment.assert_not_called()
# === TASK:WP-305:END ===
