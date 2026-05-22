import json

import httpx
import pytest

from agent_primer.openrouter import OpenRouterClient


class MockTransport(httpx.AsyncBaseTransport):
    def __init__(self, responses):
        self.responses = responses
        self.requests = []
        self.calls = 0

    async def handle_async_request(self, request):
        self.requests.append(request)
        response = self.responses[self.calls]
        self.calls += 1
        return response


@pytest.mark.asyncio
async def test_model_list_is_parsed():
    transport = MockTransport([
        httpx.Response(200, json={"data": [{"id": "model", "name": "Model"}]})
    ])
    client = OpenRouterClient("key", transport=transport)

    models = await client.list_models()

    assert models[0].id == "model"


@pytest.mark.asyncio
async def test_invalid_json_triggers_one_repair_retry():
    transport = MockTransport([
        httpx.Response(200, json={"choices": [{"message": {"content": "not-json"}}]}),
        httpx.Response(200, json={"choices": [{"message": {"content": "{\"ok\": true}"}}]}),
    ])
    client = OpenRouterClient("key", transport=transport)

    result = await client.complete_json("model", "prompt")

    assert result == {"ok": True}
    assert transport.calls == 2


@pytest.mark.asyncio
async def test_reasoning_effort_is_sent_when_requested():
    transport = MockTransport([
        httpx.Response(200, json={"choices": [{"message": {"content": "{\"ok\": true}"}}]}),
    ])
    client = OpenRouterClient("key", transport=transport)

    await client.complete_json("openai/gpt-5.5", "prompt", reasoning_effort="xhigh")

    payload = json_body(transport.requests[0])
    assert payload["reasoning"] == {"effort": "xhigh"}
    assert payload["temperature"] == 0.2


@pytest.mark.asyncio
async def test_verbosity_is_sent_without_temperature_for_opus_max():
    transport = MockTransport([
        httpx.Response(200, json={"choices": [{"message": {"content": "{\"ok\": true}"}}]}),
    ])
    client = OpenRouterClient("key", transport=transport)

    await client.complete_json("anthropic/claude-opus-4.7", "prompt", verbosity="max")

    payload = json_body(transport.requests[0])
    assert payload["verbosity"] == "max"
    assert "temperature" not in payload


def json_body(request):
    return json.loads(request.content.decode("utf-8"))
