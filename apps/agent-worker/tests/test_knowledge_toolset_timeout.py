import mcp_clients.knowledge_toolset as kt


def test_default_mcp_timeout_exceeds_server_budget() -> None:
    assert kt._mcp_timeout_s() > 5.0


def test_mcp_timeout_is_configurable(monkeypatch) -> None:
    monkeypatch.setenv("KNOWLEDGE_MCP_TIMEOUT_S", "12.5")
    assert kt._mcp_timeout_s() == 12.5


def test_invalid_value_falls_back_to_default(monkeypatch) -> None:
    monkeypatch.setenv("KNOWLEDGE_MCP_TIMEOUT_S", "not-a-number")
    assert kt._mcp_timeout_s() == 9.0
