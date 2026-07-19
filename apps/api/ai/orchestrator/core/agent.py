# === TASK:WP-302:START ===
import os
import re
import time
import json
import logging
from typing import List, Dict, Any, Optional, TypedDict, Literal
from pathlib import Path

from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from packages.contracts.dto import SafetyDecisionDTO, RuleEvidenceDTO, SearchResultDTO, CitationDTO, SearchCandidateDTO
from apps.api.capabilities.emergency.prefilter import (
    has_safety_signal,
    is_clear_non_risk,
    load_emergency_configs,
    match_rules,
    validate_configs,
)
from apps.api.ai.providers.openai import OpenAIProvider
from apps.api.ai.rag import (
    citation_validation_issues,
    map_citations_to_response,
    render_citation_markers,
    search_hospital_information,
    supported_response_text,
)
from apps.api.foundation.appointments.tools.service import (
    GetAvailableSlotsInput,
    GetDoctorListInput,
    GetSpecialtyListInput,
    LookupAppointmentInput,
)
from apps.api.ai.orchestrator.appointment_booking.pipeline import (
    AppointmentBookingPipeline,
    AppointmentBookingRequest,
)

ROOT = Path(__file__).resolve().parents[5]
BUDGET_EXHAUSTED_MESSAGE = "Xin lỗi, thời gian thực thi của tác vụ đã vượt quá giới hạn cho phép."
OUT_OF_SCOPE_MESSAGE = (
    "Xin lỗi, tôi chỉ hỗ trợ đặt lịch khám và thông tin chính thức về khám chữa bệnh, "
    "BHYT, giá dịch vụ, giờ làm việc, bác sĩ và chuyên khoa tại Bệnh viện Tim Hà Nội."
)
logger = logging.getLogger("uvicorn.error")


def _trace(config: RunnableConfig, event: str, *, started_at: Optional[float] = None, **fields: Any) -> None:
    """Emit PII-safe, grep-friendly runtime timing events."""
    configurable = config.get("configurable", {}) if config else {}
    payload = {
        "event": event,
        "session_id": configurable.get("thread_id"),
        **fields,
    }
    if started_at is not None:
        payload["elapsed_ms"] = round((time.monotonic() - started_at) * 1000, 2)
    logger.info("agent_trace %s", json.dumps(payload, ensure_ascii=False, default=str))


def deadline_remaining(state: Dict[str, Any]) -> Optional[float]:
    deadline = state.get("deadline_timestamp")
    if not deadline:
        return None
    return deadline - time.time()

# Define state structure
class AgentState(TypedDict):
    messages: List[BaseMessage]
    safety_result: Optional[Dict[str, Any]]
    clarification_count: int
    observations: List[Dict[str, Any]]
    appointment_observations: List[Dict[str, Any]]
    citations: List[Dict[str, Any]]
    call_fingerprints: List[str]
    max_tool_calls: int
    call_count: int
    elapsed_time_seconds: float
    deadline_timestamp: float
    final_response: Optional[str]
    degradation_status: Dict[str, Any]
    repair_attempted: bool
    grounding_retry_reasons: List[str]
    booking_result: Optional[Dict[str, Any]]
    booking_flow_ref: Optional[str]
    booking_flow_version: int
    booking_choices: List[Dict[str, Any]]
    booking_step: Optional[str]
    force_search_required: bool
    current_action: Optional[str]


ActionType = Literal[
    "start_booking",
    "advance_booking",
    "read_operational_data",
    "search_knowledge",
    "lookup_appointment",
    "clarify",
]


def _latest_user_text(state: Dict[str, Any]) -> str:
    return next((
        str(message.content).strip()
        for message in reversed(state.get("messages", []))
        if isinstance(message, HumanMessage)
    ), "")


def classify_action(state: Dict[str, Any]) -> ActionType:
    """Classify side-effect class; this policy never mutates booking state."""
    text = _latest_user_text(state).lower()
    booking_step = state.get("booking_step")
    if any(token in text for token in ("tra cứu lịch", "mã lịch hẹn", "tình trạng lịch hẹn")):
        return "lookup_appointment"
    explicit_booking_request = any(token in text for token in ("đặt lịch khám bệnh", "bắt đầu đặt lịch", "đặt lịch mới"))
    if explicit_booking_request and not any(token in text for token in ("tiếp tục", "quay lại")):
        return "start_booking"
    operational_question = any(token in text for token in (
        "danh sách bác sĩ", "có những bác sĩ", "bác sĩ nào", "lịch ngày nào",
        "lịch trống", "khung giờ nào", "chuyên khoa nào",
    ))
    if operational_question:
        return "read_operational_data"
    if booking_step and booking_step not in {"created", "cancelled"}:
        knowledge_interruption = any(token in text for token in (
            "thủ tục", "giấy tờ", "quy định", "chi phí", "giá bao nhiêu",
            "cần gì", "cần mang", "được hưởng", "được không",
        )) or text.endswith("?")
        if knowledge_interruption and any(token in text for token in ("bhyt", "bảo hiểm", "giá", "chi phí", "quy định", "giấy tờ")):
            return "search_knowledge"
        if any(token in text for token in ("hủy", "cancel", "khám lần đầu", "lần đầu", "tái khám", "chọn", "xác nhận")):
            return "advance_booking"
        if booking_step == "patient_data" and bool(text):
            return "advance_booking"
        for choice in state.get("booking_choices", []):
            if not isinstance(choice, dict):
                continue
            searchable_values = {
                str(choice.get(key) or "").strip().lower()
                for key in (
                    "specialty_id", "doctor_id", "slot_id", "name", "full_name",
                    "time", "date",
                )
            }
            if any(value and value in text for value in searchable_values):
                return "advance_booking"
        if booking_step in {"specialty", "doctor", "slot"} and text:
            # These steps accept a user selection only through the stateful
            # tool. The deterministic coordinator will reject an unknown ID
            # without advancing the draft.
            return "advance_booking"
        return "clarify"
    if any(token in text for token in ("đặt lịch", "đăng ký khám", "book appointment")):
        return "start_booking"
    if any(token in text for token in ("thủ tục", "bhyt", "bảo hiểm", "giá", "chi phí", "quy định", "giấy tờ")):
        return "search_knowledge"
    return "search_knowledge" if len(text.split()) >= 3 else "clarify"


