from __future__ import annotations

import ipaddress
import math
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlsplit


class ConfigurationError(ValueError):
    """Raised when local runtime configuration is invalid."""


@dataclass(frozen=True)
class Settings:
    ollama_base_url: str
    ollama_model: str
    ollama_timeout: int
    model_temperature: float
    model_top_p: float
    model_context_length: int
    endpoint_mode: str

    @classmethod
    def from_env(cls, environment: Mapping[str, str]) -> Settings:
        base_url = environment.get(
            "OLLAMA_BASE_URL", "http://127.0.0.1:11434"
        ).strip()
        model = environment.get("OLLAMA_MODEL", "qwen3.5:9b").strip()
        timeout = _positive_int(environment, "OLLAMA_TIMEOUT", 120)
        temperature = _finite_float(environment, "MODEL_TEMPERATURE", 0.2)
        top_p = _finite_float(environment, "MODEL_TOP_P", 0.9)
        context_length = _positive_int(
            environment, "MODEL_CONTEXT_LENGTH", 4096
        )

        parsed_url = urlsplit(base_url)
        try:
            parsed_url.port
        except ValueError as exc:
            raise ConfigurationError(
                "OLLAMA_BASE_URL must contain a valid port."
            ) from exc
        if (
            parsed_url.scheme not in {"http", "https"}
            or not parsed_url.hostname
            or parsed_url.username is not None
            or parsed_url.password is not None
            or parsed_url.query
            or parsed_url.fragment
            or parsed_url.path not in {"", "/"}
        ):
            raise ConfigurationError("OLLAMA_BASE_URL must be an HTTP(S) origin.")

        hostname = parsed_url.hostname.rstrip(".").lower()
        try:
            is_loopback = ipaddress.ip_address(hostname).is_loopback
        except ValueError:
            is_loopback = hostname == "localhost"

        if not model or _is_cloud_model_identifier(model):
            raise ConfigurationError(
                "OLLAMA_MODEL must identify one locally installed, non-cloud model."
            )
        if not math.isfinite(temperature) or not 0 <= temperature <= 2:
            raise ConfigurationError("MODEL_TEMPERATURE must be between 0 and 2.")
        if not math.isfinite(top_p) or not 0 < top_p <= 1:
            raise ConfigurationError("MODEL_TOP_P must be greater than 0 and at most 1.")

        return cls(
            ollama_base_url=base_url.rstrip("/"),
            ollama_model=model,
            ollama_timeout=timeout,
            model_temperature=temperature,
            model_top_p=top_p,
            model_context_length=context_length,
            endpoint_mode="loopback" if is_loopback else "non_loopback",
        )


def _positive_int(environment: Mapping[str, str], name: str, default: int) -> int:
    raw_value = environment.get(name, str(default))
    try:
        value = int(raw_value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{name} must be a positive integer.") from exc
    if value <= 0:
        raise ConfigurationError(f"{name} must be a positive integer.")
    return value


def _finite_float(environment: Mapping[str, str], name: str, default: float) -> float:
    raw_value = environment.get(name, str(default))
    try:
        value = float(raw_value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"{name} must be a finite number.") from exc
    if not math.isfinite(value):
        raise ConfigurationError(f"{name} must be a finite number.")
    return value


def _is_cloud_model_identifier(model: str) -> bool:
    lowered = model.lower()
    return lowered.endswith("-cloud") or ":cloud" in lowered or "remote://" in lowered
