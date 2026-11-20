from __future__ import annotations


class AgentError(Exception):
    code = "APPLICATION_ERROR"
    http_status = 500
    public_message = "The request could not be completed."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.public_message)


class RuntimeUnavailableError(AgentError):
    code = "OLLAMA_UNAVAILABLE"
    http_status = 503
    public_message = "The local Ollama runtime is unavailable."


class ModelNotInstalledError(AgentError):
    code = "MODEL_NOT_INSTALLED"
    http_status = 503
    public_message = "The configured local model is not installed."


class InferenceTimeoutError(AgentError):
    code = "INFERENCE_TIMEOUT"
    http_status = 504
    public_message = "Local model inference exceeded the configured timeout."


class InvalidModelOutputError(AgentError):
    code = "INVALID_MODEL_OUTPUT"
    http_status = 502
    public_message = "The local model returned an invalid interpretation."

    def __init__(
        self, message: str | None = None, *, raw_output: str | None = None
    ) -> None:
        super().__init__(message)
        self.raw_output = raw_output


class ApplicationError(AgentError):
    code = "APPLICATION_ERROR"
    http_status = 500
    public_message = "An unexpected application error occurred."