def _allowed_tools_for_action(action: ActionType) -> List[Any]:
    if action in {"start_booking", "advance_booking"}:
        return [continue_appointment_booking]
    if action == "search_knowledge":
        return [search_hospital_information_tool]
    if action == "lookup_appointment":
        return [lookup_appointment]
    if action == "read_operational_data":
        return [get_specialty_list, get_doctor_list, get_available_slots]
    return []


# Define LangChain tools with RunnableConfig access to connection context
@tool
def search_hospital_information_tool(query: str, config: RunnableConfig) -> Dict[str, Any]:
    """Search approved hospital documents for policies, procedures, services, or prices. Never use this tool to start/continue booking or list live doctors/slots."""
    configurable = config.get("configurable", {})
    cur = configurable.get("db_cursor")
    embedder = configurable.get("embedder")

    # Run the retrieval engine
    result = search_hospital_information(
        cur=cur,
        query=query,
        embedder=embedder,
        reranker_api_key=configurable.get("jina_api_key"),
        reranker_model=os.environ.get("RERANKER_MODEL"),
        reranker_base_url=os.environ.get("RERANKER_BASE_URL", "https://api.jina.ai/v1/rerank"),
        reranker_timeout=float(os.environ.get("RERANKER_TIMEOUT_SECONDS", "5.0")),
        top_n=configurable.get("top_n", 5),
        rrf_k=configurable.get("rrf_k", 60),
        trace_id=configurable.get("thread_id"),
    )
    return result.to_dict()


def _appointment_dependencies(config: RunnableConfig):
    configurable = config.get("configurable", {})
    tools = configurable.get("appointment_tools")
    sessions = configurable.get("session_service")
    session_id = configurable.get("thread_id")
    if tools is None or sessions is None or not session_id:
        raise RuntimeError("Appointment booking dependencies are unavailable")
    return tools, sessions, str(session_id)


@tool
def get_specialty_list(config: RunnableConfig, active_only: bool = True) -> Dict[str, Any]:
    """Read-only: list live hospital specialties without starting or changing a booking."""
    tools, _, _ = _appointment_dependencies(config)
    result = tools.get_specialty_list(GetSpecialtyListInput(active_only=active_only))
    return {"outcome": "information", "reference_type": "specialty", "items": result.specialties, "message": "Danh sách chuyên khoa hiện có."}


@tool
def get_doctor_list(specialty_id: str, config: RunnableConfig, active_only: bool = True) -> Dict[str, Any]:
    """Read-only: list live doctors for a canonical specialty ID without changing a booking draft."""
    tools, _, _ = _appointment_dependencies(config)
    result = tools.get_doctor_list(GetDoctorListInput(specialty_id=specialty_id, active_only=active_only))
    return {"outcome": "information", "reference_type": "doctor", "items": result.doctors, "message": "Danh sách bác sĩ thuộc chuyên khoa."}


@tool
def get_available_slots(doctor_id: str, config: RunnableConfig, date_from: Optional[str] = None, date_to: Optional[str] = None) -> Dict[str, Any]:
    """Read-only: list live available slots for a canonical doctor ID without changing a booking draft."""
    tools, _, _ = _appointment_dependencies(config)
    result = tools.get_available_slots(GetAvailableSlotsInput(doctor_id=doctor_id, date_from=date_from, date_to=date_to))
    return {"outcome": "information", "reference_type": "slot", "items": result.slots, "message": "Các khung giờ hiện còn trống."}


@tool
def lookup_appointment(appointment_id: str, config: RunnableConfig) -> Dict[str, Any]:
    """Read-only: look up an existing appointment using its exact appointment ID."""
    tools, _, _ = _appointment_dependencies(config)
    result = tools.lookup_appointment(LookupAppointmentInput(appointment_id=appointment_id))
    return {"outcome": "found", "appointment": result.to_dict() if hasattr(result, "to_dict") else result}


