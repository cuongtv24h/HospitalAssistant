from pathlib import Path


PROMPT_PATH = Path("config/prompts/hospital-agent.md")


def test_hospital_agent_prompt_limits_answers_to_hanoi_heart_hospital():
    prompt = PROMPT_PATH.read_text(encoding="utf-8")

    assert "official general assistant for Bệnh viện Tim Hà Nội" in prompt
    assert "Appointment booking" in prompt
    assert "Medical examination and treatment procedures" in prompt
    assert "Health insurance (BHYT) benefits" in prompt
    assert "Medical service pricing" in prompt
    assert "Hospital working hours" in prompt
    assert "Doctors and medical departments" in prompt
    assert "Other official hospital information" in prompt
    assert "For an out-of-scope request, do not call a tool" in prompt
    assert "tôi chỉ hỗ trợ đặt lịch khám và thông tin chính thức" in prompt


def test_hospital_agent_prompt_renumbers_summaries_from_one():
    prompt = PROMPT_PATH.read_text(encoding="utf-8")

    assert "number the displayed items consecutively starting from 1" in prompt
    assert "only part of a process" in prompt
    assert "rather than claiming it is the complete process" in prompt
