import asyncio

import httpx
import pytest

from reminder_agent.config import Settings
from reminder_agent.errors import (
    ApplicationError,
    InvalidModelOutputError,
    ModelNotInstalledError,
    RuntimeUnavailableError,
)
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
    assert payload["think"] is False
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


def test_remote_model_inventory_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.1.0"})
        return httpx.Response(
            200,
            json={
                "models": [
                    {
                        "model": "qwen3.5:9b",
                        "remote_model": "cloud-model",
                        "digest": "abc123",
                    }
                ]
            },
        )

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


def test_http_request_rejection_is_an_application_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, json={"error": "invalid format schema"})

    async def run() -> None:
        client = OllamaClient(
            Settings.from_env({}),
            http_client=httpx.AsyncClient(
                transport=httpx.MockTransport(handler),
                base_url="http://127.0.0.1:11434",
            ),
        )
        await client.generate("system", "user", SCHEMA)

    with pytest.raises(ApplicationError):
        asyncio.run(run())


def test_model_tool_calls_are_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {
                    "content": '{"status":"ready"}',
                    "tool_calls": [{"function": {"name": "external_action"}}],
                },
                "done": True,
            },
        )

    async def run() -> None:
        client = OllamaClient(
            Settings.from_env({}),
            http_client=httpx.AsyncClient(
                transport=httpx.MockTransport(handler),
                base_url="http://127.0.0.1:11434",
            ),
        )
        await client.generate("system", "user", SCHEMA)

    with pytest.raises(InvalidModelOutputError):
        asyncio.run(run())


@pytest.mark.parametrize(
    ("content", "done_reason"),
    [("", "length"), ('{"status":"ready"}', "length")],
)
def test_empty_or_truncated_response_preserves_redacted_http_metadata(
    content: str, done_reason: str
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {"content": content, "thinking": "private reasoning"},
                "done": True,
                "done_reason": done_reason,
                "eval_count": 4096,
            },
        )

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://127.0.0.1:11434",
        ) as http_client:
            client = OllamaClient(Settings.from_env({}), http_client=http_client)
            await client.generate_with_metadata("system", "user", SCHEMA)

    with pytest.raises(InvalidModelOutputError) as error:
        asyncio.run(run())
    assert error.value.raw_output == content
    metadata = error.value.response_metadata
    assert metadata is not None
    assert metadata["http_status"] == 200
    assert metadata["response_body"]["done_reason"] == "length"
    assert metadata["response_body"]["message"]["content"] == content
    assert metadata["response_body"]["message"]["thinking"]["characters"] == 17
    assert "private reasoning" not in str(metadata)


def test_invalid_ollama_http_json_preserves_diagnostic_metadata() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not JSON")

    async def run() -> None:
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(handler),
            base_url="http://127.0.0.1:11434",
        ) as http_client:
            client = OllamaClient(Settings.from_env({}), http_client=http_client)
            await client.generate_with_metadata("system", "user", SCHEMA)

    with pytest.raises(InvalidModelOutputError) as error:
        asyncio.run(run())
    assert error.value.raw_output == "not JSON"
    assert error.value.response_metadata is not None
    assert not error.value.response_metadata["json_valid"]