@tool
def continue_appointment_booking(
    config: RunnableConfig,
    visit_type: Optional[str] = None,
    specialty_id: Optional[str] = None,
    doctor_id: Optional[str] = None,
    slot_id: Optional[str] = None,
    patient_name: Optional[str] = None,
    patient_phone: Optional[str] = None,
    patient_dob: Optional[str] = None,
    has_insurance: Optional[bool] = None,
    visit_reason: Optional[str] = None,
    confirmed: bool = False,
    cancelled: bool = False,
    restart_booking: bool = False,
) -> Dict[str, Any]:
    """Start or advance the canonical booking draft. Use with no fields for an explicit new booking request; set confirmed only after explicit confirmation."""
    tools, sessions, session_id = _appointment_dependencies(config)
    if confirmed:
        latest_user_message = str(config.get("configurable", {}).get("current_user_message") or "").strip().lower()
        if latest_user_message not in {"confirm", "confirmed", "yes", "đồng ý", "xac nhan", "xác nhận"}:
            return {
                "outcome": "confirmation_required",
                "message": "Vui lòng xác nhận rõ ràng bản tóm tắt hiện tại trước khi tạo lịch.",
            }
    state = sessions.load_booking_draft(session_id)
    if restart_booking and state is not None:
        sessions.clear_booking_draft(session_id)
        state = None
    form_data = {
        key: value
        for key, value in {
            "visit_type": visit_type,
            "specialty_id": specialty_id,
            "doctor_id": doctor_id,
            "slot_id": slot_id,
            "patient_name": patient_name,
            "patient_phone": patient_phone,
            "patient_dob": patient_dob,
            "has_insurance": has_insurance,
            "visit_reason": visit_reason,
            "confirmed": confirmed,
            "cancelled": cancelled,
        }.items()
        if value is not None
    }
    if state is None and not cancelled:
        # Starting a flow is its own transition. Ignore fields the model may
        # have eagerly extracted from the same utterance.
        form_data = {}
    elif state is not None and not confirmed and not cancelled:
        # The agent may extract several values from one utterance, but only the
        # canonical field group for the current step may reach the coordinator.
        allowed_by_step = {
            "visit_type": {"visit_type"},
            "specialty": {"specialty_id"},
            "doctor": {"doctor_id"},
            "slot": {"slot_id"},
            "patient_data": {"patient_name", "patient_phone", "patient_dob", "has_insurance", "visit_reason"},
            "confirmation": set(),
        }
        allowed_fields = allowed_by_step.get(state.current_step, set())
        form_data = {key: value for key, value in form_data.items() if key in allowed_fields}
    if state is not None and confirmed:
        form_data.update({
            "expected_version": state.version,
            "confirmation_fingerprint": state.confirmation_fingerprint,
            "idempotency_key": state.idempotency_key,
        })
    response = AppointmentBookingPipeline(appointment_tools=tools).execute(
        AppointmentBookingRequest(
            request_id=f"agent-{time.time_ns()}",
            session_id=session_id,
            message="confirm" if confirmed else ("cancel" if cancelled else ""),
            state=state,
            form_data=form_data,
        )
    )
    next_state = response.conversation_state
    if response.outcome == "created" and response.appointment:
        sessions.close_booking_draft(session_id, response.appointment["appointment_id"])
    elif next_state.status == "cancelled":
        sessions.clear_booking_draft(session_id)
    elif state is None:
        sessions.create_booking_draft(session_id, next_state)
    elif not sessions.update_booking_draft_cas(session_id, next_state, state.version):
        return {"outcome": "conflict", "message": "Booking state changed; please retry from the latest state."}
    result = response.to_dict()
    result["booking_flow_ref"] = next_state.flow_id
    result["booking_flow_version"] = next_state.version
    # Deterministically follow workflow dependencies after a validated choice.
    # The model does not decide which list comes next.
    try:
        if response.outcome != "created" and next_state.current_step == "specialty":
            choices = tools.get_specialty_list(GetSpecialtyListInput(active_only=True)).specialties
            result.update({"outcome": "choices", "choice_type": "specialty", "items": choices})
        elif response.outcome != "created" and next_state.current_step == "doctor" and next_state.specialty_id:
            choices = tools.get_doctor_list(
                GetDoctorListInput(specialty_id=next_state.specialty_id, active_only=True)
            ).doctors
            result.update({
                "outcome": "choices",
                "choice_type": "doctor",
                "items": choices,
                "message": "Vui lòng chọn một bác sĩ từ danh sách hợp lệ.",
            })
        elif response.outcome != "created" and next_state.current_step == "slot" and next_state.doctor_id:
            choices = tools.get_available_slots(
                GetAvailableSlotsInput(doctor_id=next_state.doctor_id)
            ).slots
            result.update({
                "outcome": "choices",
                "choice_type": "slot",
                "items": choices,
                "message": "Vui lòng chọn một khung giờ còn trống.",
            })
    except Exception as exc:
        # The canonical transition has already been persisted. A temporary
        # reference-data failure must not turn it into a generic tool failure
        # or make the user repeat an earlier answer.
        result.update({
            "outcome": "collecting",
            "choice_type": next_state.current_step,
            "items": [],
            "choice_load_error": type(exc).__name__,
            "message": (
                f"Đã lưu bước vừa rồi. Hiện chưa tải được dữ liệu cho bước {next_state.current_step}; "
                "vui lòng thử tải lại danh sách."
            ),
        })
    return result


def has_safety_hint(text: str) -> bool:
    hints = ["đau", "sốt", "mệt", "khó chịu", "nôn", "chảy máu", "co giật", "ho", "ngất", "khó thở"]
    text_lower = text.lower()
    return any(h in text_lower for h in hints)


# Node 1: Direct rule matching (no LLM, no DB)
def direct_safety_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    started_at = time.monotonic()
    messages = state.get("messages", [])
    if not messages:
        return {}

    pending_caution = (
        state.get("safety_result")
        if (state.get("safety_result") or {}).get("risk") == "CAUTION"
        and state.get("clarification_count", 0) > 0
        else None
    )
    sanitized_messages = [
        message
        for message in messages
        if not isinstance(message, ToolMessage)
        and not (isinstance(message, AIMessage) and getattr(message, "tool_calls", None))
        and not (isinstance(message, AIMessage) and "[[" in str(message.content))
    ]
    turn_reset = {
        "messages": sanitized_messages,
        "safety_result": pending_caution,
        "observations": [],
        "appointment_observations": [],
        "citations": [],
        "call_fingerprints": [],
        "call_count": 0,
        "elapsed_time_seconds": 0.0,
        "final_response": None,
        "degradation_status": {},
        "repair_attempted": False,
        "grounding_retry_reasons": [],
        "booking_result": None,
        "booking_flow_ref": state.get("booking_flow_ref"),
        "booking_flow_version": state.get("booking_flow_version", 0),
        "booking_choices": list(state.get("booking_choices", [])),
        "booking_step": state.get("booking_step"),
        "force_search_required": False,
        "current_action": None,
    }

    last_msg = messages[-1].content
    rules, _, _ = load_emergency_configs()

    if pending_caution is not None:
        if state.get("booking_step") and not has_safety_hint(str(last_msg)):
            turn_reset["safety_result"] = {
                "risk": "LOW",
                "source": "booking_context",
                "reason_code": "ROUTINE_BOOKING_TURN",
                "evidence_spans": [],
            }
        else:
            return turn_reset

    if is_clear_non_risk(last_msg, rules):
        turn_reset["safety_result"] = {
            "risk": "LOW",
            "source": "local_clear_non_risk",
            "reason_code": "NO_SAFETY_SIGNAL_OR_REFERENCE_CONTEXT",
            "evidence_spans": [],
        }
        _trace(config, "safety.local.complete", started_at=started_at, risk="LOW")
        return turn_reset

    evidence = match_rules(last_msg, rules)
    if evidence:
        turn_reset["safety_result"] = {
                "risk": "HIGH",
                "source": "direct_rule",
                "rule_id": evidence.rule_id,
                "evidence_spans": [evidence.evidence_span]
        }
    elif state.get("booking_step") and not has_safety_hint(str(last_msg)):
        # Routine booking answers such as "Khám lần đầu" must not be diverted
        # into semantic emergency clarification. Explicit symptom hints still
        # pass through the semantic evaluator; direct emergency rules won above.
        turn_reset["safety_result"] = {
            "risk": "LOW",
            "source": "booking_context",
            "reason_code": "ROUTINE_BOOKING_TURN",
            "evidence_spans": [],
        }
    _trace(config, "safety.local.complete", started_at=started_at, risk=(turn_reset.get("safety_result") or {}).get("risk"))
    return turn_reset


