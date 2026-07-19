from langchain_core.messages import AIMessage, HumanMessage

from apps.api.ai.orchestrator.core import agent


def test_llm_node_uses_next_ordered_candidate_after_provider_failure(monkeypatch):
    attempts = []

    class FakeChatModel:
        def __init__(self, **options):
            self.options = options
            attempts.append(options["model"])

        def bind_tools(self, tools):
            return self

        def invoke(self, messages):
            if self.options["model"] == "first-model":
                raise RuntimeError("first provider is unavailable")
            return AIMessage(content="Grounded response")

    monkeypatch.setattr(agent, "ChatOpenAI", FakeChatModel)
    state = {
        "messages": [HumanMessage(content="Quy trình tiếp đón là gì?")],
        "call_count": 0,
        "max_tool_calls": 5,
        "elapsed_time_seconds": 0.0,
        "deadline_timestamp": 0.0,
        "observations": [],
        "repair_attempted": False,
    }
    config = {
        "configurable": {
            "llm_candidates": [
                {"provider": "first", "model": "first-model", "api_key": "first-key", "base_url": "https://first.example/v1"},
                {"provider": "second", "model": "second-model", "api_key": "second-key", "base_url": "https://second.example/v1"},
            ]
        }
    }

    result = agent.llm_node(state, config)

    assert attempts == ["first-model", "second-model"]
    assert result["messages"][-1].content == "Grounded response"
