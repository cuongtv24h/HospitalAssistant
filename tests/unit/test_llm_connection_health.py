from apps.api.ai.providers.connection_health import check_llm_connections, configured_llm_connections


class FakeResponse:
    def __init__(self, status_code):
        self.status_code = status_code


class FakeClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, headers):
        self.calls.append((url, headers))
        return self.response


def test_connection_configuration_never_contains_api_key():
    connections = configured_llm_connections({
        "LLM_PROVIDER_ORDER": "groq,gemini",
        "LLM_GROQ_API_KEY": "secret-groq",
        "LLM_GEMINI_API_KEY": "secret-gemini",
    })
    assert [item["provider"] for item in connections] == ["groq", "gemini"]
    assert all("secret" not in str(item) for item in connections)
    assert all(item["status"] == "configured" for item in connections)


def test_connection_check_probes_models_without_generating_completion():
    fake_client = FakeClient(FakeResponse(200))
    result = check_llm_connections(
        {"LLM_PROVIDER_ORDER": "groq", "LLM_GROQ_API_KEY": "secret-value"},
        client_factory=lambda **kwargs: fake_client,
    )
    connection = result["connections"][0]
    assert connection["status"] == "reachable"
    assert fake_client.calls[0][0].endswith("/models")
    assert fake_client.calls[0][1]["Authorization"] == "Bearer secret-value"


def test_connection_check_reports_auth_failure_without_response_body():
    result = check_llm_connections(
        {"LLM_PROVIDER_ORDER": "groq", "LLM_GROQ_API_KEY": "secret-value"},
        client_factory=lambda **kwargs: FakeClient(FakeResponse(401)),
    )
    assert result["connections"][0]["status"] == "authentication_failed"