# Node 2: Semantic safety evaluation (OpenAI structured outputs)
def semantic_safety_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    if state.get("safety_result") is not None:
        return {}

    messages = state.get("messages", [])
    if not messages:
        return {}

    last_msg = messages[-1].content
    provider = OpenAIProvider(api_key=config.get("configurable", {}).get("openai_api_key"))
    started_at = time.monotonic()
    _trace(config, "llm.safety.start", model=os.environ.get("SAFETY_MODEL", "configured"))

    try:
        decision = provider.evaluate_safety(
            last_msg,
            trace_id=config.get("configurable", {}).get("thread_id"),
        )
        result = decision.to_dict()
        _trace(config, "llm.safety.complete", started_at=started_at, risk=result.get("risk"))
        return {"safety_result": result}
    except Exception as exc:
        _trace(config, "llm.safety.error", started_at=started_at, error_type=type(exc).__name__)
        # If evaluator fails/times out, fall back to CAUTION if caution-hinted, else LOW
        rules, _, _ = load_emergency_configs()
        if has_safety_signal(last_msg, rules):
            return {
                "safety_result": {
                    "risk": "CAUTION",
                    "source": "fallback",
                    "clarification_id": "CLAR-EMERGENCY-001",
                    "reason_code": "EVALUATOR_FAILURE"
                }
            }
        return {"safety_result": {"risk": "LOW"}}


# Safety routing edge
def route_safety(state: AgentState) -> str:
    result = state.get("safety_result") or {}
    risk = result.get("risk", "LOW")
    if risk == "HIGH":
        return "high_response"
    elif risk == "CAUTION":
        return "caution_node"
    return "llm_node"


# Node 3: HIGH response node
def high_response_node(state: AgentState) -> Dict[str, Any]:
    msg = "CẢNH BÁO NGUY HIỂM: Bạn đang báo cáo một tình huống y tế khẩn cấp. Vui lòng gọi ngay số 115 hoặc di chuyển đến cơ sở y tế gần nhất ngay lập tức. Không tiếp tục chat."
    return {
        "final_response": msg,
        "messages": state.get("messages", []) + [AIMessage(content=msg)]
    }


# Node 4: CAUTION clarification node
def caution_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    count = state.get("clarification_count", 0)
    messages = state.get("messages", [])

    if count == 0:
        question = "Bạn có đang gặp phải tình trạng nguy kịch hoặc cấp cứu khẩn cấp không? Vui lòng trả lời CÓ hoặc KHÔNG."
        return {
            "clarification_count": 1,
            "final_response": question,
            "messages": messages + [AIMessage(content=question)]
        }

    # Re-evaluate clarification answer
    import re
    last_ans = messages[-1].content.strip().lower()
    words = re.findall(r'\b\w+\b', last_ans)

    # Heuristics for Vietnamese clarification reply
    if any(w in words for w in ["có", "phải", "đúng", "yes", "co"]):
        return {
            "safety_result": {"risk": "HIGH"},
            "clarification_count": count + 1
        }
    elif any(w in words for w in ["không", "khong", "no"]):
        return {
            "safety_result": {"risk": "LOW"},
            "clarification_count": count + 1
        }
    else:
        # Unresolved caution fallback message
        fallback = "CHÚ Ý: Câu hỏi của bạn có thể chứa thông tin nhạy cảm liên quan đến an toàn sức khỏe. Chúng tôi cần tạm ngừng các tác vụ thông thường. Vui lòng liên hệ hotline hỗ trợ nếu cần."
        return {
            "final_response": fallback,
            "messages": messages + [AIMessage(content=fallback)],
            "clarification_count": count + 1
        }


# Edge routing for caution clarification
def route_caution(state: AgentState) -> str:
    risk = (state.get("safety_result") or {}).get("risk", "LOW")
    if risk == "HIGH":
        return "high_response_node"
    elif risk == "LOW":
        return "llm_node"
    return END


