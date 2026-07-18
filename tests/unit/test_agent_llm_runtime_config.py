from apps.api.ai.providers.llm_provider import get_agent_llm_configs, get_primary_agent_llm_config


def test_agent_runtime_uses_first_provider_in_configurable_order():
    options = get_primary_agent_llm_config({
        "LLM_PROVIDER_ORDER": "groq,gemini",
        "LLM_GROQ_API_KEY": "test-groq-key",
        "LLM_GROQ_MODEL": "llama-test",
        "LLM_GROQ_BASE_URL": "https://groq.example/v1",
        "LLM_GEMINI_API_KEY": "test-gemini-key",
    })
    assert options["provider"] == "groq"
    assert options["model"] == "llama-test"
    assert options["base_url"] == "https://groq.example/v1"
    assert options["api_key"] == "test-groq-key"


def test_agent_llm_candidates_preserve_openai_fallback_order():
    candidates = get_agent_llm_configs({
        "LLM_PROVIDER_ORDER": "groq,openai,gemini",
        "LLM_GROQ_API_KEY": "test-groq-key",
        "LLM_OPENAI_API_KEY": "test-openai-key",
        "LLM_OPENAI_MODEL": "gpt-4o-mini",
        "LLM_GEMINI_API_KEY": "test-gemini-key",
    })

    assert [candidate["provider"] for candidate in candidates] == [
        "groq", "openai", "gemini"
    ]
    assert candidates[1]["base_url"] == "https://api.openai.com/v1"
