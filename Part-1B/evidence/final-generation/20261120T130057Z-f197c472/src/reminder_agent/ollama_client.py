from __future__ import annotations

import hashlib
from typing import Any

import httpx

from reminder_agent.config import Settings
from reminder_agent.errors import (
    ApplicationError,
    InferenceTimeoutError,
    InvalidModelOutputError,
    ModelNotInstalledError,
    RuntimeUnavailableError,
)


class OllamaClient:
    def __init__(
        self,
        settings: Settings,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = settings
        self._owns_client = http_client is None
        self._http = http_client or httpx.AsyncClient(
            base_url=settings.ollama_base_url,
            timeout=settings.ollama_timeout,
        )

    async def preflight(self) -> dict[str, Any]:
        version_result = await self._get_json("/api/version")
        tags_result = await self._get_json("/api/tags")
        inventory = tags_result.get("models")
        if not isinstance(inventory, list):
            raise RuntimeUnavailableError()

        model = next(
            (
                entry
                for entry in inventory
                if isinstance(entry, dict)
                and entry.get("model", entry.get("name")) == self.settings.ollama_model
            ),
            None,
        )
        if model is None or _has_remote_metadata(model):
            raise ModelNotInstalledError()
        return {
            "version": version_result.get("version"),
            "model": model,
            "inventory": inventory,
            "endpoint_mode": self.settings.endpoint_mode,
        }

    async def generate(self, system: str, user: str, schema: dict) -> str:
        content, _ = await self.generate_with_metadata(system, user, schema)
        return content

    async def generate_with_metadata(
        self, system: str, user: str, schema: dict
    ) -> tuple[str, dict[str, Any]]:
        payload = {
            "model": self.settings.ollama_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "format": schema,
            "stream": False,
            "think": False,
            "options": {
                "temperature": self.settings.model_temperature,
                "top_p": self.settings.model_top_p,
                "num_ctx": self.settings.model_context_length,
            },
        }
        try:
            response = await self._http.post("/api/chat", json=payload)
        except httpx.TimeoutException as exc:
            raise InferenceTimeoutError() from exc
        except httpx.RequestError as exc:
            raise RuntimeUnavailableError() from exc
        if response.status_code == 404 and _looks_like_missing_model(response.text):
            raise ModelNotInstalledError()
        if response.status_code >= 500:
            raise RuntimeUnavailableError()
        if response.is_error:
            raise ApplicationError("Ollama rejected the inference request.")
        try:
            body = response.json()
        except ValueError as exc:
            raise InvalidModelOutputError(
                raw_output=response.text,
                response_metadata={
                    "http_status": response.status_code,
                    "http_body_sha256": hashlib.sha256(response.content).hexdigest(),
                    "http_body_bytes": len(response.content),
                    "json_valid": False,
                },
            ) from exc
        metadata = _response_metadata(response, body)
        message = body.get("message") if isinstance(body, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(message, dict) or message.get("tool_calls"):
            raise InvalidModelOutputError(response_metadata=metadata)
        if not isinstance(content, str) or not content.strip():
            raise InvalidModelOutputError(
                raw_output=content if isinstance(content, str) else None,
                response_metadata=metadata,
            )
        if body.get("done") is False or body.get("done_reason") == "length":
            raise InvalidModelOutputError(raw_output=content, response_metadata=metadata)
        return content, metadata

    async def aclose(self) -> None:
        if self._owns_client:
            await self._http.aclose()

    async def _get_json(self, path: str) -> dict[str, Any]:
        try:
            response = await self._http.get(path)
        except httpx.TimeoutException as exc:
            raise InferenceTimeoutError() from exc
        except httpx.RequestError as exc:
            raise RuntimeUnavailableError() from exc
        if response.is_error:
            raise RuntimeUnavailableError()
        try:
            body = response.json()
        except ValueError as exc:
            raise RuntimeUnavailableError() from exc
        if not isinstance(body, dict):
            raise RuntimeUnavailableError()
        return body


def _has_remote_metadata(model: dict[str, Any]) -> bool:
    details = model.get("details")
    return any(
        bool(container.get(key))
        for container in (model, details if isinstance(details, dict) else {})
        for key in ("remote_model", "remote_host")
    )


def _response_metadata(response: httpx.Response, body: Any) -> dict[str, Any]:
    redacted = body.copy() if isinstance(body, dict) else body
    if isinstance(redacted, dict) and isinstance(redacted.get("message"), dict):
        message = redacted["message"].copy()
        thinking = message.get("thinking")
        if isinstance(thinking, str):
            message["thinking"] = {
                "redacted": True,
                "characters": len(thinking),
                "sha256": hashlib.sha256(thinking.encode("utf-8")).hexdigest(),
            }
        redacted["message"] = message
    return {
        "http_status": response.status_code,
        "http_body_sha256": hashlib.sha256(response.content).hexdigest(),
        "http_body_bytes": len(response.content),
        "json_valid": True,
        "response_body": redacted,
    }


def _looks_like_missing_model(response_text: str) -> bool:
    text = response_text.lower()
    return "model" in text and ("not found" in text or "pull" in text)