# Node 5: General LLM tool-calling node
def llm_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    # Check max tool call budget
    max_calls = state.get("max_tool_calls", 5)
    call_count = state.get("call_count", 0)
    remaining = deadline_remaining(state)
    if call_count >= max_calls or (remaining is not None and remaining <= 0):
        fallback = BUDGET_EXHAUSTED_MESSAGE
        return {
            "final_response": fallback,
            "messages": state.get("messages", []) + [AIMessage(content=fallback)],
            "degradation_status": {
                **state.get("degradation_status", {}),
                "terminal_failure": "execution_budget_exhausted",
            },
        }

    provider_config = config.get("configurable", {})
    action = classify_action(state)
    booking_step = state.get("booking_step")
    tools = _allowed_tools_for_action(action)
    search_observation_ready = action == "search_knowledge" and bool(state.get("observations"))

    # System instruction prompt loaded from file
    prompt_path = ROOT / "config" / "prompts" / "hospital-agent.md"
    system_instruction = prompt_path.read_text(encoding="utf-8")

    input_msgs = [SystemMessage(content=system_instruction)] + state.get("messages", [])
    if state.get("booking_choices"):
        input_msgs.append(SystemMessage(content=(
            "Validated appointment choices from the immediately preceding booking step. "
            "Resolve the user's selection only against these values; never invent an ID:\n"
            + json.dumps(state["booking_choices"], ensure_ascii=False)
        )))
    if booking_step:
        input_msgs.append(SystemMessage(content=(
            f"The canonical booking workflow is currently at step '{booking_step}'. "
            "If the latest user turn answers or changes the booking, use continue_appointment_booking "
            "to extract only the field required by this step. If it is an informational interruption, "
            "use a read-only search/list/lookup tool and leave the booking draft and current step unchanged. "
            "If the user's meaning is ambiguous, ask one clarification and do not call a tool."
        )))
    if search_observation_ready:
        input_msgs.append(SystemMessage(content=(
            "The current turn already has a validated hospital knowledge search result. "
            "Do not call search again. Answer only from the returned evidence and cite exact "
            "chunk IDs as [[chunk_id]]."
        )))

    # If this is a repair attempt, append the repair prompt
    if state.get("repair_attempted", False) and not state.get("final_response"):
        if state.get("appointment_observations"):
            repair_instruction = (
                "VERIFICATION FAILED: the response used an appointment identifier absent from the "
                "current read-only appointment tool result. Rewrite using only returned entities; "
                "do not change or advance the active booking draft."
            )
        elif not state.get("observations"):
            repair_instruction = (
                "VERIFICATION FAILED: there are no search observations for the current turn. "
                "You MUST call search_hospital_information now using the user's current question before answering."
            )
        else:
            repair_instruction = (
                "VERIFICATION FAILED: one or more factual lines had a missing/unknown [[chunk_id]] citation, "
                "or used a number absent from the cited evidence. Rewrite once using only observed chunk IDs. "
                "End every factual sentence or bullet with one or more [[chunk_id]] markers."
            )
        input_msgs.append(SystemMessage(content=repair_instruction))

    candidates = provider_config.get("llm_candidates") or [{
        "model": provider_config.get("llm_model") or os.environ.get("AGENT_MODEL", "gpt-5-mini"),
        "api_key": provider_config.get("llm_api_key") or provider_config.get("openai_api_key"),
        "base_url": provider_config.get("llm_base_url"),
        "provider": "legacy",
    }]
    started_at = time.monotonic()
    response = None
    last_llm_error = None
    for candidate in candidates:
        llm_options = {
            "model": candidate.get("model"),
            "openai_api_key": candidate.get("api_key"),
            "temperature": 0.0,
            "max_retries": 0,
        }
        if candidate.get("base_url"):
            llm_options["base_url"] = candidate["base_url"]
        if remaining is not None:
            llm_options["timeout"] = max(0.1, remaining)
        llm = ChatOpenAI(**llm_options)
        if tools:
            if search_observation_ready:
                # Keep the tool schema in the prompt while explicitly disabling
                # another invocation. Without this guard, a single-tool action
                # forces search on every graph loop and exhausts the tool budget.
                try:
                    llm_with_tools = llm.bind_tools(tools, tool_choice="none")
                except TypeError:
                    llm_with_tools = llm.bind_tools(tools)
            else:
                forced_tool = (
                    tools[0].name
                    if len(tools) == 1
                    and action not in {"read_operational_data", "search_knowledge"}
                    else None
                )
                if forced_tool:
                    try:
                        llm_with_tools = llm.bind_tools(tools, tool_choice=forced_tool)
                    except TypeError:
                        llm_with_tools = llm.bind_tools(tools)
                else:
                    llm_with_tools = llm.bind_tools(tools)
        else:
            llm_with_tools = llm
        attempt_started_at = time.monotonic()
        try:
            response = llm_with_tools.invoke(input_msgs)
            _trace(config, "llm.agent.attempt.complete", started_at=attempt_started_at, provider=candidate.get("provider"), tool_call_count=len(response.tool_calls or []))
            break
        except Exception as exc:
            last_llm_error = exc
            _trace(config, "llm.agent.attempt.error", started_at=attempt_started_at, provider=candidate.get("provider"), error_type=type(exc).__name__)
    if response is None:
        fallback = "Tạm thời không thể xử lý yêu cầu do dịch vụ ngôn ngữ không khả dụng. Vui lòng thử lại sau."
        _trace(config, "fallback", started_at=started_at, component="agent_llm", reason="providers_exhausted", error_type=type(last_llm_error).__name__ if last_llm_error else None)
        return {
            "final_response": fallback,
            "messages": state.get("messages", []) + [AIMessage(content=fallback)],
            "current_action": action,
            "degradation_status": {
                **state.get("degradation_status", {}),
                "terminal_failure": "providers_exhausted",
            },
        }
    if search_observation_ready and response.tool_calls:
        # Some OpenAI-compatible providers may ignore tool_choice="none". Do
        # not execute another expensive retrieval; let grounding verification
        # repair or abstain from the text response instead.
        _trace(
            config,
            "action_policy.reject",
            action=action,
            rejected_tools=[call.get("name") for call in response.tool_calls],
            reason="search_already_completed",
        )
        response = AIMessage(content=response.content or "")
    elapsed = state.get("elapsed_time_seconds", 0.0) + (time.monotonic() - started_at)
    allowed_tool_names = {candidate.name for candidate in tools}
    invalid_tool_calls = [
        call for call in (response.tool_calls or [])
        if call.get("name") not in allowed_tool_names
    ]
    if invalid_tool_calls:
        _trace(config, "action_policy.reject", action=action, rejected_tools=[call.get("name") for call in invalid_tool_calls])
        if action == "start_booking":
            response = AIMessage(content="", tool_calls=[{
                "name": "continue_appointment_booking",
                "args": {},
                "id": f"policy-start-{time.time_ns()}",
                "type": "tool_call",
            }])
        else:
            clarification = "Vui lòng xác nhận bạn muốn tiếp tục bước đặt lịch hiện tại hay chỉ cần xem thông tin."
            return {
                "final_response": clarification,
                "messages": state.get("messages", []) + [AIMessage(content=clarification)],
                "elapsed_time_seconds": elapsed,
                "current_action": "clarify",
            }
    elif action == "start_booking" and not response.tool_calls:
        response = AIMessage(content="", tool_calls=[{
            "name": "continue_appointment_booking",
            "args": {},
            "id": f"policy-start-{time.time_ns()}",
            "type": "tool_call",
        }])
    _trace(
        config,
        "llm.agent.complete",
        started_at=started_at,
        tool_call_count=len(response.tool_calls or []),
        tool_names=[call.get("name") for call in (response.tool_calls or [])],
    )

    # Validate duplicate tool call prevention
    if response.tool_calls:
        if call_count + len(response.tool_calls) > max_calls:
            fallback = BUDGET_EXHAUSTED_MESSAGE
            return {
                "final_response": fallback,
                "elapsed_time_seconds": elapsed,
                "messages": state.get("messages", []) + [AIMessage(content=fallback)],
                "degradation_status": {
                    **state.get("degradation_status", {}),
                    "terminal_failure": "execution_budget_exhausted",
                },
            }
        seen = state.get("call_fingerprints", [])
        new_fingerprints = []
        for tc in response.tool_calls:
            fingerprint = f"{tc['name']}:{str(tc['args'])}"
            if fingerprint in seen:
                fallback = "Xin lỗi, thời gian thực thi của tác vụ đã vượt quá giới hạn cho phép do vòng lặp."
                return {
                    "final_response": fallback,
                    "messages": state.get("messages", []) + [AIMessage(content=fallback)],
                    "degradation_status": {
                        **state.get("degradation_status", {}),
                        "terminal_failure": "tool_loop_detected",
                    },
                }
            new_fingerprints.append(fingerprint)

        return {
            "messages": state.get("messages", []) + [response],
            "call_fingerprints": seen + new_fingerprints,
            "elapsed_time_seconds": elapsed,
            "current_action": action,
        }

    return {
        "messages": state.get("messages", []) + [response],
        "elapsed_time_seconds": elapsed,
        "current_action": action,
    }


