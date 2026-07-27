"""Probleme #5 : un composant sans source de donnees ne doit rien affirmer."""
import pytest

from integration_adapters.nms_adapter import MockNmsAdapter


@pytest.mark.asyncio
async def test_mock_nms_adapter_reports_unavailable_not_operational():
    result = await MockNmsAdapter().get_network_status("Tunis")

    assert result["status"] == "unavailable"
    assert result["verified"] is False
    assert result["status"] != "operational"
    assert "reason" in result
