from __future__ import annotations

from typing import Any

import httpx

from reminder_agent.config import Settings
from reminder_agent.errors import (
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
        payload = {
            "model": self.settings.ollama_model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "format": schema,
            "stream": False,
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
        if response.is_error:
            raise RuntimeUnavailableError()
        try:
            body = response.json()
        except ValueError as exc:
            raise InvalidModelOutputError() from exc
        message = body.get("message") if isinstance(body, dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if (
            not isinstance(content, str)
            or not isinstance(message, dict)
            or message.get("tool_calls")
        ):
            raise InvalidModelOutputError()
        return content

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


def _looks_like_missing_model(response_text: str) -> bool:
    text = response_text.lower()
    return "model" in text and ("not found" in text or "pull" in text)