# Edge routing for LLM output (tools vs verification)
def route_llm(state: AgentState) -> str:
    last_msg = state.get("messages", [])[-1]
    if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
        return "tool_node"
    return "grounding_verification_node"


# Node 6: Tool execution node
def tool_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    last_msg = state.get("messages", [])[-1]
    tool_calls = last_msg.tool_calls

    new_messages = []
    observations = list(state.get("observations", []))
    appointment_observations = list(state.get("appointment_observations", []))
    booking_result = state.get("booking_result")
    booking_choices = list(state.get("booking_choices", []))
    call_count = state.get("call_count", 0)

    for tc in tool_calls:
        remaining = deadline_remaining(state)
        if remaining is not None and remaining <= 0:
            fallback = BUDGET_EXHAUSTED_MESSAGE
            return {
                "final_response": fallback,
                "messages": state.get("messages", []) + [AIMessage(content=fallback)],
                "observations": observations,
                "call_count": call_count,
                "degradation_status": {
                    **state.get("degradation_status", {}),
                    "terminal_failure": "execution_budget_exhausted",
                },
            }
        name = tc["name"]
        args = tc["args"]
        tc_id = tc["id"]
        tool_started_at = time.monotonic()
        _trace(config, "tool.start", tool=name, call_count=call_count)

        try:
            if name == "search_hospital_information_tool":
                # Preserve exact service names and codes from the user's latest turn.
                latest_user_query = next(
                    (
                        message.content
                        for message in reversed(state.get("messages", [])[:-1])
                        if isinstance(message, HumanMessage) and isinstance(message.content, str)
                    ),
                    "",
                ).strip()
                search_query = latest_user_query or args.get("query")
                res = search_hospital_information_tool.invoke({"query": search_query}, config)
                observations.append(res)
                new_messages.append(ToolMessage(content=str(res), tool_call_id=tc_id))
            elif name in {
                "get_specialty_list",
                "get_doctor_list",
                "get_available_slots",
                "lookup_appointment",
                "continue_appointment_booking",
            }:
                appointment_tool = {
                    "get_specialty_list": get_specialty_list,
                    "get_doctor_list": get_doctor_list,
                    "get_available_slots": get_available_slots,
                    "lookup_appointment": lookup_appointment,
                    "continue_appointment_booking": continue_appointment_booking,
                }[name]
                call_args = dict(args)
                if name == "continue_appointment_booking" and state.get("current_action") == "start_booking":
                    call_args["restart_booking"] = True
                res = appointment_tool.invoke(call_args, config)
                if name == "continue_appointment_booking":
                    booking_result = res
                    booking_choices = list(res.get("items") or [])
                else:
                    # Discovery/status calls are authoritative observations but
                    # cannot create, advance, or alter a booking draft.
                    appointment_observations.append({"tool": name, "result": res})
                new_messages.append(ToolMessage(content=str(res), tool_call_id=tc_id))
            else:
                raise ValueError(f"Unsupported tool call: {name}")
        except Exception as exc:
            _trace(config, "tool.error", started_at=tool_started_at, tool=name, error_type=type(exc).__name__, fallback="safe_tool_error")
            res = {"outcome": "error", "error_type": type(exc).__name__, "message": "Công cụ tạm thời không khả dụng. Vui lòng thử lại."}
            new_messages.append(ToolMessage(content=str(res), tool_call_id=tc_id))
            if name == "continue_appointment_booking":
                booking_result = res
        call_count += 1
        _trace(
            config,
            "tool.complete",
            started_at=tool_started_at,
            tool=name,
            outcome=(res or {}).get("outcome") if isinstance(res, dict) else "success",
            item_count=len((res or {}).get("items", [])) if isinstance(res, dict) else None,
        )

    return {
        "messages": state.get("messages", []) + new_messages,
        "observations": observations,
        "appointment_observations": appointment_observations,
        "booking_result": booking_result,
        "booking_flow_ref": (booking_result or {}).get("booking_flow_ref", state.get("booking_flow_ref")),
        "booking_flow_version": (booking_result or {}).get("booking_flow_version", state.get("booking_flow_version", 0)),
        "booking_choices": booking_choices,
        "booking_step": (
            ((booking_result or {}).get("conversation_state") or {}).get("current_step")
            or ((booking_result or {}).get("choice_type"))
            or state.get("booking_step")
        ),
        "call_count": call_count
    }


