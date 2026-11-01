from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("base_url_llm", "http://placeholder-llm")
os.environ.setdefault("api_llm", "placeholder-key")
os.environ.setdefault("model_llm", "placeholder-model")
os.environ.setdefault("base_url_l3", "http://placeholder-l3")
os.environ.setdefault("api_l3", "placeholder-key")
os.environ.setdefault("model_l3", "placeholder-model")

from ai_engine.api.app import app
from ai_engine.api.routes import layer3 as layer3_route
from ai_engine.llm import conversation as conv_store


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as async_client:
        yield async_client


@pytest.fixture(autouse=True)
def clear_conversations():
    conv_store._store.clear()
    yield
    conv_store._store.clear()


def _llm_response(text: str) -> MagicMock:
    response = MagicMock()
    response.content = text
    return response


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "prompt-guard-api",
    }


@pytest.mark.asyncio
async def test_chat_then_status_persists_conversation(client: AsyncClient) -> None:
    target_llm = MagicMock()
    target_llm.invoke.return_value = _llm_response("Paris.")

    with patch(
        "ai_engine.llm.bot._run_layer1",
        return_value={"is_danger": False, "confidence": 0.01},
    ), patch(
        "ai_engine.llm.bot._run_layer2",
        return_value={"is_danger": False, "similarity_score": 0.05},
    ), patch("ai_engine.llm.bot._llm", target_llm):
        response = await client.post(
            "/chat",
            json={"prompt": "What is the capital of France?", "conversation_id": "persist-flow"},
        )

    assert response.status_code == 200
    assert response.json()["response"] == "Paris."

    status_response = await client.get("/status/persist-flow")
    assert status_response.status_code == 200
    assert status_response.json() == {
        "conversation_id": "persist-flow",
        "security_status": "clear",
        "message_count": 2,
    }
    target_llm.invoke.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"prompt": "  ", "conversation_id": "invalid-prompt"},
        {"prompt": "hello", "conversation_id": "  "},
        {"prompt": "hello"},
    ],
)
async def test_chat_rejects_invalid_request(
    client: AsyncClient, payload: dict[str, str]
) -> None:
    response = await client.post("/chat", json=payload)

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_unknown_status_returns_not_found(client: AsyncClient) -> None:
    response = await client.get("/status/not-created")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_layer3_check_clears_and_blocks_conversations(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import ai_engine.layer3 as layer3_package

    verdicts = iter([False, True])
    monkeypatch.setattr(
        layer3_package, "is_danger_l3", lambda _messages: next(verdicts)
    )
    payload = {
        "conversation_id": "layer3-check-flow",
        "messages": [{"role": "user", "content": "test conversation"}],
    }

    safe_response = await client.post("/layer3-check", json=payload)
    assert safe_response.status_code == 200
    assert safe_response.json()["security_status"] == "clear"

    attack_response = await client.post("/layer3-check", json=payload)
    assert attack_response.status_code == 200
    assert attack_response.json()["is_danger"] is True
    assert attack_response.json()["security_status"] == "blocked"

    blocked_chat = await client.post(
        "/chat",
        json={"prompt": "follow-up", "conversation_id": "layer3-check-flow"},
    )
    assert blocked_chat.status_code == 403
    assert blocked_chat.json()["detail"]["error"] == "conversation_blocked"


@pytest.mark.asyncio
async def test_layer3_check_maps_invalid_model_response_to_gateway_error(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    import ai_engine.layer3 as layer3_package

    def invalid_verdict(_messages):
        raise ValueError("invalid verdict")

    monkeypatch.setattr(layer3_package, "is_danger_l3", invalid_verdict)
    response = await client.post(
        "/layer3-check",
        json={"conversation_id": "invalid-l3", "messages": [{"role": "user", "content": "hi"}]},
    )

    assert response.status_code == 502
    assert response.json()["detail"]["error"] == "layer3_invalid_response"


@pytest.mark.asyncio
async def test_layer3_alert_updates_block_state_without_external_forwarding(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(layer3_route, "NODE_ALERT_URL", "")
    response = await client.post(
        "/layer3-alert",
        json={
            "conversation_id": "layer3-alert-flow",
            "is_malicious": True,
            "messages": [{"role": "user", "content": "attack"}],
        },
    )

    assert response.status_code == 200
    assert response.json()["forwarded"] is False
    assert response.json()["is_malicious"] is True
    assert conv_store.get_state("layer3-alert-flow").security_status == "blocked"


@pytest.mark.asyncio
async def test_layer3_alert_forwards_when_configured(
    client: AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(layer3_route, "NODE_ALERT_URL", "http://node.test/security-alert")
    remote_response = SimpleNamespace(status_code=200, is_success=True)
    async_client = MagicMock()
    async_client.__aenter__.return_value = async_client
    async_client.__aexit__.return_value = False
    async_client.post = AsyncMock(return_value=remote_response)

    with patch("ai_engine.api.routes.layer3.httpx.AsyncClient", return_value=async_client):
        response = await client.post(
            "/layer3-alert",
            json={"conversation_id": "forward-alert", "is_malicious": False},
        )

    assert response.status_code == 200
    assert response.json()["forwarded"] is True
    assert response.json()["node_response_status"] == 200
    async_client.post.assert_awaited_once()


@pytest.mark.asyncio
async def test_combined_layer_alert_forwards_scores_without_changing_security_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(layer3_route, "NODE_ALERT_URL", "http://node.test/security-alert")
    remote_response = SimpleNamespace(status_code=202, is_success=True)
    async_client = MagicMock()
    async_client.__aenter__.return_value = async_client
    async_client.__aexit__.return_value = False
    async_client.post = AsyncMock(return_value=remote_response)

    with patch("ai_engine.api.routes.layer3.httpx.AsyncClient", return_value=async_client):
        forwarded, status_code = await layer3_route.forward_prompt_injection_alert(
            "combined-alert-flow", 0.72, 0.51, 0.91
        )

    assert forwarded is True
    assert status_code == 202
    payload = async_client.post.await_args.kwargs["json"]
    assert payload["conversation_id"] == "combined-alert-flow"
    assert payload["layer1_score"] == 0.72
    assert payload["layer2_score"] == 0.51
    assert payload["combined_score"] == 0.91
    assert payload["alert_type"] == "prompt_injection"
