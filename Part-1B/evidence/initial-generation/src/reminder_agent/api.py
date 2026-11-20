from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from reminder_agent.config import Settings
from reminder_agent.errors import AgentError, ApplicationError
from reminder_agent.ollama_client import OllamaClient
from reminder_agent.schemas import InterpretationRequest, InterpretationResult
from reminder_agent.service import InterpretationService

logger = logging.getLogger(__name__)


def create_app(
    settings: Settings | None = None,
    client: Any | None = None,
) -> FastAPI:
    effective_settings = settings or Settings.from_env(os.environ)
    inference_client = client or OllamaClient(effective_settings)
    owns_client = client is None
    service = InterpretationService(inference_client, effective_settings)
    if effective_settings.endpoint_mode == "non_loopback":
        logger.warning(
            "OLLAMA_BASE_URL is non-loopback; this is outside normal local-only mode."
        )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        yield
        if owns_client:
            await inference_client.aclose()

    app = FastAPI(
        title="Natural-Language Reminder Agent",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.exception_handler(AgentError)
    async def handle_agent_error(_: Request, error: AgentError) -> JSONResponse:
        return JSONResponse(
            status_code=error.http_status,
            content={
                "error": {"code": error.code, "message": error.public_message}
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_invalid_request(
        _: Request, __: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "INVALID_REQUEST",
                    "message": "The request must include valid text, reference datetime, and IANA timezone.",
                }
            },
        )

    @app.post("/v1/reminders/interpret", response_model=InterpretationResult)
    async def interpret_reminder(
        body: InterpretationRequest,
    ) -> dict[str, Any]:
        try:
            result = await service.interpret(body)
            return result.model_dump(mode="json")
        except AgentError:
            raise
        except Exception as exc:
            logger.error("Application failure (%s)", type(exc).__name__)
            raise ApplicationError() from None

    return app


app = create_app()
