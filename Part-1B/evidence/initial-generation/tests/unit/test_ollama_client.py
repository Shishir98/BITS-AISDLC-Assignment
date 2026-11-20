import asyncio

import httpx
import pytest

from reminder_agent.config import Settings
from reminder_agent.errors import ModelNotInstalledError, RuntimeUnavailableError
from reminder_agent.ollama_client import OllamaClient


SCHEMA = {"type": "object", "required": ["status"], "properties": {"status": {"type": "string"}}}


def test_chat_uses_exact_model_schema_and_generation_options_without_tools() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"message": {"content": '{"status":"ready"}'}, "done": True},
        )

    async def run() -> str:
        client = OllamaClient(
            Settings.from_env({}),
            http_client=httpx.AsyncClient(
                transport=httpx.MockTransport(handler),
                base_url="http://127.0.0.1:11434",
            ),
        )
        return await client.generate("system", "user", SCHEMA)

    assert asyncio.run(run()) == '{"status":"ready"}'
    payload = __import__("json").loads(requests[0].content)
    assert payload["model"] == "qwen3.5:9b"
    assert payload["format"] == SCHEMA
    assert payload["stream"] is False
    assert payload["options"] == {
        "temperature": 0.2,
        "top_p": 0.9,
        "num_ctx": 4096,
    }
    assert "tools" not in payload


def test_local_model_preflight_checks_actual_inventory_without_assuming_remote_keys() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.40.16"})
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "model": "qwen3.5:9b",
                        "digest": "abc123",
                        "details": {
                            "format": "gguf",
                            "family": "qwen",
                            "parameter_size": "9B",
                            "quantization_level": "Q4_K_M",
                        },
                    }
                ]
            },
        )

    async def run() -> dict:
        client = OllamaClient(
            Settings.from_env({}),
            http_client=httpx.AsyncClient(
                transport=httpx.MockTransport(handler),
                base_url="http://127.0.0.1:11434",
            ),
        )
        return await client.preflight()

    info = asyncio.run(run())
    assert info["version"] == "0.40.16"
    assert info["model"]["digest"] == "abc123"


def test_missing_model_has_distinct_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.1.0"})
        return httpx.Response(200, json={"models": []})

    async def run() -> None:
        client = OllamaClient(
            Settings.from_env({}),
            http_client=httpx.AsyncClient(
                transport=httpx.MockTransport(handler),
                base_url="http://127.0.0.1:11434",
            ),
        )
        await client.preflight()

    with pytest.raises(ModelNotInstalledError):
        asyncio.run(run())


def test_connection_error_maps_to_runtime_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    async def run() -> None:
        client = OllamaClient(
            Settings.from_env({}),
            http_client=httpx.AsyncClient(
                transport=httpx.MockTransport(handler),
                base_url="http://127.0.0.1:11434",
            ),
        )
        await client.generate("system", "user", SCHEMA)

    with pytest.raises(RuntimeUnavailableError):
        asyncio.run(run())