def route_tool(state: AgentState) -> str:
    if state.get("final_response"):
        return END
    if state.get("booking_result"):
        return "grounding_verification_node"
    return "llm_node"


def _appointment_observation_ids(observations: List[Dict[str, Any]]) -> set:
    """Collect canonical operational IDs from read-only tool results."""
    identifiers = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            for key, item in value.items():
                if key.endswith("_id") and isinstance(item, str):
                    identifiers.add(item)
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(observations)
    return identifiers


# Node 7: Grounding verification node
def grounding_verification_node(state: AgentState, config: Optional[RunnableConfig] = None) -> Dict[str, Any]:
    config = config or {"configurable": {}}
    last_msg = state.get("messages", [])[-1]
    response_text = last_msg.content

    if str(response_text).strip() == OUT_OF_SCOPE_MESSAGE:
        _trace(config, "scope.refused", action=state.get("current_action"))
        return {
            "final_response": OUT_OF_SCOPE_MESSAGE,
            "citations": [],
            "degradation_status": {
                **state.get("degradation_status", {}),
                "scope_refused": True,
            },
        }

    if state.get("booking_result"):
        booking_result = state["booking_result"]
        appointment = booking_result.get("appointment") or {}
        detail = appointment.get("detail")
        rendered = booking_result.get("message", "")
        choices = booking_result.get("items") or []
        if choices:
            choice_lines = []
            for item in choices[:10]:
                identifier = item.get("specialty_id") or item.get("doctor_id") or item.get("slot_id") or ""
                label = item.get("name") or item.get("full_name") or " ".join(
                    part for part in (item.get("date"), item.get("time"), item.get("room")) if part
                )
                choice_lines.append(f"- {label} ({identifier})" if identifier else f"- {label}")
            rendered = f"{rendered}\n\n" + "\n".join(choice_lines)
        if appointment.get("appointment_id"):
            rendered = (
                f"{rendered}\n\nMã lịch hẹn: {appointment['appointment_id']}"
                f"\nTrạng thái: {appointment.get('status', 'pending')}"
            ).strip()
        if detail:
            rendered = f"{rendered}\n\n{detail}"
        return {
            "final_response": rendered,
            "citations": [],
        }

    # Live appointment catalog/status tools are authoritative but are not RAG
    # sources and must never trigger forced hospital-document search. They also
    # do not mutate or advance the canonical booking draft.
    appointment_observations = list(state.get("appointment_observations", []))
    if appointment_observations:
        known_ids = _appointment_observation_ids(appointment_observations)
        mentioned_ids = set(re.findall(r"\b(?:SP|DOC|SL|APT)-[A-Z0-9-]+\b", response_text, re.IGNORECASE))
        unknown_ids = sorted(identifier for identifier in mentioned_ids if identifier not in known_ids)
        _trace(
            config,
            "grounding.appointment_reference.validate",
            observation_count=len(appointment_observations),
            known_id_count=len(known_ids),
            unknown_id_count=len(unknown_ids),
        )
        if not unknown_ids:
            return {
                "final_response": response_text,
                "citations": [],
                "degradation_status": {
                    "appointment_reference_grounded": True,
                    "reference_tool_count": len(appointment_observations),
                },
            }
        if not state.get("repair_attempted", False):
            return {
                "repair_attempted": True,
                "grounding_retry_reasons": [
                    f"unknown_appointment_identifier:{identifier}" for identifier in unknown_ids
                ],
            }
        abstain = "Tôi không thể xác minh thông tin này từ dữ liệu lịch khám hiện tại."
        _trace(config, "fallback", component="appointment_reference", reason="unknown_identifier_after_repair")
        return {
            "final_response": abstain,
            "messages": state.get("messages", []) + [AIMessage(content=abstain)],
        }

    if not state.get("observations"):
        current_action = state.get("current_action") or classify_action(state)
        issues = citation_validation_issues(response_text, [])
        _trace(config, "grounding.validate", observation_count=0, issue_count=len(issues), issues=issues[:5])
        if current_action == "search_knowledge" and issues and not state.get("repair_attempted", False):
            _trace(config, "grounding.repair", reason="missing_current_turn_observation", action="forced_search")
            return {
                "repair_attempted": True,
                "force_search_required": True,
                "grounding_retry_reasons": [
                    "no_current_turn_search_observations",
                    *issues,
                ],
            }
        if current_action == "search_knowledge" and issues:
            abstain = "Tôi không có đủ thông tin để trả lời câu hỏi này."
            _trace(config, "fallback", component="grounding", reason="no_observation_after_repair", issue_count=len(issues))
            return {
                "final_response": abstain,
                "grounding_retry_reasons": [
                    "no_current_turn_search_observations",
                    *issues,
                ],
                "messages": state.get("messages", []) + [AIMessage(content=abstain)],
            }
        return {
            "final_response": response_text,
            "citations": []
        }

    # Extract candidates from observations
    candidates = []
    for obs in state.get("observations", []):
        for c_dict in obs.get("candidates", []):
            candidates.append(SearchCandidateDTO(
                chunk_id=c_dict["chunk_id"],
                content=c_dict["content"],
                score=c_dict["score"],
                domain=c_dict["domain"],
                sub_topic=c_dict["sub_topic"],
                source_id=c_dict["source_id"],
                source_path=c_dict["source_path"],
                version=c_dict["version"],
                source_kind=c_dict.get("source_kind", "web"),
                title=c_dict.get("title", ""),
                display_name=c_dict.get("display_name", ""),
                source_url=c_dict.get("source_url"),
                publisher=c_dict.get("publisher", "Bệnh viện Tim Hà Nội"),
                section_path=c_dict.get("section_path", c_dict.get("sub_topic", "")),
                crawled_at=c_dict.get("crawled_at"),
                effective_date=c_dict.get("effective_date"),
                corpus_release_id=c_dict.get("corpus_release_id", ""),
                answerable=c_dict.get("answerable", True),
            ))

    grounded, citations = map_citations_to_response(response_text, candidates)
    validation_issues = citation_validation_issues(response_text, candidates)
    _trace(config, "grounding.validate", observation_count=len(state.get("observations", [])), candidate_count=len(candidates), grounded=grounded, citation_count=len(citations), issue_count=len(validation_issues), issues=validation_issues[:5])

    if grounded:
        rendered_response = render_citation_markers(response_text, citations)
        return {
            "final_response": rendered_response,
            "citations": [c.to_dict() for c in citations]
        }
    else:
        retry_reasons = citation_validation_issues(response_text, candidates)
        if citations:
            filtered_response = supported_response_text(response_text, candidates)
            rendered_response = render_citation_markers(filtered_response, citations)
            return {
                "final_response": rendered_response,
                "citations": [citation.to_dict() for citation in citations],
                "degradation_status": {
                    "grounding_claims_dropped": True,
                    "reasons": retry_reasons,
                },
            }
        # If repair was already attempted, abstain
        if state.get("repair_attempted", False):
            abstain = "Tôi không có đủ thông tin để trả lời câu hỏi này."
            _trace(config, "fallback", component="grounding", reason="citation_repair_exhausted", issue_count=len(retry_reasons))
            return {
                "final_response": abstain,
                "grounding_retry_reasons": retry_reasons,
                "messages": state.get("messages", []) + [AIMessage(content=abstain)]
            }
        else:
            # Trigger repair once
            return {
                "repair_attempted": True,
                "grounding_retry_reasons": retry_reasons,
            }


# Edge routing for repair
def route_repair(state: AgentState) -> str:
    if state.get("final_response"):
        return END
    if state.get("force_search_required"):
        return "forced_search_node"
    return "llm_node"


def forced_search_node(state: AgentState, config: RunnableConfig) -> Dict[str, Any]:
    """Guarantee retrieval for a factual turn when the model skipped its search tool."""
    query = next(
        (
            message.content
            for message in reversed(state.get("messages", []))
            if isinstance(message, HumanMessage) and isinstance(message.content, str)
        ),
        "",
    ).strip()
    started_at = time.monotonic()
    _trace(config, "tool.forced_search.start")
    try:
        result = search_hospital_information_tool.invoke({"query": query}, config)
        candidates = list(result.get("candidates") or [])
        _trace(
            config,
            "tool.forced_search.complete",
            started_at=started_at,
            outcome="success",
            candidate_count=len(candidates),
            sufficient=result.get("sufficient"),
        )
        if not candidates:
            fallback = "Tôi không tìm thấy đủ căn cứ trong nguồn chính thức để trả lời chắc chắn."
            return {
                "observations": [result],
                "force_search_required": False,
                "final_response": fallback,
                "messages": state.get("messages", []) + [AIMessage(content=fallback)],
            }
        evidence_context = json.dumps(
            {
                "candidates": candidates[:10],
                "sufficient": result.get("sufficient"),
            },
            ensure_ascii=False,
            default=str,
        )
        return {
            "observations": [result],
            "force_search_required": False,
            "messages": state.get("messages", []) + [SystemMessage(content=(
                "VALIDATED_CURRENT_TURN_SEARCH_OBSERVATION. Use only this evidence and cite exact "
                f"chunk IDs as [[chunk_id]]:\n{evidence_context}"
            ))],
        }
    except Exception as exc:
        _trace(
            config,
            "tool.forced_search.error",
            started_at=started_at,
            error_type=type(exc).__name__,
        )
        fallback = "Tạm thời không thể truy vấn nguồn thông tin chính thức. Vui lòng thử lại sau."
        return {
            "force_search_required": False,
            "final_response": fallback,
            "messages": state.get("messages", []) + [AIMessage(content=fallback)],
        }


def route_forced_search(state: AgentState) -> str:
    return END if state.get("final_response") else "llm_node"


# Build state graph
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("direct_safety", direct_safety_node)
workflow.add_node("semantic_safety", semantic_safety_node)
workflow.add_node("high_response_node", high_response_node)
workflow.add_node("caution_node", caution_node)
workflow.add_node("llm_node", llm_node)
workflow.add_node("tool_node", tool_node)
workflow.add_node("grounding_verification_node", grounding_verification_node)
workflow.add_node("forced_search_node", forced_search_node)

# Set starting point
workflow.add_edge(START, "direct_safety")
workflow.add_edge("direct_safety", "semantic_safety")

# Safety routing edge
workflow.add_conditional_edges(
    "semantic_safety",
    route_safety,
    {
        "high_response": "high_response_node",
        "caution_node": "caution_node",
        "llm_node": "llm_node"
    }
)

# Caution node routing
workflow.add_conditional_edges(
    "caution_node",
    route_caution,
    {
        "high_response_node": "high_response_node",
        "llm_node": "llm_node",
        END: END
    }
)

# LLM routing
workflow.add_conditional_edges(
    "llm_node",
    route_llm,
    {
        "tool_node": "tool_node",
        "grounding_verification_node": "grounding_verification_node"
    }
)

# Tool loop back to LLM unless execution budget was exhausted.
workflow.add_conditional_edges(
    "tool_node",
    route_tool,
    {
        "llm_node": "llm_node",
        "grounding_verification_node": "grounding_verification_node",
        END: END,
    }
)

# Verification repair loop
workflow.add_conditional_edges(
    "grounding_verification_node",
    route_repair,
    {
        "forced_search_node": "forced_search_node",
        "llm_node": "llm_node",
        END: END
    }
)
workflow.add_conditional_edges(
    "forced_search_node",
    route_forced_search,
    {"llm_node": "llm_node", END: END},
)

# Connect endpoints
workflow.add_edge("high_response_node", END)

# In-memory checkpointer for MVP tests
checkpointer = MemorySaver()
agent_graph = workflow.compile(checkpointer=checkpointer)
# === TASK:WP-302:END ===
